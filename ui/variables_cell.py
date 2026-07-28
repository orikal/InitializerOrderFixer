from __future__ import annotations

import html

from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QFontMetrics
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QVBoxLayout,
    QWidget,
)

CELL_PADDING_H = 8
CELL_PADDING_V = 8
VARIABLES_CELL_PADDING_H = 4
VARIABLES_CELL_PADDING_V = 4
LONG_VARIABLE_NAME_THRESHOLD = 20
STACKED_LAYOUT_EXTRA_HEIGHT = 10
BEFORE_BORDER_STYLE = "border: 2px solid #dc3545; border-radius: 4px; padding: 4px;"
AFTER_BORDER_STYLE = "border: 2px solid #28a745; border-radius: 4px; padding: 4px;"
WARNING_BUTTON_STYLE = (
    "QPushButton {"
    " color: #dc3545;"
    " font-weight: bold;"
    " font-size: 14px;"
    " border: 2px solid #dc3545;"
    " border-radius: 13px;"
    " background-color: #fff5f5;"
    " padding: 0;"
    "}"
    "QPushButton:hover {"
    " background-color: #fde8ea;"
    " border-color: #c82333;"
    " color: #c82333;"
    "}"
)
LABEL_BORDER_EXTRA = 12  # 2px border + 4px padding on each side


class ClassCellWidget(QWidget):
    def __init__(
        self,
        class_name: str,
        uninitialized_members: list[str],
        header_initialized_members: list[str] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._class_name = class_name
        self._uninitialized_members = list(uninitialized_members)
        self._header_initialized_members = list(header_initialized_members or [])

        layout = QHBoxLayout(self)
        layout.setContentsMargins(CELL_PADDING_H, CELL_PADDING_V, CELL_PADDING_H, CELL_PADDING_V)
        layout.setSpacing(4)

        self._name_label = QLabel(self._display_text())
        self._name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._name_label.setWordWrap(True)
        layout.addWidget(self._name_label, stretch=1)

        self._warning_btn: QPushButton | None = None
        if self._uninitialized_members:
            self._warning_btn = QPushButton("!")
            self._warning_btn.setFixedSize(26, 26)
            self._warning_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            self._warning_btn.setStyleSheet(WARNING_BUTTON_STYLE)
            self._warning_btn.setToolTip("Show member initialization details")
            self._warning_btn.clicked.connect(self._show_member_details)
            layout.addWidget(self._warning_btn, alignment=Qt.AlignmentFlag.AlignVCenter)

        tooltip = class_name
        if self._uninitialized_members:
            tooltip += "\n\nNot in initializer list:\n" + "\n".join(
                f"  • {name}" for name in self._uninitialized_members
            )
        self.setToolTip(tooltip)
        self._name_label.setToolTip(tooltip)

    def _display_text(self) -> str:
        if not self._uninitialized_members:
            return self._class_name
        members = "\n".join(f"  • {name}" for name in self._uninitialized_members)
        return f"{self._class_name}\n\nNot initialized:\n{members}"

    @staticmethod
    def _format_member_list(members: list[str]) -> str:
        if not members:
            return "  (none)"
        return "\n".join(f"  • {name}" for name in members)

    def _show_member_details(self) -> None:
        message = (
            "Declared in the header but not initialized in the constructor:\n"
            f"{self._format_member_list(self._uninitialized_members)}\n\n"
            "Declared and initialized in the header:\n"
            f"{self._format_member_list(self._header_initialized_members)}"
        )
        QMessageBox.warning(
            self,
            f"Member Initialization — {self._class_name}",
            message,
        )

    def height_for_column_width(self, width: int) -> int:
        if width < 20:
            width = 80
        content_width = max(20, width - 2 * CELL_PADDING_H - (30 if self._warning_btn else 0))
        metrics = QFontMetrics(self.font())
        rect = metrics.boundingRect(
            0,
            0,
            content_width,
            0,
            int(Qt.TextFlag.TextWordWrap),
            self._display_text(),
        )
        return max(rect.height(), 26 if self._warning_btn else 0) + 2 * CELL_PADDING_V + 4

    def sizeHint(self) -> QSize:
        total_width = self.width() if self.width() > 10 else 200
        return QSize(total_width, self.height_for_column_width(total_width))

    def minimumSizeHint(self) -> QSize:
        width = self.width() if self.width() > 10 else 200
        return QSize(width, self.height_for_column_width(width))


class WordWrapDelegate(QStyledItemDelegate):
    def initStyleOption(self, option: QStyleOptionViewItem, index) -> None:  # noqa: ANN001
        super().initStyleOption(option, index)
        option.features |= QStyleOptionViewItem.ViewItemFeature.WrapText
        option.textElideMode = Qt.TextElideMode.ElideNone

    def _content_rect(self, rect) -> "QStyleOptionViewItem":  # noqa: ANN001
        return rect.adjusted(CELL_PADDING_H, CELL_PADDING_V, -CELL_PADDING_H, -CELL_PADDING_V)

    def paint(self, painter, option: QStyleOptionViewItem, index) -> None:  # noqa: ANN001
        styled = QStyleOptionViewItem(option)
        self.initStyleOption(styled, index)
        styled.rect = self._content_rect(styled.rect)
        super().paint(painter, styled, index)

    def sizeHint(self, option, index):  # noqa: ANN001
        styled = QStyleOptionViewItem(option)
        self.initStyleOption(styled, index)
        content_width = max(20, option.rect.width() - 2 * CELL_PADDING_H)
        styled.rect.setWidth(content_width)
        hint = super().sizeHint(styled, index)
        return QSize(
            hint.width() + 2 * CELL_PADDING_H,
            hint.height() + 2 * CELL_PADDING_V,
        )


class FilesCellWidget(QWidget):
    def __init__(self, header_path: str, source_path: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._header_path = header_path
        self._source_path = source_path

        layout = QVBoxLayout(self)
        layout.setContentsMargins(CELL_PADDING_H, CELL_PADDING_V, CELL_PADDING_H, CELL_PADDING_V)
        layout.setSpacing(0)

        self._label = QLabel(self._rich_text())
        self._label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._label.setWordWrap(True)
        self._label.setTextFormat(Qt.TextFormat.RichText)
        layout.addWidget(self._label)

        tooltip = self._plain_text()
        self.setToolTip(tooltip)
        self._label.setToolTip(tooltip)

    def _rich_text(self) -> str:
        header = html.escape(self._header_path)
        source = html.escape(self._source_path)
        return f"<b>H:</b> {header}<br><b>S:</b> {source}"

    def _plain_text(self) -> str:
        return f"H: {self._header_path}\nS: {self._source_path}"

    def height_for_column_width(self, width: int) -> int:
        if width < 20:
            width = 80
        content_width = max(20, width - 2 * CELL_PADDING_H)
        metrics = QFontMetrics(self.font())
        rect = metrics.boundingRect(
            0,
            0,
            content_width,
            0,
            int(Qt.TextFlag.TextWordWrap),
            self._plain_text(),
        )
        return rect.height() + 2 * CELL_PADDING_V + 4

    def sizeHint(self) -> QSize:
        total_width = self.width() if self.width() > 10 else 280
        return QSize(total_width, self.height_for_column_width(total_width))

    def minimumSizeHint(self) -> QSize:
        width = self.width() if self.width() > 10 else 280
        return QSize(width, self.height_for_column_width(width))


class VariablesCellWidget(QWidget):
    def __init__(self, before: str, after: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._before = before
        self._after = after
        self._stacked = self._should_use_stacked_layout()

        self._before_label = QLabel(before)
        self._before_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._before_label.setWordWrap(True)
        self._before_label.setStyleSheet(BEFORE_BORDER_STYLE)

        self._after_label = QLabel(after)
        self._after_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._after_label.setWordWrap(True)
        self._after_label.setStyleSheet(AFTER_BORDER_STYLE)

        self._build_layout()

    def _should_use_stacked_layout(self) -> bool:
        for line in (self._before + "\n" + self._after).split("\n"):
            if len(line) > LONG_VARIABLE_NAME_THRESHOLD:
                return True
        return False

    def _build_layout(self) -> None:
        old_layout = self.layout()
        if old_layout is not None:
            while old_layout.count():
                item = old_layout.takeAt(0)
                if item.widget() is not None:
                    item.widget().setParent(None)

        if self._stacked:
            layout = QVBoxLayout(self)
            layout.setContentsMargins(
                VARIABLES_CELL_PADDING_H,
                VARIABLES_CELL_PADDING_V,
                VARIABLES_CELL_PADDING_H,
                VARIABLES_CELL_PADDING_V,
            )
            layout.setSpacing(6)

            divider = QFrame()
            divider.setFrameShape(QFrame.Shape.HLine)
            divider.setFrameShadow(QFrame.Shadow.Sunken)
            divider.setLineWidth(1)

            layout.addWidget(self._before_label)
            layout.addWidget(divider)
            layout.addWidget(self._after_label)
        else:
            layout = QHBoxLayout(self)
            layout.setContentsMargins(
                VARIABLES_CELL_PADDING_H,
                VARIABLES_CELL_PADDING_V,
                VARIABLES_CELL_PADDING_H,
                VARIABLES_CELL_PADDING_V,
            )
            layout.setSpacing(6)

            divider = QFrame()
            divider.setFrameShape(QFrame.Shape.VLine)
            divider.setFrameShadow(QFrame.Shadow.Sunken)
            divider.setLineWidth(1)

            layout.addWidget(self._before_label, stretch=1)
            layout.addWidget(divider)
            layout.addWidget(self._after_label, stretch=1)

        tooltip = f"Current:\n{self._before}\n\nCorrect:\n{self._after}"
        self.setToolTip(tooltip)
        self._before_label.setToolTip(tooltip)
        self._after_label.setToolTip(tooltip)

    def _text_block_height(self, text: str, width: int) -> int:
        if width < 20:
            width = 80
        metrics = QFontMetrics(self.font())
        line_height = metrics.height()
        lines = text.split("\n") if text else [""]
        wrapped_lines = 0
        for line in lines:
            if not line:
                wrapped_lines += 1
                continue
            rect = metrics.boundingRect(0, 0, width, 0, int(Qt.TextFlag.TextSingleLine), line)
            wrapped_lines += max(1, (rect.width() + width - 1) // width)
        return wrapped_lines * line_height

    def _column_text_width(self, total_width: int) -> int:
        # margins + spacing + divider
        inner = total_width - 2 * VARIABLES_CELL_PADDING_H - 6 - 2
        return max(20, inner // 2)

    def _full_text_width(self, total_width: int) -> int:
        return max(20, total_width - 2 * VARIABLES_CELL_PADDING_H)

    def height_for_column_width(self, width: int) -> int:
        if self._stacked:
            text_width = self._full_text_width(width)
            text_height = (
                self._text_block_height(self._before, text_width)
                + self._text_block_height(self._after, text_width)
                + 2 * LABEL_BORDER_EXTRA
                + STACKED_LAYOUT_EXTRA_HEIGHT
            )
        else:
            text_width = self._column_text_width(width)
            text_height = max(
                self._text_block_height(self._before, text_width),
                self._text_block_height(self._after, text_width),
            ) + LABEL_BORDER_EXTRA
        return text_height + 2 * VARIABLES_CELL_PADDING_V + 4

    def sizeHint(self) -> QSize:
        total_width = self.width() if self.width() > 10 else 280
        return QSize(total_width, self.height_for_column_width(total_width))

    def minimumSizeHint(self) -> QSize:
        width = self.width() if self.width() > 10 else 280
        return QSize(width, self.height_for_column_width(width))
