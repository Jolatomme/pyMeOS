"""
views/tabs/tab_base.py
======================
Abstract base for all tab panels (TabBase equivalent).
"""
from __future__ import annotations
from abc import ABC, abstractmethod
from PySide6.QtWidgets import QWidget
from controllers.competition import CompetitionController


class TabBase(QWidget, ABC):
    """Abstract tab panel. Every tab must implement load_page()."""

    def __init__(self, controller: CompetitionController, parent=None):
        super().__init__(parent)
        self.ctrl = controller

    @abstractmethod
    def load_page(self) -> None:
        """(Re)populate the tab contents from the model."""

    def clear_competition_data(self) -> None:
        """Called when a new event is loaded to reset any cached state."""
