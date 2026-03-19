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

from hardware.si_reader import SIReaderManager as SIReader, SICardReadEvent, SIPunchEvent
from utils.time_utils import format_time
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
        self._btn_open   = QPushButton("Open")
        self._btn_close  = QPushButton("Close")
        self._btn_refresh= QPushButton("↻ Refresh")
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
    def _on_card_read(self, si_card):
        """Called when SIReaderManager emits card_received (SICard object)."""
        self._log_line(
            f"[CARD]  {si_card.card_number:>8}  "
            f"start={format_time(si_card.start_punch.time)}  "
            f"finish={format_time(si_card.finish_punch.time)}  "
            f"punches={len(si_card.punches)}",
            color="#00aa00",
        )
        # Forward to competition controller
        ev = SICardReadEvent(card=si_card, port=self._current_port())
        self.ctrl.on_card_read(ev)

    @Slot(str, str)
    def _on_si_error(self, port: str, msg: str):
        self._lbl_status.setText(f"{port}: {msg}")
        self._log_line(f"[ERROR]  {port}: {msg}", color="#cc0000")

    @Slot(list)
    def _on_ports_changed(self, ports: list):
        if ports:
            self._lbl_status.setText(f"Open ports: {', '.join(ports)}")
        else:
            self._lbl_status.setText("No station connected.")

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def _refresh_ports(self):
        self._port_combo.clear()
        self._port_combo.addItem("TEST")
        for p in SIReader.list_serial_ports():
            self._port_combo.addItem(p)

    def _open_port(self):
        port = self._port_combo.currentText().strip()
        test_mode = (port.upper() == "TEST")
        if self._reader.open_port(port, test_mode=test_mode):
            self._log_line(f"[INFO] Opening {port}…", "#888888")
        else:
            self._log_line(f"[ERROR] Cannot open {port}", "#cc0000")

    def _close_port(self):
        port = self._port_combo.currentText().strip()
        self._reader.close_port(port)
        self._log_line(f"[INFO] {port} closed.", "#888888")

    def _current_port(self) -> str:
        ports = self._reader.open_ports
        return ports[0] if ports else ""

    def _inject_test(self):
        card_no = self._spin_card.value()
        # Ensure TEST port is open
        if "TEST" not in self._reader.open_ports:
            self._reader.open_port("TEST", test_mode=True)

        ev = self.ctrl.event
        punches = []
        for course in ev.courses.values():
            if not course.removed:
                for cid in course.control_ids[:10]:
                    ctrl = ev.controls.get(cid)
                    if ctrl and ctrl.numbers:
                        punches.append(ctrl.numbers[0])
                break

        # Build a synthetic SICard and inject it directly
        from models.card import SICard
        from models.punch import SIPunch
        from utils.time_utils import encode
        si = SICard()
        si.card_number  = card_no
        si.start_punch  = SIPunch(code=1, time=encode(3600))
        si.finish_punch = SIPunch(code=2, time=encode(3600 + 1800))
        for i, code in enumerate(punches):
            si.punches.append(SIPunch(code=code, time=encode(3660 + i * 60)))

        read_ev = SICardReadEvent(card=si, port="TEST")
        self._on_card_read(si)

    def _log_line(self, text: str, color: str = "#000000"):
        fmt = QTextCharFormat()
        fmt.setForeground(QColor(color))
        cursor = self._log.textCursor()
        cursor.movePosition(QTextCursor.End)
        cursor.insertText(text + "\n", fmt)
        self._log.setTextCursor(cursor)
        self._log.ensureCursorVisible()
