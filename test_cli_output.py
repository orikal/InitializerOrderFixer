from pathlib import Path

from cli import format_scan_table, format_variables
from models.issue import Confidence, Issue
from models.class_info import ConstructorInfo


def _make_issue(
    *,
    current_order: list[str],
    suggested_order: list[str],
    uninitialized: list[str] | None = None,
    has_order_mismatch: bool = True,
) -> Issue:
    return Issue(
        class_name="Example",
        constructor_name="Example",
        header_path="include/Example.hpp",
        source_path="src/example.cpp",
        line=10,
        declared_order=suggested_order,
        current_order=current_order,
        suggested_order=suggested_order,
        original_snippet="",
        fixed_snippet="",
        constructor_info=ConstructorInfo(
            qualified_class_name="Example",
            constructor_name="Example",
            source_path="src/example.cpp",
            line=10,
            start_byte=0,
            entries=[],
            list_start_byte=0,
            list_end_byte=0,
            full_source="",
        ),
        uninitialized_members=uninitialized or [],
        has_order_mismatch=has_order_mismatch,
        confidence=Confidence.HIGH,
    )


def test_format_variables_order_mismatch() -> None:
    issue = _make_issue(current_order=["second", "first"], suggested_order=["first", "second"])
    assert format_variables(issue) == "second, first -> first, second"


def test_format_scan_table() -> None:
    repo = Path("C:/repo")
    issues = [
        _make_issue(current_order=["b", "a"], suggested_order=["a", "b"]),
    ]
    output = format_scan_table(issues, Path("C:/repo/src/example.cpp").parent.parent)
    assert output.splitlines()[0] == "Filename | Line number | Variables"
    assert "src/example.cpp | 10 | b, a -> a, b" in output
