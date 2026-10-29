"""Pure planning logic to merge freshly generated report blocks into an existing Notion log.

The existing page is parsed into a heading tree. The new report (only the new studies) is parsed
the same way and merged node by node:

* matching headings are descended into (the initial configuration section is never part of the
  new report, so it is never touched),
* summary tables of matching sections get the new study columns,
* headings without a counterpart (new study plots, new FOV labels, ...) are appended at the end of
  their parent section, renumbered so they continue the numbering of the existing log.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any
import re

_HEADING_TYPE_RE = re.compile(r"^heading_([1-6])$")
_NUMBER_PREFIX_RE = re.compile(r"^(\d+(?:\.\d+)*)\.?\s+")

# Cells of a table: rows -> cells -> rich_text items.
TableReader = Callable[[str], list[list[list[dict[str, Any]]]]]


@dataclass(slots=True)
class InsertOp:
    after_id: str | None
    blocks: list[dict[str, Any]]


@dataclass(slots=True)
class MergePlan:
    inserts: list[InsertOp] = field(default_factory=list)
    deletes: list[str] = field(default_factory=list)
    merged_tables: int = 0
    appended_sections: int = 0


@dataclass(slots=True)
class _Node:
    level: int
    title: str
    key: str
    heading: dict[str, Any] | None
    prefix: str = ""
    content: list[dict[str, Any]] = field(default_factory=list)
    children: list["_Node"] = field(default_factory=list)


def rich_text_plain(items: list[dict[str, Any]] | None) -> str:
    parts: list[str] = []
    for item in items or []:
        plain = item.get("plain_text")
        if plain is None:
            plain = (item.get("text") or {}).get("content", "")
        parts.append(str(plain))
    return "".join(parts)


def block_plain_text(block: dict[str, Any]) -> str:
    payload = block.get(str(block.get("type", "")), {})
    if not isinstance(payload, dict):
        return ""
    return rich_text_plain(payload.get("rich_text"))


def heading_level(block: dict[str, Any]) -> int:
    match = _HEADING_TYPE_RE.match(str(block.get("type", "")))
    return int(match.group(1)) if match else 0


def split_number_prefix(text: str) -> tuple[str, str]:
    text = text.strip()
    match = _NUMBER_PREFIX_RE.match(text)
    if not match:
        return "", text
    return match.group(1), text[match.end():].strip()


def fold_text(text: str) -> str:
    return " ".join(text.lower().replace("_", "-").split())


def normalize_title(text: str) -> str:
    return fold_text(split_number_prefix(text)[1])


def existing_study_titles(blocks: list[dict[str, Any]]) -> set[str]:
    """Titles of level 3+ headings (per-study plot headings), normalized for comparison."""
    titles: set[str] = set()
    for block in blocks:
        if heading_level(block) >= 3:
            titles.add(normalize_title(block_plain_text(block)))
    return titles


def _build_tree(blocks: list[dict[str, Any]]) -> _Node:
    root = _Node(level=0, title="", key="", heading=None)
    stack = [root]
    for block in blocks:
        level = heading_level(block)
        if not level:
            stack[-1].content.append(block)
            continue
        while stack[-1].level >= level:
            stack.pop()
        prefix, title = split_number_prefix(block_plain_text(block))
        node = _Node(level=level, title=title, key=normalize_title(title), heading=block, prefix=prefix)
        stack[-1].children.append(node)
        stack.append(node)
    return root


def _last_block(node: _Node) -> dict[str, Any] | None:
    if node.children:
        return _last_block(node.children[-1])
    if node.content:
        return node.content[-1]
    return node.heading


def _flatten(node: _Node) -> list[dict[str, Any]]:
    blocks: list[dict[str, Any]] = []
    if node.heading is not None:
        blocks.append(node.heading)
    blocks.extend(node.content)
    for child in node.children:
        blocks.extend(_flatten(child))
    return blocks


def _set_heading_text(block: dict[str, Any], text: str) -> None:
    payload = block[block["type"]]
    template = (payload.get("rich_text") or [{}])[0]
    annotations = template.get("annotations") or {}
    payload["rich_text"] = [
        {
            "type": "text",
            "text": {"content": text[:2000]},
            "annotations": {
                "bold": bool(annotations.get("bold", False)),
                "italic": bool(annotations.get("italic", False)),
                "strikethrough": bool(annotations.get("strikethrough", False)),
                "underline": bool(annotations.get("underline", False)),
                "code": bool(annotations.get("code", False)),
                "color": str(annotations.get("color", "default") or "default"),
            },
        }
    ]


def _numbered(prefix: str, title: str, level: int) -> str:
    if not prefix:
        return title
    return f"{prefix}. {title}" if level == 1 else f"{prefix} {title}"


def _renumber(node: _Node, prefix: str) -> None:
    """Number a node (already attached to a parent) and its descendants consistently."""
    node.prefix = prefix
    if node.heading is not None and prefix:
        _set_heading_text(node.heading, _numbered(prefix, node.title, node.level))
    for index, child in enumerate(node.children, start=1):
        if child.prefix:
            _renumber(child, f"{prefix}.{index}" if prefix else str(index))


def _clean_rich_text(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Convert rich_text read from the API into a form accepted when creating blocks."""
    cleaned: list[dict[str, Any]] = []
    for item in items:
        annotations = item.get("annotations")
        if item.get("type") == "text" and isinstance(item.get("text"), dict):
            text = item["text"]
            entry: dict[str, Any] = {"type": "text", "text": {"content": str(text.get("content", ""))}}
            if text.get("link"):
                entry["text"]["link"] = {"url": str(text["link"].get("url", ""))}
        else:
            entry = {"type": "text", "text": {"content": rich_text_plain([item])}}
        if isinstance(annotations, dict):
            entry["annotations"] = {key: value for key, value in annotations.items()}
        cleaned.append(entry)
    return cleaned


class LogMergePlanner:
    # Sections whose per-study entries are repeated even when the title already exists
    # (two studies may share the same material name).
    _ALWAYS_APPEND_SECTIONS = {"bh curves"}

    def __init__(self, table_reader: TableReader) -> None:
        self._read_table = table_reader

    def plan(self, existing_blocks: list[dict[str, Any]], new_blocks: list[dict[str, Any]]) -> MergePlan:
        new_blocks = [block for block in new_blocks if block.get("type") != "table_of_contents"]
        plan = MergePlan()
        existing_root = _build_tree(existing_blocks)
        new_root = _build_tree(new_blocks)
        # The report title/subtitle (unnumbered headings) belong to the initial section: never merged.
        new_root.children = [child for child in new_root.children if child.prefix]
        self._merge_children(existing_root, new_root, plan, always_append=False)
        return plan

    def _merge_children(self, existing: _Node, new: _Node, plan: MergePlan, always_append: bool) -> None:
        used: set[int] = set()
        pending: list[_Node] = []
        for new_child in new.children:
            match = None
            if not always_append:
                match = next(
                    (
                        candidate
                        for candidate in existing.children
                        if id(candidate) not in used and candidate.key == new_child.key
                    ),
                    None,
                )
            if match is None:
                pending.append(new_child)
                continue
            used.add(id(match))
            self._merge_node(match, new_child, plan)

        if not pending:
            return

        anchor = _last_block(existing)
        anchor_id = str(anchor.get("id", "")) if anchor else None
        numbered_siblings = sum(1 for child in existing.children if child.prefix)
        parent_prefix = existing.prefix
        can_number = existing.level == 0 or bool(parent_prefix)

        blocks: list[dict[str, Any]] = []
        for offset, child in enumerate(pending, start=1):
            if can_number and child.prefix:
                number = numbered_siblings + offset
                child_prefix = f"{parent_prefix}.{number}" if parent_prefix else str(number)
                _renumber(child, child_prefix)
            blocks.extend(_flatten(child))
        plan.inserts.append(InsertOp(after_id=anchor_id or None, blocks=blocks))
        plan.appended_sections += len(pending)

    def _merge_node(self, existing: _Node, new: _Node, plan: MergePlan) -> None:
        old_table = next((block for block in existing.content if block.get("type") == "table"), None)
        new_table = next((block for block in new.content if block.get("type") == "table"), None)
        if old_table is not None and new_table is not None:
            self._merge_table(old_table, new_table, plan)
        self._merge_children(existing, new, plan, always_append=existing.key in self._ALWAYS_APPEND_SECTIONS)

    def _merge_table(self, old_block: dict[str, Any], new_block: dict[str, Any], plan: MergePlan) -> None:
        old_id = str(old_block.get("id", ""))
        new_children = (new_block.get("table") or {}).get("children") or []
        if not old_id or not new_children:
            return

        old_rows = self._read_table(old_id)
        new_rows = [row["table_row"]["cells"] for row in new_children]
        if not old_rows or not new_rows:
            return

        old_header = [rich_text_plain(cell).strip() for cell in old_rows[0]]
        new_header = [rich_text_plain(cell).strip() for cell in new_rows[0]]

        key_columns = 0
        while key_columns < min(len(old_header), len(new_header)) and old_header[key_columns] == new_header[key_columns]:
            key_columns += 1
        if key_columns == 0:
            return

        # Study columns not yet present in the existing table.
        new_columns = [
            idx for idx in range(key_columns, len(new_header)) if new_header[idx] and new_header[idx] not in old_header
        ]
        if not new_columns:
            return

        old_table_info = old_block.get("table") or {}
        old_width = int(old_table_info.get("table_width") or max(len(row) for row in old_rows))

        old_keys = self._row_keys(old_rows, key_columns)
        new_keys = self._row_keys(new_rows, key_columns)
        new_by_key: dict[tuple[str, ...], list[list[dict[str, Any]]]] = {}
        for key, row in zip(new_keys, new_rows):
            new_by_key.setdefault(key, [row[idx] if idx < len(row) else [] for idx in new_columns])

        merged_rows: list[dict[str, Any]] = []
        for row_index, (key, row) in enumerate(zip(old_keys, old_rows)):
            padded = list(row) + [[] for _ in range(old_width - len(row))]
            extra = new_by_key.get(key)
            if row_index == 0 and extra is None:
                extra = [new_rows[0][idx] for idx in new_columns]
            if extra is None:
                extra = [[] for _ in new_columns]
            cells = [_clean_rich_text(cell) for cell in padded[:old_width]]
            cells.extend(_clean_rich_text(cell) for cell in extra)
            merged_rows.append({"object": "block", "type": "table_row", "table_row": {"cells": cells}})

        merged_table = {
            "object": "block",
            "type": "table",
            "table": {
                "table_width": old_width + len(new_columns),
                "has_column_header": bool(old_table_info.get("has_column_header", True)),
                "has_row_header": bool(old_table_info.get("has_row_header", False)),
                "children": merged_rows,
            },
        }
        plan.inserts.append(InsertOp(after_id=old_id, blocks=[merged_table]))
        plan.deletes.append(old_id)
        plan.merged_tables += 1

    @staticmethod
    def _row_keys(rows: list[list[list[dict[str, Any]]]], key_columns: int) -> list[tuple[str, ...]]:
        keys: list[tuple[str, ...]] = []
        last_first = ""
        for row in rows:
            texts = [rich_text_plain(row[idx]).strip() if idx < len(row) else "" for idx in range(key_columns)]
            # Summary tables leave the parameter name blank on the secondary (kHz) row.
            if key_columns >= 2 and not texts[0]:
                texts[0] = last_first
            elif texts[0]:
                last_first = texts[0]
            keys.append(tuple(texts))
        return keys
