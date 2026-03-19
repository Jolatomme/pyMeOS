"""
views/tabs/tab_auto.py
======================
Automation tasks tab (TabAuto equivalent).

Allows configuring periodic background tasks:
  • Automatic backup
  • Live result uploads
  • Database synchronisation
"""
from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QGroupBox, QFormLayout, QLineEdit, QSpinBox,
    QCheckBox, QComboBox, QTableWidget, QTableWidgetItem,
    QHeaderView, QFileDialog,
)

from controllers.automation import AutomationController, TaskType
from .tab_base import TabBase


class TabAuto(TabBase):
    def __init__(self, controller, parent=None):
        super().__init__(controller, parent)
        self._auto_ctrl = AutomationController(controller.event)
        self._build_ui()
        self.ctrl.event_loaded.connect(self._on_event_loaded)

    def _build_ui(self):
        layout = QVBoxLayout(self)

        # ---- Backup group ---------------------------------------------
        grp_backup = QGroupBox("Automatic Backup")
        frm_backup = QFormLayout(grp_backup)

        self._backup_path = QLineEdit()
        btn_browse = QPushButton("Browse…")
        btn_browse.clicked.connect(self._browse_backup)
        row = QHBoxLayout()
        row.addWidget(self._backup_path); row.addWidget(btn_browse)
        frm_backup.addRow("Backup folder:", row)

        self._backup_interval = QSpinBox()
        self._backup_interval.setRange(1, 1440)
        self._backup_interval.setValue(5)
        self._backup_interval.setSuffix(" min")
        frm_backup.addRow("Interval:", self._backup_interval)

        self._chk_backup = QCheckBox("Enable automatic backup")
        frm_backup.addRow(self._chk_backup)

        btn_backup_now = QPushButton("Backup Now")
        btn_backup_now.clicked.connect(self._backup_now)
        frm_backup.addRow(btn_backup_now)
        layout.addWidget(grp_backup)

        # ---- Live results group ----------------------------------------
        grp_live = QGroupBox("Live Results Upload")
        frm_live = QFormLayout(grp_live)

        self._upload_url = QLineEdit()
        self._upload_url.setPlaceholderText("https://liveresults.example.com/api")
        frm_live.addRow("Upload URL:", self._upload_url)

        self._upload_interval = QSpinBox()
        self._upload_interval.setRange(5, 600)
        self._upload_interval.setValue(30)
        self._upload_interval.setSuffix(" s")
        frm_live.addRow("Interval:", self._upload_interval)

        self._chk_live = QCheckBox("Enable live result upload")
        frm_live.addRow(self._chk_live)
        layout.addWidget(grp_live)

        # ---- Task log --------------------------------------------------
        grp_log = QGroupBox("Task Log")
        log_layout = QVBoxLayout(grp_log)

        self._log_table = QTableWidget(0, 3)
        self._log_table.setHorizontalHeaderLabels(["Time", "Task", "Result"])
        self._log_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self._log_table.setEditTriggers(QTableWidget.NoEditTriggers)
        log_layout.addWidget(self._log_table)
        layout.addWidget(grp_log)

        # ---- Apply / Start buttons ------------------------------------
        btn_row = QHBoxLayout()
        self._btn_apply = QPushButton("Apply Settings")
        self._btn_apply.clicked.connect(self._apply_settings)
        btn_row.addStretch()
        btn_row.addWidget(self._btn_apply)
        layout.addLayout(btn_row)

        layout.addStretch()

        # Wire automation controller log callback
        self._auto_ctrl.set_log_callback(self._append_log)

    # ------------------------------------------------------------------
    # TabBase interface
    # ------------------------------------------------------------------

    def load_page(self):
        self._refresh_from_controller()

    def clear_competition_data(self):
        self._auto_ctrl.stop_all()
        self._log_table.setRowCount(0)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _on_event_loaded(self):
        self._auto_ctrl.set_event(self.ctrl.event)
        self.load_page()

    def _refresh_from_controller(self):
        cfg = self._auto_ctrl.get_config(TaskType.Backup)
        if cfg:
            self._backup_path.setText(cfg.output_path)
            self._backup_interval.setValue(cfg.interval_seconds // 60)
            self._chk_backup.setChecked(cfg.enabled)

        cfg2 = self._auto_ctrl.get_config(TaskType.LiveResults)
        if cfg2:
            self._upload_url.setText(cfg2.upload_url)
            self._upload_interval.setValue(cfg2.interval_seconds)
            self._chk_live.setChecked(cfg2.enabled)

    def _apply_settings(self):
        self._auto_ctrl.configure(
            TaskType.Backup,
            output_path=self._backup_path.text().strip(),
            interval_seconds=self._backup_interval.value() * 60,
            enabled=self._chk_backup.isChecked(),
        )
        self._auto_ctrl.configure(
            TaskType.LiveResults,
            upload_url=self._upload_url.text().strip(),
            interval_seconds=self._upload_interval.value(),
            enabled=self._chk_live.isChecked(),
        )
        self._auto_ctrl.apply()

    def _backup_now(self):
        path = self._backup_path.text().strip()
        if not path:
            return
        self._auto_ctrl.run_now(TaskType.Backup, output_path=path)

    def _browse_backup(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Backup Folder")
        if folder:
            self._backup_path.setText(folder)

    def _append_log(self, task_name: str, result: str):
        from datetime import datetime
        row = self._log_table.rowCount()
        self._log_table.insertRow(row)
        self._log_table.setItem(row, 0,
            QTableWidgetItem(datetime.now().strftime("%H:%M:%S")))
        self._log_table.setItem(row, 1, QTableWidgetItem(task_name))
        self._log_table.setItem(row, 2, QTableWidgetItem(result))
        self._log_table.scrollToBottom()
