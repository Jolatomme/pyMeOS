"""
views/tabs/tab_speaker.py
=========================
Speaker / live-result monitor tab (TabSpeaker equivalent).

Displays a real-time feed of notable events: starts, radio splits,
finish times, and prognoses. Refreshes on a timer.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QComboBox, QTableWidget, QTableWidgetItem, QHeaderView,
    QSplitter, QTextEdit, QCheckBox,
)
from PySide6.QtGui import QColor, QFont

from models import RunnerStatus
from utils.time_utils import format_time, NO_TIME
from .tab_base import TabBase


_STATUS_COLOUR = {
    RunnerStatus.OK:              QColor("#c8ffc8"),
    RunnerStatus.MP:              QColor("#ffe0a0"),
    RunnerStatus.DNF:             QColor("#ffc8c8"),
    RunnerStatus.DQ:              QColor("#ffc8c8"),
    RunnerStatus.DNS:             QColor("#e0e0e0"),
    RunnerStatus.Unknown:         QColor("#ffffff"),
}


class TabSpeaker(TabBase):
    _REFRESH_MS = 3000   # refresh every 3 seconds

    def __init__(self, controller, parent=None):
        super().__init__(controller, parent)
        self._build_ui()
        self.ctrl.event_loaded.connect(self.load_page)
        self.ctrl.runner_updated.connect(self._on_runner_updated)

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._refresh)

    def _build_ui(self):
        main_layout = QVBoxLayout(self)

        # ---- top toolbar -----------------------------------------------
        toolbar = QHBoxLayout()

        self._class_combo = QComboBox()
        self._class_combo.addItem("All classes", 0)
        self._class_combo.currentIndexChanged.connect(self._refresh)
        toolbar.addWidget(QLabel("Class:"))
        toolbar.addWidget(self._class_combo)

        self._chk_auto = QCheckBox("Auto-refresh")
        self._chk_auto.setChecked(True)
        self._chk_auto.stateChanged.connect(self._toggle_timer)
        toolbar.addWidget(self._chk_auto)

        self._btn_refresh = QPushButton("Refresh Now")
        self._btn_refresh.clicked.connect(self._refresh)
        toolbar.addWidget(self._btn_refresh)
        toolbar.addStretch()

        self._lbl_last = QLabel("Last update: –")
        toolbar.addWidget(self._lbl_last)
        main_layout.addLayout(toolbar)

        # ---- splitter: live feed (top) + leaderboard (bottom) ----------
        splitter = QSplitter(Qt.Vertical)

        # Live feed table
        self._feed = QTableWidget(0, 5)
        self._feed.setHorizontalHeaderLabels(
            ["Time", "Runner", "Class", "Info", "Running Time"])
        self._feed.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self._feed.setEditTriggers(QTableWidget.NoEditTriggers)
        self._feed.setAlternatingRowColors(True)
        splitter.addWidget(self._feed)

        # Leaderboard
        self._leaderboard = QTableWidget(0, 5)
        self._leaderboard.setHorizontalHeaderLabels(
            ["Place", "Runner", "Club", "Time", "Status"])
        self._leaderboard.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self._leaderboard.setEditTriggers(QTableWidget.NoEditTriggers)
        self._leaderboard.setAlternatingRowColors(True)
        splitter.addWidget(self._leaderboard)

        splitter.setSizes([300, 300])
        main_layout.addWidget(splitter)

    # ------------------------------------------------------------------
    # TabBase interface
    # ------------------------------------------------------------------

    def load_page(self):
        ev = self.ctrl.event
        self._class_combo.blockSignals(True)
        self._class_combo.clear()
        self._class_combo.addItem("All classes", 0)
        for cls in sorted(ev.classes.values(), key=lambda c: c.name):
            if not cls.removed:
                self._class_combo.addItem(cls.name, cls.id)
        self._class_combo.blockSignals(False)
        if self._chk_auto.isChecked():
            self._timer.start(self._REFRESH_MS)
        self._refresh()

    def clear_competition_data(self):
        self._feed.setRowCount(0)
        self._leaderboard.setRowCount(0)
        self._timer.stop()

    # ------------------------------------------------------------------
    # Refresh logic
    # ------------------------------------------------------------------

    def _toggle_timer(self, state):
        if state:
            self._timer.start(self._REFRESH_MS)
        else:
            self._timer.stop()

    def _on_runner_updated(self, runner_id: int):
        if self._chk_auto.isChecked():
            self._refresh()

    def _refresh(self):
        from datetime import datetime
        self._lbl_last.setText(f"Last update: {datetime.now().strftime('%H:%M:%S')}")
        self._update_leaderboard()

    def _update_leaderboard(self):
        ev       = self.ctrl.event
        class_id = self._class_combo.currentData() or 0

        runners = [r for r in ev.runners.values()
                   if not r.removed and
                   (class_id == 0 or r.class_id == class_id) and
                   r.t_status != RunnerStatus.Unknown]

        runners.sort(key=lambda r: r.result_sort_key())

        self._leaderboard.setRowCount(len(runners))
        for row, runner in enumerate(runners):
            club = ev.clubs.get(runner.club_id)
            rt   = runner.get_running_time()
            colour = _STATUS_COLOUR.get(runner.t_status, QColor("#ffffff"))

            items = [
                QTableWidgetItem(str(runner.place) if runner.place else "–"),
                QTableWidgetItem(runner.name),
                QTableWidgetItem(club.name if club else ""),
                QTableWidgetItem(format_time(rt) if rt != NO_TIME else ""),
                QTableWidgetItem(runner.t_status.to_code()),
            ]
            for col, item in enumerate(items):
                item.setBackground(colour)
                item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
                self._leaderboard.setItem(row, col, item)
