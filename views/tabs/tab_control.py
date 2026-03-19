"""
views/tabs/tab_control.py
=========================
Control-point management tab (TabControl equivalent).

Features:
  • Table of all controls with SI station numbers
  • Add / Edit / Delete controls
  • Status (OK, Bad, Start, Finish, Rogaining…)
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QPushButton, QTableView,
    QLineEdit, QLabel, QComboBox, QHeaderView, QMessageBox,
    QDialog, QFormLayout, QDialogButtonBox, QSpinBox,
)
from PySide6.QtGui import QStandardItemModel, QStandardItem

from models import Control, ControlStatus
from .tab_base import TabBase


_STATUS_LABELS = {
    ControlStatus.OK:         "OK",
    ControlStatus.Bad:        "Bad",
    ControlStatus.Multiple:   "Multiple",
    ControlStatus.Start:      "Start",
    ControlStatus.Finish:     "Finish",
    ControlStatus.Rogaining:  "Rogaining",
    ControlStatus.NoTiming:   "No Timing",
    ControlStatus.Optional:   "Optional",
    ControlStatus.Check:      "Check",
}


class ControlTableModel(QStandardItemModel):
    COLUMNS = ["ID", "Name", "SI Numbers", "Status", "Time Adj."]

    def __init__(self, parent=None):
        super().__init__(0, len(self.COLUMNS), parent)
        self.setHorizontalHeaderLabels(self.COLUMNS)

    def populate(self, controls):
        self.setRowCount(0)
        for c in controls:
            row = [
                QStandardItem(str(c.id)),
                QStandardItem(c.name),
                QStandardItem(c.numbers_as_string()),
                QStandardItem(_STATUS_LABELS.get(c.status, c.status.name)),
                QStandardItem(str(c.time_adjustment) if c.time_adjustment else ""),
            ]
            for item in row:
                item.setData(c.id, Qt.UserRole)
                item.setEditable(False)
            self.appendRow(row)


class TabControl(TabBase):
    def __init__(self, controller, parent=None):
        super().__init__(controller, parent)
        self._build_ui()
        self.ctrl.event_loaded.connect(self.load_page)

    def _build_ui(self):
        layout = QVBoxLayout(self)

        toolbar = QHBoxLayout()
        self._search = QLineEdit()
        self._search.setPlaceholderText("Search name / number…")
        self._search.textChanged.connect(self._refresh_table)
        toolbar.addWidget(QLabel("Search:")); toolbar.addWidget(self._search)
        toolbar.addStretch()

        self._btn_add    = QPushButton("Add Control")
        self._btn_edit   = QPushButton("Edit")
        self._btn_delete = QPushButton("Delete")
        self._btn_add.clicked.connect(self._add_control)
        self._btn_edit.clicked.connect(self._edit_control)
        self._btn_delete.clicked.connect(self._delete_control)
        for btn in (self._btn_add, self._btn_edit, self._btn_delete):
            toolbar.addWidget(btn)
        layout.addLayout(toolbar)

        self._model = ControlTableModel(self)
        self._table = QTableView()
        self._table.setModel(self._model)
        self._table.setSelectionBehavior(QTableView.SelectRows)
        self._table.setAlternatingRowColors(True)
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self._table.doubleClicked.connect(self._edit_control)
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
        ctrls = [c for c in ev.controls.values() if not c.removed]
        if text:
            ctrls = [c for c in ctrls if
                     text in c.name.lower() or
                     any(text in str(n) for n in c.numbers)]
        ctrls.sort(key=lambda c: (c.min_number(), c.name))
        self._model.populate(ctrls)
        self._lbl_count.setText(f"{len(ctrls)} control(s)")

    def _selected_control_id(self) -> int:
        idx  = self._table.currentIndex()
        if not idx.isValid():
            return 0
        item = self._model.item(idx.row(), 0)
        return item.data(Qt.UserRole) if item else 0

    def _add_control(self):
        dlg = ControlDialog(parent=self)
        if dlg.exec() == QDialog.Accepted:
            d = dlg.get_data()
            ctrl = self.ctrl.event.add_control(d["name"])
            ctrl.set_numbers_from_string(d["numbers"])
            ctrl.status = d["status"]
            ctrl.time_adjustment = d["time_adj"]
            self._refresh_table()

    def _edit_control(self):
        cid  = self._selected_control_id()
        if not cid:
            return
        ctrl = self.ctrl.event.controls.get(cid)
        if ctrl is None:
            return
        dlg = ControlDialog(control=ctrl, parent=self)
        if dlg.exec() == QDialog.Accepted:
            d = dlg.get_data()
            ctrl.name = d["name"]
            ctrl.set_numbers_from_string(d["numbers"])
            ctrl.status = d["status"]
            ctrl.time_adjustment = d["time_adj"]
            ctrl.mark_changed()
            self._refresh_table()

    def _delete_control(self):
        cid  = self._selected_control_id()
        if not cid:
            return
        ctrl = self.ctrl.event.controls.get(cid)
        if ctrl is None:
            return
        if not ctrl.can_remove():
            QMessageBox.warning(self, "Cannot Delete",
                                "This control is used by one or more courses.")
            return
        if QMessageBox.question(
            self, "Delete Control", f"Delete control '{ctrl.name}'?",
            QMessageBox.Yes | QMessageBox.No
        ) == QMessageBox.Yes:
            self.ctrl.event.remove_control(cid)
            self._refresh_table()


class ControlDialog(QDialog):
    def __init__(self, control: Control = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add Control" if control is None else "Edit Control")
        self._build_ui()
        if control:
            self._populate(control)

    def _build_ui(self):
        layout = QFormLayout(self)

        self._name    = QLineEdit()
        self._numbers = QLineEdit()
        self._numbers.setPlaceholderText("e.g. 31, 131")
        self._status  = QComboBox()
        for status, label in _STATUS_LABELS.items():
            self._status.addItem(label, status)
        self._time_adj = QSpinBox()
        self._time_adj.setRange(-9999, 9999)
        self._time_adj.setSuffix(" (0.1s units)")

        layout.addRow("Name:",           self._name)
        layout.addRow("SI Numbers:",     self._numbers)
        layout.addRow("Status:",         self._status)
        layout.addRow("Time adj. (0.1s):", self._time_adj)

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addRow(btns)

    def _populate(self, c: Control):
        self._name.setText(c.name)
        self._numbers.setText(c.numbers_as_string())
        idx = self._status.findData(c.status)
        if idx >= 0:
            self._status.setCurrentIndex(idx)
        self._time_adj.setValue(c.time_adjustment)

    def get_data(self) -> dict:
        return {
            "name":     self._name.text().strip(),
            "numbers":  self._numbers.text().strip(),
            "status":   self._status.currentData(),
            "time_adj": self._time_adj.value(),
        }
