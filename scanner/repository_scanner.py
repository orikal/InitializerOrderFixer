from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from analyzer.initializer_order_checker import check_all
from models.issue import Issue
from scanner.constructor_parser import parse_source_file
from scanner.header_parser import parse_header_file

SOURCE_EXTENSIONS = {".cpp", ".c", ".h", ".hpp"}
HEADER_EXTENSIONS = {".h", ".hpp"}
SKIP_DIRS = {
    ".git",
    "build",
    "build-coverage",
    "cmake-build-debug",
    "cmake-build-release",
    "node_modules",
    "__pycache__",
    ".venv",
    "venv",
    "_deps",
    "third_party",
    "vendor",
    "external",
}


def _is_in_selected_dirs(file_path: Path, repo_path: Path, selected_dirs: list[Path] | None) -> bool:
    if not selected_dirs:
        return True
    resolved = file_path.resolve()
    for directory in selected_dirs:
        dir_resolved = directory.resolve()
        if resolved == dir_resolved:
            return True
        try:
            resolved.relative_to(dir_resolved)
            return True
        except ValueError:
            continue
    return False


def _skip_dir_names(exclude_dirs: set[str] | None = None) -> set[str]:
    return SKIP_DIRS | (exclude_dirs or set())


def _is_excluded_path(path: Path, exclude_dirs: set[str] | None = None) -> bool:
    skip = _skip_dir_names(exclude_dirs)
    return any(part in skip for part in path.parts)


def collect_source_files(
    repo_path: Path,
    selected_dirs: list[Path] | None = None,
    exclude_dirs: set[str] | None = None,
) -> list[Path]:
    files: list[Path] = []
    for path in repo_path.rglob("*"):
        if not path.is_file():
            continue
        if _is_excluded_path(path, exclude_dirs):
            continue
        if path.suffix.lower() not in SOURCE_EXTENSIONS:
            continue
        if not _is_in_selected_dirs(path, repo_path, selected_dirs):
            continue
        files.append(path)
    return sorted(files)


def scan_repository(
    repo_path: Path,
    progress_callback: Callable[[int, int, str, int], None] | None = None,
    selected_dirs: list[Path] | None = None,
    exclude_dirs: set[str] | None = None,
) -> list[Issue]:
    repo_path = repo_path.resolve()
    all_repo_files = collect_source_files(repo_path, selected_dirs=None, exclude_dirs=exclude_dirs)
    scanned_files = collect_source_files(repo_path, selected_dirs, exclude_dirs=exclude_dirs)
    total = len(scanned_files)
    if total == 0 and not all_repo_files:
        return []

    header_files = [f for f in all_repo_files if f.suffix.lower() in HEADER_EXTENSIONS]
    classes: dict = {}
    for idx, header in enumerate(header_files):
        if progress_callback:
            progress_callback(idx, max(total, 1), str(header), 0)
        classes.update(parse_header_file(header))

    issues: list[Issue] = []
    for idx, source_file in enumerate(scanned_files):
        if progress_callback:
            progress_callback(idx, total, str(source_file), len(issues))
        constructors = parse_source_file(source_file)
        issues.extend(check_all(constructors, classes))

    if progress_callback:
        progress_callback(total, total, "", len(issues))

    return issues
