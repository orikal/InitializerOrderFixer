from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont, QIcon
from PySide6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from fixer.initializer_order_fixer import apply_fixes
from models.issue import Issue
from resources import logo_icon_path
from ui.folder_select_dialog import FolderSelectDialog
from ui.preview_dialog import PreviewDialog
from ui.scan_worker import ScanWorker
from ui.variables_cell import FilesCellWidget, VariablesCellWidget, WordWrapDelegate, CELL_PADDING_H, CELL_PADDING_V


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Initializer Order Fixer")
        self.resize(1100, 700)
        icon_path = logo_icon_path()
        if icon_path.is_file():
            self.setWindowIcon(QIcon(str(icon_path)))

        self._issues: list[Issue] = []
        self._worker: ScanWorker | None = None
        self._selected_dirs: list[str] = []
        self._all_selected = True

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        path_row = QHBoxLayout()
        self._path_edit = QLineEdit()
        self._path_edit.setPlaceholderText("Select repository folder...")
        self._path_edit.textChanged.connect(self._on_path_changed)
        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self._browse)
        self._folders_btn = QPushButton("Select Folders...")
        self._folders_btn.setEnabled(False)
        self._folders_btn.clicked.connect(self._select_folders)
        path_row.addWidget(self._heading_label("Repository:"))
        path_row.addWidget(self._path_edit, stretch=1)
        path_row.addWidget(browse_btn)
        path_row.addWidget(self._folders_btn)
        layout.addLayout(path_row)

        action_row = QHBoxLayout()
        self._scan_btn = QPushButton("Scan Repository")
        self._scan_btn.clicked.connect(self._start_scan)
        self._apply_selected_btn = QPushButton("Apply Selected Fixes")
        self._apply_selected_btn.clicked.connect(lambda: self._apply_fixes(selected_only=True))
        self._apply_all_btn = QPushButton("Apply All Fixes")
        self._apply_all_btn.clicked.connect(lambda: self._apply_fixes(selected_only=False))
        self._apply_selected_btn.setEnabled(False)
        self._apply_all_btn.setEnabled(False)
        action_row.addWidget(self._scan_btn)
        action_row.addStretch()
        action_row.addWidget(self._apply_selected_btn)
        action_row.addWidget(self._apply_all_btn)
        layout.addLayout(action_row)

        progress_group = QGroupBox("Scan Progress")
        progress_group.setStyleSheet("QGroupBox::title { font-weight: bold; }")
        progress_layout = QVBoxLayout(progress_group)
        self._progress_bar = QProgressBar()
        self._current_file_label = QLabel("Ready.")
        self._stats_label = QLabel("Files: 0/0 | Issues: 0")
        progress_layout.addWidget(self._progress_bar)
        progress_layout.addWidget(self._current_file_label)
        progress_layout.addWidget(self._stats_label)
        layout.addWidget(progress_group)

        self._table = QTableWidget(0, 5)
        self._table.setHorizontalHeaderLabels(["", "Class", "Files", "Line", "Variables"])
        self._table.setWordWrap(True)
        self._table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._table.setTextElideMode(Qt.TextElideMode.ElideNone)
        self._table.setItemDelegate(WordWrapDelegate(self._table))
        self._table.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self._table.verticalHeader().setMinimumSectionSize(32)
        self._table.verticalHeader().setDefaultSectionSize(40)
        header = self._table.horizontalHeader()
        header.setStyleSheet("QHeaderView::section { font-weight: bold; }")
        header.setDefaultAlignment(Qt.AlignmentFlag.AlignCenter)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        header.setStretchLastSection(True)
        header.setMinimumSectionSize(40)
        self._table.setColumnWidth(0, 40)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.cellDoubleClicked.connect(self._show_preview)
        layout.addWidget(self._table, stretch=1)

        self._updating_header_checkbox = False
        self._setup_select_header()
        header.sectionResized.connect(lambda *_: self._resize_table_rows())
        header.geometriesChanged.connect(self._update_select_header_geometry)

    @staticmethod
    def _heading_label(text: str) -> QLabel:
        label = QLabel(text)
        font = QFont(label.font())
        font.setBold(True)
        label.setFont(font)
        return label

    def resizeEvent(self, event) -> None:  # noqa: ANN001 — Qt API
        super().resizeEvent(event)
        if self._table.rowCount() > 0:
            QTimer.singleShot(0, self._resize_table_rows)

    def _resize_table_rows(self) -> None:
        if self._table.rowCount() == 0:
            return

        from PySide6.QtWidgets import QStyleOptionViewItem

        delegate = self._table.itemDelegate()
        for row in range(self._table.rowCount()):
            max_height = self._table.verticalHeader().minimumSectionSize()

            for col in (1, 3):
                item = self._table.item(row, col)
                if item is None:
                    continue
                col_width = self._table.columnWidth(col)
                index = self._table.model().index(row, col)
                option = QStyleOptionViewItem()
                option.rect = self._table.visualRect(index)
                option.rect.setWidth(max(col_width, 20))
                hint = delegate.sizeHint(option, index)
                max_height = max(max_height, hint.height())

            for col in (0, 2, 4):
                widget = self._table.cellWidget(row, col)
                if widget is None:
                    continue
                if col in (2, 4) and isinstance(widget, (FilesCellWidget, VariablesCellWidget)):
                    col_width = self._table.columnWidth(col)
                    max_height = max(max_height, widget.height_for_column_width(col_width))
                else:
                    widget.updateGeometry()
                    max_height = max(max_height, widget.sizeHint().height())

            self._table.setRowHeight(row, max_height + 4)

        self._update_select_header_geometry()

    def _on_path_changed(self) -> None:
        repo = self._path_edit.text().strip()
        valid = bool(repo) and Path(repo).is_dir()
        self._folders_btn.setEnabled(valid)
        if valid:
            self._selected_dirs = [str(Path(repo).resolve())]
        else:
            self._selected_dirs = []

    def _browse(self) -> None:
        directory = QFileDialog.getExistingDirectory(self, "Select Repository")
        if directory:
            self._path_edit.setText(directory)
            self._select_folders()

    def _select_folders(self) -> None:
        repo = self._path_edit.text().strip()
        if not repo or not Path(repo).is_dir():
            return
        dialog = FolderSelectDialog(
            Path(repo),
            selected_dirs=set(self._selected_dirs) if self._selected_dirs else None,
            parent=self,
        )
        if dialog.exec():
            self._selected_dirs = dialog.selected_directories()
            if not self._selected_dirs:
                QMessageBox.warning(self, "No Folders", "Please select at least one folder to scan.")
                self._selected_dirs = [str(Path(repo).resolve())]

    def _set_scanning(self, scanning: bool) -> None:
        self._scan_btn.setEnabled(not scanning)
        self._apply_selected_btn.setEnabled(not scanning and bool(self._issues))
        self._apply_all_btn.setEnabled(not scanning and bool(self._issues))
        if hasattr(self, "_header_select_checkbox") and self._issues:
            self._header_select_checkbox.setEnabled(not scanning)
        self._path_edit.setEnabled(not scanning)
        self._folders_btn.setEnabled(not scanning and bool(self._path_edit.text().strip()))

    def _start_scan(self) -> None:
        repo = self._path_edit.text().strip()
        if not repo:
            QMessageBox.warning(self, "Missing Path", "Please select a repository folder.")
            return
        if not Path(repo).is_dir():
            QMessageBox.warning(self, "Invalid Path", f"Not a directory: {repo}")
            return
        if not self._selected_dirs:
            QMessageBox.warning(self, "No Folders", "Please select at least one folder to scan.")
            return

        self._set_scanning(True)
        self._progress_bar.setValue(0)
        self._current_file_label.setText("Starting scan...")
        self._stats_label.setText("Files: 0/0 | Issues: 0")
        self._table.setRowCount(0)
        self._issues = []
        self._update_select_header_visibility()

        self._worker = ScanWorker(repo, self._selected_dirs, self)
        self._worker.progress.connect(self._on_progress)
        self._worker.finished_scan.connect(self._on_scan_finished)
        self._worker.error.connect(self._on_scan_error)
        self._worker.start()

    def _on_progress(self, done: int, total: int, current: str, issue_count: int) -> None:
        if total > 0:
            self._progress_bar.setMaximum(total)
            self._progress_bar.setValue(done)
        name = Path(current).name if current else "—"
        self._current_file_label.setText(f"Scanning: {name}" if current else "Finalizing...")
        self._stats_label.setText(f"Files: {done}/{total} | Issues: {issue_count}")

    def _on_scan_finished(self, issues: list) -> None:
        self._issues = issues
        self._all_selected = True
        self._populate_table()
        self._update_select_header_visibility()
        if self._issues:
            self._update_header_checkbox_state()
        self._set_scanning(False)
        self._current_file_label.setText(f"Scan complete. Found {len(issues)} issue(s).")
        self._stats_label.setText(
            f"Files: {self._progress_bar.maximum()}/{self._progress_bar.maximum()} | Issues: {len(issues)}"
        )

    def _on_scan_error(self, message: str) -> None:
        self._set_scanning(False)
        QMessageBox.critical(self, "Scan Error", message)

    def _files_cell_widget(self, issue: Issue) -> FilesCellWidget:
        return FilesCellWidget(
            self._rel_path(issue.header_path),
            self._rel_path(issue.source_path),
        )

    def _variables_cell_widget(self, issue: Issue) -> VariablesCellWidget:
        return VariablesCellWidget(issue.current_order_str, issue.correct_order_str)

    def _setup_select_header(self) -> None:
        self._select_header_widget = QWidget(self._table)

        self._header_select_checkbox = QCheckBox(self._select_header_widget)
        self._header_select_checkbox.setTristate(True)
        self._header_select_checkbox.setChecked(True)
        self._header_select_checkbox.stateChanged.connect(self._on_header_select_all)
        self._header_select_checkbox.setStyleSheet(
            "QCheckBox { spacing: 0px; margin: 0px; padding: 0px; }"
        )

        self._select_header_widget.hide()

    def _update_select_header_visibility(self) -> None:
        has_issues = bool(self._issues)
        if has_issues:
            self._table.setHorizontalHeaderLabels(["", "Class", "Files", "Line", "Variables"])
            self._update_select_header_geometry()
            self._select_header_widget.show()
            self._select_header_widget.raise_()
        else:
            self._select_header_widget.hide()
            self._table.setHorizontalHeaderLabels(["", "Class", "Files", "Line", "Variables"])

    def _update_select_header_geometry(self) -> None:
        if not hasattr(self, "_select_header_widget") or not self._issues:
            return
        header = self._table.horizontalHeader()
        header_top_left = header.mapTo(self._table, header.rect().topLeft())
        x = header_top_left.x() + header.sectionViewportPosition(0)
        y = header_top_left.y()
        width = header.sectionSize(0)
        height = header.height()
        self._select_header_widget.setGeometry(x, y, width, height)

        self._header_select_checkbox.adjustSize()
        checkbox_width = self._header_select_checkbox.sizeHint().width()
        checkbox_height = self._header_select_checkbox.sizeHint().height()
        self._header_select_checkbox.setGeometry(
            max(0, (width - checkbox_width) // 2),
            max(0, (height - checkbox_height) // 2),
            checkbox_width,
            checkbox_height,
        )

    def _centered_checkbox(self, checkbox: QCheckBox) -> QWidget:
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.addWidget(checkbox)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setContentsMargins(CELL_PADDING_H, CELL_PADDING_V, CELL_PADDING_H, CELL_PADDING_V)
        layout.setSpacing(0)
        return container

    def _checkbox_from_cell(self, row: int) -> QCheckBox | None:
        widget = self._table.cellWidget(row, 0)
        if widget is None:
            return None
        if isinstance(widget, QCheckBox):
            return widget
        checkbox = widget.findChild(QCheckBox)
        return checkbox if isinstance(checkbox, QCheckBox) else None

    def _table_item(self, text: str) -> QTableWidgetItem:
        item = QTableWidgetItem(text)
        item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        return item

    def _populate_table(self) -> None:
        self._table.setRowCount(len(self._issues))
        for row, issue in enumerate(self._issues):
            checkbox = QCheckBox()
            checkbox.setChecked(issue.selected)
            checkbox.stateChanged.connect(
                lambda state, r=row: self._on_row_checkbox_changed(r, state == Qt.CheckState.Checked.value)
            )

            self._table.setCellWidget(row, 0, self._centered_checkbox(checkbox))
            self._table.setItem(row, 1, self._table_item(issue.class_name))
            self._table.setCellWidget(row, 2, self._files_cell_widget(issue))
            self._table.setItem(row, 3, self._table_item(str(issue.line)))
            self._table.setCellWidget(row, 4, self._variables_cell_widget(issue))

        QTimer.singleShot(0, self._resize_table_rows)
        if self._issues:
            self._update_select_header_geometry()

    def _on_row_checkbox_changed(self, row: int, checked: bool) -> None:
        self._toggle_issue(row, checked)
        self._update_header_checkbox_state()

    def _toggle_issue(self, row: int, checked: bool) -> None:
        if 0 <= row < len(self._issues):
            self._issues[row].selected = checked

    def _update_header_checkbox_state(self) -> None:
        if not hasattr(self, "_header_select_checkbox") or not self._issues:
            return
        total = len(self._issues)
        selected_count = sum(1 for issue in self._issues if issue.selected)
        self._updating_header_checkbox = True
        if total == 0 or selected_count == 0:
            self._header_select_checkbox.setCheckState(Qt.CheckState.Unchecked)
            self._all_selected = False
        elif selected_count == total:
            self._header_select_checkbox.setCheckState(Qt.CheckState.Checked)
            self._all_selected = True
        else:
            self._header_select_checkbox.setCheckState(Qt.CheckState.PartiallyChecked)
        self._updating_header_checkbox = False

    def _on_header_select_all(self, state: int) -> None:
        if self._updating_header_checkbox:
            return
        selected = state != Qt.CheckState.Unchecked.value
        self._all_selected = selected
        for row in range(self._table.rowCount()):
            checkbox = self._checkbox_from_cell(row)
            if checkbox is not None:
                checkbox.blockSignals(True)
                checkbox.setChecked(selected)
                checkbox.blockSignals(False)
        for issue in self._issues:
            issue.selected = selected
        self._update_header_checkbox_state()

    def _rel_path(self, path: str) -> str:
        repo = self._path_edit.text().strip()
        try:
            return str(Path(path).relative_to(Path(repo)))
        except ValueError:
            return path

    def _show_preview(self, row: int, _column: int) -> None:
        if 0 <= row < len(self._issues):
            dialog = PreviewDialog(self._issues[row], self)
            dialog.exec()

    def _apply_fixes(self, selected_only: bool) -> None:
        if not self._issues:
            return

        if selected_only:
            targets = [i for i in self._issues if i.selected]
        else:
            targets = list(self._issues)
            for issue in targets:
                issue.selected = True

        if not targets:
            QMessageBox.information(self, "No Selection", "No issues selected for fixing.")
            return

        files = {i.source_path for i in targets}
        reply = QMessageBox.question(
            self,
            "Confirm Fixes",
            f"Apply fixes to {len(targets)} issue(s) in {len(files)} file(s)?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        result = apply_fixes(targets)
        if result.failed:
            details = "\n".join(f"{path}: {reason}" for path, reason in result.failed)
            QMessageBox.warning(
                self,
                "Partial Failure",
                f"Fixed {result.success_count} issue(s).\n\nFailures:\n{details}",
            )
        else:
            QMessageBox.information(
                self,
                "Success",
                f"Successfully applied {result.success_count} fix(es). Rescanning...",
            )

        self._start_scan()
