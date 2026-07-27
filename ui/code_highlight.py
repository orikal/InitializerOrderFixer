from __future__ import annotations

from PySide6.QtGui import QColor, QTextCharFormat, QTextCursor
from PySide6.QtWidgets import QPlainTextEdit, QTextEdit

from analyzer.initializer_order_checker import _members_that_move, _reorder_entries, snippet_start_byte
from models.issue import Issue


def _member_range_in_entry(entry_text: str, member_name: str, entry_start: int) -> tuple[int, int] | None:
    idx = entry_text.find(member_name)
    if idx < 0:
        return None
    return entry_start + idx, entry_start + idx + len(member_name)


def _original_member_ranges(issue: Issue, moving: set[str]) -> list[tuple[int, int]]:
    ctor = issue.constructor_info
    base = snippet_start_byte(ctor.full_source, ctor, moving)
    ranges: list[tuple[int, int]] = []
    for entry in ctor.entries:
        if entry.member_name not in moving:
            continue
        entry_start = entry.start_byte - base
        entry_text = issue.original_snippet[entry_start : entry.end_byte - base]
        member_range = _member_range_in_entry(entry_text, entry.member_name, entry_start)
        if member_range:
            ranges.append(member_range)
    return ranges


def _fixed_member_ranges(issue: Issue, moving: set[str]) -> list[tuple[int, int]]:
    reordered = _reorder_entries(issue.constructor_info.entries, issue.declared_order)
    ranges: list[tuple[int, int]] = []
    search_from = 0
    for entry in reordered:
        if entry.member_name not in moving:
            continue
        idx = issue.fixed_snippet.find(entry.text, search_from)
        if idx < 0:
            idx = issue.fixed_snippet.find(entry.text.strip(), search_from)
        if idx < 0:
            continue
        entry_text = issue.fixed_snippet[idx : idx + len(entry.text)]
        member_range = _member_range_in_entry(entry_text, entry.member_name, idx)
        if member_range:
            ranges.append(member_range)
        search_from = idx + len(entry.text)
    return ranges


def apply_highlight(
    editor: QPlainTextEdit,
    ranges: list[tuple[int, int]],
    background: QColor,
) -> None:
    fmt = QTextCharFormat()
    fmt.setBackground(background)
    selections: list[QTextEdit.ExtraSelection] = []
    for start, end in sorted(ranges):
        if start >= end:
            continue
        selection = QTextEdit.ExtraSelection()
        cursor = editor.textCursor()
        cursor.setPosition(start)
        cursor.setPosition(end, QTextCursor.MoveMode.KeepAnchor)
        selection.cursor = cursor
        selection.format = fmt
        selections.append(selection)
    editor.setExtraSelections(selections)


def highlight_issue(original_editor: QPlainTextEdit, fixed_editor: QPlainTextEdit, issue: Issue) -> None:
    moving = _members_that_move(issue.current_order, issue.suggested_order)
    if not moving:
        original_editor.setExtraSelections([])
        fixed_editor.setExtraSelections([])
        return

    apply_highlight(original_editor, _original_member_ranges(issue, moving), QColor("#fff0f0"))
    apply_highlight(fixed_editor, _fixed_member_ranges(issue, moving), QColor("#f0fff0"))
