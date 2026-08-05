from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
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

from app.models.entities import AttachedImageInfo, MaterialCurve


class MaterialDialog(QDialog):
    def __init__(self, material_name: str, material: MaterialCurve, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"Edit Material - {material_name}")
        self.resize(520, 420)
        self._material_name = material_name
        self._external_txt_path = material.external_txt_path
        self._external_png_path = material.external_png_path

        root = QVBoxLayout(self)
        meta_form = QFormLayout()
        self.links_edit = QTextEdit("\n".join(material.links))
        self.links_edit.setMinimumHeight(58)
        self.comment_edit = QTextEdit(material.comment)
        self.comment_edit.setMinimumHeight(60)
        meta_form.addRow("Reference links (one per line)", self.links_edit)
        meta_form.addRow("Comment", self.comment_edit)
        root.addLayout(meta_form)

        self.images: list[AttachedImageInfo] = [AttachedImageInfo(path=img.path, comment=img.comment) for img in material.images]
        root.addWidget(QLabel("Material images"))
        self.images_table = QTableWidget(0, 2, self)
        self.images_table.setHorizontalHeaderLabels(["Image", "Comment"])
        self.images_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.images_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        root.addWidget(self.images_table)

        image_actions = QHBoxLayout()
        self.btn_add_images = QPushButton("Attach image(s)")
        self.btn_remove_image = QPushButton("Remove selected")
        image_actions.addWidget(self.btn_add_images)
        image_actions.addWidget(self.btn_remove_image)
        image_actions.addStretch(1)
        root.addLayout(image_actions)

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
        self.btn_add_images.clicked.connect(self._attach_images)
        self.btn_remove_image.clicked.connect(self._remove_selected_image)

        self._render_images_table()

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

        images: list[AttachedImageInfo] = []
        for row in range(self.images_table.rowCount()):
            path_item = self.images_table.item(row, 0)
            comment_item = self.images_table.item(row, 1)
            if path_item is None:
                continue
            path = path_item.text().strip()
            if not path:
                continue
            comment = comment_item.text().strip() if comment_item is not None else ""
            images.append(AttachedImageInfo(path=path, comment=comment))

        links = [line.strip() for line in self.links_edit.toPlainText().splitlines() if line.strip()]

        return MaterialCurve(
            name=self._material_name,
            points=points,
            comment=self.comment_edit.toPlainText().strip(),
            links=links,
            images=images,
            external_txt_path=self._external_txt_path,
            external_png_path=self._external_png_path,
        )

    def _attach_images(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Attach material images",
            "",
            "Images (*.png *.jpg *.jpeg *.bmp *.tif *.tiff *.webp);;All files (*)",
        )
        if not paths:
            return

        existing = {img.path for img in self.images}
        for path in paths:
            if path not in existing:
                self.images.append(AttachedImageInfo(path=path, comment=""))
                existing.add(path)
        self._render_images_table()

    def _remove_selected_image(self) -> None:
        row = self.images_table.currentRow()
        if row < 0 or row >= len(self.images):
            return
        self._collect_images_from_table()
        self.images.pop(row)
        self._render_images_table()

    def _collect_images_from_table(self) -> None:
        updated: list[AttachedImageInfo] = []
        for row in range(self.images_table.rowCount()):
            path_item = self.images_table.item(row, 0)
            comment_item = self.images_table.item(row, 1)
            if path_item is None:
                continue
            path = path_item.text().strip()
            if not path:
                continue
            comment = comment_item.text().strip() if comment_item is not None else ""
            updated.append(AttachedImageInfo(path=path, comment=comment))
        self.images = updated

    def _render_images_table(self) -> None:
        self.images_table.setRowCount(len(self.images))
        for row, image_info in enumerate(self.images):
            path_item = QTableWidgetItem(image_info.path)
            path_item.setFlags(path_item.flags() & ~Qt.ItemIsEditable)
            self.images_table.setItem(row, 0, path_item)
            self.images_table.setItem(row, 1, QTableWidgetItem(image_info.comment))


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
