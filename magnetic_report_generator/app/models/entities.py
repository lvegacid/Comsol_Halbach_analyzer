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
    y_length_min_mm: float
    y_length_max_mm: float
    z_length_min_mm: float
    z_length_max_mm: float
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
    comment: str = ""
    links: list[str] = field(default_factory=list)
    images: list[AttachedImageInfo] = field(default_factory=list)
    external_txt_path: str | None = None
    external_png_path: str | None = None


@dataclass(slots=True)
class ExternalMaterialSelection:
    display_name: str
    folder_path: str
    external_txt_path: str | None = None
    external_png_path: str | None = None
    is_external: bool = True


@dataclass(slots=True)
class SimulationStudyConfig:
    folder_name: str
    folder_path: str
    selected: bool = False
    symmetry: str = "No"
    material_name: str = ""
    external_material: ExternalMaterialSelection | None = None


@dataclass(slots=True)
class DomainFigures:
    name: str
    plot_3d: str | None = None
    histogram: str | None = None
    custom_coordinates: str | None = None
    histogram_txt: str | None = None
    projection_xy: str | None = None
    projection_yz: str | None = None
    projection_xz: str | None = None


@dataclass(slots=True)
class MagnetsFigures:
    plot_3d: str | None = None
    histogram: str | None = None
    normh_histogram: str | None = None
    projection_xy: str | None = None
    projection_yz: str | None = None
    projection_xz: str | None = None


@dataclass(slots=True)
class MagnetHistogramSummary:
    lt_98_pct: float
    lt_95_pct: float
    lt_90_pct: float
    lt_85_pct: float
    wdv: float
    m_min_t: float
    m_min_pct: float
    m_max_t: float
    m_max_pct: float
    br_t: float


@dataclass(slots=True)
class SimulationStudyResult:
    folder_name: str
    folder_path: str
    symmetry: str
    material_name: str
    external_material: ExternalMaterialSelection | None = None
    material_curve: MaterialCurve | None = None
    domains: list[DomainFigures] = field(default_factory=list)
    magnets: MagnetsFigures = field(default_factory=MagnetsFigures)
    histogram_metrics: dict[str, dict[str, float]] = field(default_factory=dict)
    magnet_histogram_summary: MagnetHistogramSummary | None = None


@dataclass(slots=True)
class ReportPayload:
    magnet_metrics: MagnetMetrics | None
    studies: list[SimulationStudyResult]
    output_path: Path
    output_format: str = "pdf"
    summary_labels: list[str] = field(default_factory=list)
    summary_parameters: list[str] = field(default_factory=list)
    report_comment: str = ""
    label_comments: dict[str, str] = field(default_factory=dict)
    label_expected_ppms: dict[str, str] = field(default_factory=dict)


@dataclass(slots=True)
class AppSettings:
    comsol_version: str = "6.4"
    last_txt_path: str = ""
    last_simulation_parent: str = ""
    last_simulation_studies: list[dict[str, Any]] = field(default_factory=list)
    last_pdf_export_path: str = ""
    last_project: str = ""
    last_magnet_characteristics: str = ""
    last_expected_ppm: str = ""
    last_other_information: str = ""
    last_report_comment: str = ""
    last_summary_rows: list[str] | None = None
    last_summary_label_comments: dict[str, str] = field(default_factory=dict)
    last_summary_label_expected_ppms: dict[str, str] = field(default_factory=dict)
    notion_token: str = ""
    notion_author_name: str = "Lorena Vega"
    notion_author_user_id: str = ""
    notion_projects_database_id: str = ""
    notion_simulation_logs_database_id: str = ""
    notion_last_project_page_id: str = ""
    notion_known_tags: list[str] = field(default_factory=list)
    notion_last_selected_tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "comsol_version": self.comsol_version,
            "last_txt_path": self.last_txt_path,
            "last_simulation_parent": self.last_simulation_parent,
            "last_simulation_studies": [dict(item) for item in self.last_simulation_studies],
            "last_pdf_export_path": self.last_pdf_export_path,
            "last_project": self.last_project,
            "last_magnet_characteristics": self.last_magnet_characteristics,
            "last_expected_ppm": self.last_expected_ppm,
            "last_other_information": self.last_other_information,
            "last_report_comment": self.last_report_comment,
            "last_summary_rows": None if self.last_summary_rows is None else list(self.last_summary_rows),
            "last_summary_label_comments": dict(self.last_summary_label_comments),
            "last_summary_label_expected_ppms": dict(self.last_summary_label_expected_ppms),
            "notion_token": self.notion_token,
            "notion_author_name": self.notion_author_name,
            "notion_author_user_id": self.notion_author_user_id,
            "notion_projects_database_id": self.notion_projects_database_id,
            "notion_simulation_logs_database_id": self.notion_simulation_logs_database_id,
            "notion_last_project_page_id": self.notion_last_project_page_id,
            "notion_known_tags": list(self.notion_known_tags),
            "notion_last_selected_tags": list(self.notion_last_selected_tags),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AppSettings":
        return cls(
            comsol_version=str(data.get("comsol_version", "6.4")),
            last_txt_path=str(data.get("last_txt_path", "")),
            last_simulation_parent=str(data.get("last_simulation_parent", "")),
            last_simulation_studies=[
                dict(item)
                for item in data.get("last_simulation_studies", [])
                if isinstance(item, dict)
            ],
            last_pdf_export_path=str(data.get("last_pdf_export_path", "")),
            last_project=str(data.get("last_project", "")),
            last_magnet_characteristics=str(data.get("last_magnet_characteristics", "")),
            last_expected_ppm=str(data.get("last_expected_ppm", "")),
            last_other_information=str(data.get("last_other_information", "")),
            last_report_comment=str(data.get("last_report_comment", "")),
            last_summary_rows=(
                None
                if "last_summary_rows" not in data
                else [str(item) for item in data.get("last_summary_rows", []) if str(item).strip()]
            ),
            last_summary_label_comments={
                str(key).strip(): str(value).strip()
                for key, value in dict(data.get("last_summary_label_comments", {})).items()
                if str(key).strip() and str(value).strip()
            },
            last_summary_label_expected_ppms={
                str(key).strip(): str(value).strip()
                for key, value in dict(data.get("last_summary_label_expected_ppms", {})).items()
                if str(key).strip() and str(value).strip()
            },
            notion_token=str(data.get("notion_token", "")),
            notion_author_name=str(data.get("notion_author_name", "Lorena Vega") or "Lorena Vega"),
            notion_author_user_id=str(data.get("notion_author_user_id", "")),
            notion_projects_database_id=str(data.get("notion_projects_database_id", "")),
            notion_simulation_logs_database_id=str(data.get("notion_simulation_logs_database_id", "")),
            notion_last_project_page_id=str(data.get("notion_last_project_page_id", "")),
            notion_known_tags=[str(item).strip() for item in data.get("notion_known_tags", []) if str(item).strip()],
            notion_last_selected_tags=[
                str(item).strip() for item in data.get("notion_last_selected_tags", []) if str(item).strip()
            ],
        )


def today_iso() -> str:
    return date.today().isoformat()
