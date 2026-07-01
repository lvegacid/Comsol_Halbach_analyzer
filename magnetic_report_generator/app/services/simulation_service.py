from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path

from app.models.entities import DomainFigures, MagnetsFigures, SimulationStudyConfig, SimulationStudyResult


class SimulationService:
    DOMAIN_PATTERN = re.compile(r"^B_(?P<domain>.+?)_(?P<kind>3DPlot|Histogram|CustomCoordinates)", re.IGNORECASE)
    MAGNETS_PATTERN = re.compile(r"^Magnets_(?P<kind>3DPlot|Histogram)", re.IGNORECASE)
    BFOV_3D_PATTERN = re.compile(r"^BFOV_", re.IGNORECASE)
    BFOV_HIST_PATTERN = re.compile(r"^BFOV_histogram_", re.IGNORECASE)
    BFOV_COORD_PATTERN = re.compile(r"^B_coordinates_", re.IGNORECASE)

    def detect_first_level_subfolders(self, parent_folder: str) -> list[SimulationStudyConfig]:
        parent = Path(parent_folder)
        if not parent.exists() or not parent.is_dir():
            return []

        configs: list[SimulationStudyConfig] = []
        for entry in sorted(parent.iterdir()):
            if entry.is_dir():
                configs.append(
                    SimulationStudyConfig(
                        folder_name=entry.name,
                        folder_path=str(entry),
                        selected=False,
                        symmetry="No",
                        material_name="",
                    )
                )
        return configs

    def build_study_result(self, cfg: SimulationStudyConfig) -> SimulationStudyResult:
        folder = Path(cfg.folder_path)
        png_files = sorted([p for p in folder.rglob("*") if p.suffix.lower() == ".png"])

        domain_map: dict[str, dict[str, str]] = defaultdict(dict)
        magnets = MagnetsFigures()

        for png in png_files:
            name = png.stem
            parsed_domain = self._parse_domain_filename(name)
            if parsed_domain is not None:
                domain_name, kind = parsed_domain
                domain_map[domain_name][kind] = str(png)
                if kind == "histogram":
                    candidate_txt = png.with_suffix(".txt")
                    if candidate_txt.exists():
                        domain_map[domain_name]["histogram_txt"] = str(candidate_txt)
                continue

            magnets_kind = self._parse_magnets_filename(name)
            if magnets_kind is not None:
                kind = magnets_kind
                if kind == "3dplot":
                    magnets.plot_3d = str(png)
                elif kind == "histogram":
                    magnets.histogram = str(png)

        domains: list[DomainFigures] = []
        for domain_name in sorted(domain_map.keys()):
            kinds = domain_map[domain_name]
            domains.append(
                DomainFigures(
                    name=domain_name,
                    plot_3d=kinds.get("3dplot"),
                    histogram=kinds.get("histogram"),
                    custom_coordinates=kinds.get("customcoordinates"),
                    histogram_txt=kinds.get("histogram_txt"),
                )
            )

        return SimulationStudyResult(
            folder_name=cfg.folder_name,
            folder_path=cfg.folder_path,
            symmetry=cfg.symmetry,
            material_name=cfg.material_name,
            domains=domains,
            magnets=magnets,
        )

    def _parse_domain_filename(self, stem: str) -> tuple[str, str] | None:
        kinds = ["3DPlot", "Histogram", "CustomCoordinates"]
        lower_name = stem.lower()

        # Default FOV workflow from comsol_analyzer_gui.m
        if self.BFOV_HIST_PATTERN.match(stem):
            return "FOV", "histogram"
        if self.BFOV_3D_PATTERN.match(stem):
            return "FOV", "3dplot"
        if self.BFOV_COORD_PATTERN.match(stem):
            return "FOV", "customcoordinates"

        if not lower_name.startswith("b_"):
            return None

        for kind in kinds:
            marker = f"_{kind.lower()}_"
            idx = lower_name.find(marker)
            if idx <= 2:
                continue

            domain = stem[2:idx].strip(" _")
            if not domain:
                continue
            return domain, kind.lower()

        # Fallback to regex for compatibility with old naming edge cases.
        domain_match = self.DOMAIN_PATTERN.match(stem)
        if domain_match:
            return domain_match.group("domain"), domain_match.group("kind").lower()

        return None

    def _parse_magnets_filename(self, stem: str) -> str | None:
        lower_name = stem.lower()
        if lower_name.startswith("magnets_histogram"):
            return "histogram"
        if lower_name.startswith("magnets_"):
            return "3dplot"

        magnets_match = self.MAGNETS_PATTERN.match(stem)
        if magnets_match:
            return magnets_match.group("kind").lower()
        return None
