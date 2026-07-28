from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from analyzer.initializer_order_checker import _replace_initializer_list, _reorder_entries
from models.issue import Issue


@dataclass
class FixResult:
    success_count: int
    failed: list[tuple[str, str]]


def _apply_single_issue(source: str, issue: Issue) -> str:
    ctor = issue.constructor_info
    class_declared = issue.declared_order
    reordered = _reorder_entries(ctor.entries, class_declared)
    return _replace_initializer_list(source, ctor, reordered)


def apply_fixes(issues: list[Issue]) -> FixResult:
    selected = [
        i
        for i in issues
        if i.selected and i.has_order_mismatch and i.confidence.value == "high"
    ]
    if not selected:
        return FixResult(success_count=0, failed=[])

    by_file: dict[str, list[Issue]] = {}
    for issue in selected:
        by_file.setdefault(issue.source_path, []).append(issue)

    success_count = 0
    failed: list[tuple[str, str]] = []

    for source_path, file_issues in by_file.items():
        path = Path(source_path)
        try:
            original = path.read_text(encoding="utf-8", errors="replace")
            modified = original

            # Apply from bottom to top so byte offsets remain valid.
            sorted_issues = sorted(
                file_issues,
                key=lambda i: i.constructor_info.list_start_byte,
                reverse=True,
            )
            for issue in sorted_issues:
                modified = _apply_single_issue(modified, issue)

            if modified == original:
                continue

            temp_path = path.with_suffix(path.suffix + ".tmp")
            temp_path.write_text(modified, encoding="utf-8", newline="")
            temp_path.replace(path)
            success_count += len(file_issues)
        except OSError as exc:
            failed.append((source_path, str(exc)))
        except Exception as exc:  # noqa: BLE001 — surface fix errors to UI
            failed.append((source_path, str(exc)))

    return FixResult(success_count=success_count, failed=failed)
