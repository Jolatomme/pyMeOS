"""
views/tabs/tab_class.py
=======================
Class management tab (TabClass equivalent).
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout, QVBoxLayout, QSplitter, QListWidget, QListWidgetItem,
    QPushButton, QGroupBox, QFormLayout, QLineEdit, QComboBox,
    QSpinBox, QCheckBox, QLabel, QMessageBox, QWidget
)

from .tab_base import TabBase
from models.enums import ClassType, StartType
from utils.localizer import trs
from utils.time_utils import format_time, parse_time


class TabClass(TabBase):

    def __init__(self, controller, parent=None):
        super().__init__(controller, parent)
        self._current_id: int = 0
        self._building = False
        self._build_ui()

    # ------------------------------------------------------------------
    # Build UI
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        root = QHBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        # ---- Left: list + buttons -----------------------------------
        left = QWidget()
        lv   = QVBoxLayout(left)
        lv.setContentsMargins(0, 0, 0, 0)

        self._list = QListWidget()
        self._list.currentRowChanged.connect(self._on_select)
        lv.addWidget(QLabel(trs("Classes") + ":"))
        lv.addWidget(self._list)

        btn_row = QHBoxLayout()
        self._btn_add = QPushButton(trs("Add"))
        self._btn_del = QPushButton(trs("Delete"))
        btn_row.addWidget(self._btn_add)
        btn_row.addWidget(self._btn_del)
        btn_row.addStretch()
        lv.addLayout(btn_row)
        splitter.addWidget(left)

        # ---- Right: detail form -------------------------------------
        right = QWidget()
        rv    = QVBoxLayout(right)
        rv.setContentsMargins(0, 0, 0, 0)

        grp = QGroupBox(trs("Class"))
        form = QFormLayout(grp)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self._ed_name         = QLineEdit()
        self._cb_type         = QComboBox()
        for ct in ClassType:
            self._cb_type.addItem(ct.value.capitalize(), ct)
        self._cb_start_type   = QComboBox()
        for st in StartType:
            self._cb_start_type.addItem(st.name, st)
        self._ed_first_start  = QLineEdit()
        self._ed_first_start.setPlaceholderText("H:MM:SS")
        self._sp_interval     = QSpinBox()
        self._sp_interval.setRange(0, 99999)
        self._sp_interval.setSuffix(" s")
        self._sp_fee          = QSpinBox()
        self._sp_fee.setRange(0, 999999)
        self._chk_no_timing   = QCheckBox()

        form.addRow(trs("Name") + ":",         self._ed_name)
        form.addRow("Type:",                    self._cb_type)
        form.addRow("Start type:",              self._cb_start_type)
        form.addRow("First start:",             self._ed_first_start)
        form.addRow("Interval (s):",            self._sp_interval)
        form.addRow("Entry fee:",               self._sp_fee)
        form.addRow("No timing:",               self._chk_no_timing)
        rv.addWidget(grp)

        btn_apply = QPushButton(trs("Save"))
        btn_apply.clicked.connect(self._apply)
        rv.addWidget(btn_apply, alignment=Qt.AlignmentFlag.AlignRight)
        rv.addStretch()
        splitter.addWidget(right)
        splitter.setSizes([200, 400])
        root.addWidget(splitter)

        # Signals
        self._btn_add.clicked.connect(self._add_class)
        self._btn_del.clicked.connect(self._delete_class)

    # ------------------------------------------------------------------
    # TabBase
    # ------------------------------------------------------------------

    def load_page(self) -> None:
        self._building = True
        self._list.clear()
        ev = self.ctrl.event
        for cls in sorted(ev.classes.values(), key=lambda c: c.name):
            if cls.removed:
                continue
            item = QListWidgetItem(cls.name)
            item.setData(Qt.ItemDataRole.UserRole, cls.id)
            self._list.addItem(item)
        self._building = False
        if self._list.count():
            self._list.setCurrentRow(0)

    def clear_competition_data(self) -> None:
        self._list.clear()
        self._current_id = 0

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def _on_select(self, row: int) -> None:
        if self._building or row < 0:
            return
        item = self._list.item(row)
        if item is None:
            return
        cid = item.data(Qt.ItemDataRole.UserRole)
        self._current_id = cid
        self._populate_form(cid)

    def _populate_form(self, class_id: int) -> None:
        cls = self.ctrl.event.classes.get(class_id)
        if cls is None:
            return
        self._building = True
        self._ed_name.setText(cls.name)
        idx = self._cb_type.findData(cls.class_type)
        if idx >= 0:
            self._cb_type.setCurrentIndex(idx)
        idx = self._cb_start_type.findData(cls.start_type)
        if idx >= 0:
            self._cb_start_type.setCurrentIndex(idx)
        self._ed_first_start.setText(format_time(cls.first_start))
        self._sp_interval.setValue(cls.start_interval // 10)
        self._sp_fee.setValue(cls.entry_fee)
        self._chk_no_timing.setChecked(cls.no_timing)
        self._building = False

    def _apply(self) -> None:
        cls = self.ctrl.event.classes.get(self._current_id)
        if cls is None:
            return
        cls.name         = self._ed_name.text().strip()
        cls.class_type   = self._cb_type.currentData()
        cls.start_type   = self._cb_start_type.currentData()
        cls.first_start  = parse_time(self._ed_first_start.text())
        cls.start_interval = self._sp_interval.value() * 10
        cls.entry_fee    = self._sp_fee.value()
        cls.no_timing    = self._chk_no_timing.isChecked()
        cls.mark_changed()
        # Refresh list label
        item = self._list.currentItem()
        if item:
            item.setText(cls.name)

    def _add_class(self) -> None:
        cls = self.ctrl.event.add_class("New class")
        item = QListWidgetItem(cls.name)
        item.setData(Qt.ItemDataRole.UserRole, cls.id)
        self._list.addItem(item)
        self._list.setCurrentItem(item)

    def _delete_class(self) -> None:
        row = self._list.currentRow()
        if row < 0:
            return
        item = self._list.item(row)
        if item is None:
            return
        cid = item.data(Qt.ItemDataRole.UserRole)
        if not self.ctrl.event.classes[cid].can_remove():
            QMessageBox.warning(self, trs("Warning"),
                                "Class is in use and cannot be deleted.")
            return
        self.ctrl.event.remove_class(cid)
        self._list.takeItem(row)
        self._current_id = 0
