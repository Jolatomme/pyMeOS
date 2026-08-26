"""
views/tabs/tab_class.py
======================
Class management tab (TabClass equivalent).

Features:
   Table of all classes
   Add / Edit / Delete class dialog
   Course assignment
"""
from __future__ import annotations

from PySide6.QtCore import Qt, QSortFilterProxyModel
from PySide6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QPushButton, QTableView,
    QLabel, QComboBox, QHeaderView, QMessageBox,
    QDialog, QFormLayout, QDialogButtonBox, QSpinBox,
)
from PySide6.QtGui import QStandardItemModel, QStandardItem

from models import Class, ClassType, StartType
from utils.icon_utils import get_icon
from .tab_base import TabBase


class ClassTableModel(QStandardItemModel):
    COLUMNS = ["ID", "Name", "Course", "Type", "Start Type", "First Start", "Interval"]

    def __init__(self, parent=None):
        super().__init__(0, len(self.COLUMNS), parent)
        self.setHorizontalHeaderLabels(self.COLUMNS)

    def populate(self, classes, event):
        self.setRowCount(0)
        for c in classes:
            course = event.courses.get(c.course_id)
            row = [
                QStandardItem(str(c.id)),
                QStandardItem(c.name),
                QStandardItem(course.name if course else ""),
                QStandardItem(c.type.name),
                QStandardItem(c.start_type.name),
                QStandardItem(str(c.first_start_time) if c.first_start_time else ""),
                QStandardItem(str(c.start_interval) if c.start_interval else ""),
            ]
            for item in row:
                item.setData(c.id, Qt.UserRole)
                item.setEditable(False)
            self.appendRow(row)


class TabClass(TabBase):
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
        toolbar.addStretch()

        self._btn_add    = QPushButton(get_icon("actions/add"),    "Add Class")
        self._btn_edit   = QPushButton(get_icon("actions/edit"),   "Edit")
        self._btn_delete = QPushButton(get_icon("actions/delete"), "Delete")
        self._btn_add.clicked.connect(self._add_class)
        self._btn_edit.clicked.connect(self._edit_class)
        self._btn_delete.clicked.connect(self._delete_class)
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

        self._model = ClassTableModel(self)
        self._proxy = QSortFilterProxyModel(self)
        self._proxy.setSourceModel(self._model)
        self._table.setModel(self._proxy)

        layout.addWidget(self._table)

    # ------------------------------------------------------------------
    # Load / Refresh
    # ------------------------------------------------------------------

    def load_page(self) -> None:
        self._model.populate(
            [c for c in self.ctrl.event.classes.values() if not c.removed],
            self.ctrl.event)

    # ------------------------------------------------------------------
    # Class dialogs
    # ------------------------------------------------------------------

    def _add_class(self):
        dlg = ClassDialog(self.ctrl.event, self)
        if dlg.exec() == QDialog.Accepted:
            self.ctrl.event.add_class(name=dlg.name.text())
            self.ctrl.event._notify("classes_changed", None)

    def _edit_class(self):
        selected = self._table.selectionModel().selectedRows()
        if not selected:
            return
        proxy_index = selected[0]
        source_index = self._proxy.mapToSource(proxy_index)
        class_id = self._model.index(source_index.row(), 0).data(Qt.UserRole)

        cls = self.ctrl.event.classes.get(class_id)
        if not cls:
            return

        dlg = ClassDialog(self.ctrl.event, self, cls)
        if dlg.exec() == QDialog.Accepted:
            cls.name = dlg.name.text()
            course = self.ctrl.event.get_course_by_name(dlg.course_combo.currentText())
            if course:
                cls.course_id = course.id
            cls.type = ClassType[dlg.type_combo.currentText()]
            cls.start_type = StartType[dlg.start_type_combo.currentText()]
            cls.first_start_time = dlg.first_start.value() * 10  # Convert to internal units
            cls.start_interval = dlg.interval.value() * 10
            cls.mark_changed()
            self.ctrl.event._notify("classes_changed", cls)

    def _delete_class(self):
        selected = self._table.selectionModel().selectedRows()
        if not selected:
            return
        proxy_index = selected[0]
        source_index = self._proxy.mapToSource(proxy_index)
        class_id = self._model.index(source_index.row(), 0).data(Qt.UserRole)

        cls = self.ctrl.event.classes.get(class_id)
        if cls:
            reply = QMessageBox.question(
                self, "Delete Class",
                f"Delete {cls.name}?",
                QMessageBox.Yes | QMessageBox.No)
            if reply == QMessageBox.Yes:
                self.ctrl.event.remove_class(class_id)


class ClassDialog(QDialog):
    def __init__(self, event, parent=None, cls=None):
        super().__init__(parent)
        self.setWindowTitle("Add Class" if not cls else "Edit Class")
        self._build_ui(event, cls)

    def _build_ui(self, event, cls):
        layout = QFormLayout(self)

        self.name = QLineEdit()
        self.course_combo = QComboBox()
        self.type_combo = QComboBox()
        self.start_type_combo = QComboBox()
        self.first_start = QSpinBox()
        self.first_start.setRange(0, 24 * 3600)  # 0 to 24 hours in seconds
        self.interval = QSpinBox()
        self.interval.setRange(0, 3600)  # 0 to 1 hour in seconds

        # Populate combos
        for course in event.courses.values():
            if not course.removed:
                self.course_combo.addItem(course.name)
        for t in ClassType:
            self.type_combo.addItem(t.name)
        for t in StartType:
            self.start_type_combo.addItem(t.name)

        # Set values
        if cls:
            self.name.setText(cls.name)
            course = event.courses.get(cls.course_id)
            if course:
                self.course_combo.setCurrentText(course.name)
            self.type_combo.setCurrentText(cls.type.name)
            self.start_type_combo.setCurrentText(cls.start_type.name)
            self.first_start.setValue(cls.first_start_time // 10 if cls.first_start_time else 0)
            self.interval.setValue(cls.start_interval // 10 if cls.start_interval else 0)

        layout.addRow("Name:", self.name)
        layout.addRow("Course:", self.course_combo)
        layout.addRow("Type:", self.type_combo)
        layout.addRow("Start Type:", self.start_type_combo)
        layout.addRow("First Start (s):", self.first_start)
        layout.addRow("Interval (s):", self.interval)

        # Buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)
