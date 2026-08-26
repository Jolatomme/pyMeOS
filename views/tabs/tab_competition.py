"""
views/tabs/tab_competition.py
==============================
Competition management tab (TabCompetition equivalent).

Features:
   New / Open / Save competition
   Event metadata editing
   Database connection management
"""
from __future__ import annotations

from PySide6.QtCore import Qt, QDate
from PySide6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QFormLayout, QGroupBox, QLineEdit, QDateEdit,
    QFileDialog, QMessageBox, QInputDialog,
)

from utils.icon_utils import get_icon
from .tab_base import TabBase


class TabCompetition(TabBase):
    def __init__(self, controller, parent=None):
        super().__init__(controller, parent)
        self._build_ui()
        self.ctrl.event_loaded.connect(self.load_page)

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self):
        layout = QVBoxLayout(self)

        # ---- Event info group ------------------------------------------------
        info_grp = QGroupBox("Event Information")
        ig = QFormLayout(info_grp)

        self._name_edit    = QLineEdit()
        self._date_edit    = QDateEdit()
        self._date_edit.setCalendarPopup(True)
        self._org_edit     = QLineEdit()
        self._country_edit = QLineEdit()

        ig.addRow("Name:", self._name_edit)
        ig.addRow("Date:", self._date_edit)
        ig.addRow("Organiser:", self._org_edit)
        ig.addRow("Country:", self._country_edit)

        layout.addWidget(info_grp)

        # ---- File controls ---------------------------------------------------
        file_grp = QGroupBox("File")
        fg = QHBoxLayout(file_grp)

        self._btn_new    = QPushButton(get_icon("general/new"),    "New Competition")
        self._btn_open   = QPushButton(get_icon("general/open"),   "Open...")
        self._btn_save   = QPushButton(get_icon("general/save"),   "Save")
        self._btn_saveas = QPushButton(get_icon("general/save_as"), "Save As...")

        self._btn_new.clicked.connect(self._on_new)
        self._btn_open.clicked.connect(self._on_open)
        self._btn_save.clicked.connect(self._on_save)
        self._btn_saveas.clicked.connect(self._on_save_as)

        for btn in (self._btn_new, self._btn_open, self._btn_save, self._btn_saveas):
            fg.addWidget(btn)

        layout.addWidget(file_grp)

        # ---- Status -----------------------------------------------------------
        self._lbl_file = QLabel("No competition loaded.")
        layout.addWidget(self._lbl_file)

        layout.addStretch()

    # ------------------------------------------------------------------
    # Load / Refresh
    # ------------------------------------------------------------------

    def load_page(self) -> None:
        ev = self.ctrl.event
        self._name_edit.setText(ev.name)
        self._date_edit.setDate(QDate.fromString(ev.date, "yyyy-MM-dd")) if ev.date else QDate.currentDate()
        self._org_edit.setText(ev.organiser)
        self._country_edit.setText(ev.country)

        if ev.current_file:
            self._lbl_file.setText(f"File: {ev.current_file}")
        else:
            self._lbl_file.setText("New competition (unsaved)")

    # ------------------------------------------------------------------
    # Button handlers
    # ------------------------------------------------------------------

    def _on_new(self):
        name, ok = QInputDialog.getText(
            self, "New Competition", "Competition name:")
        if ok and name:
            self.ctrl.new_event(name)

    def _on_open(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Open Competition",
            filter="MeOS XML (*.meosxml *.mexml *.xml);;All Files (*)")
        if path:
            ok = self.ctrl.open_event_from_xml(path)
            if not ok:
                QMessageBox.critical(self, "Error", "Failed to open file.")

    def _on_save(self):
        if self.ctrl.event.current_file:
            self.ctrl.save_event_to_xml(self.ctrl.event.current_file)
        else:
            self._on_save_as()

    def _on_save_as(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Competition",
            filter="MeOS XML (*.mexml);;All Files (*)")
        if path:
            if not path.endswith((".mexml", ".meosxml")):
                path += ".mexml"
            self.ctrl.event.current_file = path
            self.ctrl.save_event_to_xml(path)
