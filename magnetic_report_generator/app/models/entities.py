from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class RingInfo:
    ring_index: int
    x_position_mm: float
    magnets: int


@dataclass(slots=True)
class AttachedImageInfo:
    path: str
    comment: str = ""


@dataclass(slots=True)
class MagnetMetrics:
    project: str
    magnet_characteristics: str
    comsol_version: str
    run_date: str
    txt_path: str
    n_magnets: int
    n_rings: int
    br_t: float
    magnet_size_mm3: str
    magnet_length_mm: float
    major_ellipse_side_mm: float
    major_axis_direction: str
    minor_ellipse_side_mm: float
    minor_axis_direction: str
    interring_distance_mm: float | None = None
    interring_note: str = ""
    expected_ppm: float | None = None
    other_information: str = ""
    other_info_images: list[AttachedImageInfo] = field(default_factory=list)
    rings: list[RingInfo] = field(default_factory=list)


@dataclass(slots=True)
class MaterialCurve:
    name: str
    points: list[tuple[float, float]]
    link: str = ""
    comment: str = ""


@dataclass(slots=True)
class SimulationStudyConfig:
    folder_name: str
    folder_path: str
    selected: bool = False
    symmetry: str = "No"
    material_name: str = ""


@dataclass(slots=True)
class DomainFigures:
    name: str
    plot_3d: str | None = None
    histogram: str | None = None
    custom_coordinates: str | None = None
    histogram_txt: str | None = None


@dataclass(slots=True)
class MagnetsFigures:
    plot_3d: str | None = None
    histogram: str | None = None


@dataclass(slots=True)
class SimulationStudyResult:
    folder_name: str
    folder_path: str
    symmetry: str
    material_name: str
    material_curve: MaterialCurve | None = None
    domains: list[DomainFigures] = field(default_factory=list)
    magnets: MagnetsFigures = field(default_factory=MagnetsFigures)
    histogram_metrics: dict[str, dict[str, float]] = field(default_factory=dict)


@dataclass(slots=True)
class ReportPayload:
    magnet_metrics: MagnetMetrics | None
    studies: list[SimulationStudyResult]
    output_pdf: Path
    summary_labels: list[str] = field(default_factory=list)
    summary_parameters: list[str] = field(default_factory=list)
    report_comment: str = ""
    label_comments: dict[str, str] = field(default_factory=dict)


@dataclass(slots=True)
class AppSettings:
    comsol_version: str = "6.4"
    last_txt_path: str = ""
    last_simulation_parent: str = ""
    last_pdf_export_path: str = ""
    last_project: str = ""
    last_magnet_characteristics: str = ""
    last_expected_ppm: str = ""
    last_other_information: str = ""
    last_report_comment: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "comsol_version": self.comsol_version,
            "last_txt_path": self.last_txt_path,
            "last_simulation_parent": self.last_simulation_parent,
            "last_pdf_export_path": self.last_pdf_export_path,
            "last_project": self.last_project,
            "last_magnet_characteristics": self.last_magnet_characteristics,
            "last_expected_ppm": self.last_expected_ppm,
            "last_other_information": self.last_other_information,
            "last_report_comment": self.last_report_comment,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AppSettings":
        return cls(
            comsol_version=str(data.get("comsol_version", "6.4")),
            last_txt_path=str(data.get("last_txt_path", "")),
            last_simulation_parent=str(data.get("last_simulation_parent", "")),
            last_pdf_export_path=str(data.get("last_pdf_export_path", "")),
            last_project=str(data.get("last_project", "")),
            last_magnet_characteristics=str(data.get("last_magnet_characteristics", "")),
            last_expected_ppm=str(data.get("last_expected_ppm", "")),
            last_other_information=str(data.get("last_other_information", "")),
            last_report_comment=str(data.get("last_report_comment", "")),
        )


def today_iso() -> str:
    return date.today().isoformat()
