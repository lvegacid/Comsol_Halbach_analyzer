from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path

from app.models.entities import DomainFigures, MagnetsFigures, SimulationStudyConfig, SimulationStudyResult


class SimulationService:
    DOMAIN_PATTERN = re.compile(r"^B_(?P<domain>.+?)_(?P<kind>3DPlot|Histogram|CustomCoordinates)", re.IGNORECASE)
    MAGNETS_PATTERN = re.compile(r"^Magnets_(?P<kind>3DPlot|Histogram)", re.IGNORECASE)
    BFOV_3D_PATTERN = re.compile(r"^BFOV_(?!histogram_)", re.IGNORECASE)
    BFOV_HIST_PATTERN = re.compile(r"^BFOV_histogram_", re.IGNORECASE)
    BFOV_COORD_PATTERN = re.compile(r"^B_coordinates_", re.IGNORECASE)
    PROJECTION_SUFFIX_PATTERN = re.compile(r"^(?P<base>.+)_(?P<proj>XY|YZ|XZ)$", re.IGNORECASE)

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

        domain_groups: dict[str, dict[str, dict[str, str]]] = defaultdict(lambda: defaultdict(dict))
        magnet_groups: dict[str, dict[str, str]] = defaultdict(dict)

        for png in png_files:
            name = png.stem
            base_name, projection_key = self._split_projection_suffix(name)

            parsed_domain = self._parse_domain_filename(base_name)
            if parsed_domain is not None:
                domain_name, kind = parsed_domain
                slot = domain_groups[domain_name][base_name]

                if kind == "3dplot":
                    if projection_key:
                        slot[projection_key] = str(png)
                    else:
                        slot["plot_3d"] = str(png)
                elif kind == "histogram" and projection_key is None:
                    slot["histogram"] = str(png)
                    candidate_txt = png.with_suffix(".txt")
                    if candidate_txt.exists():
                        slot["histogram_txt"] = str(candidate_txt)
                elif kind == "customcoordinates" and projection_key is None:
                    slot["custom_coordinates"] = str(png)
                continue

            magnets_kind = self._parse_magnets_filename(base_name)
            if magnets_kind is not None:
                slot = magnet_groups["Magnets"]
                if magnets_kind == "3dplot":
                    if projection_key:
                        slot[projection_key] = str(png)
                    else:
                        slot["plot_3d"] = str(png)
                elif magnets_kind == "histogram" and projection_key is None:
                    slot["histogram"] = str(png)
                elif magnets_kind == "normh_histogram" and projection_key is None:
                    slot["normh_histogram"] = str(png)

        magnets = self._build_magnets_figures(magnet_groups)

        domains: list[DomainFigures] = []
        for domain_name in sorted(domain_groups.keys()):
            figure = self._build_domain_figure(domain_name, domain_groups[domain_name])
            self._debug_print_domain(figure)
            domains.append(figure)

        return SimulationStudyResult(
            folder_name=cfg.folder_name,
            folder_path=cfg.folder_path,
            symmetry=cfg.symmetry,
            material_name=cfg.material_name,
            external_material=cfg.external_material,
            domains=domains,
            magnets=magnets,
        )

    def _split_projection_suffix(self, stem: str) -> tuple[str, str | None]:
        match = self.PROJECTION_SUFFIX_PATTERN.match(stem)
        if not match:
            return stem, None

        projection = str(match.group("proj")).upper()
        key = f"projection_{projection.lower()}"
        return str(match.group("base")), key

    def _build_domain_figure(self, domain_name: str, base_groups: dict[str, dict[str, str]]) -> DomainFigures:
        best_plot_group = self._select_best_plot_group(base_groups)
        histogram = self._first_present(base_groups, "histogram")
        custom_coordinates = self._first_present(base_groups, "custom_coordinates")
        histogram_txt = self._first_present(base_groups, "histogram_txt")

        return DomainFigures(
            name=domain_name,
            plot_3d=best_plot_group.get("plot_3d"),
            histogram=histogram,
            custom_coordinates=custom_coordinates,
            histogram_txt=histogram_txt,
            projection_xy=best_plot_group.get("projection_xy"),
            projection_yz=best_plot_group.get("projection_yz"),
            projection_xz=best_plot_group.get("projection_xz"),
        )

    def _build_magnets_figures(self, base_groups: dict[str, dict[str, str]]) -> MagnetsFigures:
        best_plot_group = self._select_best_plot_group(base_groups)
        histogram = self._first_present(base_groups, "histogram")
        normh_histogram = self._first_present(base_groups, "normh_histogram")

        return MagnetsFigures(
            plot_3d=best_plot_group.get("plot_3d"),
            histogram=histogram,
            normh_histogram=normh_histogram,
            projection_xy=best_plot_group.get("projection_xy"),
            projection_yz=best_plot_group.get("projection_yz"),
            projection_xz=best_plot_group.get("projection_xz"),
        )

    @staticmethod
    def _select_best_plot_group(base_groups: dict[str, dict[str, str]]) -> dict[str, str]:
        best: dict[str, str] = {}
        best_score = (-1, -1)
        for values in base_groups.values():
            has_plot = 1 if values.get("plot_3d") else 0
            projections = sum(1 for key in ("projection_xy", "projection_yz", "projection_xz") if values.get(key))
            score = (has_plot, projections)
            if score > best_score:
                best_score = score
                best = values
        return best

    @staticmethod
    def _first_present(base_groups: dict[str, dict[str, str]], key: str) -> str | None:
        for base_name in sorted(base_groups.keys()):
            value = base_groups[base_name].get(key)
            if value:
                return value
        return None

    @staticmethod
    def _debug_print_domain(figure: DomainFigures) -> None:
        print(f"Domain: {figure.name}")
        print(f"3D: {figure.plot_3d or ''}")
        print(f"Histogram: {figure.histogram or ''}")
        print(f"XY: {figure.projection_xy or ''}")
        print(f"YZ: {figure.projection_yz or ''}")
        print(f"XZ: {figure.projection_xz or ''}")

    def _parse_domain_filename(self, stem: str) -> tuple[str, str] | None:
        kinds = ["3DPlot", "Histogram", "CustomCoordinates"]
        lower_name = stem.lower()

        # Default FOV workflow from comsol_analyzer_gui.m
        if self.BFOV_HIST_PATTERN.match(stem):
            return "FOV", "histogram"
        if self.BFOV_COORD_PATTERN.match(stem):
            return "FOV", "customcoordinates"
        if self.BFOV_3D_PATTERN.match(stem):
            return "FOV", "3dplot"

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
        if lower_name.startswith("magnets_histogram_normh_") and lower_name.endswith("_hfield"):
            return "normh_histogram"
        if lower_name.startswith("magnets_histogram") and not lower_name.startswith("magnets_histogram_normh_"):
            return "histogram"
        if lower_name.startswith("magnets_"):
            return "3dplot"

        magnets_match = self.MAGNETS_PATTERN.match(stem)
        if magnets_match:
            return magnets_match.group("kind").lower()
        return None
