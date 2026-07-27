"""Shared asset paths for dev runs and PyInstaller bundles."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def asset_path(name: str) -> Path:
    base = Path(sys._MEIPASS) if getattr(sys, "frozen", False) else ROOT
    return base / "assets" / name


def logo_path() -> Path:
    return asset_path("logo.png")


def logo_icon_path() -> Path:
    ico = asset_path("logo.ico")
    if ico.is_file():
        return ico
    return logo_path()
