from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QThread, Signal

from models.issue import Issue
from scanner.repository_scanner import scan_repository


class ScanWorker(QThread):
    progress = Signal(int, int, str, int)
    finished_scan = Signal(list)
    error = Signal(str)

    def __init__(
        self,
        repo_path: str,
        selected_dirs: list[str] | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._repo_path = repo_path
        self._selected_dirs = selected_dirs or []

    def run(self) -> None:
        try:
            path = Path(self._repo_path)
            if not path.is_dir():
                self.error.emit(f"Invalid repository path: {self._repo_path}")
                return

            dir_paths = [Path(d) for d in self._selected_dirs] if self._selected_dirs else None

            def callback(done: int, total: int, current: str, issue_count: int) -> None:
                self.progress.emit(done, total, current, issue_count)

            issues = scan_repository(path, progress_callback=callback, selected_dirs=dir_paths)
            self.finished_scan.emit(issues)
        except Exception as exc:  # noqa: BLE001
            self.error.emit(str(exc))
