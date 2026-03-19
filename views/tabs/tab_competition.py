"""
views/tabs/tab_competition.py
=============================
Competition settings tab (TabCompetition equivalent).

Allows creating, opening, saving events and editing event metadata
(name, date, organiser, zero time, currency, etc.).
"""
from __future__ import annotations

import os
from pathlib import Path

from PySide6.QtCore import Qt, QDate
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QFormLayout,
    QLineEdit, QPushButton, QDateEdit, QTimeEdit, QLabel,
    QFileDialog, QMessageBox, QComboBox, QSpinBox, QSizePolicy,
    QScrollArea, QFrame
)
from PySide6.QtCore import QTime

from .tab_base import TabBase
from utils.localizer import trs
from utils.time_utils import parse_time, format_time


class TabCompetition(TabBase):
    """Event metadata editor + new/open/save actions."""

    def __init__(self, controller, parent=None):
        super().__init__(controller, parent)
        self._building = False
        self._build_ui()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(10)

        # --- Action buttons row ----------------------------------------
        btn_row = QHBoxLayout()
        self._btn_new    = QPushButton(trs("New"))
        self._btn_open   = QPushButton(trs("Open") + "…")
        self._btn_save   = QPushButton(trs("Save"))
        self._btn_saveas = QPushButton(trs("Save") + " as…")
        for b in (self._btn_new, self._btn_open, self._btn_save, self._btn_saveas):
            b.setFixedWidth(120)
            btn_row.addWidget(b)
        btn_row.addStretch()
        root.addLayout(btn_row)

        # --- Scroll area -----------------------------------------------
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        inner = QWidget()
        scroll.setWidget(inner)
        root.addWidget(scroll)

        inner_layout = QVBoxLayout(inner)
        inner_layout.setContentsMargins(0, 0, 0, 0)
        inner_layout.setSpacing(14)

        # --- Event metadata group --------------------------------------
        grp_meta = QGroupBox(trs("Competition"))
        form = QFormLayout(grp_meta)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)

        self._edit_name = QLineEdit()
        self._edit_annotation = QLineEdit()
        self._edit_organiser  = QLineEdit()
        self._date_edit = QDateEdit()
        self._date_edit.setCalendarPopup(True)
        self._date_edit.setDisplayFormat("yyyy-MM-dd")
        self._zero_time_edit = QTimeEdit()
        self._zero_time_edit.setDisplayFormat("HH:mm:ss")

        form.addRow(trs("EventName") + ":", self._edit_name)
        form.addRow(trs("EventDate") + ":", self._date_edit)
        form.addRow(trs("EventOrganiser") + ":", self._edit_organiser)
        form.addRow(trs("ZeroTime") + ":", self._zero_time_edit)
        form.addRow("Annotation:", self._edit_annotation)
        inner_layout.addWidget(grp_meta)

        # --- Currency group -------------------------------------------
        grp_curr = QGroupBox("Currency")
        form_curr = QFormLayout(grp_curr)
        self._edit_currency = QLineEdit()
        self._edit_currency.setMaximumWidth(80)
        form_curr.addRow("Currency code:", self._edit_currency)
        inner_layout.addWidget(grp_curr)

        inner_layout.addStretch()

        # --- Apply button ---------------------------------------------
        btn_apply = QPushButton(trs("Save"))
        btn_apply.setFixedWidth(120)
        btn_apply.clicked.connect(self._apply)
        root.addWidget(btn_apply, alignment=Qt.AlignmentFlag.AlignRight)

        # --- Signals --------------------------------------------------
        self._btn_new.clicked.connect(self._new_event)
        self._btn_open.clicked.connect(self._open_event)
        self._btn_save.clicked.connect(self._save_event)
        self._btn_saveas.clicked.connect(self._save_as_event)

    # ------------------------------------------------------------------
    # TabBase interface
    # ------------------------------------------------------------------

    def load_page(self) -> None:
        self._building = True
        ev = self.ctrl.event
        self._edit_name.setText(ev.name)
        self._edit_annotation.setText(ev.annotation)
        self._edit_organiser.setText(ev.organiser)
        self._edit_currency.setText(ev.currency)

        if ev.date:
            self._date_edit.setDate(QDate.fromString(ev.date, "yyyy-MM-dd"))
        else:
            self._date_edit.setDate(QDate.currentDate())

        zt = ev.zero_time
        h  = zt // (3600 * 10)
        m  = (zt % (3600 * 10)) // (60 * 10)
        s  = (zt % (60 * 10)) // 10
        self._zero_time_edit.setTime(QTime(h, m, s))

        self._building = False

    def clear_competition_data(self) -> None:
        pass

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def _apply(self) -> None:
        ev = self.ctrl.event
        ev.name        = self._edit_name.text().strip()
        ev.annotation  = self._edit_annotation.text().strip()
        ev.organiser   = self._edit_organiser.text().strip()
        ev.currency    = self._edit_currency.text().strip() or "SEK"
        ev.date        = self._date_edit.date().toString("yyyy-MM-dd")
        t = self._zero_time_edit.time()
        ev.zero_time   = (t.hour() * 3600 + t.minute() * 60 + t.second()) * 10
        ev.mark_changed()
        QMessageBox.information(self, trs("Info"), "Event metadata saved.")

    def _new_event(self) -> None:
        if QMessageBox.question(
            self, trs("New"), "Create a new event? Unsaved changes will be lost.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        ) != QMessageBox.StandardButton.Yes:
            return
        self.ctrl.new_event()
        self.load_page()

    def _open_event(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, trs("Open"), "",
            "MeOS XML (*.xml);;All Files (*)"
        )
        if path:
            try:
                self.ctrl.load_from_xml(path)
                self.load_page()
            except Exception as exc:
                QMessageBox.critical(self, trs("Error"), str(exc))

    def _save_event(self) -> None:
        path = self.ctrl.event.current_file
        if not path:
            self._save_as_event()
            return
        try:
            self.ctrl.save_to_xml(path)
        except Exception as exc:
            QMessageBox.critical(self, trs("Error"), str(exc))

    def _save_as_event(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, trs("Save") + " as", "",
            "MeOS XML (*.xml);;All Files (*)"
        )
        if path:
            try:
                self.ctrl.save_to_xml(path)
                self.ctrl.event.current_file = path
            except Exception as exc:
                QMessageBox.critical(self, trs("Error"), str(exc))
