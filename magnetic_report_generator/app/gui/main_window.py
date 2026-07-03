from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QFileDialog,
    QMainWindow,
    QMessageBox,
    QTabWidget,
)

from app.gui.tabs.generate_tab import GenerateTab
from app.gui.tabs.magnet_data_tab import MagnetDataTab
from app.gui.tabs.simulation_results_tab import SimulationResultsTab
from app.models.entities import AppSettings, MagnetMetrics, ReportPayload, SimulationStudyResult
from app.services.histogram_metrics_service import HistogramMetricsService
from app.services.magnet_data_service import MagnetDataService
from app.services.report_service import ReportService
from app.services.settings_service import SettingsService
from app.services.simulation_service import SimulationService


class MainWindow(QMainWindow):
    def __init__(
        self,
        settings_service: SettingsService,
        magnet_data_service: MagnetDataService,
        simulation_service: SimulationService,
        report_service: ReportService,
    ) -> None:
        super().__init__()
        self.setWindowTitle("Magnetic Simulation Report Generator")
        self.resize(1250, 820)

        self._settings_service = settings_service
        self._magnet_data_service = magnet_data_service
        self._simulation_service = simulation_service
        self._report_service = report_service
        self._histogram_metrics_service = HistogramMetricsService()

        self._settings = self._settings_service.load_settings()
        self._materials = self._settings_service.load_materials()

        self._magnet_metrics: MagnetMetrics | None = None
        self._study_results: list[SimulationStudyResult] = []

        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)

        self.tab_magnet = MagnetDataTab(self._magnet_data_service, self._settings.comsol_version)
        self.tab_sim = SimulationResultsTab(self._simulation_service, self._settings_service, self._materials)
        self.tab_generate = GenerateTab()

        self.tabs.addTab(self.tab_magnet, "Tab 1 - Magnet Data")
        self.tabs.addTab(self.tab_sim, "Tab 2 - Simulation Results")
        self.tabs.addTab(self.tab_generate, "Tab 3 - Export Report")

        if self._settings.last_txt_path:
            self.tab_magnet.txt_path_edit.setText(self._settings.last_txt_path)
        if self._settings.last_project:
            self.tab_magnet.project_edit.setText(self._settings.last_project)
        if self._settings.last_magnet_characteristics:
            self.tab_magnet.magnet_characteristics_edit.setText(self._settings.last_magnet_characteristics)
        if self._settings.last_expected_ppm:
            self.tab_magnet.expected_ppm_edit.setText(self._settings.last_expected_ppm)
        if self._settings.last_other_information:
            self.tab_magnet.other_info_edit.setPlainText(self._settings.last_other_information)
        if self._settings.last_simulation_parent:
            self.tab_sim.set_parent_folder(self._settings.last_simulation_parent)

        self.tab_magnet.data_updated.connect(self.on_magnet_data_updated)
        self.tab_sim.studies_updated.connect(self.on_studies_or_materials_changed)
        self.tab_sim.materials_updated.connect(self.on_studies_or_materials_changed)
        self.tab_generate.export_clicked.connect(self.on_export_pdf)
        self.tab_generate.browse_folder_clicked.connect(self.on_browse_export_folder)

        self._apply_style()
        self._refresh_export_defaults()
        self._refresh_available_labels()

    def closeEvent(self, event) -> None:
        self._settings.comsol_version = self.tab_magnet.comsol_edit.text().strip() or "6.4"
        self._settings.last_txt_path = self.tab_magnet.txt_path_edit.text().strip()
        self._settings.last_simulation_parent = self.tab_sim.parent_folder_edit.text().strip()
        self._settings.last_project = self.tab_magnet.project_edit.text().strip()
        self._settings.last_magnet_characteristics = self.tab_magnet.magnet_characteristics_edit.text().strip()
        self._settings.last_expected_ppm = self.tab_magnet.expected_ppm_edit.text().strip()
        self._settings.last_other_information = self.tab_magnet.other_info_edit.toPlainText().strip()
        if self.tab_generate.output_folder():
            self._settings.last_pdf_export_path = str(Path(self.tab_generate.output_folder()) / self.tab_generate.output_name())
        self._settings_service.save_settings(self._settings)
        super().closeEvent(event)

    def on_magnet_data_updated(self, metrics: MagnetMetrics) -> None:
        self._magnet_metrics = metrics
        self._settings.comsol_version = self.tab_magnet.comsol_edit.text().strip() or "6.4"
        self._settings.last_txt_path = self.tab_magnet.txt_path_edit.text().strip()
        self._settings.last_project = self.tab_magnet.project_edit.text().strip()
        self._settings.last_magnet_characteristics = self.tab_magnet.magnet_characteristics_edit.text().strip()
        self._settings.last_expected_ppm = self.tab_magnet.expected_ppm_edit.text().strip()
        self._settings.last_other_information = self.tab_magnet.other_info_edit.toPlainText().strip()
        self._settings_service.save_settings(self._settings)
        self._refresh_export_defaults()

    def on_studies_or_materials_changed(self) -> None:
        self._refresh_available_labels()

    def _collect_study_results(self) -> list[SimulationStudyResult]:
        selected_configs = self.tab_sim.get_selected_studies()
        studies = [self._simulation_service.build_study_result(cfg) for cfg in selected_configs]
        for study in studies:
            study.material_curve = self._materials.get(study.material_name)
            study.histogram_metrics = self._histogram_metrics_service.ensure_metrics_for_study(study)
        return studies

    def on_export_pdf(self) -> None:
        try:
            studies = self._collect_study_results()
            if not studies:
                QMessageBox.warning(self, "No Studies", "Select at least one simulation study.")
                return

            target_path = self._current_export_path()
            selected_labels = self.tab_generate.selected_labels()
            selected_parameters = self.tab_generate.selected_parameters()
            payload = ReportPayload(
                magnet_metrics=self._magnet_metrics,
                studies=studies,
                output_pdf=target_path,
                summary_labels=selected_labels,
                summary_parameters=selected_parameters,
                report_comment="",
                label_comments=self.tab_generate.selected_label_comments(),
                label_expected_ppms=self.tab_generate.selected_label_expected_ppms(),
            )
            self._report_service.generate_pdf(payload)
            self._study_results = studies
            self._settings.last_pdf_export_path = str(target_path)
            self._settings.last_project = self.tab_magnet.project_edit.text().strip()
            self._settings.last_magnet_characteristics = self.tab_magnet.magnet_characteristics_edit.text().strip()
            self._settings.last_expected_ppm = self.tab_magnet.expected_ppm_edit.text().strip()
            self._settings.last_other_information = self.tab_magnet.other_info_edit.toPlainText().strip()
            self._settings_service.save_settings(self._settings)
            self.tab_generate.set_status(f"Exported: {target_path}")
            QMessageBox.information(self, "Exported", f"PDF exported to:\n{target_path}")
        except Exception as err:
            QMessageBox.critical(self, "Export Error", str(err))

    def on_browse_export_folder(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Select Export Folder", self.tab_generate.output_folder())
        if not path:
            return
        self.tab_generate.set_output_folder(path)

    def _refresh_export_defaults(self) -> None:
        default_path = self._build_default_export_path()
        current_name = self.tab_generate.output_name().strip()
        self.tab_generate.set_output_folder(str(default_path.parent))
        if not current_name or current_name.startswith("Simulation_report_"):
            self.tab_generate.set_output_name(default_path.name)

    def _refresh_available_labels(self) -> None:
        try:
            studies = self._collect_study_results()
        except Exception as err:
            self.tab_generate.set_status(f"Label refresh skipped: {err}")
            self.tab_generate.set_available_labels([])
            return

        labels = sorted({label for study in studies for label in study.histogram_metrics.keys()})
        self.tab_generate.set_available_labels(labels)
        self.tab_generate.set_status("Ready" if labels or studies else "No studies selected")

    def _current_export_path(self) -> Path:
        folder = self.tab_generate.output_folder().strip()
        name = self.tab_generate.output_name().strip()
        if not folder:
            raise ValueError("Select an export folder.")
        if not name:
            raise ValueError("Enter a report name.")
        if not name.lower().endswith(".pdf"):
            name = f"{name}.pdf"
            self.tab_generate.set_output_name(name)
        target_dir = Path(folder)
        target_dir.mkdir(parents=True, exist_ok=True)
        return target_dir / name

    def _build_default_export_path(self) -> Path:
        txt_path = self.tab_magnet.txt_path_edit.text().strip()
        txt_file = Path(txt_path) if txt_path else None
        if txt_file and txt_file.exists():
            base_name = txt_file.stem
            default_name = f"Simulation_report_{base_name}.pdf"
            return txt_file.parent / default_name
        if self._settings.last_pdf_export_path:
            previous = Path(self._settings.last_pdf_export_path)
            return previous if previous.suffix.lower() == ".pdf" else previous / "Simulation_report.pdf"
        out_dir = Path.home() / "Documents"
        out_dir.mkdir(parents=True, exist_ok=True)
        return out_dir / "Simulation_report.pdf"

    def _apply_style(self) -> None:
        self.setStyleSheet(
            """
            QMainWindow {
                background: #F4F7FB;
            }
            QTabWidget::pane {
                border: 1px solid #CBD6E2;
                background: #FFFFFF;
                border-radius: 8px;
            }
            QTabBar::tab {
                background: #E6EEF7;
                color: #26435E;
                padding: 10px 16px;
                margin-right: 2px;
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
            }
            QTabBar::tab:selected {
                background: #2D5E87;
                color: #FFFFFF;
            }
            QPushButton {
                background-color: #2D5E87;
                color: white;
                border-radius: 6px;
                padding: 7px 12px;
            }
            QPushButton:hover {
                background-color: #3E79AA;
            }
            QGroupBox {
                border: 1px solid #CBD6E2;
                border-radius: 8px;
                margin-top: 12px;
                font-weight: bold;
                color: #26435E;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 6px;
            }
            """
        )
