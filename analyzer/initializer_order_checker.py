from __future__ import annotations

from models.class_info import ClassInfo, ConstructorInfo, InitializerEntry
from models.issue import Confidence, Issue

SNIPPET_CONTEXT_LINES = 1


def _members_that_move(current: list[str], suggested: list[str]) -> set[str]:
    current_subset = [m for m in current if m in suggested]
    suggested_subset = [m for m in suggested if m in current]
    moving: set[str] = set()
    for name in current_subset:
        if current_subset.index(name) != suggested_subset.index(name):
            moving.add(name)
    return moving


def _line_start(source: str, byte_offset: int) -> int:
    prev = source.rfind("\n", 0, byte_offset)
    return 0 if prev == -1 else prev + 1


def _line_end(source: str, byte_offset: int) -> int:
    next_newline = source.find("\n", byte_offset)
    return len(source) if next_newline == -1 else next_newline + 1


def _expand_lines(source: str, start: int, end: int, before: int, after: int) -> tuple[int, int]:
    for _ in range(before):
        if start == 0:
            break
        prev = source.rfind("\n", 0, start - 1)
        if prev == -1:
            start = 0
            break
        start = prev + 1

    for _ in range(after):
        next_newline = source.find("\n", end)
        if next_newline == -1:
            end = len(source)
            break
        end = next_newline + 1

    return start, end


def _change_snippet_bounds(
    source: str,
    ctor: ConstructorInfo,
    moving: set[str],
    context_lines: int = SNIPPET_CONTEXT_LINES,
) -> tuple[int, int]:
    entries = [e for e in ctor.entries if e.member_name in moving]
    if not entries:
        entries = [e for e in ctor.entries if e.member_name and not e.is_base_or_unknown]
    if not entries:
        core_start = _line_start(source, ctor.start_byte)
        end = source.find("}", ctor.list_end_byte)
        end = min(len(source), ctor.list_end_byte + 200) if end == -1 else end + 1
        return _expand_lines(source, core_start, end, context_lines, context_lines)

    first = min(entries, key=lambda e: e.start_byte)
    last = max(entries, key=lambda e: e.end_byte)
    change_start = _line_start(source, first.start_byte)
    change_end = _line_end(source, last.end_byte)
    return _expand_lines(source, change_start, change_end, context_lines, context_lines)


def snippet_start_byte(
    source: str,
    ctor: ConstructorInfo,
    moving: set[str],
    context_lines: int = SNIPPET_CONTEXT_LINES,
) -> int:
    return _change_snippet_bounds(source, ctor, moving, context_lines)[0]


def _resolve_class(
    ctor: ConstructorInfo,
    classes: dict[str, ClassInfo],
) -> ClassInfo | None:
    if ctor.qualified_class_name in classes:
        return classes[ctor.qualified_class_name]

    simple = ctor.qualified_class_name.split("::")[-1]
    matches = [c for c in classes.values() if c.simple_name == simple]
    if len(matches) == 1:
        return matches[0]
    return None


def _member_names_in_init(entries: list[InitializerEntry]) -> list[str]:
    return [e.member_name for e in entries if e.member_name and not e.is_base_or_unknown]


def _reorder_entries(
    entries: list[InitializerEntry],
    declared_order: list[str],
) -> list[InitializerEntry]:
    declared_set = set(declared_order)
    known = [e for e in entries if e.member_name in declared_set and not e.is_base_or_unknown]
    unknown = [e for e in entries if e.member_name not in declared_set or e.is_base_or_unknown]

    if not known:
        return entries

    order_index = {name: i for i, name in enumerate(declared_order)}
    sorted_known = sorted(known, key=lambda e: order_index.get(e.member_name, len(declared_order)))

    # Preserve relative positions of unknown/base entries among themselves,
    # inserting known members in declared order as a block where known members appeared.
    first_known_idx = min(entries.index(e) for e in known)
    last_known_idx = max(entries.index(e) for e in known)

    prefix = [e for e in entries[:first_known_idx] if e in unknown]
    suffix = [e for e in entries[last_known_idx + 1 :] if e in unknown]
    middle_unknown = [e for e in unknown if e not in prefix and e not in suffix]

    return prefix + sorted_known + middle_unknown + suffix


def _build_list_text(
    entries: list[InitializerEntry],
    original_entries: list[InitializerEntry],
    original_list_body: str,
) -> str:
    if not entries:
        return ""

    multiline = "\n" in original_list_body
    if multiline:
        lines = original_list_body.split("\n")
        indent = "      "
        for line in lines[1:]:
            stripped = line.lstrip()
            if stripped and not stripped.startswith("//"):
                indent = line[: len(line) - len(stripped)]
                break

        parts = [entries[0].text]
        for entry in entries[1:]:
            parts.append(f",\n{indent}{entry.text.lstrip()}")
        return "".join(parts)

    if ", " in original_list_body:
        return ", ".join(e.text for e in entries)
    return ",".join(e.text for e in entries)


def _replace_initializer_list(source: str, ctor: ConstructorInfo, new_entries: list[InitializerEntry]) -> str:
    original_list = source[ctor.list_start_byte : ctor.list_end_byte]
    colon_idx = original_list.find(":")
    list_body = original_list[colon_idx + 1 :] if colon_idx >= 0 else original_list
    list_body_stripped = list_body.lstrip()
    leading_ws = list_body[: len(list_body) - len(list_body_stripped)]

    new_list_body = _build_list_text(new_entries, ctor.entries, list_body_stripped)
    before = source[: ctor.list_start_byte]
    after = source[ctor.list_end_byte :]

    if colon_idx >= 0:
        colon_part = original_list[: colon_idx + 1]
        return before + colon_part + leading_ws + new_list_body + after
    return before + new_list_body + after


def _extract_change_snippet(
    source: str,
    ctor: ConstructorInfo,
    moving: set[str],
    context_lines: int = SNIPPET_CONTEXT_LINES,
) -> str:
    start, end = _change_snippet_bounds(source, ctor, moving, context_lines)
    return source[start:end]


def check_constructor(
    ctor: ConstructorInfo,
    classes: dict[str, ClassInfo],
) -> Issue | None:
    class_info = _resolve_class(ctor, classes)
    if class_info is None:
        return None

    declared = class_info.instance_member_names
    if not declared:
        return None

    current = _member_names_in_init(ctor.entries)
    if len(current) < 2:
        return None

    declared_subset = [m for m in declared if m in current]
    if len(declared_subset) < 2:
        return None

    current_subset = [m for m in current if m in set(declared)]
    if current_subset == declared_subset:
        return None

    reordered = _reorder_entries(ctor.entries, declared)
    suggested = _member_names_in_init(reordered)
    moving = _members_that_move(current, suggested)

    fixed_source = _replace_initializer_list(ctor.full_source, ctor, reordered)
    fixed_ctor = ConstructorInfo(
        qualified_class_name=ctor.qualified_class_name,
        constructor_name=ctor.constructor_name,
        source_path=ctor.source_path,
        line=ctor.line,
        start_byte=ctor.start_byte,
        entries=reordered,
        list_start_byte=ctor.list_start_byte,
        list_end_byte=ctor.list_end_byte,
        full_source=fixed_source,
    )

    return Issue(
        class_name=class_info.qualified_name,
        constructor_name=ctor.constructor_name,
        header_path=class_info.header_path,
        source_path=ctor.source_path,
        line=ctor.line,
        declared_order=declared,
        current_order=current,
        suggested_order=suggested,
        original_snippet=_extract_change_snippet(ctor.full_source, ctor, moving),
        fixed_snippet=_extract_change_snippet(fixed_source, fixed_ctor, moving),
        constructor_info=ctor,
        confidence=Confidence.HIGH,
        selected=True,
    )


def check_all(
    constructors: list[ConstructorInfo],
    classes: dict[str, ClassInfo],
) -> list[Issue]:
    issues: list[Issue] = []
    for ctor in constructors:
        issue = check_constructor(ctor, classes)
        if issue:
            issues.append(issue)
    return issues
