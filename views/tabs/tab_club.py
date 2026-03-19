"""
views/tabs/tab_club.py
======================
Club / organisation management tab (TabClub equivalent).
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QPushButton, QTableView,
    QLineEdit, QLabel, QHeaderView, QMessageBox,
    QDialog, QFormLayout, QDialogButtonBox,
)
from PySide6.QtGui import QStandardItemModel, QStandardItem

from models import Club
from .tab_base import TabBase


class ClubTableModel(QStandardItemModel):
    COLUMNS = ["ID", "Name", "Short Name", "Country", "Runners"]

    def __init__(self, parent=None):
        super().__init__(0, len(self.COLUMNS), parent)
        self.setHorizontalHeaderLabels(self.COLUMNS)

    def populate(self, clubs, event):
        self.setRowCount(0)
        runner_counts = {}
        for r in event.runners.values():
            if not r.removed:
                runner_counts[r.club_id] = runner_counts.get(r.club_id, 0) + 1

        for c in clubs:
            row = [
                QStandardItem(str(c.id)),
                QStandardItem(c.name),
                QStandardItem(c.short_name),
                QStandardItem(c.country),
                QStandardItem(str(runner_counts.get(c.id, 0))),
            ]
            for item in row:
                item.setData(c.id, Qt.UserRole)
                item.setEditable(False)
            self.appendRow(row)


class TabClub(TabBase):
    def __init__(self, controller, parent=None):
        super().__init__(controller, parent)
        self._build_ui()
        self.ctrl.event_loaded.connect(self.load_page)

    def _build_ui(self):
        layout = QVBoxLayout(self)

        toolbar = QHBoxLayout()
        self._search = QLineEdit()
        self._search.setPlaceholderText("Search club…")
        self._search.textChanged.connect(self._refresh_table)
        toolbar.addWidget(QLabel("Search:")); toolbar.addWidget(self._search)
        toolbar.addStretch()

        self._btn_add    = QPushButton("Add Club")
        self._btn_edit   = QPushButton("Edit")
        self._btn_delete = QPushButton("Delete")
        self._btn_add.clicked.connect(self._add_club)
        self._btn_edit.clicked.connect(self._edit_club)
        self._btn_delete.clicked.connect(self._delete_club)
        for btn in (self._btn_add, self._btn_edit, self._btn_delete):
            toolbar.addWidget(btn)
        layout.addLayout(toolbar)

        self._model = ClubTableModel(self)
        self._table = QTableView()
        self._table.setModel(self._model)
        self._table.setSelectionBehavior(QTableView.SelectRows)
        self._table.setAlternatingRowColors(True)
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self._table.doubleClicked.connect(self._edit_club)
        layout.addWidget(self._table)

        self._lbl_count = QLabel()
        layout.addWidget(self._lbl_count)

    def load_page(self):
        self._refresh_table()

    def clear_competition_data(self):
        self._model.setRowCount(0)

    def _refresh_table(self):
        ev   = self.ctrl.event
        text = self._search.text().strip().lower()
        clubs = [c for c in ev.clubs.values() if not c.removed]
        if text:
            clubs = [c for c in clubs if
                     text in c.name.lower() or text in c.short_name.lower()]
        clubs.sort(key=lambda c: c.name.lower())
        self._model.populate(clubs, ev)
        self._lbl_count.setText(f"{len(clubs)} club(s)")

    def _selected_club_id(self) -> int:
        idx  = self._table.currentIndex()
        if not idx.isValid():
            return 0
        item = self._model.item(idx.row(), 0)
        return item.data(Qt.UserRole) if item else 0

    def _add_club(self):
        dlg = ClubDialog(parent=self)
        if dlg.exec() == QDialog.Accepted:
            d = dlg.get_data()
            club = self.ctrl.event.add_club(d["name"])
            club.short_name = d["short_name"]
            club.country    = d["country"]
            club.mark_changed()
            self._refresh_table()

    def _edit_club(self):
        cid  = self._selected_club_id()
        if not cid:
            return
        club = self.ctrl.event.clubs.get(cid)
        if club is None:
            return
        dlg = ClubDialog(club=club, parent=self)
        if dlg.exec() == QDialog.Accepted:
            d = dlg.get_data()
            club.name       = d["name"]
            club.short_name = d["short_name"]
            club.country    = d["country"]
            club.mark_changed()
            self._refresh_table()

    def _delete_club(self):
        cid  = self._selected_club_id()
        if not cid:
            return
        club = self.ctrl.event.clubs.get(cid)
        if club is None:
            return
        if not club.can_remove():
            QMessageBox.warning(self, "Cannot Delete",
                                "This club has runners assigned to it.")
            return
        if QMessageBox.question(
            self, "Delete Club", f"Delete club '{club.name}'?",
            QMessageBox.Yes | QMessageBox.No
        ) == QMessageBox.Yes:
            self.ctrl.event.remove_club(cid)
            self._refresh_table()


class ClubDialog(QDialog):
    def __init__(self, club: Club = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add Club" if club is None else "Edit Club")
        self._build_ui()
        if club:
            self._populate(club)

    def _build_ui(self):
        layout = QFormLayout(self)
        self._name       = QLineEdit()
        self._short_name = QLineEdit()
        self._country    = QLineEdit()
        layout.addRow("Full name:",   self._name)
        layout.addRow("Short name:",  self._short_name)
        layout.addRow("Country:",     self._country)
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addRow(btns)

    def _populate(self, c: Club):
        self._name.setText(c.name)
        self._short_name.setText(c.short_name)
        self._country.setText(c.country)

    def get_data(self) -> dict:
        return {
            "name":       self._name.text().strip(),
            "short_name": self._short_name.text().strip(),
            "country":    self._country.text().strip(),
        }
