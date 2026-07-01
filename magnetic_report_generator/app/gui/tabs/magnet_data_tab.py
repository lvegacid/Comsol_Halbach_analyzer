from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from pathlib import Path

from app.models.entities import AttachedImageInfo, MagnetMetrics, today_iso
from app.services.magnet_data_service import MagnetDataService


class MagnetDataTab(QWidget):
    data_updated = Signal(object)

    def __init__(self, service: MagnetDataService, default_comsol_version: str) -> None:
        super().__init__()
        self._service = service
        self.metrics: MagnetMetrics | None = None

        root = QVBoxLayout(self)

        form_box = QGroupBox("Magnet Data")
        form = QFormLayout(form_box)

        self.project_edit = QLineEdit()
        self.comsol_edit = QLineEdit(default_comsol_version)
        self.date_edit = QLineEdit(today_iso())
        self.date_edit.setReadOnly(True)

        self.txt_path_edit = QLineEdit()
        self.txt_path_edit.setReadOnly(True)
        self.magnet_characteristics_edit = QLineEdit()
        self.expected_ppm_edit = QLineEdit()
        self.other_info_edit = QTextEdit()
        self.other_info_edit.setMinimumHeight(70)
        self.other_info_images: list[AttachedImageInfo] = []
        self.other_images_table = QTableWidget(0, 2)
        self.other_images_table.setHorizontalHeaderLabels(["Image", "Comment"])

        self.btn_attach_images = QPushButton("Attach image(s)")
        self.btn_clear_images = QPushButton("Clear")
        images_row = QVBoxLayout()
        images_actions = QHBoxLayout()
        images_actions.addWidget(self.btn_attach_images)
        images_actions.addWidget(self.btn_clear_images)
        images_actions.addStretch(1)
        images_row.addLayout(images_actions)
        images_row.addWidget(self.other_images_table)

        browse_row = QHBoxLayout()
        browse_row.addWidget(self.txt_path_edit, 1)
        self.btn_browse = QPushButton("Browse TXT")
        self.btn_compute = QPushButton("Compute")
        browse_row.addWidget(self.btn_browse)
        browse_row.addWidget(self.btn_compute)

        form.addRow("Project", self.project_edit)
        form.addRow("COMSOL Version", self.comsol_edit)
        form.addRow("Date", self.date_edit)
        form.addRow("Original .txt file", browse_row)
        form.addRow("Magnet characteristics", self.magnet_characteristics_edit)
        form.addRow("Expected ppm", self.expected_ppm_edit)
        form.addRow("Other information", self.other_info_edit)
        form.addRow("Other information images", images_row)

        root.addWidget(form_box)

        self.summary_label = QLabel("No data loaded")
        root.addWidget(self.summary_label)

        self.ring_table = QTableWidget(0, 3)
        self.ring_table.setHorizontalHeaderLabels(["Ring", "X position (mm)", "Magnets"])
        root.addWidget(self.ring_table)

        self.btn_browse.clicked.connect(self.on_browse)
        self.btn_compute.clicked.connect(self.compute)
        self.btn_attach_images.clicked.connect(self.on_attach_images)
        self.btn_clear_images.clicked.connect(self.on_clear_images)

    def on_browse(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Open Magnet TXT", "", "Text files (*.txt);;All files (*)")
        if path:
            self.txt_path_edit.setText(path)
            self.magnet_characteristics_edit.setText(Path(path).name)
            expected = self._service.detect_expected_ppm_from_filename(path)
            if expected is not None:
                self.expected_ppm_edit.setText(self._format_number(expected))

    def compute(self) -> None:
        self._collect_other_image_comments()
        txt_path = self.txt_path_edit.text().strip()
        project = self.project_edit.text().strip() or "Untitled"
        magnet_characteristics = self.magnet_characteristics_edit.text().strip()
        version = self.comsol_edit.text().strip() or "6.4"
        run_date = self.date_edit.text().strip()
        expected_ppm_text = self.expected_ppm_edit.text().strip()
        expected_ppm = float(expected_ppm_text) if expected_ppm_text else None
        other_information = self.other_info_edit.toPlainText().strip()

        self.metrics = self._service.parse_txt(
            txt_path,
            project,
            magnet_characteristics,
            version,
            run_date,
            expected_ppm=expected_ppm,
            other_information=other_information,
            other_info_images=self.other_info_images,
        )
        self._render_metrics()
        self.data_updated.emit(self.metrics)

    def _render_metrics(self) -> None:
        if self.metrics is None:
            return

        m = self.metrics
        self.summary_label.setText(
            " | ".join(
                [
                    f"Magnets: {m.n_magnets}",
                    f"Rings: {m.n_rings}",
                    f"Br: {m.br_t:.6f} T",
                    f"Size: {m.magnet_size_mm3} mm^3",
                    f"Length: {self._format_number(m.magnet_length_mm, 3)} mm",
                    f"Major: {self._format_number(m.major_ellipse_side_mm, 3)} ({m.major_axis_direction})",
                    f"Minor: {self._format_number(m.minor_ellipse_side_mm, 3)} ({m.minor_axis_direction})",
                    f"InterRing: {self._format_number(m.interring_distance_mm) if m.interring_distance_mm is not None else m.interring_note}",
                    f"Expected ppm: {self._format_number(m.expected_ppm) if m.expected_ppm is not None else 'N/A'}",
                ]
            )
        )

        self.ring_table.setRowCount(len(m.rings))
        for row_idx, ring in enumerate(m.rings):
            self.ring_table.setItem(row_idx, 0, QTableWidgetItem(str(ring.ring_index)))
            self.ring_table.setItem(row_idx, 1, QTableWidgetItem(self._format_number(ring.x_position_mm, 3)))
            self.ring_table.setItem(row_idx, 2, QTableWidgetItem(str(ring.magnets)))

    def on_attach_images(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Attach images",
            "",
            "Images (*.png *.jpg *.jpeg *.bmp *.tif *.tiff *.webp);;All files (*)",
        )
        if not paths:
            return

        existing = {item.path for item in self.other_info_images}
        for p in paths:
            if p not in existing:
                self.other_info_images.append(AttachedImageInfo(path=p))
                existing.add(p)
        self._render_other_images_label()

    def on_clear_images(self) -> None:
        self.other_info_images = []
        self._render_other_images_label()

    def _render_other_images_label(self) -> None:
        if not self.other_info_images:
            self.other_images_table.setRowCount(0)
            return

        self.other_images_table.setRowCount(len(self.other_info_images))
        for row_idx, item in enumerate(self.other_info_images):
            path_item = QTableWidgetItem(item.path)
            path_item.setFlags(path_item.flags() & ~Qt.ItemIsEditable)
            self.other_images_table.setItem(row_idx, 0, path_item)
            self.other_images_table.setItem(row_idx, 1, QTableWidgetItem(item.comment))

    def _collect_other_image_comments(self) -> None:
        updated: list[AttachedImageInfo] = []
        for row_idx, item in enumerate(self.other_info_images):
            comment_item = self.other_images_table.item(row_idx, 1)
            comment = comment_item.text().strip() if comment_item is not None else ""
            updated.append(AttachedImageInfo(path=item.path, comment=comment))
        self.other_info_images = updated

    @staticmethod
    def _format_number(value: float | None, decimals: int = 2) -> str:
        if value is None:
            return ""
        rounded = round(float(value), decimals)
        if abs(rounded - int(rounded)) < 1e-9:
            return str(int(rounded))
        return (f"{rounded:.{decimals}f}").rstrip("0").rstrip(".")
