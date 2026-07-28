from __future__ import annotations

import re
from collections.abc import Callable
from pathlib import Path

from analyzer.initializer_order_checker import check_all, sort_issues
from models.issue import Issue
from scanner.constructor_parser import parse_source_file
from scanner.header_parser import parse_header_file

CPP_EXTENSIONS = {".cpp", ".c"}
HEADER_EXTENSIONS = {".h", ".hpp"}
SOURCE_EXTENSIONS = CPP_EXTENSIONS | HEADER_EXTENSIONS
INCLUDE_QUOTED_RE = re.compile(r'#\s*include\s+"([^"]+)"')
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


def _collect_files(
    repo_path: Path,
    extensions: set[str],
    selected_dirs: list[Path] | None = None,
    exclude_dirs: set[str] | None = None,
) -> list[Path]:
    files: list[Path] = []
    for path in repo_path.rglob("*"):
        if not path.is_file():
            continue
        if _is_excluded_path(path, exclude_dirs):
            continue
        if path.suffix.lower() not in extensions:
            continue
        if not _is_in_selected_dirs(path, repo_path, selected_dirs):
            continue
        files.append(path)
    return sorted(files)


def collect_source_files(
    repo_path: Path,
    selected_dirs: list[Path] | None = None,
    exclude_dirs: set[str] | None = None,
) -> list[Path]:
    """Collect implementation files (.cpp / .c) to scan for constructors."""
    return _collect_files(repo_path, CPP_EXTENSIONS, selected_dirs, exclude_dirs)


def collect_header_files(
    repo_path: Path,
    exclude_dirs: set[str] | None = None,
) -> list[Path]:
    return _collect_files(repo_path, HEADER_EXTENSIONS, selected_dirs=None, exclude_dirs=exclude_dirs)


def _build_header_index(
    repo_path: Path,
    exclude_dirs: set[str] | None = None,
) -> dict[str, list[Path]]:
    index: dict[str, list[Path]] = {}
    for path in collect_header_files(repo_path, exclude_dirs):
        key = path.name.lower()
        index.setdefault(key, []).append(path)
    return index


def _extract_quoted_includes(cpp_path: Path) -> list[str]:
    try:
        text = cpp_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    return INCLUDE_QUOTED_RE.findall(text)


def _resolve_include(
    include: str,
    cpp_path: Path,
    repo_path: Path,
    header_index: dict[str, list[Path]],
) -> Path | None:
    relative_to_cpp = (cpp_path.parent / include).resolve()
    if relative_to_cpp.is_file():
        return relative_to_cpp

    relative_to_repo = (repo_path / include).resolve()
    if relative_to_repo.is_file():
        return relative_to_repo

    basename = Path(include).name.lower()
    matches = header_index.get(basename, [])
    if len(matches) == 1:
        return matches[0]

    include_normalized = include.replace("\\", "/").lower()
    suffix_matches = [
        candidate
        for candidate in matches
        if str(candidate).replace("\\", "/").lower().endswith(include_normalized)
    ]
    if len(suffix_matches) == 1:
        return suffix_matches[0]

    return None


def _guess_header_for_cpp(cpp_path: Path, header_index: dict[str, list[Path]]) -> Path | None:
    stem = cpp_path.stem.lower()
    candidates = [
        path
        for name, paths in header_index.items()
        for path in paths
        if Path(name).stem.lower() == stem
    ]
    if len(candidates) == 1:
        return candidates[0]
    return None


def headers_for_cpp(
    cpp_path: Path,
    repo_path: Path,
    header_index: dict[str, list[Path]],
) -> list[Path]:
    """Resolve header files referenced by a .cpp file via #include or matching stem."""
    seen: set[Path] = set()
    headers: list[Path] = []

    for include in _extract_quoted_includes(cpp_path):
        resolved = _resolve_include(include, cpp_path, repo_path, header_index)
        if resolved is not None and resolved not in seen:
            seen.add(resolved)
            headers.append(resolved)

    if not headers:
        guessed = _guess_header_for_cpp(cpp_path, header_index)
        if guessed is not None:
            headers.append(guessed)

    return headers


def scan_repository(
    repo_path: Path,
    progress_callback: Callable[[int, int, str, int], None] | None = None,
    selected_dirs: list[Path] | None = None,
    exclude_dirs: set[str] | None = None,
) -> list[Issue]:
    repo_path = repo_path.resolve()
    cpp_files = collect_source_files(repo_path, selected_dirs, exclude_dirs)
    total = len(cpp_files)
    if total == 0:
        return []

    header_index = _build_header_index(repo_path, exclude_dirs)
    issues: list[Issue] = []

    for idx, cpp_file in enumerate(cpp_files):
        if progress_callback:
            progress_callback(idx, total, str(cpp_file), len(issues))

        header_files = headers_for_cpp(cpp_file, repo_path, header_index)
        classes: dict = {}
        for header in header_files:
            classes.update(parse_header_file(header))

        constructors = parse_source_file(cpp_file)
        issues.extend(check_all(constructors, classes))

    if progress_callback:
        progress_callback(total, total, "", len(issues))

    return sort_issues(issues)
