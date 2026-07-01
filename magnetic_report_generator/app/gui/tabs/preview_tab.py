from __future__ import annotations

from PySide6.QtWidgets import QTextEdit, QVBoxLayout, QWidget


class PreviewTab(QWidget):
    def __init__(self) -> None:
        super().__init__()
        root = QVBoxLayout(self)
        self.preview = QTextEdit()
        self.preview.setReadOnly(True)
        root.addWidget(self.preview)

    def set_text(self, text: str) -> None:
        self.preview.setPlainText(text)
