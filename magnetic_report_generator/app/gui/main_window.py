from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QMainWindow,
    QMessageBox,
    QTabWidget,
)

from app.gui.dialogs.notion_upload_dialog import NotionUploadDialog
from app.gui.dialogs.notion_token_dialog import NotionTokenDialog
from app.gui.tabs.generate_tab import GenerateTab
from app.gui.tabs.magnet_data_tab import MagnetDataTab
from app.gui.tabs.simulation_results_tab import SimulationResultsTab
from app.models.entities import AppSettings, MagnetMetrics, ReportPayload, SimulationStudyResult
from app.services.histogram_metrics_service import HistogramMetricsService
from app.services.magnet_data_service import MagnetDataService
from app.services.notion_service import NotionAuthenticationError, NotionService, NotionServiceError, NotionWorkspace
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
        self._notion_service = NotionService()
        self._histogram_metrics_service = HistogramMetricsService()
        self._notion_workspace: NotionWorkspace | None = None

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
            self.tab_magnet.set_last_browse_dir(self._settings.last_txt_path)
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
        self.tab_generate.upload_to_notion_clicked.connect(self.on_upload_to_notion)
        self.tab_generate.browse_folder_clicked.connect(self.on_browse_export_folder)
        self.tab_generate.summary_rows_changed.connect(self.on_summary_rows_changed)

        if self._settings.last_summary_rows is not None:
            self.tab_generate.set_selected_parameters(self._settings.last_summary_rows)

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
        self._settings.last_summary_rows = self.tab_generate.selected_parameters()
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
        self.tab_magnet.set_last_browse_dir(self._settings.last_txt_path)
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
            payload = self._build_current_payload(self._current_export_path(), self.tab_generate.selected_output_format())
            self._report_service.generate(payload)
            self._study_results = payload.studies
            self._settings.last_pdf_export_path = str(payload.output_path)
            self._settings.last_project = self.tab_magnet.project_edit.text().strip()
            self._settings.last_magnet_characteristics = self.tab_magnet.magnet_characteristics_edit.text().strip()
            self._settings.last_expected_ppm = self.tab_magnet.expected_ppm_edit.text().strip()
            self._settings.last_other_information = self.tab_magnet.other_info_edit.toPlainText().strip()
            self._settings.last_summary_rows = payload.summary_parameters
            self._settings_service.save_settings(self._settings)
            self.tab_generate.set_status(f"Exported: {payload.output_path}")
            QMessageBox.information(self, "Exported", f"Report exported to:\n{payload.output_path}")
        except Exception as err:
            QMessageBox.critical(self, "Export Error", str(err))

    def on_upload_to_notion(self) -> None:
        try:
            workspace = self._ensure_notion_workspace()
            if workspace is None:
                return

            default_title = self._default_notion_title()
            available_tags = sorted({*workspace.tags, *self._settings.notion_known_tags}, key=str.lower)
            dlg = NotionUploadDialog(
                workspace.projects,
                available_tags,
                default_title,
                default_project_id=self._settings.notion_last_project_page_id,
                selected_tags=self._settings.notion_last_selected_tags,
                parent=self,
            )
            if dlg.exec() != NotionUploadDialog.Accepted:
                return

            markdown_path = self._current_markdown_export_path()
            payload = self._build_current_payload(markdown_path, "md")
            self._report_service.generate(payload)
            project_id = dlg.selected_project_id()
            page_id, notion_url = self._notion_service.create_simulation_log_page(
                token=self._settings.notion_token,
                workspace=workspace,
                report_title=dlg.report_title(),
                project_page_id=project_id,
                tags=dlg.selected_tags(),
            )
            self._notion_service.append_markdown_report(self._settings.notion_token, page_id, markdown_path)
            self._settings.notion_last_project_page_id = project_id
            self._settings.notion_last_selected_tags = dlg.selected_tags()
            self._settings.notion_known_tags = sorted({*available_tags, *dlg.selected_tags()}, key=str.lower)
            self._settings_service.save_settings(self._settings)
            self.tab_generate.set_status(f"Uploaded to Notion: {notion_url}")
            QMessageBox.information(self, "Upload complete", f"Report uploaded to Notion.\n{notion_url}")
        except NotionAuthenticationError as err:
            self._notion_workspace = None
            self._handle_missing_or_invalid_notion_token(f"Notion authentication failed. {err}")
        except NotionServiceError as err:
            QMessageBox.critical(self, "Notion Upload Error", str(err))
        except Exception as err:
            QMessageBox.critical(self, "Notion Upload Error", str(err))

    def on_summary_rows_changed(self, selected_rows: list[str]) -> None:
        self._settings.last_summary_rows = list(selected_rows)
        self._settings_service.save_settings(self._settings)

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

    def _build_current_payload(self, target_path: Path, output_format: str) -> ReportPayload:
        studies = self._collect_study_results()
        if not studies:
            raise ValueError("Select at least one simulation study.")

        return ReportPayload(
            magnet_metrics=self._magnet_metrics,
            studies=studies,
            output_path=target_path,
            output_format=output_format,
            summary_labels=self.tab_generate.selected_labels(),
            summary_parameters=self.tab_generate.selected_parameters(),
            report_comment="",
            label_comments=self.tab_generate.selected_label_comments(),
            label_expected_ppms=self.tab_generate.selected_label_expected_ppms(),
        )

    def _current_export_path(self) -> Path:
        folder = self.tab_generate.output_folder().strip()
        name = self.tab_generate.output_name().strip()
        if not folder:
            raise ValueError("Select an export folder.")
        if not name:
            raise ValueError("Enter a report name.")
        selected_format = self.tab_generate.selected_output_format()
        expected_suffix = ".md" if selected_format == "md" else ".pdf"
        if not name.lower().endswith(expected_suffix):
            name = str(Path(name).with_suffix(expected_suffix))
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

    def _current_markdown_export_path(self) -> Path:
        folder = self.tab_generate.output_folder().strip()
        if not folder:
            folder = str(self._build_default_export_path().parent)
        name = self.tab_generate.output_name().strip()
        if not name:
            name = self._build_default_export_path().name
        target_dir = Path(folder)
        target_dir.mkdir(parents=True, exist_ok=True)
        return target_dir / f"{Path(name).stem}.md"

    def _default_notion_title(self) -> str:
        txt_path = self.tab_magnet.txt_path_edit.text().strip()
        txt_name = Path(txt_path).stem if txt_path else "report"
        return f'COMSOL Magnet simulation results for "{txt_name}"'

    def _ensure_notion_workspace(self) -> NotionWorkspace | None:
        if self._notion_workspace is not None:
            return self._notion_workspace

        token = self._settings.notion_token.strip()
        if not token:
            if self._handle_missing_or_invalid_notion_token(
                "Enter your Notion Personal Access Token once. It will be saved to settings.json."
            ):
                return self._notion_workspace
            return None

        try:
            workspace = self._notion_service.bootstrap_workspace(token, self._settings.notion_author_name)
        except NotionAuthenticationError as err:
            self._notion_workspace = None
            self._settings.notion_token = ""
            self._settings_service.save_settings(self._settings)
            if self._handle_missing_or_invalid_notion_token(
                f"Notion authentication failed. {err}"
            ):
                return self._notion_workspace
            return None
        except NotionServiceError as err:
            self._notion_workspace = None
            QMessageBox.critical(self, "Notion Setup Error", str(err))
            return None

        self._notion_workspace = workspace
        self._settings.notion_token = token
        self._settings.notion_projects_database_id = workspace.projects_database_id
        self._settings.notion_simulation_logs_database_id = workspace.simulation_logs_database_id
        self._settings.notion_author_name = workspace.author_name
        self._settings.notion_author_user_id = workspace.author_user_id
        self._settings.notion_known_tags = list(workspace.tags)
        self._settings_service.save_settings(self._settings)
        return workspace

    def _handle_missing_or_invalid_notion_token(self, message: str) -> bool:
        dlg = NotionTokenDialog(message, self._settings.notion_token, self)
        if dlg.exec() != QDialog.Accepted:
            return False

        token = dlg.token()
        if not token:
            QMessageBox.warning(self, "Missing token", "Enter the Notion Personal Access Token.")
            return False

        try:
            workspace = self._notion_service.bootstrap_workspace(token, self._settings.notion_author_name)
        except NotionAuthenticationError as err:
            self._notion_workspace = None
            self._settings.notion_token = ""
            self._settings_service.save_settings(self._settings)
            QMessageBox.critical(self, "Notion Token Error", str(err))
            return False
        except NotionServiceError as err:
            self._notion_workspace = None
            QMessageBox.critical(self, "Notion Setup Error", str(err))
            return False

        self._notion_workspace = workspace
        self._settings.notion_token = token
        self._settings.notion_projects_database_id = workspace.projects_database_id
        self._settings.notion_simulation_logs_database_id = workspace.simulation_logs_database_id
        self._settings.notion_author_user_id = workspace.author_user_id
        self._settings.notion_known_tags = list(workspace.tags)
        self._settings_service.save_settings(self._settings)
        return True

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
