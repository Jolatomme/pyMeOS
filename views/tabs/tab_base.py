"""
views/tabs/tab_base.py
======================
Abstract base for all tab panels (TabBase equivalent).

Note: We intentionally do NOT use ABCMeta here.  Combining ABCMeta with
PySide6's Shiboken metaclass (used internally by QWidget) corrupts the ABC
machinery and breaks isinstance() checks with the error:
  AttributeError: type object 'TabXxx' has no attribute '_abc_impl'

Abstract-method enforcement is achieved with plain NotImplementedError.
"""
from __future__ import annotations

from PySide6.QtWidgets import QWidget


class TabBase(QWidget):
    """Base tab panel.  Every tab must implement :meth:`load_page`."""

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
