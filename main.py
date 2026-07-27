#!/usr/bin/env python3
"""Initializer Order Fixer — entry point."""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure project root is on sys.path when run as script.
ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _is_cli_mode(argv: list[str]) -> bool:
    if "--no-ui" in argv:
        return True
    # Allow --help / -h without launching the GUI.
    return any(arg in ("--help", "-h") for arg in argv[1:])


def run_gui() -> int:
    from PySide6.QtGui import QIcon
    from PySide6.QtWidgets import QApplication

    from resources import logo_icon_path
    from ui.main_window import MainWindow

    app = QApplication(sys.argv)
    app.setApplicationName("Initializer Order Fixer")
    icon_path = logo_icon_path()
    if icon_path.is_file():
        app.setWindowIcon(QIcon(str(icon_path)))
    window = MainWindow()
    window.show()
    return app.exec()


def main() -> int:
    if _is_cli_mode(sys.argv):
        from cli import cli_main

        return cli_main()
    return run_gui()


if __name__ == "__main__":
    sys.exit(main())
