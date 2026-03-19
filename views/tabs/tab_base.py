"""
views/tabs/tab_base.py
======================
Abstract base for all tab panels (TabBase equivalent).
"""
from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QWidget
from PySide6.QtCore import QObject


# Resolve the metaclass conflict between QWidget (uses Shiboken's metaclass)
# and ABC (uses ABCMeta) by defining a combined metaclass.
from abc import ABCMeta
from shiboken6 import Shiboken

class _QWidgetABCMeta(type(QWidget), ABCMeta):
    pass


class TabBase(QWidget, metaclass=_QWidgetABCMeta):
    """Abstract tab panel. Every tab must implement load_page()."""

    def __init__(self, controller, parent=None):
        super().__init__(parent)
        self.ctrl = controller

    def load_page(self) -> None:
        """(Re)populate the tab contents from the model."""
        raise NotImplementedError(
            f"{self.__class__.__name__} must implement load_page()"
        )

    def clear_competition_data(self) -> None:
        """Called when a new event is loaded to reset any cached state."""
