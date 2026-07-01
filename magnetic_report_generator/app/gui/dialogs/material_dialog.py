from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
)

from app.models.entities import MaterialCurve


class MaterialDialog(QDialog):
    def __init__(self, material_name: str, material: MaterialCurve, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"Edit Material - {material_name}")
        self.resize(520, 420)
        self._material_name = material_name

        root = QVBoxLayout(self)
        meta_form = QFormLayout()
        self.link_edit = QLineEdit(material.link)
        self.comment_edit = QTextEdit(material.comment)
        self.comment_edit.setMinimumHeight(60)
        meta_form.addRow("Reference link", self.link_edit)
        meta_form.addRow("Comment", self.comment_edit)
        root.addLayout(meta_form)

        root.addWidget(QLabel("BH Curve: H (kA/m) | B (T)"))

        self.table = QTableWidget(0, 2, self)
        self.table.setHorizontalHeaderLabels(["H (kA/m)", "B (T)"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        root.addWidget(self.table)

        for h, b in material.points:
            self._add_row(h, b)

        actions = QHBoxLayout()
        btn_add = QPushButton("Add Row")
        btn_delete = QPushButton("Delete Row")
        btn_ok = QPushButton("OK")
        btn_cancel = QPushButton("Cancel")
        actions.addWidget(btn_add)
        actions.addWidget(btn_delete)
        actions.addStretch(1)
        actions.addWidget(btn_ok)
        actions.addWidget(btn_cancel)
        root.addLayout(actions)

        btn_add.clicked.connect(lambda: self._add_row())
        btn_delete.clicked.connect(self._delete_selected_row)
        btn_ok.clicked.connect(self.accept)
        btn_cancel.clicked.connect(self.reject)

    def _add_row(self, h: float = 0.0, b: float = 0.0) -> None:
        row = self.table.rowCount()
        self.table.insertRow(row)
        self.table.setItem(row, 0, QTableWidgetItem(f"{h}"))
        self.table.setItem(row, 1, QTableWidgetItem(f"{b}"))

    def _delete_selected_row(self) -> None:
        row = self.table.currentRow()
        if row >= 0:
            self.table.removeRow(row)

    def to_material(self) -> MaterialCurve:
        points: list[tuple[float, float]] = []
        for row in range(self.table.rowCount()):
            h_item = self.table.item(row, 0)
            b_item = self.table.item(row, 1)
            if h_item is None or b_item is None:
                continue
            try:
                h_val = float(h_item.text().strip())
                b_val = float(b_item.text().strip())
            except ValueError as exc:
                raise ValueError(f"Invalid numeric value in row {row + 1}") from exc
            points.append((h_val, b_val))

        if not points:
            raise ValueError("Material curve cannot be empty")

        return MaterialCurve(
            name=self._material_name,
            points=points,
            link=self.link_edit.text().strip(),
            comment=self.comment_edit.toPlainText().strip(),
        )


class NewMaterialDialog:
    @staticmethod
    def ask_name(parent=None) -> str | None:
        name, ok = QInputDialog.getText(parent, "New Material", "Material name:")
        if not ok:
            return None
        name = name.strip()
        return name or None

    @staticmethod
    def show_error(parent, message: str) -> None:
        QMessageBox.critical(parent, "Material Error", message)
