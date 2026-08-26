"""
views/tabs/tab_si.py
====================
SportIdent card reader control tab (TabSI equivalent).

Features:
   Open / close serial ports
   Display live card reads in a log
   Manual card entry
   Test card injection
"""
from __future__ import annotations

from PySide6.QtCore import Qt, Slot
from PySide6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QPushButton, QTextEdit, QLabel,
    QComboBox, QCheckBox, QGroupBox, QFormLayout, QSpinBox,
    QLineEdit, QDialogButtonBox, QDialog,
)
from PySide6.QtGui import QColor, QTextCharFormat, QTextCursor

from hardware.si_reader import SIReaderManager as SIReader, SICardReadEvent, SIPunchEvent
from utils.time_utils import format_time
from utils.icon_utils import get_icon
from .tab_base import TabBase


class TabSI(TabBase):
    def __init__(self, controller, parent=None):
        super().__init__(controller, parent)
        self._reader = SIReader(parent=self)
        self._reader.card_received.connect(self._on_card_read)
        self._reader.error.connect(self._on_si_error)
        self._reader.ports_changed.connect(self._on_ports_changed)

        self._build_ui()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self):
        layout = QVBoxLayout(self)

        # ---- Port controls --------------------------------------------
        port_grp = QGroupBox("SportIdent Station")
        pg = QFormLayout(port_grp)

        self._port_combo = QComboBox()
        self._port_combo.setEditable(True)
        self._refresh_ports()
        pg.addRow("Port:", self._port_combo)

        btn_row = QHBoxLayout()
        self._btn_open   = QPushButton(get_icon("si/usb"),   "Open")
        self._btn_close  = QPushButton(get_icon("si/usb_off"), "Close")
        self._btn_refresh= QPushButton(get_icon("actions/refresh"), "Refresh")
        self._btn_open.clicked.connect(self._open_port)
        self._btn_close.clicked.connect(self._close_port)
        self._btn_refresh.clicked.connect(self._refresh_ports)
        btn_row.addWidget(self._btn_open)
        btn_row.addWidget(self._btn_close)
        btn_row.addWidget(self._btn_refresh)
        pg.addRow(btn_row)

        self._chk_subsecond = QCheckBox("Sub-second precision")
        pg.addRow(self._chk_subsecond)

        layout.addWidget(port_grp)

        # ---- Status label ---------------------------------------------
        self._lbl_status = QLabel("No station connected.")
        layout.addWidget(self._lbl_status)

        # ---- Log view -------------------------------------------------
        log_grp = QGroupBox("Card Read Log")
        lg = QVBoxLayout(log_grp)
        self._log = QTextEdit()
        self._log.setReadOnly(True)
        self._log.setFontFamily("Monospace")
        lg.addWidget(self._log)

        clear_btn = QPushButton(get_icon("actions/clear_log"), "Clear Log")
        clear_btn.clicked.connect(self._log.clear)
        lg.addWidget(clear_btn)
        layout.addWidget(log_grp)

        # ---- Manual / test controls ----------------------------------
        test_grp = QGroupBox("Test / Manual")
        tg = QHBoxLayout(test_grp)

        self._spin_card = QSpinBox()
        self._spin_card.setRange(1, 9_999_999)
        self._spin_card.setValue(1234567)
        tg.addWidget(QLabel("Card no:"))
        tg.addWidget(self._spin_card)

        self._btn_test = QPushButton(get_icon("si/test_card"), "Inject Test Card")
        self._btn_test.clicked.connect(self._inject_test)
        tg.addWidget(self._btn_test)

        layout.addWidget(test_grp)

    # ------------------------------------------------------------------
    # Port management
    # ------------------------------------------------------------------

    def _refresh_ports(self):
        ports = self._reader.list_serial_ports()
        self._port_combo.clear()
        for p in ports:
            self._port_combo.addItem(p, p)
        # Add TEST mode
        self._port_combo.addItem("TEST (Simulation)", "TEST")

    def _open_port(self):
        port = self._port_combo.currentData()
        if not port:
            return
        if port == "TEST":
            self._reader.open_port("TEST", test_mode=True)
            self._lbl_status.setText("Test mode active (simulation).")
        else:
            self._reader.open_port(port)
            self._lbl_status.setText(f"Connected to {port}.")

    def _close_port(self):
        self._reader.close_all()
        self._lbl_status.setText("No station connected.")

    def _on_ports_changed(self):
        self._refresh_ports()

    # ------------------------------------------------------------------
    # Card handling
    # ------------------------------------------------------------------

    @Slot
    def _on_card_read(self, ev: SICardReadEvent):
        card = ev.card
        self._log.append(f"Card {card.card_number} read from {ev.port}")
        self._log.append(f"  Start: {format_time(card.get_start_time())}")
        self._log.append(f"  Finish: {format_time(card.get_finish_time())}")
        self._log.append(f"  Punches: {len(card.punches)}")
        self._log.append("")

        # Scroll to bottom
        cursor = self._log.textCursor()
        cursor.movePosition(QTextCursor.End)
        self._log.setTextCursor(cursor)

    @Slot
    def _on_si_error(self, port: str, message: str):
        self._log.append(f"ERROR [{port}]: {message}")

    def _inject_test(self):
        card_number = self._spin_card.value()
        self._reader.emit_test_card(card_number)
        self._log.append(f"Test card {card_number} injected.")
