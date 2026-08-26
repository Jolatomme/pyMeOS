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
# Qt environment tweaks - MUST happen before QApplication is created
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
# However, QApplication may not exist yet at import time, so we defer to main()

from views.main_window import MainWindow
from resources.styles import is_dark_mode_enabled, get_theme_path, get_animations_path


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="PyMeOS - Orienteering Software")
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
    p.add_argument("--theme",
                   default="auto",
                   choices=["light", "dark", "auto"],
                   help="UI theme: light, dark, or auto (default: auto)")
    p.add_argument("--no-animations",
                   action="store_true",
                   help="Disable UI animations")
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

    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication

    # Set high-DPI policy before creating QApplication
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    app.setApplicationName("PyMeOS")
    app.setApplicationVersion("5.0.0")
    app.setOrganizationName("PyMeOS Community")

    # Load stylesheet with theme support
    theme = args.theme
    with_animations = not args.no_animations
    
    # Determine theme path
    if theme == "auto":
        theme_path = get_theme_path("dark" if is_dark_mode_enabled() else "light")
    else:
        theme_path = get_theme_path(theme)
    
    # Load and apply stylesheet
    stylesheet = ""
    if theme_path.exists():
        stylesheet = theme_path.read_text(encoding="utf-8")
        
        # Add animations if enabled
        if with_animations:
            animations_path = get_animations_path()
            if animations_path.exists():
                stylesheet += "\n\n" + animations_path.read_text(encoding="utf-8")
        
        app.setStyleSheet(stylesheet)
    else:
        # Fallback to default if theme file not found
        default_path = PROJECT_ROOT / "resources" / "styles" / "default.qss"
        if default_path.exists():
            app.setStyleSheet(default_path.read_text(encoding="utf-8"))

    window = MainWindow(db_url=args.db)
    window.show()

    # Open file passed on the command line
    if args.open:
        window._ctrl.open_event_from_xml(args.open)
        window._refresh_all_tabs()

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
