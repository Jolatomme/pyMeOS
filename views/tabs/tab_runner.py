"""
views/tabs/tab_runner.py
========================
Runner management tab (TabRunner equivalent).

Features:
  • Table of all runners (sortable)
  • Add / Edit / Delete runner dialog
  • Manual time/status entry
  • Search / filter by class, club, name
"""
from __future__ import annotations

from PySide6.QtCore import Qt, QSortFilterProxyModel
from PySide6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QPushButton, QTableView,
    QLineEdit, QLabel, QComboBox, QHeaderView, QMessageBox,
    QDialog, QFormLayout, QDialogButtonBox, QSpinBox,
)
from PySide6.QtGui import QStandardItemModel, QStandardItem

from models import RunnerStatus, Runner
from utils.time_utils import format_time, parse_time, NO_TIME
from .tab_base import TabBase


class RunnerTableModel(QStandardItemModel):
    COLUMNS = ["#", "First Name", "Last Name", "Club", "Class",
               "Card", "Start", "Finish", "Time", "Status", "Place"]

    def __init__(self, parent=None):
        super().__init__(0, len(self.COLUMNS), parent)
        self.setHorizontalHeaderLabels(self.COLUMNS)

    def populate(self, runners, event):
        self.setRowCount(0)
        for r in runners:
            club = event.clubs.get(r.club_id)
            cls  = event.classes.get(r.class_id)
            rt   = r.get_running_time()
            row = [
                QStandardItem(str(r.start_no)),
                QStandardItem(r.first_name),
                QStandardItem(r.last_name),
                QStandardItem(club.name if club else ""),
                QStandardItem(cls.name  if cls  else ""),
                QStandardItem(str(r.card_number) if r.card_number else ""),
                QStandardItem(format_time(r.start_time)),
                QStandardItem(format_time(r.finish_time)),
                QStandardItem(format_time(rt) if rt != NO_TIME else ""),
                QStandardItem(r.status.to_code()),
                QStandardItem(str(r.place) if r.place else ""),
            ]
            for item in row:
                item.setData(r.id, Qt.UserRole)
                item.setEditable(False)
            self.appendRow(row)


class TabRunner(TabBase):
    def __init__(self, controller, parent=None):
        super().__init__(controller, parent)
        self._build_ui()
        self.ctrl.runner_updated.connect(self._on_runner_updated)
        self.ctrl.event_loaded.connect(self.load_page)

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self):
        layout = QVBoxLayout(self)

        # ---- Toolbar ---------------------------------------------------
        toolbar = QHBoxLayout()

        self._search = QLineEdit()
        self._search.setPlaceholderText("Search name / card…")
        self._search.textChanged.connect(self._apply_filter)
        toolbar.addWidget(QLabel("Search:"))
        toolbar.addWidget(self._search)

        self._class_combo = QComboBox()
        self._class_combo.addItem("All classes", 0)
        self._class_combo.currentIndexChanged.connect(self._apply_filter)
        toolbar.addWidget(QLabel("Class:"))
        toolbar.addWidget(self._class_combo)

        toolbar.addStretch()

        self._btn_add    = QPushButton("Add Runner")
        self._btn_edit   = QPushButton("Edit")
        self._btn_delete = QPushButton("Delete")
        self._btn_add.clicked.connect(self._add_runner)
        self._btn_edit.clicked.connect(self._edit_runner)
        self._btn_delete.clicked.connect(self._delete_runner)
        for btn in (self._btn_add, self._btn_edit, self._btn_delete):
            toolbar.addWidget(btn)

        layout.addLayout(toolbar)

        # ---- Table -----------------------------------------------------
        self._model = RunnerTableModel(self)
        self._proxy = QSortFilterProxyModel(self)
        self._proxy.setSourceModel(self._model)
        self._proxy.setFilterCaseSensitivity(Qt.CaseInsensitive)
        self._proxy.setFilterKeyColumn(-1)   # search all columns

        self._table = QTableView()
        self._table.setModel(self._proxy)
        self._table.setSortingEnabled(True)
        self._table.setSelectionBehavior(QTableView.SelectRows)
        self._table.setAlternatingRowColors(True)
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self._table.doubleClicked.connect(self._edit_runner)
        layout.addWidget(self._table)

        # ---- Status bar -----------------------------------------------
        self._lbl_count = QLabel()
        layout.addWidget(self._lbl_count)

    # ------------------------------------------------------------------
    # TabBase interface
    # ------------------------------------------------------------------

    def load_page(self):
        ev = self.ctrl.event

        # Rebuild class combo
        self._class_combo.blockSignals(True)
        self._class_combo.clear()
        self._class_combo.addItem("All classes", 0)
        for cls in sorted(ev.classes.values(), key=lambda c: c.name):
            if not cls.removed:
                self._class_combo.addItem(cls.name, cls.id)
        self._class_combo.blockSignals(False)

        self._refresh_table()

    def clear_competition_data(self):
        self._model.setRowCount(0)
        self._class_combo.clear()

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _refresh_table(self):
        ev = self.ctrl.event
        runners = [r for r in ev.runners.values() if not r.removed]
        runners.sort(key=lambda r: r.sort_name)
        self._model.populate(runners, ev)
        self._apply_filter()
        self._lbl_count.setText(f"{len(runners)} runner(s)")

    def _apply_filter(self):
        text = self._search.text().strip()
        class_id = self._class_combo.currentData() or 0
        if class_id:
            # Simple approach: rebuild with class filter
            ev = self.ctrl.event
            runners = [r for r in ev.runners.values()
                       if not r.removed and r.class_id == class_id]
            runners.sort(key=lambda r: r.sort_name)
            self._model.populate(runners, ev)
        self._proxy.setFilterFixedString(text)

    def _selected_runner_id(self) -> int:
        idx = self._table.currentIndex()
        if not idx.isValid():
            return 0
        src = self._proxy.mapToSource(idx)
        item = self._model.item(src.row(), 0)
        return item.data(Qt.UserRole) if item else 0

    def _on_runner_updated(self, runner_id: int):
        self._refresh_table()

    # ------------------------------------------------------------------
    # CRUD actions
    # ------------------------------------------------------------------

    def _add_runner(self):
        dlg = RunnerDialog(self.ctrl.event, parent=self)
        if dlg.exec() == QDialog.Accepted:
            d = dlg.get_data()
            self.ctrl.add_runner(
                d["first_name"], d["last_name"],
                d["club_name"], d["class_name"], d["card_number"]
            )
            self._refresh_table()

    def _edit_runner(self):
        rid = self._selected_runner_id()
        if not rid:
            return
        runner = self.ctrl.event.runners.get(rid)
        if runner is None:
            return
        dlg = RunnerDialog(self.ctrl.event, runner=runner, parent=self)
        if dlg.exec() == QDialog.Accepted:
            d = dlg.get_data()
            runner.first_name  = d["first_name"]
            runner.last_name   = d["last_name"]
            runner.card_number = d["card_number"]
            runner.mark_changed()
            self._refresh_table()

    def _delete_runner(self):
        rid = self._selected_runner_id()
        if not rid:
            return
        runner = self.ctrl.event.runners.get(rid)
        if runner is None:
            return
        if not runner.can_remove():
            QMessageBox.warning(self, "Cannot Delete",
                                "Runner is part of a team and cannot be deleted.")
            return
        if QMessageBox.question(
            self, "Delete Runner",
            f"Delete {runner.name}?",
            QMessageBox.Yes | QMessageBox.No
        ) == QMessageBox.Yes:
            self.ctrl.delete_runner(rid)
            self._refresh_table()


# ---------------------------------------------------------------------------
# Runner editor dialog
# ---------------------------------------------------------------------------

class RunnerDialog(QDialog):
    def __init__(self, event, runner=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Runner" if runner is None else "Edit Runner")
        self._event  = event
        self._runner = runner
        self._build_ui()
        if runner:
            self._populate(runner)

    def _build_ui(self):
        layout = QFormLayout(self)

        self._first = QLineEdit()
        self._last  = QLineEdit()
        self._club  = QComboBox()
        self._club.setEditable(True)
        self._class = QComboBox()
        self._class.setEditable(True)
        self._card  = QSpinBox()
        self._card.setMaximum(9_999_999)

        layout.addRow("First name:", self._first)
        layout.addRow("Last name:",  self._last)
        layout.addRow("Club:",       self._club)
        layout.addRow("Class:",      self._class)
        layout.addRow("SI card:",    self._card)

        # Populate combos
        for club in sorted(self._event.clubs.values(), key=lambda c: c.name):
            if not club.removed:
                self._club.addItem(club.name)
        for cls in sorted(self._event.classes.values(), key=lambda c: c.name):
            if not cls.removed:
                self._class.addItem(cls.name)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def _populate(self, r: Runner):
        self._first.setText(r.first_name)
        self._last.setText(r.last_name)
        self._card.setValue(r.card_number)
        club = self._event.clubs.get(r.club_id)
        if club:
            self._club.setCurrentText(club.name)
        cls = self._event.classes.get(r.class_id)
        if cls:
            self._class.setCurrentText(cls.name)

    def get_data(self) -> dict:
        return {
            "first_name":  self._first.text().strip(),
            "last_name":   self._last.text().strip(),
            "club_name":   self._club.currentText().strip(),
            "class_name":  self._class.currentText().strip(),
            "card_number": self._card.value(),
        }
