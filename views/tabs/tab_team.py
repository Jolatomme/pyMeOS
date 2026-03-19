"""
views/tabs/tab_team.py
======================
Relay team management tab (TabTeam equivalent).

Features:
  • Table of all teams with per-leg runner assignments
  • Add / Edit / Delete team dialogs
  • Leg runner assignment
"""
from __future__ import annotations

from PySide6.QtCore import Qt, QSortFilterProxyModel
from PySide6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QPushButton, QTableView,
    QLineEdit, QLabel, QComboBox, QHeaderView, QMessageBox,
    QDialog, QFormLayout, QDialogButtonBox, QSpinBox,
    QGroupBox, QScrollArea, QWidget,
)
from PySide6.QtGui import QStandardItemModel, QStandardItem

from models import RunnerStatus, Team
from utils.time_utils import format_time, NO_TIME
from .tab_base import TabBase


class TeamTableModel(QStandardItemModel):
    COLUMNS = ["#", "Name", "Club", "Class", "Status", "Total Time", "Place"]

    def __init__(self, parent=None):
        super().__init__(0, len(self.COLUMNS), parent)
        self.setHorizontalHeaderLabels(self.COLUMNS)

    def populate(self, teams, event):
        self.setRowCount(0)
        for t in teams:
            club = event.clubs.get(t.club_id)
            cls  = event.classes.get(t.class_id)
            tt   = t.t_total_time
            row = [
                QStandardItem(str(t.start_no)),
                QStandardItem(t.name),
                QStandardItem(club.name if club else ""),
                QStandardItem(cls.name  if cls  else ""),
                QStandardItem(t.status.to_code()),
                QStandardItem(format_time(tt) if tt != NO_TIME else ""),
                QStandardItem(str(t.place) if t.place else ""),
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
        self.ctrl.runner_updated.connect(lambda _: self._refresh_table())

    def _build_ui(self):
        layout = QVBoxLayout(self)

        # Toolbar
        toolbar = QHBoxLayout()
        self._search = QLineEdit()
        self._search.setPlaceholderText("Search team name…")
        self._search.textChanged.connect(self._apply_filter)
        toolbar.addWidget(QLabel("Search:"))
        toolbar.addWidget(self._search)

        self._class_combo = QComboBox()
        self._class_combo.addItem("All classes", 0)
        self._class_combo.currentIndexChanged.connect(self._apply_filter)
        toolbar.addWidget(QLabel("Class:"))
        toolbar.addWidget(self._class_combo)
        toolbar.addStretch()

        self._btn_add    = QPushButton("Add Team")
        self._btn_edit   = QPushButton("Edit")
        self._btn_delete = QPushButton("Delete")
        self._btn_add.clicked.connect(self._add_team)
        self._btn_edit.clicked.connect(self._edit_team)
        self._btn_delete.clicked.connect(self._delete_team)
        for btn in (self._btn_add, self._btn_edit, self._btn_delete):
            toolbar.addWidget(btn)
        layout.addLayout(toolbar)

        # Table
        self._model = TeamTableModel(self)
        self._proxy = QSortFilterProxyModel(self)
        self._proxy.setSourceModel(self._model)
        self._proxy.setFilterCaseSensitivity(Qt.CaseInsensitive)
        self._proxy.setFilterKeyColumn(-1)

        self._table = QTableView()
        self._table.setModel(self._proxy)
        self._table.setSortingEnabled(True)
        self._table.setSelectionBehavior(QTableView.SelectRows)
        self._table.setAlternatingRowColors(True)
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self._table.doubleClicked.connect(self._edit_team)
        layout.addWidget(self._table)

        self._lbl_count = QLabel()
        layout.addWidget(self._lbl_count)

    def load_page(self):
        ev = self.ctrl.event
        self._class_combo.blockSignals(True)
        self._class_combo.clear()
        self._class_combo.addItem("All classes", 0)
        for cls in sorted(ev.classes.values(), key=lambda c: c.name):
            if not cls.removed and cls.is_relay():
                self._class_combo.addItem(cls.name, cls.id)
        self._class_combo.blockSignals(False)
        self._refresh_table()

    def clear_competition_data(self):
        self._model.setRowCount(0)
        self._class_combo.clear()

    def _refresh_table(self):
        ev = self.ctrl.event
        class_id = self._class_combo.currentData() or 0
        teams = [t for t in ev.teams.values()
                 if not t.removed and (class_id == 0 or t.class_id == class_id)]
        teams.sort(key=lambda t: t.result_sort_key())
        self._model.populate(teams, ev)
        self._apply_filter()
        self._lbl_count.setText(f"{len(teams)} team(s)")

    def _apply_filter(self):
        text = self._search.text().strip()
        class_id = self._class_combo.currentData() or 0
        if class_id:
            self._refresh_table()
            return
        self._proxy.setFilterFixedString(text)

    def _selected_team_id(self) -> int:
        idx = self._table.currentIndex()
        if not idx.isValid():
            return 0
        src  = self._proxy.mapToSource(idx)
        item = self._model.item(src.row(), 0)
        return item.data(Qt.UserRole) if item else 0

    def _add_team(self):
        dlg = TeamDialog(self.ctrl.event, parent=self)
        if dlg.exec() == QDialog.Accepted:
            d = dlg.get_data()
            ev = self.ctrl.event
            club_id  = ev.add_club(d["club_name"]).id if d["club_name"] else 0
            cls_obj  = ev.get_class_by_name(d["class_name"])
            class_id = cls_obj.id if cls_obj else 0
            ev.add_team(d["name"], club_id, class_id)
            self._refresh_table()

    def _edit_team(self):
        tid = self._selected_team_id()
        if not tid:
            return
        team = self.ctrl.event.teams.get(tid)
        if team is None:
            return
        dlg = TeamDialog(self.ctrl.event, team=team, parent=self)
        if dlg.exec() == QDialog.Accepted:
            d = dlg.get_data()
            team.name = d["name"]
            team.mark_changed()
            self._refresh_table()

    def _delete_team(self):
        tid = self._selected_team_id()
        if not tid:
            return
        team = self.ctrl.event.teams.get(tid)
        if team is None:
            return
        if QMessageBox.question(
            self, "Delete Team", f"Delete team '{team.name}'?",
            QMessageBox.Yes | QMessageBox.No
        ) == QMessageBox.Yes:
            self.ctrl.event.remove_team(tid)
            self._refresh_table()


class TeamDialog(QDialog):
    def __init__(self, event, team=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add Team" if team is None else "Edit Team")
        self._event = event
        self._team  = team
        self._build_ui()
        if team:
            self._populate(team)

    def _build_ui(self):
        layout = QFormLayout(self)
        self._name  = QLineEdit()
        self._club  = QComboBox(); self._club.setEditable(True)
        self._class = QComboBox(); self._class.setEditable(True)

        layout.addRow("Team name:", self._name)
        layout.addRow("Club:",      self._club)
        layout.addRow("Class:",     self._class)

        for club in sorted(self._event.clubs.values(), key=lambda c: c.name):
            if not club.removed:
                self._club.addItem(club.name)
        for cls in sorted(self._event.classes.values(), key=lambda c: c.name):
            if not cls.removed and cls.is_relay():
                self._class.addItem(cls.name)

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addRow(btns)

    def _populate(self, t: Team):
        self._name.setText(t.name)
        club = self._event.clubs.get(t.club_id)
        if club:
            self._club.setCurrentText(club.name)
        cls = self._event.classes.get(t.class_id)
        if cls:
            self._class.setCurrentText(cls.name)

    def get_data(self) -> dict:
        return {
            "name":       self._name.text().strip(),
            "club_name":  self._club.currentText().strip(),
            "class_name": self._class.currentText().strip(),
        }
