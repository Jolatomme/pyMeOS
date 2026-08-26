"""
views/tabs/tab_team.py
=====================
Team management tab (TabTeam equivalent).

Features:
   Table of all teams (sortable)
   Add / Edit / Delete team dialog
   Team member management
"""
from __future__ import annotations

from PySide6.QtCore import Qt, QSortFilterProxyModel
from PySide6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QPushButton, QTableView,
    QLineEdit, QLabel, QComboBox, QHeaderView, QMessageBox,
    QDialog, QFormLayout, QDialogButtonBox,
)
from PySide6.QtGui import QStandardItemModel, QStandardItem

from models import Team
from utils.icon_utils import get_icon
from .tab_base import TabBase


class TeamTableModel(QStandardItemModel):
    COLUMNS = ["#", "Name", "Club", "Class", "Members", "Card"]

    def __init__(self, parent=None):
        super().__init__(0, len(self.COLUMNS), parent)
        self.setHorizontalHeaderLabels(self.COLUMNS)

    def populate(self, teams, event):
        self.setRowCount(0)
        for t in teams:
            club = event.clubs.get(t.club_id)
            cls  = event.classes.get(t.class_id)
            row = [
                QStandardItem(str(t.id)),
                QStandardItem(t.name),
                QStandardItem(club.name if club else ""),
                QStandardItem(cls.name  if cls  else ""),
                QStandardItem(str(len(t.members))),
                QStandardItem(str(t.card_number) if t.card_number else ""),
            ]
            for item in row:
                item.setData(t.id, Qt.UserRole)
                item.setEditable(False)
            self.appendRow(row)


class TabTeam(TabBase):
    def __init__(self, controller, parent=None):
        super().__init__(controller, parent)
        self._build_ui()
        self.ctrl.event_loaded.connect(self.load_page)

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self):
        layout = QVBoxLayout(self)

        # ---- Toolbar ---------------------------------------------------
        toolbar = QHBoxLayout()

        self._search = QLineEdit()
        self._search.setPlaceholderText("Search team...")
        self._search.textChanged.connect(self._apply_filter)
        toolbar.addWidget(QLabel("Search:"))
        toolbar.addWidget(self._search)

        toolbar.addStretch()

        self._btn_add    = QPushButton(get_icon("actions/add"),    "Add Team")
        self._btn_edit   = QPushButton(get_icon("actions/edit"),   "Edit")
        self._btn_delete = QPushButton(get_icon("actions/delete"), "Delete")
        self._btn_add.clicked.connect(self._add_team)
        self._btn_edit.clicked.connect(self._edit_team)
        self._btn_delete.clicked.connect(self._delete_team)
        for btn in (self._btn_add, self._btn_edit, self._btn_delete):
            toolbar.addWidget(btn)

        layout.addLayout(toolbar)

        # ---- Table ------------------------------------------------------
        self._table = QTableView()
        self._table.setSelectionBehavior(QTableView.SelectRows)
        self._table.setSelectionMode(QTableView.SingleSelection)
        self._table.setSortingEnabled(True)
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.verticalHeader().setVisible(False)
        self._table.setAlternatingRowColors(True)

        self._model = TeamTableModel(self)
        self._proxy = QSortFilterProxyModel(self)
        self._proxy.setSourceModel(self._model)
        self._table.setModel(self._proxy)

        layout.addWidget(self._table)

    # ------------------------------------------------------------------
    # Load / Refresh
    # ------------------------------------------------------------------

    def load_page(self) -> None:
        self._model.populate(
            [t for t in self.ctrl.event.teams.values() if not t.removed],
            self.ctrl.event)
        self._apply_filter()

    def _apply_filter(self):
        text = self._search.text().lower()
        if text:
            self._proxy.setFilterRegularExpression(text)
        else:
            self._proxy.setFilterRegularExpression("")

    # ------------------------------------------------------------------
    # Team dialogs
    # ------------------------------------------------------------------

    def _add_team(self):
        dlg = TeamDialog(self.ctrl.event, self)
        if dlg.exec() == QDialog.Accepted:
            self.ctrl.event.add_team(
                name=dlg.name.text(),
                club_id=self.ctrl.event.get_club_by_name(dlg.club_combo.currentText()).id
                if dlg.club_combo.currentText() else 0,
                class_id=self.ctrl.event.get_class_by_name(dlg.class_combo.currentText()).id
                if dlg.class_combo.currentText() else 0)
            self.ctrl.event._notify("teams_changed", None)

    def _edit_team(self):
        selected = self._table.selectionModel().selectedRows()
        if not selected:
            return
        proxy_index = selected[0]
        source_index = self._proxy.mapToSource(proxy_index)
        team_id = self._model.index(source_index.row(), 0).data(Qt.UserRole)

        team = self.ctrl.event.teams.get(team_id)
        if not team:
            return

        dlg = TeamDialog(self.ctrl.event, self, team)
        if dlg.exec() == QDialog.Accepted:
            team.name = dlg.name.text()
            club = self.ctrl.event.get_club_by_name(dlg.club_combo.currentText())
            cls = self.ctrl.event.get_class_by_name(dlg.class_combo.currentText())
            if club:
                team.club_id = club.id
            if cls:
                team.class_id = cls.id
            team.mark_changed()
            self.ctrl.event._notify("teams_changed", team)

    def _delete_team(self):
        selected = self._table.selectionModel().selectedRows()
        if not selected:
            return
        proxy_index = selected[0]
        source_index = self._proxy.mapToSource(proxy_index)
        team_id = self._model.index(source_index.row(), 0).data(Qt.UserRole)

        team = self.ctrl.event.teams.get(team_id)
        if team:
            reply = QMessageBox.question(
                self, "Delete Team",
                f"Delete {team.name}?",
                QMessageBox.Yes | QMessageBox.No)
            if reply == QMessageBox.Yes:
                self.ctrl.event.remove_team(team_id)


class TeamDialog(QDialog):
    def __init__(self, event, parent=None, team=None):
        super().__init__(parent)
        self.setWindowTitle("Add Team" if not team else "Edit Team")
        self._build_ui(event, team)

    def _build_ui(self, event, team):
        layout = QFormLayout(self)

        self.name = QLineEdit()
        self.club_combo = QComboBox()
        self.class_combo = QComboBox()

        # Populate combos
        for club in event.clubs.values():
            if not club.removed:
                self.club_combo.addItem(club.name)
        for cls in event.classes.values():
            if not cls.removed:
                self.class_combo.addItem(cls.name)

        # Set values
        if team:
            self.name.setText(team.name)
            club = event.clubs.get(team.club_id)
            if club:
                self.club_combo.setCurrentText(club.name)
            cls = event.classes.get(team.class_id)
            if cls:
                self.class_combo.setCurrentText(cls.name)

        layout.addRow("Name:", self.name)
        layout.addRow("Club:", self.club_combo)
        layout.addRow("Class:", self.class_combo)

        # Buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)
