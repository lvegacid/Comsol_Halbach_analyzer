from __future__ import annotations

from typing import Callable

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
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
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.gui.dialogs.material_dialog import MaterialDialog, NewMaterialDialog
from app.models.entities import AttachedImageInfo, MaterialCurve, SimulationStudyConfig
from app.services.settings_service import SettingsService
from app.services.simulation_service import SimulationService


class SimulationResultsTab(QWidget):
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

        self.study_table = QTableWidget(0, 5)
        self.study_table.setHorizontalHeaderLabels(["Use", "Folder", "Symmetry", "Material", "Path"])
        self.study_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.study_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.study_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.study_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.study_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.Stretch)
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
        self._study_configs = self._simulation_service.detect_first_level_subfolders(parent)
        self._render_study_table()
        self.studies_updated.emit()

    def _render_study_table(self) -> None:
        self.study_table.blockSignals(True)
        self.study_table.setRowCount(len(self._study_configs))
        material_names = list(self._materials.keys())

        for row, cfg in enumerate(self._study_configs):
            use_item = QTableWidgetItem()
            use_item.setFlags(use_item.flags() | Qt.ItemIsUserCheckable)
            use_item.setCheckState(Qt.Checked if cfg.selected else Qt.Unchecked)
            self.study_table.setItem(row, 0, use_item)

            self.study_table.setItem(row, 1, QTableWidgetItem(cfg.folder_name))

            symmetry_combo = QComboBox()
            symmetry_combo.addItems(["Yes", "No"])
            symmetry_combo.setCurrentText(cfg.symmetry)
            symmetry_combo.currentTextChanged.connect(self._make_symmetry_handler(row))
            self.study_table.setCellWidget(row, 2, symmetry_combo)

            material_combo = QComboBox()
            material_combo.addItems(material_names)
            if cfg.material_name and cfg.material_name in material_names:
                material_combo.setCurrentText(cfg.material_name)
            elif material_names:
                cfg.material_name = material_names[0]
            material_combo.currentTextChanged.connect(self._make_material_handler(row))
            self.study_table.setCellWidget(row, 3, material_combo)

            self.study_table.setItem(row, 4, QTableWidgetItem(cfg.folder_path))

        self.study_table.blockSignals(False)
        self.study_table.itemChanged.connect(self.on_item_changed)

    def on_item_changed(self, item: QTableWidgetItem) -> None:
        if item.column() != 0:
            return
        row = item.row()
        if row < 0 or row >= len(self._study_configs):
            return
        self._study_configs[row].selected = item.checkState() == Qt.Checked
        self.studies_updated.emit()

    def _make_symmetry_handler(self, row: int) -> Callable[[str], None]:
        def handler(value: str) -> None:
            if 0 <= row < len(self._study_configs):
                self._study_configs[row].symmetry = value
                self.studies_updated.emit()

        return handler

    def _make_material_handler(self, row: int) -> Callable[[str], None]:
        def handler(value: str) -> None:
            if 0 <= row < len(self._study_configs):
                self._study_configs[row].material_name = value
                self.studies_updated.emit()

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
