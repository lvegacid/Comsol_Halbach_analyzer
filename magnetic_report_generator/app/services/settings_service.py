from __future__ import annotations

import json
from pathlib import Path

from app.models.entities import AppSettings, AttachedImageInfo, MaterialCurve


class SettingsService:
    def __init__(self) -> None:
        app_dir = Path.home() / ".magnetic_sim_report_generator"
        app_dir.mkdir(parents=True, exist_ok=True)
        self._settings_path = app_dir / "settings.json"
        self._materials_path = app_dir / "materials.json"

    @property
    def settings_path(self) -> Path:
        return self._settings_path

    @property
    def materials_path(self) -> Path:
        return self._materials_path

    def load_settings(self) -> AppSettings:
        if not self._settings_path.exists():
            settings = AppSettings()
            self.save_settings(settings)
            return settings
        with self._settings_path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        settings = AppSettings.from_dict(data)
        original_token = settings.notion_token
        self._sanitize_settings(settings)
        if settings.notion_token != original_token:
            self.save_settings(settings)
        return settings

    def save_settings(self, settings: AppSettings) -> None:
        with self._settings_path.open("w", encoding="utf-8") as f:
            json.dump(settings.to_dict(), f, indent=2)

    @staticmethod
    def _sanitize_settings(settings: AppSettings) -> AppSettings:
        token = settings.notion_token.strip()
        if (
            not token
            or "\n" in token
            or "\r" in token
            or len(token) < 20
            or not token.startswith(("secret_", "ntn_"))
        ):
            settings.notion_token = ""
        return settings

    def load_materials(self) -> dict[str, MaterialCurve]:
        if not self._materials_path.exists():
            defaults = {
                "N48": MaterialCurve(
                    name="N48",
                    points=[(-868.0, 0.0), (-833.0, 0.300682), (0.0, 1.4)],
                ),
                "N48_Linear": MaterialCurve(
                    name="N48_Linear",
                    points=[(-833.0, 0.300682), (0.0, 1.4)],
                ),
            }
            self.save_materials(defaults)
            return defaults

        with self._materials_path.open("r", encoding="utf-8") as f:
            data = json.load(f)

        materials: dict[str, MaterialCurve] = {}
        for name, raw in data.items():
            parsed_points: list[tuple[float, float]] = []
            comment = ""
            links: list[str] = []
            images: list[AttachedImageInfo] = []
            external_txt_path: str | None = None
            external_png_path: str | None = None

            if isinstance(raw, dict):
                raw_points = raw.get("points", [])
                comment = str(raw.get("comment", "") or "")
                legacy_link = str(raw.get("link", "") or "").strip()
                raw_links = raw.get("links", [])
                if isinstance(raw_links, list):
                    links = [str(item).strip() for item in raw_links if str(item).strip()]
                if legacy_link and legacy_link not in links:
                    links.insert(0, legacy_link)

                raw_images = raw.get("images", [])
                if isinstance(raw_images, list):
                    for item in raw_images:
                        if isinstance(item, dict):
                            path = str(item.get("path", "") or "").strip()
                            if not path:
                                continue
                            images.append(AttachedImageInfo(path=path, comment=str(item.get("comment", "") or "")))

                raw_external_txt = str(raw.get("external_txt_path", "") or "").strip()
                raw_external_png = str(raw.get("external_png_path", "") or "").strip()
                external_txt_path = raw_external_txt or None
                external_png_path = raw_external_png or None
            else:
                # Backward compatibility with legacy schema: material -> [[h, b], ...]
                raw_points = raw

            for row in raw_points:
                if isinstance(row, list) and len(row) >= 2:
                    parsed_points.append((float(row[0]), float(row[1])))
            materials[name] = MaterialCurve(
                name=name,
                points=parsed_points,
                comment=comment,
                links=links,
                images=images,
                external_txt_path=external_txt_path,
                external_png_path=external_png_path,
            )
        return materials

    def save_materials(self, materials: dict[str, MaterialCurve]) -> None:
        serializable = {
            name: {
                "points": [[p[0], p[1]] for p in mat.points],
                "comment": mat.comment,
                "links": list(mat.links),
                "images": [{"path": img.path, "comment": img.comment} for img in mat.images],
                "external_txt_path": mat.external_txt_path or "",
                "external_png_path": mat.external_png_path or "",
            }
            for name, mat in materials.items()
        }
        with self._materials_path.open("w", encoding="utf-8") as f:
            json.dump(serializable, f, indent=2)
