from __future__ import annotations

from PySide6.QtWidgets import QDialog, QFormLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QVBoxLayout


class NotionTokenDialog(QDialog):
    def __init__(self, message: str, existing_token: str = "", parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Notion token required")
        self.resize(560, 180)

        root = QVBoxLayout(self)

        label = QLabel(message)
        label.setWordWrap(True)
        root.addWidget(label)

        form = QFormLayout()
        self.token_edit = QLineEdit(existing_token)
        self.token_edit.setEchoMode(QLineEdit.Password)
        form.addRow("Notion Personal Access Token", self.token_edit)
        root.addLayout(form)

        actions = QHBoxLayout()
        self.btn_ok = QPushButton("Save")
        self.btn_cancel = QPushButton("Cancel")
        actions.addStretch(1)
        actions.addWidget(self.btn_ok)
        actions.addWidget(self.btn_cancel)
        root.addLayout(actions)

        self.btn_ok.clicked.connect(self.accept)
        self.btn_cancel.clicked.connect(self.reject)

    def token(self) -> str:
        return self.token_edit.text().strip()
