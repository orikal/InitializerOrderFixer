from pathlib import Path

import pytest

from cli import parse_include_dirs
from scanner.repository_scanner import collect_source_files


FIXTURE_REPO = Path(__file__).parent / "test_fixtures/example"


def test_parse_include_dirs_empty() -> None:
    assert parse_include_dirs("", FIXTURE_REPO) is None
    assert parse_include_dirs("  ,  ", FIXTURE_REPO) is None


def test_parse_include_dirs_relative() -> None:
    dirs = parse_include_dirs("src,include", FIXTURE_REPO)
    assert dirs is not None
    assert len(dirs) == 2
    assert dirs[0].name == "src"
    assert dirs[1].name == "include"


def test_parse_include_dirs_missing_raises() -> None:
    with pytest.raises(ValueError, match="not found"):
        parse_include_dirs("does_not_exist", FIXTURE_REPO)


def test_parse_include_dirs_outside_repo_raises(tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    with pytest.raises(ValueError, match="under repository root"):
        parse_include_dirs(str(outside), FIXTURE_REPO)


def test_collect_source_files_with_include_dirs() -> None:
    all_files = collect_source_files(FIXTURE_REPO)
    src_files = collect_source_files(
        FIXTURE_REPO,
        selected_dirs=[FIXTURE_REPO / "src"],
    )
    assert all(f.suffix.lower() in {".cpp", ".c"} for f in all_files)
    assert len(src_files) == len(all_files)
    assert all("src" in str(f) for f in src_files)
