"""
views/tabs/tab_si.py
====================
SportIdent card reader control tab (TabSI equivalent).

Features:
  • Open / close serial ports
  • Display live card reads in a log
  • Manual card entry
  • Test card injection
"""
from __future__ import annotations

from PySide6.QtCore import Qt, Slot
from PySide6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QPushButton, QTextEdit, QLabel,
    QComboBox, QCheckBox, QGroupBox, QFormLayout, QSpinBox,
    QLineEdit, QDialogButtonBox, QDialog,
)
from PySide6.QtGui import QColor, QTextCharFormat, QTextCursor

from hardware.si_reader import SIReader, SICardReadEvent, SIPunchEvent
from utils.time_utils import format_time
from .tab_base import TabBase


class TabSI(TabBase):
    def __init__(self, controller, parent=None):
        super().__init__(controller, parent)
        self._reader = SIReader(parent=self)
        self._reader.card_read.connect(self._on_card_read)
        self._reader.punch_recv.connect(self._on_punch)
        self._reader.port_status.connect(self._on_port_status)
        self._reader.error.connect(self._on_error)

        # Forward card reads to competition controller
        self._reader.card_read.connect(self.ctrl.on_card_read)
        self._reader.punch_recv.connect(self.ctrl.on_punch_received)

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
        self._btn_open  = QPushButton("Open")
        self._btn_close = QPushButton("Close")
        self._btn_refresh= QPushButton("↻ Refresh")
        self._btn_open.clicked.connect(self._open_port)
        self._btn_close.clicked.connect(self._close_port)
        self._btn_refresh.clicked.connect(self._refresh_ports)
        btn_row.addWidget(self._btn_open)
        btn_row.addWidget(self._btn_close)
        btn_row.addWidget(self._btn_refresh)
        pg.addRow(btn_row)

        self._chk_subsecond = QCheckBox("Sub-second precision")
        self._chk_subsecond.toggled.connect(
            lambda v: self._reader.set_subsecond_mode(v)
        )
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

        clear_btn = QPushButton("Clear Log")
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

        self._btn_test = QPushButton("Inject Test Card")
        self._btn_test.clicked.connect(self._inject_test)
        tg.addWidget(self._btn_test)

        layout.addWidget(test_grp)

    # ------------------------------------------------------------------
    # TabBase interface
    # ------------------------------------------------------------------

    def load_page(self):
        self._refresh_ports()

    def clear_competition_data(self):
        self._log.clear()

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    @Slot(object)
    def _on_card_read(self, ev: SICardReadEvent):
        card = ev.card
        self._log_line(
            f"[CARD]  {card.card_number:>8}  "
            f"start={format_time(card.start_punch.time)}  "
            f"finish={format_time(card.finish_punch.time)}  "
            f"punches={len(card.punches)}",
            color="#00aa00",
        )

    @Slot(object)
    def _on_punch(self, ev: SIPunchEvent):
        self._log_line(
            f"[PUNCH] card={ev.card_number} code={ev.code} "
            f"time={format_time(ev.time)}",
            color="#0055ff",
        )

    @Slot(str, str)
    def _on_port_status(self, port: str, msg: str):
        self._lbl_status.setText(f"{port}: {msg}")
        self._log_line(f"[STATUS] {port}: {msg}", color="#888888")

    @Slot(str)
    def _on_error(self, msg: str):
        self._log_line(f"[ERROR]  {msg}", color="#cc0000")

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def _refresh_ports(self):
        self._port_combo.clear()
        self._port_combo.addItem("TEST")
        for p in SIReader.list_ports():
            self._port_combo.addItem(p)

    def _open_port(self):
        port = self._port_combo.currentText().strip()
        if port == "TEST":
            self._log_line("[INFO] Test mode – no physical reader.", "#888888")
            return
        if self._reader.open_port(port):
            self._log_line(f"[INFO] Opening {port}…", "#888888")
        else:
            self._log_line(f"[ERROR] Cannot open {port}", "#cc0000")

    def _close_port(self):
        port = self._port_combo.currentText().strip()
        self._reader.close_port(port)
        self._log_line(f"[INFO] {port} closed.", "#888888")

    def _inject_test(self):
        card_no = self._spin_card.value()
        ev = self.ctrl.event
        # Build punches from the first available course
        punches = []
        for course in ev.courses.values():
            if not course.removed:
                for cid in course.control_ids[:10]:
                    ctrl = ev.controls.get(cid)
                    if ctrl and ctrl.numbers:
                        punches.append(ctrl.numbers[0])
                break
        self._reader.add_test_card(card_no, punches)

    def _log_line(self, text: str, color: str = "#000000"):
        fmt = QTextCharFormat()
        fmt.setForeground(QColor(color))
        cursor = self._log.textCursor()
        cursor.movePosition(QTextCursor.End)
        cursor.insertText(text + "\n", fmt)
        self._log.setTextCursor(cursor)
        self._log.ensureCursorVisible()
