"""
views/tabs/tab_results.py
=========================
Results list tab (TabList equivalent).
Displays sorted results per class with place, time, and status.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QPushButton, QTableWidget, QTableWidgetItem,
    QComboBox, QLabel, QHeaderView, QFileDialog,
)
from PySide6.QtGui import QColor

from models import RunnerStatus
from controllers.result import compute_class_results
from utils.time_utils import format_time, NO_TIME
from .tab_base import TabBase

# Status colour coding
STATUS_COLORS = {
    RunnerStatus.OK:              "#e8f5e9",
    RunnerStatus.MP:              "#fff9c4",
    RunnerStatus.DNF:             "#fce4ec",
    RunnerStatus.DNS:             "#f3e5f5",
    RunnerStatus.DQ:              "#fbe9e7",
    RunnerStatus.MAX:             "#fff3e0",
    RunnerStatus.OutOfCompetition:"#e3f2fd",
}


class TabResults(TabBase):
    def __init__(self, controller, parent=None):
        super().__init__(controller, parent)
        self._build_ui()
        self.ctrl.runner_updated.connect(lambda _: self._refresh_results())
        self.ctrl.event_loaded.connect(self.load_page)

    def _build_ui(self):
        layout = QVBoxLayout(self)

        toolbar = QHBoxLayout()
        self._cls_combo = QComboBox()
        self._cls_combo.currentIndexChanged.connect(self._refresh_results)
        toolbar.addWidget(QLabel("Class:"))
        toolbar.addWidget(self._cls_combo)
        toolbar.addStretch()

        self._btn_refresh = QPushButton("↻ Refresh")
        self._btn_refresh.clicked.connect(self._refresh_results)
        toolbar.addWidget(self._btn_refresh)

        self._btn_export = QPushButton("Export HTML…")
        self._btn_export.clicked.connect(self._export_html)
        toolbar.addWidget(self._btn_export)

        layout.addLayout(toolbar)

        self._table = QTableWidget(0, 6)
        self._table.setHorizontalHeaderLabels(
            ["Place", "Name", "Club", "Card", "Time", "Status"]
        )
        self._table.setAlternatingRowColors(True)
        self._table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(self._table)

    def load_page(self):
        ev = self.ctrl.event
        self._cls_combo.blockSignals(True)
        self._cls_combo.clear()
        for cls in sorted(ev.classes.values(), key=lambda c: c.name):
            if not cls.removed:
                self._cls_combo.addItem(cls.name, cls.id)
        self._cls_combo.blockSignals(False)
        self._refresh_results()

    def clear_competition_data(self):
        self._table.setRowCount(0)

    def _refresh_results(self):
        class_id = self._cls_combo.currentData()
        if not class_id:
            self._table.setRowCount(0)
            return

        runners = compute_class_results(self.ctrl.event, class_id)
        self._table.setRowCount(len(runners))

        for row, r in enumerate(runners):
            ev   = self.ctrl.event
            club = ev.clubs.get(r.club_id)
            rt   = r.get_running_time()
            color = QColor(STATUS_COLORS.get(r.t_status, "#ffffff"))

            vals = [
                str(r.place) if r.place else "",
                r.name,
                club.name if club else "",
                str(r.card_number) if r.card_number else "",
                format_time(rt) if rt != NO_TIME else "",
                r.t_status.to_code(),
            ]
            for col, val in enumerate(vals):
                item = QTableWidgetItem(val)
                item.setBackground(color)
                self._table.setItem(row, col, item)

    def _export_html(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Results", "results.html", "HTML (*.html)"
        )
        if not path:
            return
        ev = self.ctrl.event
        class_id = self._cls_combo.currentData()
        if not class_id:
            return
        cls = ev.classes.get(class_id)
        runners = compute_class_results(ev, class_id)

        lines = [
            "<!DOCTYPE html><html><head><meta charset='utf-8'>",
            f"<title>Results – {cls.name if cls else ''}</title></head><body>",
            f"<h1>{ev.name}</h1>",
            f"<h2>{cls.name if cls else ''}</h2>",
            "<table border='1' cellpadding='4' cellspacing='0'>",
            "<tr><th>Place</th><th>Name</th><th>Club</th><th>Time</th><th>Status</th></tr>",
        ]
        for r in runners:
            club = ev.clubs.get(r.club_id)
            rt   = r.get_running_time()
            lines.append(
                f"<tr><td>{r.place or ''}</td><td>{r.name}</td>"
                f"<td>{club.name if club else ''}</td>"
                f"<td>{format_time(rt) if rt != NO_TIME else ''}</td>"
                f"<td>{r.t_status.to_code()}</td></tr>"
            )
        lines += ["</table></body></html>"]

        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
