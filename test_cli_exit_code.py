from pathlib import Path
from tempfile import TemporaryDirectory

from cli import ci_blocking_issues, cli_main
from models.class_info import ConstructorInfo
from models.issue import Confidence, Issue


def _make_issue(*, has_order_mismatch: bool, uninitialized: list[str] | None = None) -> Issue:
    return Issue(
        class_name="Example",
        constructor_name="Example",
        header_path="include/Example.hpp",
        source_path="src/example.cpp",
        line=10,
        declared_order=["a", "b"],
        current_order=["b", "a"] if has_order_mismatch else [],
        suggested_order=["a", "b"],
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


def test_ci_blocking_issues_only_order_mismatch() -> None:
    order_issue = _make_issue(has_order_mismatch=True)
    uninit_issue = _make_issue(has_order_mismatch=False, uninitialized=["x"])
    blocking = ci_blocking_issues([order_issue, uninit_issue])
    assert blocking == [order_issue]


def test_cli_scan_exits_zero_for_uninitialized_only(tmp_path: Path) -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "include").mkdir()
        (root / "src").mkdir()
        (root / "include" / "Foo.hpp").write_text(
            """class Foo {
    int first;
    int second;
    Foo();
};
""",
            encoding="utf-8",
        )
        (root / "src" / "Foo.cpp").write_text(
            """#include "../include/Foo.hpp"

Foo::Foo()
{
}
""",
            encoding="utf-8",
        )

        code = cli_main(["--no-ui", "--path", str(root), "--action", "scan"])
        assert code == 0


def test_cli_scan_exits_one_for_order_mismatch(tmp_path: Path) -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "include").mkdir()
        (root / "src").mkdir()
        (root / "include" / "Foo.hpp").write_text(
            """class Foo {
    int first;
    int second;
    Foo();
};
""",
            encoding="utf-8",
        )
        (root / "src" / "Foo.cpp").write_text(
            """#include "../include/Foo.hpp"

Foo::Foo()
    : second(2),
      first(1)
{
}
""",
            encoding="utf-8",
        )

        code = cli_main(["--no-ui", "--path", str(root), "--action", "scan"])
        assert code == 1
