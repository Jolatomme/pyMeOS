"""
views/tabs/tab_runner.py
========================
Runner management tab (TabRunner equivalent).

Features:
   Table of all runners (sortable)
   Add / Edit / Delete runner dialog
   Manual time/status entry
   Search / filter by class, club, name
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
from utils.icon_utils import get_icon
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
        self._search.setPlaceholderText("Search name / card...")
        self._search.textChanged.connect(self._apply_filter)
        toolbar.addWidget(QLabel("Search:"))
        toolbar.addWidget(self._search)

        self._class_combo = QComboBox()
        self._class_combo.addItem("All classes", 0)
        self._class_combo.currentIndexChanged.connect(self._apply_filter)
        toolbar.addWidget(QLabel("Class:"))
        toolbar.addWidget(self._class_combo)

        toolbar.addStretch()

        self._btn_add    = QPushButton(get_icon("actions/add"),    "Add Runner")
        self._btn_edit   = QPushButton(get_icon("actions/edit"),   "Edit")
        self._btn_delete = QPushButton(get_icon("actions/delete"), "Delete")
        self._btn_add.clicked.connect(self._add_runner)
        self._btn_edit.clicked.connect(self._edit_runner)
        self._btn_delete.clicked.connect(self._delete_runner)
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

        # Set column widths
        self._table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents)
        self._table.horizontalHeader().setMinimumSectionSize(60)

        # Set model
        self._model = RunnerTableModel(self)
        self._proxy = QSortFilterProxyModel(self)
        self._proxy.setSourceModel(self._model)
        self._proxy.setFilterKeyColumn(-1)  # Search all columns
        self._table.setModel(self._proxy)

        # Connect double-click to edit
        self._table.doubleClicked.connect(self._on_table_double_clicked)

        layout.addWidget(self._table)

    # ------------------------------------------------------------------
    # Load / Refresh
    # ------------------------------------------------------------------

    def load_page(self) -> None:
        self._model.populate(
            [r for r in self.ctrl.event.runners.values() if not r.removed],
            self.ctrl.event)
        self._refresh_class_combo()
        self._apply_filter()

    def _refresh_class_combo(self):
        self._class_combo.clear()
        self._class_combo.addItem("All classes", 0)
        for cls in self.ctrl.event.classes.values():
            if not cls.removed:
                self._class_combo.addItem(cls.name, cls.id)

    def _apply_filter(self):
        text = self._search.text().lower()
        class_id = self._class_combo.currentData()

        # Filter by text
        if text:
            self._proxy.setFilterRegularExpression(text)
        else:
            self._proxy.setFilterRegularExpression("")

        # Filter by class (implemented via custom filtering)
        if class_id:
            self._table.setRowHidden(
                row, self._model.index(row, 0).data(Qt.UserRole),
                lambda runner_id, class_id: (
                    self.ctrl.event.runners.get(runner_id, {}).class_id != class_id
                )
            )

    def _on_runner_updated(self, runner_id: int):
        self.load_page()

    def _on_table_double_clicked(self, index):
        proxy_index = self._proxy.mapToSource(index)
        runner_id = self._model.index(proxy_index.row(), 0).data(Qt.UserRole)
        self._edit_runner(runner_id)

    # ------------------------------------------------------------------
    # Runner dialogs
    # ------------------------------------------------------------------

    def _add_runner(self):
        dlg = RunnerDialog(self.ctrl.event, self)
        if dlg.exec() == QDialog.Accepted:
            self.ctrl.add_runner(
                dlg.first_name.text(),
                dlg.last_name.text(),
                dlg.club_combo.currentText(),
                dlg.class_combo.currentText(),
                int(dlg.card_spin.value()) if dlg.card_spin.value() else 0)

    def _edit_runner(self, runner_id: int = None):
        if runner_id is None:
            selected = self._table.selectionModel().selectedRows()
            if not selected:
                return
            proxy_index = selected[0]
            source_index = self._proxy.mapToSource(proxy_index)
            runner_id = self._model.index(source_index.row(), 0).data(Qt.UserRole)

        runner = self.ctrl.event.runners.get(runner_id)
        if not runner:
            return

        dlg = RunnerDialog(self.ctrl.event, self, runner)
        if dlg.exec() == QDialog.Accepted:
            runner.first_name = dlg.first_name.text()
            runner.last_name = dlg.last_name.text()
            runner.card_number = int(dlg.card_spin.value()) if dlg.card_spin.value() else 0
            # Update club and class
            club = self.ctrl.event.get_club_by_name(dlg.club_combo.currentText())
            cls = self.ctrl.event.get_class_by_name(dlg.class_combo.currentText())
            if club:
                runner.club_id = club.id
            if cls:
                runner.class_id = cls.id
            runner.mark_changed()
            self.ctrl.event._notify("runners_changed", runner)

    def _delete_runner(self):
        selected = self._table.selectionModel().selectedRows()
        if not selected:
            return
        proxy_index = selected[0]
        source_index = self._proxy.mapToSource(proxy_index)
        runner_id = self._model.index(source_index.row(), 0).data(Qt.UserRole)

        runner = self.ctrl.event.runners.get(runner_id)
        if runner:
            reply = QMessageBox.question(
                self, "Delete Runner",
                f"Delete {runner.name}?",
                QMessageBox.Yes | QMessageBox.No)
            if reply == QMessageBox.Yes:
                self.ctrl.delete_runner(runner_id)


class RunnerDialog(QDialog):
    def __init__(self, event, parent=None, runner=None):
        super().__init__(parent)
        self.setWindowTitle("Add Runner" if not runner else "Edit Runner")
        self._build_ui(event, runner)

    def _build_ui(self, event, runner):
        layout = QFormLayout(self)

        self.first_name = QLineEdit()
        self.last_name = QLineEdit()
        self.club_combo = QComboBox()
        self.class_combo = QComboBox()
        self.card_spin = QSpinBox()
        self.card_spin.setRange(0, 9_999_999)

        # Populate combos
        for club in event.clubs.values():
            if not club.removed:
                self.club_combo.addItem(club.name)
        for cls in event.classes.values():
            if not cls.removed:
                self.class_combo.addItem(cls.name)

        # Set values
        if runner:
            self.first_name.setText(runner.first_name)
            self.last_name.setText(runner.last_name)
            self.card_spin.setValue(runner.card_number or 0)
            club = event.clubs.get(runner.club_id)
            if club:
                self.club_combo.setCurrentText(club.name)
            cls = event.classes.get(runner.class_id)
            if cls:
                self.class_combo.setCurrentText(cls.name)

        layout.addRow("First Name:", self.first_name)
        layout.addRow("Last Name:", self.last_name)
        layout.addRow("Club:", self.club_combo)
        layout.addRow("Class:", self.class_combo)
        layout.addRow("Card Number:", self.card_spin)

        # Buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)
