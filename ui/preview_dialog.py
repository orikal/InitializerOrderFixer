from __future__ import annotations

from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QVBoxLayout,
)

from models.issue import Issue
from ui.code_highlight import highlight_issue


class PreviewDialog(QDialog):
    @staticmethod
    def _heading_label(text: str) -> QLabel:
        label = QLabel(text)
        font = QFont(label.font())
        font.setBold(True)
        label.setFont(font)
        return label

    def __init__(self, issue: Issue, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"Preview — {issue.class_name}::{issue.constructor_name}")
        self.resize(900, 500)

        mono = QFont("Consolas")
        if not mono.family():
            mono = QFont("Courier New")
        mono.setStyleHint(QFont.StyleHint.Monospace)

        original = QPlainTextEdit(issue.original_snippet)
        original.setReadOnly(True)
        original.setFont(mono)
        original.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)

        fixed = QPlainTextEdit(issue.fixed_snippet)
        fixed.setReadOnly(True)
        fixed.setFont(mono)
        fixed.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)

        highlight_issue(original, fixed, issue)

        left = QVBoxLayout()
        left.addWidget(self._heading_label("Original"))
        left.addWidget(original)

        right = QVBoxLayout()
        right.addWidget(self._heading_label("Fixed"))
        right.addWidget(fixed)

        columns = QHBoxLayout()
        columns.addLayout(left)
        columns.addLayout(right)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)

        layout = QVBoxLayout(self)
        layout.addLayout(columns)
        layout.addWidget(buttons)
