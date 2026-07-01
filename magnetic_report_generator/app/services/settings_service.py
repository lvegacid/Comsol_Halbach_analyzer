from __future__ import annotations

import json
from pathlib import Path

from app.models.entities import AppSettings, MaterialCurve


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
        return AppSettings.from_dict(data)

    def save_settings(self, settings: AppSettings) -> None:
        with self._settings_path.open("w", encoding="utf-8") as f:
            json.dump(settings.to_dict(), f, indent=2)

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
            link = ""
            comment = ""

            if isinstance(raw, dict):
                raw_points = raw.get("points", [])
                link = str(raw.get("link", "") or "")
                comment = str(raw.get("comment", "") or "")
            else:
                # Backward compatibility with legacy schema: material -> [[h, b], ...]
                raw_points = raw

            for row in raw_points:
                if isinstance(row, list) and len(row) >= 2:
                    parsed_points.append((float(row[0]), float(row[1])))
            materials[name] = MaterialCurve(name=name, points=parsed_points, link=link, comment=comment)
        return materials

    def save_materials(self, materials: dict[str, MaterialCurve]) -> None:
        serializable = {
            name: {
                "points": [[p[0], p[1]] for p in mat.points],
                "link": mat.link,
                "comment": mat.comment,
            }
            for name, mat in materials.items()
        }
        with self._materials_path.open("w", encoding="utf-8") as f:
            json.dump(serializable, f, indent=2)
