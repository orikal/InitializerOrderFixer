from pathlib import Path
from tempfile import TemporaryDirectory

from scanner.repository_scanner import scan_repository


def test_uninitialized_member_detected() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "include").mkdir()
        (root / "src").mkdir()
        (root / "include" / "Foo.hpp").write_text(
            """class Foo {
    int first;
    int second;
    int third;
};
""",
            encoding="utf-8",
        )
        (root / "src" / "Foo.cpp").write_text(
            """#include "../include/Foo.hpp"

Foo::Foo() : second(2), first(1) {}
""",
            encoding="utf-8",
        )
        issues = scan_repository(root)
        assert len(issues) == 1
        assert issues[0].uninitialized_members == ["third"]
        assert issues[0].has_order_mismatch is True


def test_default_member_initializer_excluded() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "include").mkdir()
        (root / "src").mkdir()
        (root / "include" / "Foo.hpp").write_text(
            """class Foo {
    int first;
    int second = 0;
    int third;
};
""",
            encoding="utf-8",
        )
        (root / "src" / "Foo.cpp").write_text(
            """#include "../include/Foo.hpp"

Foo::Foo() : second(2), first(1) {}
""",
            encoding="utf-8",
        )
        issues = scan_repository(root)
        assert len(issues) == 1
        assert issues[0].uninitialized_members == ["third"]
        assert issues[0].header_initialized_members == ["second"]


def test_uninitialized_with_correct_order() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "include").mkdir()
        (root / "src").mkdir()
        (root / "include" / "Foo.hpp").write_text(
            """class Foo {
    int first;
    int second;
    int third;
};
""",
            encoding="utf-8",
        )
        (root / "src" / "Foo.cpp").write_text(
            """#include "../include/Foo.hpp"

Foo::Foo() : first(1), second(2) {}
""",
            encoding="utf-8",
        )
        issues = scan_repository(root)
        assert len(issues) == 1
        assert issues[0].uninitialized_members == ["third"]
        assert issues[0].has_order_mismatch is False
        assert issues[0].selected is False


def test_uninitialized_without_initializer_list() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "include").mkdir()
        (root / "src").mkdir()
        (root / "include" / "Foo.hpp").write_text(
            """class Foo {
    int first;
    int second;
};
""",
            encoding="utf-8",
        )
        (root / "src" / "Foo.cpp").write_text(
            """#include "../include/Foo.hpp"

Foo::Foo() {}
""",
            encoding="utf-8",
        )
        issues = scan_repository(root)
        assert len(issues) == 1
        assert issues[0].uninitialized_members == ["first", "second"]
        assert issues[0].has_order_mismatch is False


if __name__ == "__main__":
    test_uninitialized_member_detected()
    test_default_member_initializer_excluded()
    test_uninitialized_with_correct_order()
    test_uninitialized_without_initializer_list()
    print("All tests passed.")
