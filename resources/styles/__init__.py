"""
styles/__init__.py
===================
Style utilities for PyMeOS.

Provides:
  - Theme detection (light/dark mode)
  - Style loading utilities
  - Animation support
"""
from __future__ import annotations

import platform
import sys
from pathlib import Path
from typing import Optional


def get_theme_path(theme: str = "auto") -> Path:
    """
    Get the path to the stylesheet file.
    
    Args:
        theme: "light", "dark", or "auto" (detect from system)
    
    Returns:
        Path to the QSS file
    """
    styles_dir = Path(__file__).parent
    
    if theme == "auto":
        theme = "dark" if is_dark_mode_enabled() else "light"
    
    if theme == "dark":
        return styles_dir / "dark.qss"
    else:
        return styles_dir / "default.qss"


def get_animations_path() -> Path:
    """Get the path to the animations stylesheet."""
    return Path(__file__).parent / "animations.qss"


def is_dark_mode_enabled() -> bool:
    """
    Detect if the system prefers dark mode.
    
    Supports:
      - macOS (via NSUserDefaults)
      - Windows 10/11 (via registry)
      - Linux (via GTK settings or environment)
    
    Returns:
        True if dark mode is preferred, False otherwise
    """
    system = platform.system()
    
    # macOS
    if system == "Darwin":
        try:
            from AppKit import NSUserDefaults
            defaults = NSUserDefaults.standardUserDefaults()
            style = defaults.stringForKey_("AppleInterfaceStyle")
            return style == "Dark"
        except ImportError:
            pass
    
    # Windows 10/11
    if system == "Windows":
        try:
            import winreg
            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize"
            ) as key:
                apps_use_light_theme = winreg.QueryValueEx(key, "AppsUseLightTheme")[0]
                return apps_use_light_theme == 0
        except (ImportError, FileNotFoundError, PermissionError, OSError):
            pass
    
    # Linux (via settings or environment)
    if system == "Linux":
        # Try GTK settings
        try:
            from PySide6.QtCore import QSettings
            settings = QSettings("org.gnome.desktop.interface", QSettings.Format.NativeFormat)
            gtk_theme = settings.value("gtk-theme", "Adwaita")
            return "dark" in str(gtk_theme).lower()
        except:
            # Check environment variable
            import os
            return os.environ.get("GTK_THEME", "").lower() == "dark"
    
    # Fallback: check if we're running with a dark environment variable
    import os
    if os.environ.get("PYMEOS_THEME", "").lower() == "dark":
        return True
    if os.environ.get("QT_STYLE_OVERRIDE", "").lower() == "dark":
        return True
    
    # Default to light mode
    return False


def load_stylesheet(theme: str = "auto", with_animations: bool = True) -> str:
    """
    Load the stylesheet content.
    
    Args:
        theme: "light", "dark", or "auto"
        with_animations: Whether to include animations
    
    Returns:
        Combined QSS string
    """
    # Load main theme
    theme_path = get_theme_path(theme)
    if not theme_path.exists():
        # Fallback to default
        theme_path = Path(__file__).parent / "default.qss"
    
    stylesheet = theme_path.read_text(encoding="utf-8")
    
    # Add animations if requested
    if with_animations:
        animations_path = get_animations_path()
        if animations_path.exists():
            stylesheet += "\n\n" + animations_path.read_text(encoding="utf-8")
    
    return stylesheet


def set_application_theme(app, theme: str = "auto", with_animations: bool = True) -> None:
    """
    Apply the theme to a QApplication.
    
    Args:
        app: The QApplication instance
        theme: "light", "dark", or "auto"
        with_animations: Whether to include animations
    """
    stylesheet = load_stylesheet(theme, with_animations)
    app.setStyleSheet(stylesheet)
