from pathlib import Path
from tempfile import TemporaryDirectory

from scanner.constructor_parser import parse_source_file
from scanner.repository_scanner import scan_repository


def test_inline_method_not_treated_as_constructor() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        header = root / "Foo.hpp"
        header.write_text(
            """class Foo {
    int value;
    void helper() {}
    Foo() {}
};
""",
            encoding="utf-8",
        )
        constructors = parse_source_file(header)
        ctor_names = {c.constructor_name for c in constructors}
        assert ctor_names == {"Foo"}
        assert "helper" not in ctor_names


def test_scan_does_not_flood_with_inline_methods() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "include").mkdir()
        (root / "src").mkdir()
        (root / "include" / "Widget.hpp").write_text(
            """class Widget {
    int id;
    int count;
    void reset() {}
    void update() {}
    void draw() const {}
    Widget() {}
};
""",
            encoding="utf-8",
        )
        (root / "src" / "Widget.cpp").write_text(
            """#include "../include/Widget.hpp"
""",
            encoding="utf-8",
        )
        issues = scan_repository(root)
        assert len(issues) == 1
        assert issues[0].class_name == "Widget"
        assert issues[0].uninitialized_members == ["id", "count"]


if __name__ == "__main__":
    test_inline_method_not_treated_as_constructor()
    test_scan_does_not_flood_with_inline_methods()
    print("All constructor parser tests passed.")
