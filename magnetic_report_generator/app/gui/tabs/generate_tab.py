from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)


class GenerateTab(QWidget):
    SUMMARY_PARAMETERS = [
        "P2P ppm",
        "Bmin",
        "Bmax",
        "Bavg",
        "1-99% ppm",
        "P1",
        "P99",
        "5-95% ppm",
        "P5",
        "P95",
        "Peak",
    ]

    export_clicked = Signal()
    upload_to_notion_clicked = Signal()
    browse_folder_clicked = Signal()
    summary_rows_changed = Signal(list)
    summary_labels_changed = Signal()

    def __init__(self) -> None:
        super().__init__()
        root = QVBoxLayout(self)

        export_box = QGroupBox("Export")
        export_form = QFormLayout(export_box)

        self.output_folder_edit = QLineEdit()
        self.output_folder_edit.setReadOnly(True)
        folder_row = QHBoxLayout()
        folder_row.addWidget(self.output_folder_edit, 1)
        self.btn_browse_folder = QPushButton("Browse")
        folder_row.addWidget(self.btn_browse_folder)

        self.output_name_edit = QLineEdit()
        self.output_format_combo = QComboBox()
        self.output_format_combo.addItem("PDF (.pdf)", "pdf")
        self.output_format_combo.addItem("Markdown (.md)", "md")

        export_form.addRow("Path", folder_row)
        export_form.addRow("Name", self.output_name_edit)
        export_form.addRow("Format", self.output_format_combo)
        root.addWidget(export_box)

        labels_box = QGroupBox("Summary Labels")
        labels_root = QVBoxLayout(labels_box)
        self.labels_table = QTableWidget(0, 4)
        self.labels_table.setHorizontalHeaderLabels(["Use", "Label", "Comment", "Expected ppms"])
        self.labels_table.horizontalHeader().setStretchLastSection(True)
        labels_root.addWidget(self.labels_table)
        self.labels_table.itemChanged.connect(self._on_labels_item_changed)
        root.addWidget(labels_box, 1)

        parameters_box = QGroupBox("Summary Rows")
        parameters_root = QVBoxLayout(parameters_box)
        self.parameters_table = QTableWidget(0, 2)
        self.parameters_table.setHorizontalHeaderLabels(["Use", "Row"])
        self.parameters_table.horizontalHeader().setStretchLastSection(True)
        parameters_root.addWidget(self.parameters_table)
        root.addWidget(parameters_box, 1)

        self._init_parameters_table()
        self.parameters_table.itemChanged.connect(self._on_parameters_item_changed)

        self.status_label = QLabel("Ready")
        root.addWidget(self.status_label)

        row = QHBoxLayout()
        self.btn_export = QPushButton("Export Report")
        self.btn_upload_notion = QPushButton("Upload to Notion")
        row.addWidget(self.btn_export)
        row.addWidget(self.btn_upload_notion)
        row.addStretch(1)
        root.addLayout(row)

        self.btn_export.clicked.connect(self.export_clicked.emit)
        self.btn_upload_notion.clicked.connect(self.upload_to_notion_clicked.emit)
        self.btn_browse_folder.clicked.connect(self.browse_folder_clicked.emit)

    def set_status(self, text: str) -> None:
        self.status_label.setText(text)

    def set_output_folder(self, folder: str) -> None:
        self.output_folder_edit.setText(folder)

    def set_output_name(self, name: str) -> None:
        self.output_name_edit.setText(name)

    def output_folder(self) -> str:
        return self.output_folder_edit.text().strip()

    def output_name(self) -> str:
        return self.output_name_edit.text().strip()

    def selected_output_format(self) -> str:
        return str(self.output_format_combo.currentData() or "pdf")

    def set_selected_output_format(self, fmt: str) -> None:
        match = "md" if str(fmt).strip().lower() in {"md", "markdown"} else "pdf"
        index = self.output_format_combo.findData(match)
        if index >= 0:
            self.output_format_combo.setCurrentIndex(index)

    def set_available_labels(self, labels: list[str]) -> None:
        previous = set(self.selected_labels())
        previous_comments = self.selected_label_comments()
        previous_expected_ppms = self.selected_label_expected_ppms()
        self.labels_table.blockSignals(True)
        try:
            self.labels_table.setRowCount(len(labels))
            for row, label in enumerate(labels):
                use_item = QTableWidgetItem()
                use_item.setFlags(use_item.flags() | Qt.ItemIsUserCheckable)
                use_item.setCheckState(Qt.Checked if not previous or label in previous else Qt.Unchecked)
                self.labels_table.setItem(row, 0, use_item)
                label_item = QTableWidgetItem(label)
                label_item.setFlags(label_item.flags() & ~Qt.ItemIsEditable)
                self.labels_table.setItem(row, 1, label_item)
                self.labels_table.setItem(row, 2, QTableWidgetItem(previous_comments.get(label, "")))
                self.labels_table.setItem(row, 3, QTableWidgetItem(previous_expected_ppms.get(label, "")))
        finally:
            self.labels_table.blockSignals(False)

    def set_label_metadata(self, comments: dict[str, str], expected_ppms: dict[str, str]) -> None:
        self.labels_table.blockSignals(True)
        try:
            for row in range(self.labels_table.rowCount()):
                label_item = self.labels_table.item(row, 1)
                if label_item is None:
                    continue
                label = label_item.text().strip()
                if not label:
                    continue
                comment_item = self.labels_table.item(row, 2)
                expected_item = self.labels_table.item(row, 3)
                if comment_item is not None:
                    comment_item.setText(comments.get(label, ""))
                if expected_item is not None:
                    expected_item.setText(expected_ppms.get(label, ""))
        finally:
            self.labels_table.blockSignals(False)

    def selected_labels(self) -> list[str]:
        labels: list[str] = []
        for row in range(self.labels_table.rowCount()):
            use_item = self.labels_table.item(row, 0)
            label_item = self.labels_table.item(row, 1)
            if use_item is None or label_item is None:
                continue
            if use_item.checkState() == Qt.Checked:
                labels.append(label_item.text().strip())
        return labels

    def selected_label_comments(self) -> dict[str, str]:
        comments: dict[str, str] = {}
        for row in range(self.labels_table.rowCount()):
            label_item = self.labels_table.item(row, 1)
            comment_item = self.labels_table.item(row, 2)
            if label_item is None:
                continue
            label = label_item.text().strip()
            if not label:
                continue
            comment = comment_item.text().strip() if comment_item is not None else ""
            if comment:
                comments[label] = comment
        return comments

    def selected_label_expected_ppms(self) -> dict[str, str]:
        expected_ppms: dict[str, str] = {}
        for row in range(self.labels_table.rowCount()):
            label_item = self.labels_table.item(row, 1)
            expected_item = self.labels_table.item(row, 3)
            if label_item is None:
                continue
            label = label_item.text().strip()
            if not label:
                continue
            expected_ppm = expected_item.text().strip() if expected_item is not None else ""
            if expected_ppm:
                expected_ppms[label] = expected_ppm
        return expected_ppms

    def _on_labels_item_changed(self, item: QTableWidgetItem) -> None:
        if item is None:
            return
        self.summary_labels_changed.emit()

    def _init_parameters_table(self) -> None:
        self.parameters_table.setRowCount(len(self.SUMMARY_PARAMETERS))
        for row, parameter in enumerate(self.SUMMARY_PARAMETERS):
            use_item = QTableWidgetItem()
            use_item.setFlags(use_item.flags() | Qt.ItemIsUserCheckable)
            use_item.setCheckState(Qt.Checked)
            self.parameters_table.setItem(row, 0, use_item)

            parameter_item = QTableWidgetItem(parameter)
            parameter_item.setFlags(parameter_item.flags() & ~Qt.ItemIsEditable)
            self.parameters_table.setItem(row, 1, parameter_item)

    def selected_parameters(self) -> list[str]:
        parameters: list[str] = []
        for row in range(self.parameters_table.rowCount()):
            use_item = self.parameters_table.item(row, 0)
            parameter_item = self.parameters_table.item(row, 1)
            if use_item is None or parameter_item is None:
                continue
            if use_item.checkState() == Qt.Checked:
                parameters.append(parameter_item.text().strip())
        return parameters

    def set_selected_parameters(self, selected: list[str]) -> None:
        selected_set = {item for item in selected}
        self.parameters_table.blockSignals(True)
        try:
            for row in range(self.parameters_table.rowCount()):
                use_item = self.parameters_table.item(row, 0)
                parameter_item = self.parameters_table.item(row, 1)
                if use_item is None or parameter_item is None:
                    continue
                parameter = parameter_item.text().strip()
                state = Qt.Checked if parameter in selected_set else Qt.Unchecked
                use_item.setCheckState(state)
        finally:
            self.parameters_table.blockSignals(False)

    def _on_parameters_item_changed(self, item: QTableWidgetItem) -> None:
        if item.column() != 0:
            return
        self.summary_rows_changed.emit(self.selected_parameters())
