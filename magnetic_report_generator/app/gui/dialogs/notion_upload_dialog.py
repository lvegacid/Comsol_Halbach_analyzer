from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QButtonGroup,
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
    QRadioButton,
    QVBoxLayout,
    QWidget,
)

from app.services.notion_service import NotionLog, NotionProject, NotionService

MODE_NEW_LOG = "new"
MODE_EXISTING_LOG = "existing"


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
        log_loader: Callable[[str], list[NotionLog]] | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Upload report to Notion")
        self.resize(760, 560)

        self._projects = projects
        self._log_loader = log_loader
        self._loaded_logs_project_id: str | None = None

        root = QVBoxLayout(self)

        mode_box = QGroupBox("Destination")
        mode_layout = QVBoxLayout(mode_box)
        self.radio_new_log = QRadioButton("Create new log")
        self.radio_existing_log = QRadioButton("Add to existing log")
        self.radio_new_log.setChecked(True)
        self._mode_group = QButtonGroup(self)
        self._mode_group.addButton(self.radio_new_log)
        self._mode_group.addButton(self.radio_existing_log)
        mode_layout.addWidget(self.radio_new_log)
        mode_layout.addWidget(self.radio_existing_log)
        root.addWidget(mode_box)

        form = QFormLayout()
        self.project_combo = QComboBox()
        self.title_edit = QLineEdit(default_title)

        form.addRow("Project", self.project_combo)
        form.addRow("Report title", self.title_edit)
        root.addLayout(form)

        self.existing_box = QGroupBox("Existing log (only the new studies are appended)")
        existing_form = QFormLayout(self.existing_box)
        log_row = QHBoxLayout()
        self.log_combo = QComboBox()
        self.log_combo.setMinimumContentsLength(40)
        self.btn_refresh_logs = QPushButton("Refresh")
        log_row.addWidget(self.log_combo, 1)
        log_row.addWidget(self.btn_refresh_logs)
        self.log_url_edit = QLineEdit()
        self.log_url_edit.setPlaceholderText("Optional: paste a Notion page URL or ID (overrides the list)")
        self.log_status_label = QLabel("")
        self.log_status_label.setWordWrap(True)
        existing_form.addRow("Recent logs", log_row)
        existing_form.addRow("Page URL / ID", self.log_url_edit)
        existing_form.addRow("", self.log_status_label)
        root.addWidget(self.existing_box)

        self.tags_box = QGroupBox("Tags")
        tags_layout = QVBoxLayout(self.tags_box)
        self.tag_selector = _TagSelectorWidget(tags, selected_tags or [])
        tags_layout.addWidget(self.tag_selector)
        root.addWidget(self.tags_box)

        actions = QHBoxLayout()
        self.btn_upload = QPushButton("Upload")
        self.btn_cancel = QPushButton("Cancel")
        actions.addStretch(1)
        actions.addWidget(self.btn_upload)
        actions.addWidget(self.btn_cancel)
        root.addLayout(actions)

        self.btn_upload.clicked.connect(self._on_upload)
        self.btn_cancel.clicked.connect(self.reject)
        self.radio_new_log.toggled.connect(self._on_mode_changed)
        self.project_combo.currentIndexChanged.connect(self._on_project_changed)
        self.btn_refresh_logs.clicked.connect(lambda: self._load_logs(force=True))

        self._load_projects(default_project_id, default_project_title)
        self._on_mode_changed()

    def selected_project_id(self) -> str:
        return str(self.project_combo.currentData() or "")

    def report_title(self) -> str:
        return self.title_edit.text().strip()

    def selected_tags(self) -> list[str]:
        return self.tag_selector.selected_tags()

    def mode(self) -> str:
        return MODE_EXISTING_LOG if self.radio_existing_log.isChecked() else MODE_NEW_LOG

    def existing_log_page_id(self) -> str:
        """Page ID of the chosen log: the pasted URL/ID wins over the dropdown selection."""
        typed = self.log_url_edit.text().strip()
        if typed:
            return NotionService.parse_page_id(typed)
        return str(self.log_combo.currentData() or "")

    def _on_mode_changed(self) -> None:
        existing = self.mode() == MODE_EXISTING_LOG
        self.existing_box.setVisible(existing)
        self.title_edit.setEnabled(not existing)
        self.tags_box.setEnabled(not existing)
        self.btn_upload.setText("Add to log" if existing else "Upload")
        if existing:
            self._load_logs()

    def _on_project_changed(self) -> None:
        if self.mode() == MODE_EXISTING_LOG:
            self._load_logs()

    def _load_logs(self, force: bool = False) -> None:
        project_id = self.selected_project_id()
        if not force and project_id == self._loaded_logs_project_id:
            return
        self.log_combo.clear()
        if self._log_loader is None or not project_id:
            self.log_status_label.setText("Select a project, or paste the log URL/ID.")
            return

        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            logs = self._log_loader(project_id)
        except Exception as err:
            self.log_status_label.setText(f"Could not load the logs of this project: {err}")
            return
        finally:
            QApplication.restoreOverrideCursor()

        self._loaded_logs_project_id = project_id
        for log in logs:
            stamp = log.last_edited[:10]
            label = f"{log.title}  [{stamp}]" if stamp else log.title
            self.log_combo.addItem(label, log.page_id)
        self.log_status_label.setText(
            f"{len(logs)} log(s) found in this project." if logs else "No logs found in this project. Paste a URL/ID instead."
        )

    def _on_upload(self) -> None:
        if not self.selected_project_id():
            QMessageBox.warning(self, "No project", "Select a project from the list.")
            return
        if self.mode() == MODE_EXISTING_LOG:
            if not self.existing_log_page_id():
                QMessageBox.warning(
                    self,
                    "No log selected",
                    "Select an existing log from the list or paste a valid Notion page URL/ID.",
                )
                return
            self.accept()
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