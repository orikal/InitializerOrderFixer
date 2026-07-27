from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
)

from scanner.repository_scanner import SKIP_DIRS


class FolderSelectDialog(QDialog):
    def __init__(self, repo_path: Path, selected_dirs: set[str] | None = None, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Select Folders to Scan")
        self.resize(500, 450)

        self._repo_path = repo_path.resolve()
        self._selected_dirs: set[str] = set(selected_dirs or [])
        self._items_by_path: dict[str, QTreeWidgetItem] = {}

        info = QLabel(f"Repository: {self._repo_path}")
        info.setWordWrap(True)

        self._tree = QTreeWidget()
        self._tree.setHeaderHidden(True)
        self._tree.itemChanged.connect(self._on_item_changed)

        select_row = QHBoxLayout()
        select_all_btn = QPushButton("Select All")
        select_all_btn.clicked.connect(lambda: self._set_all(Qt.CheckState.Checked))
        select_none_btn = QPushButton("Select None")
        select_none_btn.clicked.connect(lambda: self._set_all(Qt.CheckState.Unchecked))
        select_row.addWidget(select_all_btn)
        select_row.addWidget(select_none_btn)
        select_row.addStretch()

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(info)
        layout.addLayout(select_row)
        layout.addWidget(self._tree)
        layout.addWidget(buttons)

        self._build_tree()

    def _should_skip(self, path: Path) -> bool:
        return any(part in SKIP_DIRS for part in path.parts)

    def _build_tree(self) -> None:
        self._tree.blockSignals(True)
        self._tree.clear()
        self._items_by_path.clear()

        root_item = self._create_item(self._repo_path, None)
        self._tree.addTopLevelItem(root_item)
        self._add_children(root_item, self._repo_path)
        root_item.setExpanded(True)
        self._sync_checked_ancestors(root_item)
        self._tree.blockSignals(False)

    def _is_path_checked(self, path_str: str) -> bool:
        root_str = str(self._repo_path)
        if not self._selected_dirs:
            return True
        if root_str in self._selected_dirs:
            return True
        if path_str in self._selected_dirs:
            return True
        path = Path(path_str)
        try:
            current = self._repo_path
            rel = path.relative_to(self._repo_path)
            for part in rel.parts:
                current = current / part
                if str(current) in self._selected_dirs:
                    return True
        except ValueError:
            pass
        return False

    def _sync_checked_ancestors(self, item: QTreeWidgetItem) -> None:
        if item.checkState(0) == Qt.CheckState.Checked:
            self._sync_descendants(item, Qt.CheckState.Checked)
        for i in range(item.childCount()):
            self._sync_checked_ancestors(item.child(i))

    def _create_item(self, path: Path, parent_item: QTreeWidgetItem | None) -> QTreeWidgetItem:
        rel = path.relative_to(self._repo_path)
        label = "ALL" if rel.parts == () else str(rel).replace("\\", "/")
        item = QTreeWidgetItem([label])
        item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
        path_str = str(path)
        checked = self._is_path_checked(path_str)
        item.setCheckState(0, Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked)
        item.setData(0, Qt.ItemDataRole.UserRole, path_str)
        self._items_by_path[path_str] = item
        if parent_item is not None:
            parent_item.addChild(item)
        return item

    def _add_children(self, parent_item: QTreeWidgetItem, parent_path: Path) -> None:
        try:
            children = sorted(
                [p for p in parent_path.iterdir() if p.is_dir() and not self._should_skip(p)],
                key=lambda p: p.name.lower(),
            )
        except OSError:
            return
        for child in children:
            child_item = self._create_item(child, parent_item)
            self._add_children(child_item, child)

    def _on_item_changed(self, item: QTreeWidgetItem, _column: int) -> None:
        if self._tree.signalsBlocked():
            return
        state = item.checkState(0)
        self._tree.blockSignals(True)
        self._sync_descendants(item, state)
        if state == Qt.CheckState.Unchecked:
            self._sync_ancestors_unchecked(item)
        self._tree.blockSignals(False)

    def _sync_ancestors_unchecked(self, item: QTreeWidgetItem) -> None:
        parent = item.parent()
        while parent is not None:
            parent.setCheckState(0, Qt.CheckState.Unchecked)
            parent = parent.parent()

    def _sync_descendants(self, item: QTreeWidgetItem, state: Qt.CheckState) -> None:
        for i in range(item.childCount()):
            self._set_child_state(item.child(i), state)

    def _set_child_state(self, item: QTreeWidgetItem, state: Qt.CheckState) -> None:
        item.setCheckState(0, state)
        for i in range(item.childCount()):
            self._set_child_state(item.child(i), state)

    def _set_all(self, state: Qt.CheckState) -> None:
        self._tree.blockSignals(True)
        for i in range(self._tree.topLevelItemCount()):
            top = self._tree.topLevelItem(i)
            top.setCheckState(0, state)
            self._sync_descendants(top, state)
        self._tree.blockSignals(False)

    def selected_directories(self) -> list[str]:
        selected: list[str] = []
        for path_str, item in self._items_by_path.items():
            if item.checkState(0) == Qt.CheckState.Checked:
                selected.append(path_str)
        return selected
