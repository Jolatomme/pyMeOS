"""
views/tabs/tab_course.py
========================
Course management tab (TabCourse equivalent).
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout, QVBoxLayout, QSplitter, QListWidget, QListWidgetItem,
    QPushButton, QGroupBox, QFormLayout, QLineEdit, QSpinBox,
    QLabel, QMessageBox, QWidget, QTableWidget, QTableWidgetItem,
    QHeaderView, QAbstractItemView
)

from .tab_base import TabBase
from utils.localizer import trs


class TabCourse(TabBase):

    def __init__(self, controller, parent=None):
        super().__init__(controller, parent)
        self._current_id: int = 0
        self._building = False
        self._build_ui()

    def _build_ui(self) -> None:
        root = QHBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # ---- Left list -----------------------------------------------
        left = QWidget()
        lv   = QVBoxLayout(left)
        lv.setContentsMargins(0, 0, 0, 0)
        self._list = QListWidget()
        self._list.currentRowChanged.connect(self._on_select)
        lv.addWidget(QLabel(trs("Courses") + ":"))
        lv.addWidget(self._list)
        btn_row = QHBoxLayout()
        self._btn_add = QPushButton(trs("Add"))
        self._btn_del = QPushButton(trs("Delete"))
        btn_row.addWidget(self._btn_add)
        btn_row.addWidget(self._btn_del)
        btn_row.addStretch()
        lv.addLayout(btn_row)
        splitter.addWidget(left)

        # ---- Right form ----------------------------------------------
        right = QWidget()
        rv    = QVBoxLayout(right)
        rv.setContentsMargins(0, 0, 0, 0)

        grp = QGroupBox(trs("Course"))
        form = QFormLayout(grp)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        self._ed_name   = QLineEdit()
        self._sp_length = QSpinBox(); self._sp_length.setRange(0, 99999); self._sp_length.setSuffix(" m")
        self._sp_climb  = QSpinBox(); self._sp_climb.setRange(0, 9999);   self._sp_climb.setSuffix(" m")
        form.addRow(trs("Name") + ":",   self._ed_name)
        form.addRow("Length:",  self._sp_length)
        form.addRow("Climb:",   self._sp_climb)
        rv.addWidget(grp)

        # Control sequence table
        rv.addWidget(QLabel("Controls (in order):"))
        self._tbl = QTableWidget(0, 2)
        self._tbl.setHorizontalHeaderLabels(["#", "Control code"])
        self._tbl.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch)
        self._tbl.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows)
        rv.addWidget(self._tbl)

        tbl_btn_row = QHBoxLayout()
        self._btn_ctrl_add = QPushButton("Add control")
        self._btn_ctrl_del = QPushButton("Remove")
        tbl_btn_row.addWidget(self._btn_ctrl_add)
        tbl_btn_row.addWidget(self._btn_ctrl_del)
        tbl_btn_row.addStretch()
        rv.addLayout(tbl_btn_row)

        btn_apply = QPushButton(trs("Save"))
        btn_apply.clicked.connect(self._apply)
        rv.addWidget(btn_apply, alignment=Qt.AlignmentFlag.AlignRight)

        splitter.addWidget(right)
        splitter.setSizes([200, 500])
        root.addWidget(splitter)

        self._btn_add.clicked.connect(self._add_course)
        self._btn_del.clicked.connect(self._delete_course)
        self._btn_ctrl_add.clicked.connect(self._add_ctrl_row)
        self._btn_ctrl_del.clicked.connect(self._del_ctrl_row)

    # ------------------------------------------------------------------
    def load_page(self) -> None:
        self._building = True
        self._list.clear()
        for c in sorted(self.ctrl.event.courses.values(), key=lambda x: x.name):
            if c.removed:
                continue
            item = QListWidgetItem(c.name)
            item.setData(Qt.ItemDataRole.UserRole, c.id)
            self._list.addItem(item)
        self._building = False
        if self._list.count():
            self._list.setCurrentRow(0)

    def clear_competition_data(self) -> None:
        self._list.clear()
        self._current_id = 0

    def _on_select(self, row: int) -> None:
        if self._building or row < 0:
            return
        item = self._list.item(row)
        if not item:
            return
        cid = item.data(Qt.ItemDataRole.UserRole)
        self._current_id = cid
        self._populate_form(cid)

    def _populate_form(self, course_id: int) -> None:
        c = self.ctrl.event.courses.get(course_id)
        if c is None:
            return
        self._building = True
        self._ed_name.setText(c.name)
        self._sp_length.setValue(c.length)
        self._sp_climb.setValue(c.climb)

        self._tbl.setRowCount(0)
        ev = self.ctrl.event
        for i, ctrl_id in enumerate(c.control_ids):
            ctrl = ev.controls.get(ctrl_id)
            code_str = ctrl.numbers_as_string() if ctrl else str(ctrl_id)
            self._tbl.insertRow(i)
            self._tbl.setItem(i, 0, QTableWidgetItem(str(i + 1)))
            self._tbl.setItem(i, 1, QTableWidgetItem(code_str))
        self._building = False

    def _apply(self) -> None:
        c = self.ctrl.event.courses.get(self._current_id)
        if c is None:
            return
        c.name   = self._ed_name.text().strip()
        c.length = self._sp_length.value()
        c.climb  = self._sp_climb.value()
        # Rebuild control_ids from table
        new_ids: list[int] = []
        ev = self.ctrl.event
        for row in range(self._tbl.rowCount()):
            code_item = self._tbl.item(row, 1)
            if code_item:
                code_str = code_item.text().strip()
                try:
                    code = int(code_str)
                    ctrl = ev.add_control(str(code), numbers=[code]) if not any(
                        ct.has_number(code) for ct in ev.controls.values()
                    ) else next(ct for ct in ev.controls.values() if ct.has_number(code))
                    new_ids.append(ctrl.id)
                except ValueError:
                    pass
        c.control_ids = new_ids
        c.mark_changed()
        item = self._list.currentItem()
        if item:
            item.setText(c.name)

    def _add_course(self) -> None:
        c = self.ctrl.event.add_course("New course")
        item = QListWidgetItem(c.name)
        item.setData(Qt.ItemDataRole.UserRole, c.id)
        self._list.addItem(item)
        self._list.setCurrentItem(item)

    def _delete_course(self) -> None:
        row = self._list.currentRow()
        if row < 0:
            return
        item = self._list.item(row)
        cid = item.data(Qt.ItemDataRole.UserRole)
        if not self.ctrl.event.courses[cid].can_remove():
            QMessageBox.warning(self, trs("Warning"),
                                "Course is in use and cannot be deleted.")
            return
        self.ctrl.event.remove_course(cid)
        self._list.takeItem(row)

    def _add_ctrl_row(self) -> None:
        row = self._tbl.rowCount()
        self._tbl.insertRow(row)
        self._tbl.setItem(row, 0, QTableWidgetItem(str(row + 1)))
        self._tbl.setItem(row, 1, QTableWidgetItem(""))

    def _del_ctrl_row(self) -> None:
        row = self._tbl.currentRow()
        if row >= 0:
            self._tbl.removeRow(row)
            for i in range(self._tbl.rowCount()):
                self._tbl.setItem(i, 0, QTableWidgetItem(str(i + 1)))
