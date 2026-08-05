from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from html.parser import HTMLParser
import json
import mimetypes
from pathlib import Path
import re
import traceback
from typing import Any
from urllib import error as urllib_error
from urllib import request as urllib_request
from urllib.parse import urlencode


@dataclass(slots=True)
class _HttpResponse:
    status_code: int
    text: str

    def json(self) -> dict[str, Any]:
        if not self.text:
            return {}
        return json.loads(self.text)


def json_encode(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload).encode("utf-8")


class NotionServiceError(RuntimeError):
    pass


@dataclass(slots=True)
class NotionProject:
    page_id: str
    title: str


@dataclass(slots=True)
class NotionDatabaseSchema:
    title_property_name: str
    project_property_name: str
    date_property_name: str
    author_property_name: str
    tags_property_name: str


@dataclass(slots=True)
class NotionWorkspace:
    projects_database_id: str
    simulation_logs_database_id: str
    projects: list[NotionProject]
    tags: list[str]
    author_name: str
    author_user_id: str
    logs_schema: NotionDatabaseSchema


class NotionAuthenticationError(NotionServiceError):
    pass


class NotionImageUploadError(NotionServiceError):
    def __init__(self, message: str, image_filename: str, upload_url: str, http_response: str = "") -> None:
        super().__init__(message)
        self.image_filename = image_filename
        self.upload_url = upload_url
        self.http_response = http_response


class _ImageTableParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.rows: list[list[dict[str, str]]] = []
        self._current_row: list[dict[str, str]] | None = None
        self._current_cell: dict[str, str] | None = None
        self._in_strong = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_dict = dict(attrs)
        if tag == "tr":
            self._current_row = []
        elif tag == "td":
            self._current_cell = {"title": "", "src": "", "caption": ""}
        elif tag == "strong":
            self._in_strong = True
        elif tag == "img" and self._current_cell is not None:
            self._current_cell["src"] = str(attrs_dict.get("src", "") or "")

    def handle_endtag(self, tag: str) -> None:
        if tag == "strong":
            self._in_strong = False
        elif tag == "td":
            if self._current_row is not None and self._current_cell is not None:
                self._current_row.append(self._current_cell)
            self._current_cell = None
        elif tag == "tr":
            if self._current_row:
                self.rows.append(self._current_row)
            self._current_row = None

    def handle_data(self, data: str) -> None:
        text = data.strip()
        if not text or self._current_cell is None:
            return
        if self._in_strong:
            self._current_cell["title"] += text
        else:
            existing = self._current_cell["caption"]
            self._current_cell["caption"] = f"{existing} {text}".strip()


class NotionService:
    BASE_URL = "https://api.notion.com/v1"
    NOTION_VERSION = "2022-06-28"
    MAX_CHILDREN_PER_APPEND = 100

    def bootstrap_workspace(self, token: str, author_name: str) -> NotionWorkspace:
        token = token.strip()
        author_name = author_name.strip() or "Lorena Vega"
        if not token:
            raise NotionServiceError("Notion token is required.")

        headers = self._headers(token)
        projects_database = self._find_database_by_title(headers, "R&D Projects")
        logs_database = self._find_database_by_title(headers, "Simulation Logs")
        logs_schema = self._extract_logs_schema(logs_database, projects_database["id"])
        projects = self.list_projects(token, str(projects_database.get("id", "")))
        tags = self.list_database_tags(token, str(logs_database.get("id", "")), logs_schema.tags_property_name)
        resolved_author_name, author_user_id = self._resolve_author(headers, author_name)

        return NotionWorkspace(
            projects_database_id=str(projects_database.get("id", "")),
            simulation_logs_database_id=str(logs_database.get("id", "")),
            projects=projects,
            tags=tags,
            author_name=resolved_author_name,
            author_user_id=author_user_id,
            logs_schema=logs_schema,
        )

    def list_projects(self, token: str, database_id: str) -> list[NotionProject]:
        token = token.strip()
        database_id = database_id.strip()
        if not token:
            raise NotionServiceError("Notion token is required.")
        if not database_id:
            raise NotionServiceError("R&D Projects database ID is required.")

        headers = self._headers(token)
        projects: list[NotionProject] = []
        payload: dict[str, Any] = {"page_size": 100}
        next_cursor: str | None = None

        while True:
            if next_cursor:
                payload["start_cursor"] = next_cursor
            response = self._request("POST", f"{self.BASE_URL}/databases/{database_id}/query", headers=headers, json=payload)
            data = response.json()
            for result in data.get("results", []):
                title = self._extract_page_title(result)
                if title:
                    projects.append(NotionProject(page_id=str(result.get("id", "")), title=title))
            if not data.get("has_more"):
                break
            next_cursor = data.get("next_cursor")

        return sorted(projects, key=lambda item: item.title.lower())

    def list_database_tags(self, token: str, database_id: str, property_name: str) -> list[str]:
        token = token.strip()
        database_id = database_id.strip()
        property_name = property_name.strip()
        if not token:
            raise NotionServiceError("Notion token is required.")
        if not database_id:
            raise NotionServiceError("Simulation Logs database ID is required.")

        headers = self._headers(token)
        database = self._retrieve_database(headers, database_id)
        properties = database.get("properties", {})
        prop = properties.get(property_name, {})
        multi_select = prop.get("multi_select", {}) if isinstance(prop, dict) else {}
        options = multi_select.get("options", []) if isinstance(multi_select, dict) else []
        tags = [str(option.get("name", "")).strip() for option in options if str(option.get("name", "")).strip()]
        return sorted(dict.fromkeys(tags), key=str.lower)

    def create_simulation_log_page(
        self,
        token: str,
        workspace: NotionWorkspace,
        report_title: str,
        project_page_id: str,
        tags: list[str],
        uploaded_at: datetime | None = None,
    ) -> tuple[str, str]:
        token = token.strip()
        report_title = report_title.strip()
        project_page_id = project_page_id.strip()
        if not token:
            raise NotionServiceError("Notion token is required.")
        if not workspace.simulation_logs_database_id:
            raise NotionServiceError("Simulation Logs database ID is required.")
        if not report_title:
            raise NotionServiceError("Report title is required.")
        if not project_page_id:
            raise NotionServiceError("A project must be selected.")

        selected_tags = [tag.strip() for tag in tags if tag.strip()]
        headers = self._headers(token)
        resolved_tags = self.ensure_multi_select_tags(
            token,
            workspace.simulation_logs_database_id,
            workspace.logs_schema.tags_property_name,
            selected_tags,
        )
        stamp = (uploaded_at or datetime.now()).astimezone().isoformat(timespec="seconds")
        properties = {
            workspace.logs_schema.title_property_name: {
                "title": [self._text_obj(report_title)],
            },
            workspace.logs_schema.project_property_name: {
                "relation": [{"id": project_page_id}],
            },
            workspace.logs_schema.date_property_name: {
                "date": {"start": stamp},
            },
            workspace.logs_schema.tags_property_name: {
                "multi_select": [{"name": tag} for tag in resolved_tags],
            },
        }
        if workspace.logs_schema.author_property_name and workspace.author_user_id:
            properties[workspace.logs_schema.author_property_name] = {
                "people": [{"id": workspace.author_user_id}],
            }

        response = self._request(
            "POST",
            f"{self.BASE_URL}/pages",
            headers=headers,
            json={
                "parent": {"database_id": workspace.simulation_logs_database_id},
                "properties": properties,
            },
        )
        page = response.json()
        page_id = str(page.get("id", ""))
        if not page_id:
            raise NotionServiceError("Notion did not return a page ID for the created log entry.")
        return page_id, str(page.get("url", "") or page_id)

    def append_markdown_report(self, token: str, page_id: str, markdown_path: Path) -> None:
        token = token.strip()
        page_id = page_id.strip()
        if not token:
            raise NotionServiceError("Notion token is required.")
        if not page_id:
            raise NotionServiceError("A Notion page ID is required.")
        if not markdown_path.exists():
            raise NotionServiceError(f"Markdown report not found: {markdown_path}")

        headers = self._headers(token)
        blocks = self._markdown_to_blocks(markdown_path, token)
        self._append_blocks(headers, page_id, blocks)

    def ensure_multi_select_tags(
        self,
        token: str,
        database_id: str,
        property_name: str,
        tags: list[str],
    ) -> list[str]:
        token = token.strip()
        database_id = database_id.strip()
        property_name = property_name.strip()
        cleaned_tags = [tag.strip() for tag in tags if tag.strip()]
        if not cleaned_tags:
            return []

        headers = self._headers(token)
        database = self._retrieve_database(headers, database_id)
        properties = database.get("properties", {})
        prop = properties.get(property_name)
        if not isinstance(prop, dict) or prop.get("type") != "multi_select":
            raise NotionServiceError(f'Property "{property_name}" is not a multi-select field in Simulation Logs.')

        multi_select = prop.get("multi_select", {}) if isinstance(prop, dict) else {}
        existing_options = multi_select.get("options", []) if isinstance(multi_select, dict) else []
        existing_names = [str(option.get("name", "")).strip() for option in existing_options if str(option.get("name", "")).strip()]
        missing_tags = [tag for tag in cleaned_tags if tag not in existing_names]
        if missing_tags:
            merged_options = list(existing_options)
            for tag in missing_tags:
                merged_options.append({"name": tag, "color": "default"})
            self._request(
                "PATCH",
                f"{self.BASE_URL}/databases/{database_id}",
                headers=headers,
                json={"properties": {property_name: {"multi_select": {"options": merged_options}}}},
            )
            existing_names.extend(missing_tags)

        # Return only the tags selected by the user for page assignment.
        # Database options are still updated above so new selected tags can be saved.
        selected_ordered = list(dict.fromkeys(cleaned_tags))
        return selected_ordered

    def _search_databases(self, headers: dict[str, str], query: str) -> list[dict[str, Any]]:
        payload: dict[str, Any] = {
            "query": query,
            "filter": {"property": "object", "value": "database"},
            "page_size": 100,
        }
        results: list[dict[str, Any]] = []
        next_cursor: str | None = None

        while True:
            if next_cursor:
                payload["start_cursor"] = next_cursor
            response = self._request("POST", f"{self.BASE_URL}/search", headers=headers, json=payload)
            data = response.json()
            for result in data.get("results", []):
                if isinstance(result, dict) and result.get("object") == "database":
                    results.append(result)
            if not data.get("has_more"):
                break
            next_cursor = data.get("next_cursor")

        return results

    def _find_database_by_title(self, headers: dict[str, str], title: str) -> dict[str, Any]:
        title = title.strip()
        if not title:
            raise NotionServiceError("Database title is required.")

        candidates = self._search_databases(headers, title)
        normalized_title = self._normalize_title(title)
        exact_matches: list[dict[str, Any]] = []
        partial_matches: list[dict[str, Any]] = []
        for candidate in candidates:
            candidate_title = self._database_title(candidate)
            normalized_candidate = self._normalize_title(candidate_title)
            if normalized_candidate == normalized_title:
                exact_matches.append(candidate)
            elif normalized_title in normalized_candidate or normalized_candidate in normalized_title:
                partial_matches.append(candidate)

        chosen = exact_matches[0] if exact_matches else (partial_matches[0] if partial_matches else None)
        if chosen is None:
            raise NotionServiceError(f'Could not find the Notion database named "{title}".')
        return chosen

    def _retrieve_database(self, headers: dict[str, str], database_id: str) -> dict[str, Any]:
        response = self._request("GET", f"{self.BASE_URL}/databases/{database_id}", headers=headers)
        return response.json()

    def _resolve_user_id(self, headers: dict[str, str], author_name: str) -> str:
        author_name = author_name.strip()
        if not author_name:
            raise NotionServiceError("Notion author name is required.")

        next_cursor: str | None = None
        matches: list[dict[str, Any]] = []

        while True:
            query = {"page_size": 100}
            if next_cursor:
                query["start_cursor"] = next_cursor
            response = self._request("GET", f"{self.BASE_URL}/users?{urlencode(query)}", headers=headers)
            data = response.json()
            for user in data.get("results", []):
                if not isinstance(user, dict):
                    continue
                display_name = self._user_display_name(user)
                if self._normalize_title(display_name) == self._normalize_title(author_name):
                    matches.append(user)
            if not data.get("has_more"):
                break
            next_cursor = data.get("next_cursor")

        if not matches:
            raise NotionServiceError(f'Could not find the Notion user named "{author_name}".')
        return str(matches[0].get("id", ""))

    def _resolve_author(self, headers: dict[str, str], preferred_author_name: str) -> tuple[str, str]:
        preferred_author_name = preferred_author_name.strip() or "Lorena Vega"

        me = self._request("GET", f"{self.BASE_URL}/users/me", headers=headers).json()
        if isinstance(me, dict):
            bot = me.get("bot", {})
            owner = bot.get("owner", {}) if isinstance(bot, dict) else {}
            owner_type = str(owner.get("type", "") or "") if isinstance(owner, dict) else ""
            owner_user = owner.get("user", {}) if isinstance(owner, dict) else {}
            if owner_type == "user" and isinstance(owner_user, dict):
                owner_id = str(owner_user.get("id", "") or "").strip()
                if owner_id:
                    owner_name = self._user_display_name(owner_user)
                    return (owner_name or preferred_author_name), owner_id

            me_id = str(me.get("id", "") or "").strip()
            me_type = str(me.get("type", "") or "").strip()
            if me_id and me_type == "person":
                me_name = self._user_display_name(me)
                return (me_name or preferred_author_name), me_id

        return preferred_author_name, ""

    @staticmethod
    def _database_title(database: dict[str, Any]) -> str:
        title_parts = database.get("title", [])
        return "".join(str(item.get("plain_text", "")) for item in title_parts if isinstance(item, dict))

    @staticmethod
    def _user_display_name(user: dict[str, Any]) -> str:
        name = str(user.get("name", "") or "").strip()
        if name:
            return name
        person = user.get("person", {})
        if isinstance(person, dict):
            email = str(person.get("email", "") or "").strip()
            if email:
                return email
        return str(user.get("id", "") or "")

    @staticmethod
    def _normalize_title(text: str) -> str:
        return " ".join(text.strip().lower().split())

    @staticmethod
    def _extract_logs_schema(database: dict[str, Any], projects_database_id: str) -> NotionDatabaseSchema:
        properties = database.get("properties", {})
        if not isinstance(properties, dict):
            raise NotionServiceError("Notion Simulation Logs database schema is invalid.")

        title_property = NotionService._first_property_name(properties, {"title"}, {"Title"})
        project_property = NotionService._first_relation_property_name(properties, projects_database_id)
        date_property = NotionService._first_property_name(properties, {"date"}, {"Date"})
        if date_property is None:
            date_property = NotionService._first_property_name(properties, {"date"}, set())
        author_property = NotionService._first_property_name(properties, {"people"}, {"Author"})
        if author_property is None:
            author_property = NotionService._first_property_name(properties, {"people"}, set())
        tags_property = NotionService._first_property_name(properties, {"multi_select"}, {"Tags"})
        if tags_property is None:
            tags_property = NotionService._first_property_name(properties, {"multi_select"}, set())

        if title_property is None or project_property is None or date_property is None or tags_property is None:
            raise NotionServiceError("Could not resolve the required properties in the Simulation Logs database.")

        return NotionDatabaseSchema(
            title_property_name=title_property,
            project_property_name=project_property,
            date_property_name=date_property,
            author_property_name=author_property or "",
            tags_property_name=tags_property,
        )

    @staticmethod
    def _first_relation_property_name(properties: dict[str, Any], database_id: str) -> str | None:
        preferred = NotionService._first_property_name(properties, {"relation"}, {"Project"})
        if preferred is not None:
            prop = properties.get(preferred, {})
            relation = prop.get("relation", {}) if isinstance(prop, dict) else {}
            if isinstance(relation, dict) and str(relation.get("database_id", "") or "") == str(database_id):
                return preferred

        for name, prop in properties.items():
            if not isinstance(prop, dict) or prop.get("type") != "relation":
                continue
            relation = prop.get("relation", {})
            if isinstance(relation, dict) and str(relation.get("database_id", "") or "") == str(database_id):
                return name
        return preferred

    @staticmethod
    def _first_property_name(
        properties: dict[str, Any],
        property_types: set[str],
        preferred_names: set[str],
    ) -> str | None:
        for name in properties:
            if name in preferred_names:
                prop = properties.get(name, {})
                if isinstance(prop, dict) and prop.get("type") in property_types:
                    return name
        for name, prop in properties.items():
            if isinstance(prop, dict) and prop.get("type") in property_types:
                return name
        return None

    def upload_markdown_report(
        self,
        token: str,
        project_page_id: str,
        page_title: str,
        markdown_path: Path,
    ) -> str:
        token = token.strip()
        project_page_id = project_page_id.strip()
        page_title = page_title.strip()
        if not token:
            raise NotionServiceError("Notion token is required.")
        if not project_page_id:
            raise NotionServiceError("A target R&D Project must be selected.")
        if not page_title:
            raise NotionServiceError("Report title is required.")
        if not markdown_path.exists():
            raise NotionServiceError(f"Markdown report not found: {markdown_path}")

        headers = self._headers(token)
        page_response = self._request(
            "POST",
            f"{self.BASE_URL}/pages",
            headers=headers,
            json={
                "parent": {"type": "page_id", "page_id": project_page_id},
                "properties": {
                    "title": {
                        "title": [
                            {"type": "text", "text": {"content": page_title[:2000]}}
                        ]
                    }
                },
            },
        )
        page = page_response.json()
        page_id = str(page.get("id", ""))
        if not page_id:
            raise NotionServiceError("Notion did not return a page ID for the created report page.")

        created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        blocks = [
            self._paragraph_block(f"Created: {created_at}"),
            self._paragraph_block("Source: COMSOL Magnet Report"),
        ]
        blocks.extend(self._markdown_to_blocks(markdown_path, token))
        self._append_blocks(headers, page_id, blocks)

        return str(page.get("url", "") or page_id)

    def _markdown_to_blocks(self, markdown_path: Path, token: str) -> list[dict[str, Any]]:
        lines = markdown_path.read_text(encoding="utf-8").splitlines()
        blocks: list[dict[str, Any]] = []
        i = 0
        toc_inserted = False
        skipping_index = False
        while i < len(lines):
            line = lines[i].rstrip()
            stripped = line.strip()

            if skipping_index:
                if stripped.startswith("# ") or stripped.startswith("## "):
                    skipping_index = False
                else:
                    i += 1
                    continue

            if not stripped:
                i += 1
                continue

            if stripped.lower() == "## index":
                skipping_index = True
                i += 1
                continue

            if stripped.startswith("```"):
                i += 1
                code_lines: list[str] = []
                while i < len(lines) and not lines[i].strip().startswith("```"):
                    code_lines.append(lines[i].rstrip("\n"))
                    i += 1
                if i < len(lines) and lines[i].strip().startswith("```"):
                    i += 1
                blocks.append(self._code_block("\n".join(code_lines)))
                continue

            heading_match = re.match(r"^(#{1,6})\s+(.*)$", stripped)
            if heading_match:
                markdown_level = len(heading_match.group(1))
                heading_text = heading_match.group(2).strip()

                if re.match(r"^\d+(?:\.\d+)*\.?\s+", heading_text) and not toc_inserted:
                    blocks.append(self._table_of_contents_block())
                    toc_inserted = True

                normalized = heading_text.replace("Simulation B_field results", "Simulation B-field results")
                notion_level = min(max(markdown_level, 1), 6)
                blocks.append(self._heading_block(notion_level, normalized))
                i += 1
                continue

            if stripped.startswith("<table>"):
                html_lines: list[str] = []
                while i < len(lines):
                    html_lines.append(lines[i])
                    if "</table>" in lines[i]:
                        break
                    i += 1
                blocks.extend(self._html_table_to_image_blocks("\n".join(html_lines), markdown_path.parent, token))
                i += 1
                continue

            if stripped.startswith("# "):
                blocks.append(self._heading_block(1, stripped[2:].strip()))
                i += 1
                continue

            if stripped.startswith("- "):
                blocks.append(self._bulleted_item_block(stripped[2:].strip()))
                i += 1
                continue

            if self._is_markdown_table_header(lines, i):
                table_lines = [lines[i].strip(), lines[i + 1].strip()]
                i += 2
                while i < len(lines) and lines[i].strip().startswith("|"):
                    table_lines.append(lines[i].strip())
                    i += 1
                blocks.append(self._markdown_table_block(table_lines))
                continue

            paragraph_lines = [stripped]
            i += 1
            while i < len(lines):
                candidate = lines[i].strip()
                if not candidate:
                    break
                if candidate.startswith(("#", "- ", "|", "<table>", "```")):
                    break
                paragraph_lines.append(candidate)
                i += 1
            blocks.append(self._paragraph_block(" ".join(paragraph_lines)))
        return blocks

    @staticmethod
    def _is_markdown_table_header(lines: list[str], idx: int) -> bool:
        if idx + 1 >= len(lines):
            return False
        header = lines[idx].strip()
        divider = lines[idx + 1].strip()
        if not header.startswith("|") or not divider.startswith("|"):
            return False

        divider_cells = [cell.strip() for cell in divider.strip("|").split("|")]
        if not divider_cells:
            return False

        for cell in divider_cells:
            if not cell or "-" not in cell:
                return False
            if any(ch not in "-:" for ch in cell):
                return False
        return True

    def _markdown_table_block(self, table_lines: list[str]) -> dict[str, Any]:
        try:
            rows = [self._split_markdown_row(line) for line in table_lines if line.startswith("|")]
            if len(rows) < 2:
                return self._code_block("\n".join(table_lines))
            if not any(cell.strip() for row in rows for cell in row):
                return self._code_block("\n".join(table_lines))

            if len(rows[0]) >= 2 and rows[0][0].strip().lower() == "field" and rows[0][1].strip().lower() == "value":
                key_value_rows = [row for row in rows[2:] if len(row) >= 2]
                if key_value_rows:
                    return self._key_value_table_block(key_value_rows)

            data_rows = [rows[0]] + rows[2:]
            width = max(len(row) for row in data_rows) if data_rows else len(rows[0])
            if width <= 0 or width > 50:
                return self._code_block("\n".join(table_lines))
            if any(len(row) == 0 for row in data_rows):
                return self._code_block("\n".join(table_lines))

            summary_table = bool(data_rows and data_rows[0] and data_rows[0][0].strip() in {"Parameter", "Simulation"})
            children = []
            for row_index, row in enumerate(data_rows):
                padded = row + [""] * (width - len(row))
                row_is_header = row_index == 0
                row_has_ppm_metric = any("ppm" in cell.lower() for cell in row)
                children.append(
                    {
                        "object": "block",
                        "type": "table_row",
                        "table_row": {
                            "cells": [
                                [
                                    self._text_obj(
                                        cell,
                                        bold=row_is_header or row_has_ppm_metric,
                                        color=self._table_cell_color(summary_table, row_index, col_index, row_has_ppm_metric),
                                    )
                                ]
                                for col_index, cell in enumerate(padded)
                            ]
                        },
                    }
                )

            return {
                "object": "block",
                "type": "table",
                "table": {
                    "table_width": width,
                    "has_column_header": True,
                    "has_row_header": summary_table,
                    "children": children,
                },
            }
        except Exception:
            return self._code_block("\n".join(table_lines))

    @staticmethod
    def _split_markdown_row(line: str) -> list[str]:
        inner = line.strip().strip("|")
        parts = [part.strip().replace("\\|", "|") for part in inner.split("|")]
        return parts

    def _key_value_table_block(self, key_value_rows: list[list[str]]) -> dict[str, Any]:
        children: list[dict[str, Any]] = []
        for row in key_value_rows:
            key = str(row[0]) if len(row) >= 1 else ""
            value = str(row[1]) if len(row) >= 2 else ""
            children.append(
                {
                    "object": "block",
                    "type": "table_row",
                    "table_row": {
                        "cells": [
                            [self._text_obj(key, color="blue_background")],
                            [self._text_obj(value)],
                        ]
                    },
                }
            )

        return {
            "object": "block",
            "type": "table",
            "table": {
                "table_width": 2,
                "has_column_header": False,
                "has_row_header": True,
                "children": children,
            },
        }

    @staticmethod
    def _table_cell_color(summary_table: bool, row_index: int, col_index: int, row_has_ppm_metric: bool) -> str:
        if row_has_ppm_metric and row_index > 0:
            return "orange_background"
        if row_index == 0:
            return "blue_background" if summary_table else "default"
        if col_index == 0:
            return "gray_background" if summary_table else "default"
        return "default"

    def _html_table_to_image_blocks(self, html: str, base_dir: Path, token: str) -> list[dict[str, Any]]:
        parser = _ImageTableParser()
        parser.feed(html)
        blocks: list[dict[str, Any]] = []
        for row in parser.rows:
            row_cells = [cell for cell in row if any(str(cell.get(k, "")).strip() for k in ("title", "src", "caption"))]
            if not row_cells:
                continue

            if len(row_cells) > 1:
                column_children: list[dict[str, Any]] = []
                for cell in row_cells:
                    cell_blocks = self._image_cell_blocks(cell, base_dir, token)
                    if not cell_blocks:
                        cell_blocks = [self._paragraph_block(" ")]
                    column_children.append(
                        {
                            "object": "block",
                            "type": "column",
                            "column": {"children": cell_blocks},
                        }
                    )

                blocks.append(
                    {
                        "object": "block",
                        "type": "column_list",
                        "column_list": {"children": column_children},
                    }
                )
            else:
                blocks.extend(self._image_cell_blocks(row_cells[0], base_dir, token))
        return blocks

    def _image_cell_blocks(self, cell: dict[str, str], base_dir: Path, token: str) -> list[dict[str, Any]]:
        title = cell.get("title", "").strip()
        caption = cell.get("caption", "").strip()
        src = cell.get("src", "").strip()

        result: list[dict[str, Any]] = []
        if title:
            result.append(self._paragraph_block(title))
        if not src:
            if caption:
                result.append(self._paragraph_block(caption))
            return result

        image_path = Path(src)
        if not image_path.is_absolute():
            image_path = (base_dir / image_path).resolve()

        if image_path.exists():
            try:
                upload_id = self._upload_image_file(token, image_path)
                result.append(
                    {
                        "object": "block",
                        "type": "image",
                        "image": {
                            "type": "file_upload",
                            "file_upload": {"id": upload_id},
                            "caption": [self._text_obj(caption)] if caption else [],
                        },
                    }
                )
                return result
            except Exception as ex:
                print("Notion image upload failed.")
                print(f"Exception message: {ex}")
                traceback.print_exc()

                if isinstance(ex, NotionImageUploadError):
                    print(f"Image filename: {ex.image_filename}")
                    print(f"Upload URL: {ex.upload_url}")
                    print(f"Notion HTTP response: {ex.http_response or '<empty>'}")
                else:
                    print(f"Image filename: {image_path.name}")
                    print("Upload URL: <unknown>")
                    print("Notion HTTP response: <unknown>")

                fallback_caption = f"{caption} (image upload failed: {image_path.name})".strip()
                result.extend(self._image_upload_fallback_blocks(fallback_caption, image_path))
                return result

        result.append(self._paragraph_block(caption or f"Image: {image_path}"))
        return result

    def _upload_image_file(self, token: str, image_path: Path) -> str:
        mime_type = mimetypes.guess_type(str(image_path))[0] or "application/octet-stream"
        headers = self._headers(token)
        try:
            create_response = self._request(
                "POST",
                f"{self.BASE_URL}/file_uploads",
                headers=headers,
                json={"filename": image_path.name, "content_type": mime_type},
            )
        except NotionServiceError as ex:
            raise NotionImageUploadError(
                "Notion image upload session creation failed.",
                image_filename=image_path.name,
                upload_url="",
                http_response=str(ex),
            ) from ex

        create_data = create_response.json()
        upload_id = str(create_data.get("id", "") or create_data.get("file_upload", {}).get("id", ""))
        upload_url = str(create_data.get("upload_url", "") or create_data.get("file_upload", {}).get("upload_url", ""))
        if not upload_id or not upload_url:
            raise NotionImageUploadError(
                "Notion image upload session could not be created.",
                image_filename=image_path.name,
                upload_url=upload_url,
                http_response=create_response.text,
            )

        with image_path.open("rb") as handle:
            file_bytes = handle.read()

        boundary = f"----NotionUploadBoundary{upload_id.replace('-', '')}"
        multipart_body = self._build_multipart_file_body(boundary, image_path.name, mime_type, file_bytes)
        upload_response = self._raw_request(
            "POST",
            upload_url,
            headers={
                "Authorization": f"Bearer {token}",
                "Notion-Version": self.NOTION_VERSION,
                "Content-Type": f"multipart/form-data; boundary={boundary}",
            },
            data=multipart_body,
            timeout=120,
        )
        if upload_response.status_code >= 400:
            raise NotionImageUploadError(
                f"Notion image upload failed with status {upload_response.status_code}.",
                image_filename=image_path.name,
                upload_url=upload_url,
                http_response=upload_response.text,
            )

        upload_status = ""
        try:
            upload_data = upload_response.json()
            if isinstance(upload_data, dict):
                upload_status = str(upload_data.get("status", "") or "").strip().lower()
        except Exception:
            upload_status = ""

        if upload_status not in {"uploaded", "complete"}:
            try:
                self._request(
                    "POST",
                    f"{self.BASE_URL}/file_uploads/{upload_id}/complete",
                    headers=headers,
                    json={},
                )
            except NotionServiceError as ex:
                ex_message = str(ex)
                if "status of \"uploaded\"" not in ex_message:
                    raise NotionImageUploadError(
                        "Notion image upload completion failed.",
                        image_filename=image_path.name,
                        upload_url=upload_url,
                        http_response=ex_message,
                    ) from ex

        return upload_id

    def _image_upload_fallback_blocks(self, caption: str, image_path: Path) -> list[dict[str, Any]]:
        text = caption or f"Image: {image_path.name}"
        return [
            self._paragraph_block(text),
            self._code_block(f"Image file (not embedded): {image_path}"),
        ]

    @staticmethod
    def _build_multipart_file_body(boundary: str, filename: str, mime_type: str, file_bytes: bytes) -> bytes:
        # Notion file upload endpoint expects multipart/form-data with field name "file".
        preamble = (
            f"--{boundary}\r\n"
            f"Content-Disposition: form-data; name=\"file\"; filename=\"{filename}\"\r\n"
            f"Content-Type: {mime_type}\r\n\r\n"
        ).encode("utf-8")
        closing = f"\r\n--{boundary}--\r\n".encode("utf-8")
        return preamble + file_bytes + closing

    def _append_blocks(self, headers: dict[str, str], parent_block_id: str, blocks: list[dict[str, Any]]) -> None:
        for start in range(0, len(blocks), self.MAX_CHILDREN_PER_APPEND):
            chunk = blocks[start : start + self.MAX_CHILDREN_PER_APPEND]
            self._request(
                "PATCH",
                f"{self.BASE_URL}/blocks/{parent_block_id}/children",
                headers=headers,
                json={"children": chunk},
            )

    @staticmethod
    def _extract_page_title(page: dict[str, Any]) -> str:
        properties = page.get("properties", {})
        for prop in properties.values():
            if prop.get("type") != "title":
                continue
            return "".join(item.get("plain_text", "") for item in prop.get("title", []))
        return ""

    @staticmethod
    def _headers(token: str) -> dict[str, str]:
        token = token.strip()
        if not token:
            raise NotionServiceError("Notion token is required.")

        return {
            "Authorization": f"Bearer {token}",
            "Notion-Version": NotionService.NOTION_VERSION,
            "Content-Type": "application/json",
        }

    def _request(self, method: str, url: str, headers: dict[str, str], json: dict[str, Any] | None = None) -> _HttpResponse:
        payload = None if json is None else json_encode(json)
        if json is not None:
            print(f"Notion request payload for {method} {url}:")
            print(payload.decode("utf-8"))
        response = self._raw_request(method, url, headers=headers, data=payload, timeout=60)
        if response.status_code >= 400:
            code = ""
            message = response.text
            try:
                error_data = response.json()
                if isinstance(error_data, dict):
                    code = str(error_data.get("code", "") or "").strip()
                    parsed_message = str(error_data.get("message", "") or "").strip()
                    if parsed_message:
                        message = parsed_message
            except Exception:
                # Keep raw response text if JSON parsing fails.
                pass

            if response.status_code == 401 or code == "invalid_api_key":
                raise NotionAuthenticationError(
                    "Notion authentication failed. Update the Personal Access Token in settings.json. "
                    f"Notion response: {message}"
                )

            if response.status_code == 403:
                raise NotionServiceError(
                    "Notion denied access (403). The token can be valid, but the integration likely lacks permissions or "
                    "the required pages/databases are not shared with it. "
                    f"Notion response: {message}"
                )

            suffix = f", {code}" if code else ""
            raise NotionServiceError(f"Notion API error ({response.status_code}{suffix}): {message}")
        return response

    def _raw_request(
        self,
        method: str,
        url: str,
        headers: dict[str, str],
        data: bytes | None,
        timeout: int,
    ) -> _HttpResponse:
        try:
            req = urllib_request.Request(url=url, data=data, headers=headers, method=method)
            with urllib_request.urlopen(req, timeout=timeout) as response:
                body = response.read().decode("utf-8", errors="replace")
                return _HttpResponse(status_code=int(response.status), text=body)
        except urllib_error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            return _HttpResponse(status_code=int(exc.code), text=body)
        except urllib_error.URLError as exc:
            raise NotionServiceError(f"Notion network error: {exc}") from exc

    @staticmethod
    def _text_obj(
        text: str,
        *,
        bold: bool = False,
        color: str = "default",
    ) -> dict[str, Any]:
        return {
            "type": "text",
            "text": {"content": text[:2000]},
            "annotations": {
                "bold": bold,
                "italic": False,
                "strikethrough": False,
                "underline": False,
                "code": False,
                "color": color,
            },
        }

    def _heading_block(self, level: int, text: str) -> dict[str, Any]:
        block_type = {
            1: "heading_1",
            2: "heading_2",
            3: "heading_3",
            4: "heading_4",
            5: "heading_5",
            6: "heading_6",
        }.get(level, "heading_6")

        return {
            "object": "block",
            "type": block_type,
            block_type: {
                "rich_text": [self._text_obj(text)],
            },
    }

    def _paragraph_block(self, text: str) -> dict[str, Any]:
        return {
            "object": "block",
            "type": "paragraph",
            "paragraph": {"rich_text": [self._text_obj(text)]},
        }

    @staticmethod
    def _table_of_contents_block() -> dict[str, Any]:
        return {
            "object": "block",
            "type": "table_of_contents",
            "table_of_contents": {"color": "default"},
        }

    def _code_block(self, text: str) -> dict[str, Any]:
        return {
            "object": "block",
            "type": "code",
            "code": {
                "rich_text": [self._text_obj(text)],
                "language": "plain text",
            },
        }

    def _bulleted_item_block(self, text: str) -> dict[str, Any]:
        return {
            "object": "block",
            "type": "bulleted_list_item",
            "bulleted_list_item": {"rich_text": [self._text_obj(text)]},
        }