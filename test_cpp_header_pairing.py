from pathlib import Path
from tempfile import TemporaryDirectory

from scanner.repository_scanner import headers_for_cpp, scan_repository


def test_scan_pairs_cpp_with_included_header_not_other_headers() -> None:
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
        (root / "include" / "Bar.hpp").write_text(
            """class Bar {
    int x;
    Bar() {}
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

        issues = scan_repository(root)
        assert len(issues) == 1
        assert issues[0].class_name == "Foo"
        assert issues[0].source_path.endswith("Foo.cpp")
        assert issues[0].header_path.endswith("Foo.hpp")
        assert "Bar.hpp" not in issues[0].header_path


def test_headers_for_cpp_resolves_relative_include() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "include").mkdir()
        (root / "src").mkdir()
        header = root / "include" / "Example.hpp"
        header.write_text("class Example {};\n", encoding="utf-8")
        cpp = root / "src" / "Example.cpp"
        cpp.write_text('#include "../include/Example.hpp"\n', encoding="utf-8")

        from scanner.repository_scanner import _build_header_index

        index = _build_header_index(root)
        resolved = headers_for_cpp(cpp, root.resolve(), index)
        assert resolved == [header.resolve()]


if __name__ == "__main__":
    test_scan_pairs_cpp_with_included_header_not_other_headers()
    test_headers_for_cpp_resolves_relative_include()
    print("OK")
