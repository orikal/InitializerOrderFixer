from pathlib import Path

from fixer.initializer_order_fixer import apply_fixes
from scanner.repository_scanner import scan_repository

FIXTURE_CPP = Path(__file__).parent / "test_fixtures/example/src/Example.cpp"
ORIGINAL = """#include "../include/Example.hpp"

Example::Example()
    : second(20),
      first(10)
{
}
"""


def main() -> None:
    FIXTURE_CPP.write_text(ORIGINAL, encoding="utf-8")
    repo = Path(__file__).parent / "test_fixtures/example"
    issues = scan_repository(repo)
    print(f"Issues found: {len(issues)}")
    for issue in issues:
        print(
            f"  Class={issue.class_name}, "
            f"current={issue.current_order_str}, "
            f"correct={issue.correct_order_str}"
        )

    if not issues:
        raise SystemExit(1)

    result = apply_fixes(issues)
    print(f"Fix result: success={result.success_count}, failed={result.failed}")

    issues_after = scan_repository(repo)
    print(f"Issues after fix: {len(issues_after)}")
    print("--- Fixed file ---")
    print(FIXTURE_CPP.read_text(encoding="utf-8"))

    if issues_after:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
