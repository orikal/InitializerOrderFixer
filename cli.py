"""Headless CLI for Initializer Order Fixer (CI / Azure Pipeline)."""

from __future__ import annotations

import argparse
import json
import sys
from enum import Enum
from pathlib import Path

from fixer.initializer_order_fixer import apply_fixes
from models.issue import Issue
from scanner.repository_scanner import scan_repository


class Action(str, Enum):
    SCAN = "scan"
    FIX = "fix"
    REPORT = "report"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="initializer-order-fixer",
        description="Scan C/C++ repositories for constructor initializer-list order mismatches.",
    )
    parser.add_argument(
        "--no-ui",
        action="store_true",
        help="Run without the graphical interface (required for CI/pipelines).",
    )
    parser.add_argument(
        "--path",
        type=Path,
        metavar="PATH",
        help="Repository root directory to scan.",
    )
    parser.add_argument(
        "--action",
        choices=[a.value for a in Action],
        default=Action.SCAN.value,
        help=(
            "scan: detect issues only; "
            "fix: scan and apply fixes; "
            "report: scan and write a detailed report."
        ),
    )
    parser.add_argument(
        "--include-dirs",
        metavar="DIRS",
        default="",
        help=(
            "Comma-separated directories to scan, relative to --path "
            "(e.g. src,lib/core). When set, only these folders are scanned."
        ),
    )
    parser.add_argument(
        "--exclude-dirs",
        metavar="DIRS",
        default="",
        help="Comma-separated directory names to skip (e.g. tests,third_party).",
    )
    parser.add_argument(
        "--report-file",
        type=Path,
        metavar="FILE",
        help="Output file for --action report (default: stdout).",
    )
    parser.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="Report format when using --action report (default: text).",
    )
    return parser


def parse_exclude_dirs(raw: str) -> set[str]:
    if not raw.strip():
        return set()
    return {part.strip() for part in raw.split(",") if part.strip()}


def parse_include_dirs(raw: str, repo_path: Path) -> list[Path] | None:
    if not raw.strip():
        return None

    resolved: list[Path] = []
    repo_resolved = repo_path.resolve()
    for part in raw.split(","):
        entry = part.strip()
        if not entry:
            continue
        path = Path(entry)
        if not path.is_absolute():
            path = repo_resolved / entry
        path = path.resolve()
        if not path.is_dir():
            raise ValueError(f"Include directory not found: {entry}")
        try:
            path.relative_to(repo_resolved)
        except ValueError as exc:
            raise ValueError(
                f"Include directory must be under repository root: {entry}"
            ) from exc
        resolved.append(path)
    return resolved or None


def issue_to_dict(issue: Issue, repo_path: Path) -> dict:
    def rel(path_str: str) -> str:
        try:
            return str(Path(path_str).resolve().relative_to(repo_path.resolve()))
        except ValueError:
            return path_str

    return {
        "class": issue.class_name,
        "constructor": issue.constructor_name,
        "header": rel(issue.header_path),
        "source": rel(issue.source_path),
        "line": issue.line,
        "current_order": issue.current_order,
        "suggested_order": issue.suggested_order,
        "uninitialized_members": issue.uninitialized_members,
        "header_initialized_members": issue.header_initialized_members,
        "has_order_mismatch": issue.has_order_mismatch,
        "confidence": issue.confidence.value,
    }


def format_text_report(issues: list[Issue], repo_path: Path) -> str:
    if not issues:
        return "No initializer order issues found.\n"

    lines = [f"Found {len(issues)} issue(s):\n"]
    for idx, issue in enumerate(issues, start=1):
        data = issue_to_dict(issue, repo_path)
        lines.append(f"{idx}. {data['class']}::{data['constructor']}")
        lines.append(f"   Source: {data['source']}:{data['line']}")
        lines.append(f"   Header: {data['header']}")
        lines.append(f"   Current:   {', '.join(data['current_order']) or '(none)'}")
        lines.append(f"   Suggested: {', '.join(data['suggested_order']) or '(none)'}")
        if data["uninitialized_members"]:
            lines.append(
                "   Not initialized in constructor: "
                + ", ".join(data["uninitialized_members"])
            )
        if data["header_initialized_members"]:
            lines.append(
                "   Initialized in header: "
                + ", ".join(data["header_initialized_members"])
            )
        lines.append("")
    return "\n".join(lines)


def format_json_report(issues: list[Issue], repo_path: Path) -> str:
    payload = {
        "issue_count": len(issues),
        "issues": [issue_to_dict(issue, repo_path) for issue in issues],
    }
    return json.dumps(payload, indent=2) + "\n"


def write_report(content: str, report_file: Path | None) -> None:
    if report_file:
        report_file.parent.mkdir(parents=True, exist_ok=True)
        report_file.write_text(content, encoding="utf-8")
    else:
        sys.stdout.write(content)


def run_scan(
    repo_path: Path,
    exclude_dirs: set[str],
    include_dirs: list[Path] | None = None,
) -> list[Issue]:
    if not repo_path.is_dir():
        raise ValueError(f"Not a directory: {repo_path}")
    return scan_repository(
        repo_path,
        selected_dirs=include_dirs,
        exclude_dirs=exclude_dirs or None,
    )


def cli_main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if not args.no_ui:
        if any(arg in ("--help", "-h") for arg in (argv or sys.argv)[1:]):
            parser.print_help()
            return 0
        parser.error("--no-ui is required for headless CLI mode.")

    if args.path is None:
        parser.error("--path is required when using --no-ui.")

    repo_path = args.path.resolve()
    exclude_dirs = parse_exclude_dirs(args.exclude_dirs)
    action = Action(args.action)

    try:
        include_dirs = parse_include_dirs(args.include_dirs, repo_path)
        issues = run_scan(repo_path, exclude_dirs, include_dirs)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    if action == Action.SCAN:
        if issues:
            print(f"Found {len(issues)} initializer order issue(s).")
            for issue in issues:
                data = issue_to_dict(issue, repo_path)
                print(f"  {data['class']} @ {data['source']}:{data['line']}")
            return 1
        print("No initializer order issues found.")
        return 0

    if action == Action.REPORT:
        if args.format == "json":
            content = format_json_report(issues, repo_path)
        else:
            content = format_text_report(issues, repo_path)
        write_report(content, args.report_file)
        return 1 if issues else 0

    # Action.FIX
    if not issues:
        print("No initializer order issues found.")
        return 0

    result = apply_fixes(issues)
    print(f"Applied fixes to {result.success_count} issue(s).")
    if result.failed:
        for path, err in result.failed:
            print(f"  FAILED {path}: {err}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(cli_main())
