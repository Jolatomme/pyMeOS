#!/usr/bin/env python3
"""
main.py
=======
PyMeOS application entry point.

Usage
-----
    python main.py                        # default SQLite DB in current dir
    python main.py --db sqlite:///my.db   # custom DB path
    python main.py --db mysql+pymysql://user:pw@host/dbname
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Ensure the project root is on sys.path when running as a script
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# ---------------------------------------------------------------------------
# Qt environment tweaks – MUST happen before QApplication is created
# ---------------------------------------------------------------------------

# Silence the "dbus reply error" spam from the GNOME platform-theme plugin.
# This fires whenever Qt runs outside a full GNOME session (KDE, XFCE, TTY,
# plain X11, Wayland without gnome-session, etc.).  The app works perfectly
# without the GNOME theme service; the messages are purely informational noise.
_existing_rules = os.environ.get("QT_LOGGING_RULES", "")
_gnome_rule = "qt.qpa.theme.gnome=false"
if _gnome_rule not in _existing_rules:
    os.environ["QT_LOGGING_RULES"] = (
        f"{_existing_rules};{_gnome_rule}" if _existing_rules else _gnome_rule
    )

# High-DPI rounding policy must be set before QApplication is instantiated.
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

QApplication.setHighDpiScaleFactorRoundingPolicy(
    Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
)

from views.main_window import MainWindow


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="PyMeOS – Orienteering Software")
    p.add_argument("--db",
                   default="sqlite:///pymeos.db",
                   help="SQLAlchemy database URL (default: sqlite:///pymeos.db)")
    p.add_argument("--log-level",
                   default="WARNING",
                   choices=["DEBUG", "INFO", "WARNING", "ERROR"],
                   help="Logging verbosity")
    p.add_argument("--open",
                   metavar="FILE",
                   help="Open a .mexml competition file on startup")
    return p.parse_args()


def main() -> int:
    args = _parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
    )

    # Initialise database
    from persistence import init_db
    init_db(args.db)

    app = QApplication(sys.argv)
    app.setApplicationName("PyMeOS")
    app.setApplicationVersion("5.0.0")
    app.setOrganizationName("PyMeOS Community")

    window = MainWindow(db_url=args.db)
    window.show()

    # Open file passed on the command line
    if args.open:
        window._ctrl.open_event_from_xml(args.open)
        window._refresh_all_tabs()

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
