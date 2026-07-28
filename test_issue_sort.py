from analyzer.initializer_order_checker import sort_issues
from models.class_info import ConstructorInfo
from models.issue import Confidence, Issue


def _make_issue(
    *,
    class_name: str,
    source_path: str,
    line: int,
    has_order_mismatch: bool,
    uninitialized: list[str] | None = None,
) -> Issue:
    return Issue(
        class_name=class_name,
        constructor_name=class_name,
        header_path=f"include/{class_name}.hpp",
        source_path=source_path,
        line=line,
        declared_order=["a", "b"],
        current_order=["b", "a"] if has_order_mismatch else [],
        suggested_order=["a", "b"],
        original_snippet="",
        fixed_snippet="",
        constructor_info=ConstructorInfo(
            qualified_class_name=class_name,
            constructor_name=class_name,
            source_path=source_path,
            line=line,
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


def test_sort_issues_order_mismatch_before_uninitialized() -> None:
    issues = [
        _make_issue(
            class_name="UninitOnly",
            source_path="src/a.cpp",
            line=5,
            has_order_mismatch=False,
            uninitialized=["x"],
        ),
        _make_issue(
            class_name="OrderMismatch",
            source_path="src/b.cpp",
            line=10,
            has_order_mismatch=True,
        ),
        _make_issue(
            class_name="BothProblems",
            source_path="src/c.cpp",
            line=15,
            has_order_mismatch=True,
            uninitialized=["y"],
        ),
    ]

    sorted_issues = sort_issues(issues)

    assert [issue.class_name for issue in sorted_issues] == [
        "OrderMismatch",
        "BothProblems",
        "UninitOnly",
    ]


if __name__ == "__main__":
    test_sort_issues_order_mismatch_before_uninitialized()
    print("OK")
