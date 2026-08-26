"""
utils/icon_utils.py
=====================
Icon loading utilities for PyMeOS.

Provides a centralized way to load SVG icons and apply them to widgets.
Uses absolute paths to ensure icons are found regardless of working directory.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6.QtGui import QIcon


# Get the absolute path to the project root
# This works regardless of where the script is run from
PROJECT_ROOT = Path(__file__).resolve().parent.parent
ICON_DIR = PROJECT_ROOT / "resources" / "icons"


class IconLoader:
    """
    Centralized icon loader for PyMeOS.
    
    Usage:
        icons = IconLoader()
        button.setIcon(icons.get("actions/add"))
        action.setIcon(icons.get("general/new"))
    """
    
    def __init__(self) -> None:
        self._cache: dict[str, QIcon] = {}
    
    def get(self, icon_name: str, size: int = 24) -> QIcon:
        """
        Get an icon by name.
        
        Args:
            icon_name: Icon name with or without category (e.g., "actions/add", "add", "general/new")
            size: Icon size in pixels (default: 24) - Note: SVG icons scale automatically
        
        Returns:
            QIcon object, or empty icon if not found
        """
        if icon_name in self._cache:
            return self._cache[icon_name]
        
        # Try to find the icon file
        icon_path = self._find_icon_path(icon_name)
        
        if icon_path and icon_path.exists():
            icon = QIcon(str(icon_path))
            self._cache[icon_name] = icon
            return icon
        
        # Return empty icon if not found
        print(f"Warning: Icon '{icon_name}' not found in {ICON_DIR}")
        return QIcon()
    
    def _find_icon_path(self, icon_name: str) -> Optional[Path]:
        """Find the path to an icon file."""
        # Remove .svg extension if present
        icon_name = icon_name.replace('.svg', '')
        
        # Try direct path with .svg
        path = ICON_DIR / f"{icon_name}.svg"
        if path.exists():
            return path
        
        # Try with category prefix
        if "/" in icon_name:
            path = ICON_DIR / f"{icon_name}.svg"
            if path.exists():
                return path
        
        # Try to find in subdirectories
        for category in ["general", "actions", "competition", "si", "status"]:
            # Try category/name.svg
            path = ICON_DIR / category / f"{icon_name.split('/')[-1]}.svg"
            if path.exists():
                return path
            
            # Try category/name (without extension)
            path = ICON_DIR / category / icon_name.split('/')[-1]
            if path.exists():
                return path
        
        # Try without category
        path = ICON_DIR / f"{icon_name.split('/')[-1]}.svg"
        if path.exists():
            return path
        
        return None


# Global icon loader instance
icons = IconLoader()


def get_icon(name: str, size: int = 24) -> QIcon:
    """
    Get an icon by name (convenience function).
    
    Args:
        name: Icon name (e.g., "general/new", "actions/add", "new")
        size: Icon size (not used for SVG, but kept for compatibility)
    
    Returns:
        QIcon object
    """
    return icons.get(name, size)


def set_icon_to_button(button, icon_name: str, text: str = "") -> None:
    """
    Set an icon to a button.
    
    Args:
        button: The button widget (QPushButton or QToolButton)
        icon_name: Icon name (e.g., "actions/add")
        text: Button text (optional)
    """
    icon = get_icon(icon_name)
    button.setIcon(icon)
    if text:
        button.setText(text)


def set_icon_to_action(action, icon_name: str) -> None:
    """
    Set an icon to an action.
    
    Args:
        action: The QAction object
        icon_name: Icon name (e.g., "general/new")
    """
    action.setIcon(get_icon(icon_name))
