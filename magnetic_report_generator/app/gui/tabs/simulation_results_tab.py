from __future__ import annotations

from pathlib import Path
from typing import Any
from typing import Callable

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QListWidget,
    QListWidgetItem,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.gui.dialogs.material_dialog import MaterialDialog, NewMaterialDialog
from app.models.entities import AttachedImageInfo, ExternalMaterialSelection, MaterialCurve, SimulationStudyConfig
from app.services.settings_service import SettingsService
from app.services.simulation_service import SimulationService


class SimulationResultsTab(QWidget):
    EXTERNAL_DATABASE_DEFAULT_DIR = r"Z:\Projects\Magnets\Datasheets\Database"
    EXTERNAL_MATERIAL_OPTION = "From External Folder..."

    studies_updated = Signal()
    materials_updated = Signal()

    def __init__(
        self,
        simulation_service: SimulationService,
        settings_service: SettingsService,
        materials: dict[str, MaterialCurve],
    ) -> None:
        super().__init__()
        self._simulation_service = simulation_service
        self._settings_service = settings_service
        self._materials = materials
        self._study_configs: list[SimulationStudyConfig] = []

        root = QVBoxLayout(self)

        folder_box = QGroupBox("Simulation Results")
        folder_form = QFormLayout(folder_box)

        self.parent_folder_edit = QLineEdit()
        self.parent_folder_edit.setReadOnly(True)
        row = QHBoxLayout()
        row.addWidget(self.parent_folder_edit, 1)
        self.btn_browse_parent = QPushButton("Browse Parent Folder")
        self.btn_scan = QPushButton("Scan")
        row.addWidget(self.btn_browse_parent)
        row.addWidget(self.btn_scan)
        folder_form.addRow("Parent folder", row)
        root.addWidget(folder_box)

        self.study_table = QTableWidget(0, 8)
        self.study_table.setHorizontalHeaderLabels(["#", "Use", "Folder", "Symmetry", "Material", "Up", "Down", "Path"])
        self.study_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.study_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.study_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.study_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.study_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.study_table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeToContents)
        self.study_table.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeToContents)
        self.study_table.horizontalHeader().setSectionResizeMode(7, QHeaderView.Stretch)
        root.addWidget(self.study_table, 1)

        materials_box = QGroupBox("Materials Database")
        mat_layout = QGridLayout(materials_box)
        self.material_combo = QComboBox()
        self._refresh_material_combo()

        self.btn_new_material = QPushButton("New Material")
        self.btn_duplicate_material = QPushButton("Duplicate")
        self.btn_delete_material = QPushButton("Delete")
        self.btn_edit_material = QPushButton("Edit")
        self.btn_add_to_db = QPushButton("Add to Magnet Database")

        mat_layout.addWidget(QLabel("Material"), 0, 0)
        mat_layout.addWidget(self.material_combo, 0, 1, 1, 4)
        mat_layout.addWidget(self.btn_new_material, 1, 0)
        mat_layout.addWidget(self.btn_duplicate_material, 1, 1)
        mat_layout.addWidget(self.btn_delete_material, 1, 2)
        mat_layout.addWidget(self.btn_edit_material, 1, 3)
        mat_layout.addWidget(self.btn_add_to_db, 1, 4)
        root.addWidget(materials_box)

        self.btn_browse_parent.clicked.connect(self.on_browse_parent)
        self.btn_scan.clicked.connect(self.scan_parent)
        self.btn_new_material.clicked.connect(self.on_new_material)
        self.btn_duplicate_material.clicked.connect(self.on_duplicate_material)
        self.btn_delete_material.clicked.connect(self.on_delete_material)
        self.btn_edit_material.clicked.connect(self.on_edit_material)
        self.btn_add_to_db.clicked.connect(self.on_new_material)

    def set_parent_folder(self, parent_folder: str) -> None:
        self.parent_folder_edit.setText(parent_folder)

    def on_browse_parent(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Select Parent Simulation Folder")
        if path:
            self.parent_folder_edit.setText(path)

    def scan_parent(self) -> None:
        parent = self.parent_folder_edit.text().strip()
        detected = self._simulation_service.detect_first_level_subfolders(parent)
        detected_by_path = {str(Path(cfg.folder_path).resolve()): cfg for cfg in detected}
        ordered: list[SimulationStudyConfig] = []
        consumed: set[str] = set()

        for previous in self._study_configs:
            key = str(Path(previous.folder_path).resolve())
            matched = detected_by_path.get(key)
            if matched is None:
                continue
            matched.selected = previous.selected
            matched.symmetry = previous.symmetry
            matched.material_name = previous.material_name
            matched.external_material = previous.external_material
            ordered.append(matched)
            consumed.add(key)

        for cfg in detected:
            key = str(Path(cfg.folder_path).resolve())
            if key in consumed:
                continue
            ordered.append(cfg)

        self._study_configs = ordered
        self._render_study_table()
        self.studies_updated.emit()

    def _render_study_table(self) -> None:
        self.study_table.blockSignals(True)
        self.study_table.setRowCount(len(self._study_configs))
        try:
            self.study_table.itemChanged.disconnect(self.on_item_changed)
        except Exception:
            pass
        material_names = list(self._materials.keys())

        for row, cfg in enumerate(self._study_configs):
            index_item = QTableWidgetItem(str(row + 1))
            index_item.setFlags(index_item.flags() & ~Qt.ItemIsEditable)
            self.study_table.setItem(row, 0, index_item)

            use_item = QTableWidgetItem()
            use_item.setFlags(use_item.flags() | Qt.ItemIsUserCheckable)
            use_item.setCheckState(Qt.Checked if cfg.selected else Qt.Unchecked)
            self.study_table.setItem(row, 1, use_item)

            folder_item = QTableWidgetItem(cfg.folder_name)
            folder_item.setFlags(folder_item.flags() & ~Qt.ItemIsEditable)
            self.study_table.setItem(row, 2, folder_item)

            symmetry_combo = QComboBox()
            symmetry_combo.addItems(["Yes", "No"])
            symmetry_combo.setCurrentText(cfg.symmetry)
            symmetry_combo.currentTextChanged.connect(self._make_symmetry_handler(row))
            self.study_table.setCellWidget(row, 3, symmetry_combo)

            material_combo = QComboBox()
            self._populate_material_combo(material_combo, cfg, material_names)
            material_combo.currentTextChanged.connect(self._make_material_handler(row, material_combo))
            self.study_table.setCellWidget(row, 4, material_combo)

            up_button = QPushButton("Up")
            up_button.setEnabled(row > 0)
            up_button.clicked.connect(self._make_move_handler(row, -1))
            self.study_table.setCellWidget(row, 5, up_button)

            down_button = QPushButton("Down")
            down_button.setEnabled(row < len(self._study_configs) - 1)
            down_button.clicked.connect(self._make_move_handler(row, 1))
            self.study_table.setCellWidget(row, 6, down_button)

            path_item = QTableWidgetItem(cfg.folder_path)
            path_item.setFlags(path_item.flags() & ~Qt.ItemIsEditable)
            self.study_table.setItem(row, 7, path_item)

        self.study_table.blockSignals(False)
        self.study_table.itemChanged.connect(self.on_item_changed)

    def on_item_changed(self, item: QTableWidgetItem) -> None:
        if item.column() != 1:
            return
        row = item.row()
        if row < 0 or row >= len(self._study_configs):
            return
        self._study_configs[row].selected = item.checkState() == Qt.Checked
        self.studies_updated.emit()

    def _make_move_handler(self, row: int, delta: int) -> Callable[[], None]:
        def handler() -> None:
            self._move_study(row, delta)

        return handler

    def _move_study(self, row: int, delta: int) -> None:
        target = row + delta
        if row < 0 or row >= len(self._study_configs):
            return
        if target < 0 or target >= len(self._study_configs):
            return
        self._study_configs[row], self._study_configs[target] = self._study_configs[target], self._study_configs[row]
        self._render_study_table()
        self.studies_updated.emit()

    def _make_symmetry_handler(self, row: int) -> Callable[[str], None]:
        def handler(value: str) -> None:
            if 0 <= row < len(self._study_configs):
                self._study_configs[row].symmetry = value
                self.studies_updated.emit()

        return handler

    def _make_material_handler(self, row: int, combo: QComboBox) -> Callable[[str], None]:
        def handler(value: str) -> None:
            if 0 <= row < len(self._study_configs):
                self._handle_material_selection(row, combo, value)

        return handler

    def get_selected_studies(self) -> list[SimulationStudyConfig]:
        return [cfg for cfg in self._study_configs if cfg.selected]

    def _refresh_material_combo(self) -> None:
        self.material_combo.clear()
        self.material_combo.addItems(sorted(self._materials.keys()))

    def _persist_materials(self) -> None:
        self._settings_service.save_materials(self._materials)
        self._refresh_material_combo()
        self._render_study_table()
        self.materials_updated.emit()

    def on_new_material(self) -> None:
        name = NewMaterialDialog.ask_name(self)
        if not name:
            return
        if name in self._materials:
            QMessageBox.warning(self, "Material exists", f"Material '{name}' already exists.")
            return

        default_curve = MaterialCurve(name=name, points=[(-1.0, 0.0), (0.0, 1.0)])
        dlg = MaterialDialog(name, default_curve, self)
        if dlg.exec() != MaterialDialog.Accepted:
            return
        try:
            self._materials[name] = dlg.to_material()
        except ValueError as err:
            NewMaterialDialog.show_error(self, str(err))
            return
        self._persist_materials()

    def on_duplicate_material(self) -> None:
        source = self.material_combo.currentText().strip()
        if not source:
            return
        name = NewMaterialDialog.ask_name(self)
        if not name:
            return
        if name in self._materials:
            QMessageBox.warning(self, "Material exists", f"Material '{name}' already exists.")
            return

        source_material = self._materials[source]
        self._materials[name] = MaterialCurve(
            name=name,
            points=list(source_material.points),
            comment=source_material.comment,
            links=list(source_material.links),
            images=[AttachedImageInfo(path=item.path, comment=item.comment) for item in source_material.images],
            external_txt_path=source_material.external_txt_path,
            external_png_path=source_material.external_png_path,
        )
        self._persist_materials()

    def on_delete_material(self) -> None:
        name = self.material_combo.currentText().strip()
        if not name:
            return
        if len(self._materials) <= 1:
            QMessageBox.warning(self, "Cannot delete", "At least one material must remain.")
            return
        self._materials.pop(name, None)
        self._persist_materials()

    def on_edit_material(self) -> None:
        name = self.material_combo.currentText().strip()
        if not name:
            return
        dlg = MaterialDialog(name, self._materials[name], self)
        if dlg.exec() != MaterialDialog.Accepted:
            return
        try:
            self._materials[name] = dlg.to_material()
        except ValueError as err:
            NewMaterialDialog.show_error(self, str(err))
            return
        self._persist_materials()

    def _populate_material_combo(self, combo: QComboBox, cfg: SimulationStudyConfig, material_names: list[str]) -> None:
        combo.blockSignals(True)
        combo.clear()
        combo.addItem(self.EXTERNAL_MATERIAL_OPTION)
        combo.insertSeparator(1)
        for name in material_names:
            combo.addItem(name)

        self._apply_material_selection(combo, cfg)
        combo.blockSignals(False)

    def _apply_material_selection(self, combo: QComboBox, cfg: SimulationStudyConfig) -> None:
        if cfg.external_material is not None:
            external_name = cfg.external_material.display_name.strip()
            if external_name:
                if combo.findText(external_name) < 0:
                    combo.addItem(external_name)
                combo.setCurrentText(external_name)
                cfg.material_name = external_name
                return

        if cfg.material_name and combo.findText(cfg.material_name) >= 0:
            combo.setCurrentText(cfg.material_name)
            return

        if combo.count() > 2:
            cfg.material_name = combo.itemText(2)
            cfg.external_material = None
            combo.setCurrentIndex(2)
        else:
            cfg.material_name = ""
            cfg.external_material = None
            combo.setCurrentIndex(0)

    def _handle_material_selection(self, row: int, combo: QComboBox, value: str) -> None:
        cfg = self._study_configs[row]
        if value == self.EXTERNAL_MATERIAL_OPTION:
            imported = self._import_external_material_for_row()
            if imported is None:
                combo.blockSignals(True)
                self._apply_material_selection(combo, cfg)
                combo.blockSignals(False)
                return

            cfg.external_material = imported
            cfg.material_name = imported.display_name
            combo.blockSignals(True)
            if combo.findText(imported.display_name) < 0:
                combo.addItem(imported.display_name)
            combo.setCurrentText(imported.display_name)
            combo.blockSignals(False)
            self.studies_updated.emit()
            return

        cfg.material_name = value
        cfg.external_material = None
        self.studies_updated.emit()

    def _import_external_material_for_row(self) -> ExternalMaterialSelection | None:
        default_dir = self.EXTERNAL_DATABASE_DEFAULT_DIR
        if not Path(default_dir).exists():
            default_dir = str(Path.home())

        selected_folder = QFileDialog.getExistingDirectory(
            self,
            "Select External Material Folder",
            default_dir,
        )
        if not selected_folder:
            return None

        folder = Path(selected_folder)
        selected_files = self._select_external_files_from_folder(folder)
        if selected_files is None:
            return None
        if not selected_files:
            QMessageBox.information(self, "No files selected", "Select at least one .txt or .png file.")
            return None

        txt_files = [path for path in selected_files if path.suffix.lower() == ".txt"]
        png_files = [path for path in selected_files if path.suffix.lower() == ".png"]
        if len(txt_files) > 1 or len(png_files) > 1:
            QMessageBox.warning(
                self,
                "Invalid selection",
                "Select at most one .txt and at most one .png file.",
            )
            return None

        return ExternalMaterialSelection(
            display_name=folder.name,
            folder_path=str(folder),
            external_txt_path=str(txt_files[0]) if txt_files else None,
            external_png_path=str(png_files[0]) if png_files else None,
            is_external=True,
        )

    def export_study_configs(self) -> list[dict[str, Any]]:
        exported: list[dict[str, Any]] = []
        for cfg in self._study_configs:
            external = None
            if cfg.external_material is not None:
                external = {
                    "display_name": cfg.external_material.display_name,
                    "folder_path": cfg.external_material.folder_path,
                    "external_txt_path": cfg.external_material.external_txt_path or "",
                    "external_png_path": cfg.external_material.external_png_path or "",
                    "is_external": bool(cfg.external_material.is_external),
                }
            exported.append(
                {
                    "folder_name": cfg.folder_name,
                    "folder_path": cfg.folder_path,
                    "selected": bool(cfg.selected),
                    "symmetry": cfg.symmetry,
                    "material_name": cfg.material_name,
                    "external_material": external,
                }
            )
        return exported

    def restore_study_configs(self, parent_folder: str, saved_configs: list[dict[str, Any]]) -> None:
        detected = self._simulation_service.detect_first_level_subfolders(parent_folder)
        if not detected:
            self._study_configs = []
            self._render_study_table()
            self.studies_updated.emit()
            return

        detected_by_path = {str(Path(cfg.folder_path).resolve()): cfg for cfg in detected}
        detected_by_name = {cfg.folder_name: cfg for cfg in detected}
        ordered: list[SimulationStudyConfig] = []
        consumed: set[str] = set()

        for item in saved_configs:
            if not isinstance(item, dict):
                continue
            path_text = str(item.get("folder_path", "") or "").strip()
            name_text = str(item.get("folder_name", "") or "").strip()
            cfg: SimulationStudyConfig | None = None
            if path_text:
                cfg = detected_by_path.get(str(Path(path_text).resolve()))
            if cfg is None and name_text:
                cfg = detected_by_name.get(name_text)
            if cfg is None:
                continue
            key = str(Path(cfg.folder_path).resolve())
            if key in consumed:
                continue

            cfg.selected = bool(item.get("selected", False))
            cfg.symmetry = str(item.get("symmetry", "No") or "No")
            cfg.material_name = str(item.get("material_name", "") or "")

            raw_external = item.get("external_material")
            if isinstance(raw_external, dict):
                display_name = str(raw_external.get("display_name", "") or "").strip()
                if display_name:
                    cfg.external_material = ExternalMaterialSelection(
                        display_name=display_name,
                        folder_path=str(raw_external.get("folder_path", "") or ""),
                        external_txt_path=(str(raw_external.get("external_txt_path", "") or "").strip() or None),
                        external_png_path=(str(raw_external.get("external_png_path", "") or "").strip() or None),
                        is_external=bool(raw_external.get("is_external", True)),
                    )
            else:
                cfg.external_material = None

            ordered.append(cfg)
            consumed.add(key)

        for cfg in detected:
            key = str(Path(cfg.folder_path).resolve())
            if key in consumed:
                continue
            ordered.append(cfg)

        self._study_configs = ordered
        self._render_study_table()
        self.studies_updated.emit()

    def _select_external_files_from_folder(self, folder: Path) -> list[Path] | None:
        candidates = [
            path
            for path in sorted(folder.iterdir(), key=lambda p: p.name.lower())
            if path.is_file() and path.suffix.lower() in {".txt", ".png"}
        ]
        if not candidates:
            QMessageBox.information(self, "No files", "No .txt or .png files found in the selected folder.")
            return None

        dlg = QDialog(self)
        dlg.setWindowTitle("Select External Material Files")
        dlg.resize(560, 360)
        root = QVBoxLayout(dlg)

        file_list = QListWidget(dlg)
        file_list.setSelectionMode(QAbstractItemView.MultiSelection)
        for path in candidates:
            item = QListWidgetItem(path.name)
            item.setData(Qt.UserRole, str(path))
            file_list.addItem(item)
        root.addWidget(file_list)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, parent=dlg)
        buttons.accepted.connect(dlg.accept)
        buttons.rejected.connect(dlg.reject)
        root.addWidget(buttons)

        if dlg.exec() != QDialog.Accepted:
            return None

        selected: list[Path] = []
        for item in file_list.selectedItems():
            path = Path(str(item.data(Qt.UserRole) or "")).resolve()
            if path.parent.resolve() == folder.resolve() and path.suffix.lower() in {".txt", ".png"}:
                selected.append(path)
        return selected
