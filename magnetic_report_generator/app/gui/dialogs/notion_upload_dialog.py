from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QGroupBox,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.services.notion_service import NotionProject


class _TagSelectorWidget(QWidget):
    def __init__(self, tags: list[str], selected_tags: list[str] | None = None, parent=None) -> None:
        super().__init__(parent)
        self._selected_tags = set(selected_tags or [])

        root = QVBoxLayout(self)

        self.list_widget = QListWidget()
        self.list_widget.setSelectionMode(QAbstractItemView.NoSelection)
        root.addWidget(self.list_widget)

        add_row = QHBoxLayout()
        self.new_tag_edit = QLineEdit()
        self.new_tag_edit.setPlaceholderText("Type a new tag and press Add")
        self.btn_add_tag = QPushButton("Add")
        add_row.addWidget(self.new_tag_edit, 1)
        add_row.addWidget(self.btn_add_tag)
        root.addLayout(add_row)

        self.btn_add_tag.clicked.connect(self._add_tag_from_input)
        self.new_tag_edit.returnPressed.connect(self._add_tag_from_input)
        self.set_tags(tags, selected_tags or [])

    def set_tags(self, tags: list[str], selected_tags: list[str] | None = None) -> None:
        self.list_widget.clear()
        self._selected_tags = set(selected_tags or [])
        for tag in tags:
            self._add_item(tag, checked=tag in self._selected_tags)

    def add_tag(self, tag: str, checked: bool = True) -> None:
        tag = tag.strip()
        if not tag:
            return
        for row in range(self.list_widget.count()):
            item = self.list_widget.item(row)
            if item is not None and item.text().strip().lower() == tag.lower():
                item.setCheckState(Qt.Checked if checked else Qt.Unchecked)
                return
        self._add_item(tag, checked=checked)

    def selected_tags(self) -> list[str]:
        tags: list[str] = []
        for row in range(self.list_widget.count()):
            item = self.list_widget.item(row)
            if item is None:
                continue
            if item.checkState() == Qt.Checked:
                tag = item.text().strip()
                if tag:
                    tags.append(tag)
        return tags

    def _add_tag_from_input(self) -> None:
        tag = self.new_tag_edit.text().strip()
        if not tag:
            return
        self.add_tag(tag, checked=True)
        self.new_tag_edit.clear()

    def _add_item(self, tag: str, checked: bool) -> None:
        item = QListWidgetItem(tag)
        item.setFlags(item.flags() | Qt.ItemIsUserCheckable | Qt.ItemIsEnabled | Qt.ItemIsSelectable)
        item.setCheckState(Qt.Checked if checked else Qt.Unchecked)
        self.list_widget.addItem(item)


class NotionUploadDialog(QDialog):
    def __init__(
        self,
        projects: list[NotionProject],
        tags: list[str],
        default_title: str,
        default_project_id: str = "",
        default_project_title: str = "",
        selected_tags: list[str] | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Upload report to Notion")
        self.resize(760, 420)

        self._projects = projects

        root = QVBoxLayout(self)

        form = QFormLayout()
        self.project_combo = QComboBox()
        self.title_edit = QLineEdit(default_title)

        form.addRow("Project", self.project_combo)
        form.addRow("Report title", self.title_edit)
        root.addLayout(form)

        tags_box = QGroupBox("Tags")
        tags_layout = QVBoxLayout(tags_box)
        self.tag_selector = _TagSelectorWidget(tags, selected_tags or [])
        tags_layout.addWidget(self.tag_selector)
        root.addWidget(tags_box)

        actions = QHBoxLayout()
        self.btn_upload = QPushButton("Upload")
        self.btn_cancel = QPushButton("Cancel")
        actions.addStretch(1)
        actions.addWidget(self.btn_upload)
        actions.addWidget(self.btn_cancel)
        root.addLayout(actions)

        self.btn_upload.clicked.connect(self._on_upload)
        self.btn_cancel.clicked.connect(self.reject)

        self._load_projects(default_project_id, default_project_title)

    def selected_project_id(self) -> str:
        return str(self.project_combo.currentData() or "")

    def report_title(self) -> str:
        return self.title_edit.text().strip()

    def selected_tags(self) -> list[str]:
        return self.tag_selector.selected_tags()

    def _on_upload(self) -> None:
        if not self.selected_project_id():
            QMessageBox.warning(self, "No project", "Select a project from the list.")
            return
        if not self.report_title():
            QMessageBox.warning(self, "Missing title", "Enter a report title.")
            return
        self.accept()

    def _load_projects(self, default_project_id: str, default_project_title: str) -> None:
        self.project_combo.clear()
        for project in self._projects:
            self.project_combo.addItem(project.title, project.page_id)

        if not self._projects:
            self.project_combo.setEnabled(False)
            return

        self.project_combo.setEnabled(True)

        selected_index = -1
        if default_project_id:
            selected_index = self.project_combo.findData(default_project_id)
        if selected_index < 0 and default_project_title:
            selected_index = self.project_combo.findText(default_project_title, Qt.MatchFixedString)
        if selected_index < 0:
            selected_index = 0
        self.project_combo.setCurrentIndex(selected_index)