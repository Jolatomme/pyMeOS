"""
hardware/si_reader.py
=====================
Cross-platform SportIdent SI-station reader using pyserial.

Replaces the Win32 thread + HANDLE SportIdent.cpp with:
  SIPortReader    – a QThread that monitors one serial port
  SITestReader    – emits synthetic cards (no hardware needed)
  SIReaderManager – owns all open port readers, routes signals to UI
"""
from __future__ import annotations

import logging
import threading
import time
from typing import Dict, List, Optional

try:
    import serial
    import serial.tools.list_ports
    HAS_SERIAL = True
except ImportError:
    HAS_SERIAL = False

try:
    from PySide6.QtCore import QThread, Signal, QObject
    _QT = True
except ImportError:
    import threading as _threading
    _QT = False
    class QObject:  # type: ignore
        def __init__(self, parent=None): pass
    class QThread(_threading.Thread):  # type: ignore
        def __init__(self, parent=None):
            super().__init__(daemon=True)
        def start(self): super().start()
        def wait(self, ms=0): self.join(ms/1000 if ms else None)
    def Signal(*a):  # type: ignore
        return None

from models.card import SICard
from models.punch import SIPunch
from hardware.si_card import (
    STX, ETX, ACK, WAKEUP,
    calc_crc, check_crc,
    get_card5_data, get_card6_data, get_card9_data,
)
from hardware.si_protocol import set_crc, parse_station_data, StationData


def _emit(signal, *args):
    """Safely emit a Qt signal if Qt is available."""
    if _QT and signal is not None and hasattr(signal, 'emit'):
        signal.emit(*args)


logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Per-port reader thread
# ---------------------------------------------------------------------------

class SIPortReader(QThread):
    """Runs in its own thread; reads SI frames from one serial port."""

    card_received = Signal(object)    # SICard
    error         = Signal(str, str)  # (port, message)
    station_info  = Signal(str, object)

    BAUD = 38400

    def __init__(self, port: str, parent=None) -> None:
        # NOTE: do NOT pass parent – Qt must not auto-delete a running thread
        super().__init__(None)
        self.port     = port
        self._running = False
        self._ser: Optional["serial.Serial"] = None

    def run(self) -> None:
        if not HAS_SERIAL:
            _emit(self.error, self.port, "pyserial is not installed")
            return
        try:
            self._ser = serial.Serial(
                port=self.port,
                baudrate=self.BAUD,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=0.3,
            )
        except serial.SerialException as exc:
            _emit(self.error, self.port, str(exc))
            return

        logger.info("SI reader opened %s", self.port)
        self._running = True
        self._send_wakeup()
        try:
            self._monitor_loop()
        except Exception as exc:
            logger.exception("SI reader %s crashed", self.port)
            _emit(self.error, self.port, str(exc))
        finally:
            if self._ser and self._ser.is_open:
                self._ser.close()
            logger.info("SI reader closed %s", self.port)

    def stop(self) -> None:
        self._running = False

    # ------------------------------------------------------------------
    # Low-level protocol
    # ------------------------------------------------------------------

    def _send_wakeup(self) -> None:
        if self._ser:
            try:
                self._ser.write(bytes([WAKEUP, STX, STX]))
            except Exception:
                pass

    def _send_cmd(self, cmd: int, data: bytes = b"") -> None:
        buf = bytearray([cmd, len(data)] + list(data) + [0, 0])
        set_crc(buf)
        self._ser.write(bytes([STX]) + bytes(buf) + bytes([ETX]))

    def _read_frame(self) -> Optional[bytes]:
        ser = self._ser
        # Find STX
        while self._running:
            b = ser.read(1)
            if not b:
                continue
            if b[0] == 0xFF:   # wakeup echo
                continue
            if b[0] == STX:
                break
        else:
            return None
        header = ser.read(2)
        if len(header) < 2:
            return None
        cmd, length = header[0], header[1]
        rest = ser.read(length + 2)
        if len(rest) < length + 2:
            return None
        payload = bytes([cmd, length]) + rest
        if not check_crc(payload):
            logger.debug("CRC mismatch on %s", self.port)
            return None
        return payload

    def _monitor_loop(self) -> None:
        while self._running:
            frame = self._read_frame()
            if frame is None:
                continue
            cmd = frame[0]
            if cmd in (0xE5, 0xE6, 0xE8):   # card insert events
                self._handle_card_insert(cmd, frame)
            elif cmd == 0x83:                # system data
                sd = parse_station_data(frame[2:])
                if sd:
                    _emit(self.station_info, self.port, sd)

    def _handle_card_insert(self, cmd: int, frame: bytes) -> None:
        if not self._ser:
            return
        self._ser.write(bytes([ACK]))
        time.sleep(0.05)
        if cmd == 0xE5:
            self._send_cmd(0xB1)          # GET_SI5
            resp = self._read_frame()
            if resp:
                card = get_card5_data(resp[2:])
                if card:
                    _emit(self.card_received, card)
        elif cmd == 0xE6:
            self._send_cmd(0xE1)          # GET_SI6
            resp = self._read_frame()
            if resp:
                card = get_card6_data(resp[2:])
                if card:
                    _emit(self.card_received, card)
        elif cmd == 0xE8:
            self._send_cmd(0xEF)          # GET_SI9
            resp = self._read_frame()
            if resp:
                card = get_card9_data(resp[2:])
                if card:
                    _emit(self.card_received, card)


# ---------------------------------------------------------------------------
# Test-mode reader (no hardware)
# ---------------------------------------------------------------------------

class SITestReader(QThread):
    """Emits synthetic SI cards for testing and demos."""

    card_received = Signal(object)
    error         = Signal(str, str)
    station_info  = Signal(str, object)

    # Short default interval so tests don't have to wait long
    DEFAULT_INTERVAL_MS = 500

    def __init__(self, port: str = "TEST",
                 cards: Optional[List[SICard]] = None,
                 interval_ms: int = DEFAULT_INTERVAL_MS,
                 parent=None) -> None:
        # NOTE: do NOT pass parent – Qt must not auto-delete a running thread
        super().__init__(None)
        self.port      = port
        self._cards    = cards or _default_test_cards()
        self._interval = interval_ms / 1000.0
        self._stop_event = threading.Event()

    def run(self) -> None:
        idx = 0
        while not self._stop_event.wait(timeout=self._interval):
            _emit(self.card_received, self._cards[idx % len(self._cards)])
            idx += 1

    def stop(self) -> None:
        """Signal the thread to stop; returns immediately."""
        self._stop_event.set()

    def wait(self, msecs: int = -1) -> bool:
        """Block until the thread finishes (with optional timeout in ms)."""
        if _QT:
            # Use Qt's wait for proper event-loop integration
            return super().wait(msecs) if msecs >= 0 else super().wait()
        return True


def _default_test_cards() -> List[SICard]:
    from utils.time_utils import encode
    cards = []
    for i, card_no in enumerate([123456, 234567, 345678]):
        c = SICard()
        c.card_number = card_no
        base = encode(3600 + i * 180)
        c.start_punch  = SIPunch(1, base)
        c.finish_punch = SIPunch(2, base + encode(1800 + i * 60))
        c.punches = [
            SIPunch(31, base + encode(300)),
            SIPunch(32, base + encode(700)),
            SIPunch(33, base + encode(1200)),
        ]
        cards.append(c)
    return cards


# ---------------------------------------------------------------------------
# Manager
# ---------------------------------------------------------------------------

class SIReaderManager(QObject):
    """Owns all open SI reader ports."""

    card_received = Signal(object)
    error         = Signal(str, str)
    station_info  = Signal(str, object)
    ports_changed = Signal(list)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._readers: Dict[str, QThread] = {}

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def __del__(self) -> None:
        """Ensure all threads are stopped when the manager is garbage-collected."""
        try:
            self.close_all()
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Port management
    # ------------------------------------------------------------------

    def open_port(self, port: str, test_mode: bool = False) -> bool:
        if port in self._readers:
            return True
        if test_mode or port.upper() == "TEST":
            reader: QThread = SITestReader(port=port)
        else:
            reader = SIPortReader(port=port)

        if hasattr(reader, 'card_received'):
            reader.card_received.connect(self.card_received)
        if hasattr(reader, 'error'):
            reader.error.connect(self.error)
        if hasattr(reader, 'station_info'):
            reader.station_info.connect(self.station_info)

        reader.start()
        self._readers[port] = reader
        _emit(self.ports_changed, list(self._readers.keys()))
        return True

    def close_port(self, port: str) -> None:
        reader = self._readers.pop(port, None)
        if reader is None:
            return
        # Signal the thread to stop
        if hasattr(reader, "stop"):
            reader.stop()
        # Wait up to 3 s for a clean exit (covers the max sleep interval)
        if _QT and hasattr(reader, 'wait'):
            reader.wait(3000)
        _emit(self.ports_changed, list(self._readers.keys()))

    def close_all(self) -> None:
        for port in list(self._readers.keys()):
            self.close_port(port)

    @property
    def open_ports(self) -> List[str]:
        return list(self._readers.keys())

    @staticmethod
    def list_serial_ports() -> List[str]:
        if not HAS_SERIAL:
            return []
        return [p.device for p in serial.tools.list_ports.comports()]


# ---------------------------------------------------------------------------
# Event dataclasses (used by competition controller)
# ---------------------------------------------------------------------------

from dataclasses import dataclass

@dataclass
class SICardReadEvent:
    """Payload emitted when a card is read from a port."""
    card: SICard
    port: str = ""

@dataclass
class SIPunchEvent:
    """Payload emitted for a pass-through punch."""
    code:        int = 0
    time:        int = 0
    card_number: int = 0
    port:        str = ""


@dataclass
class PortInfo:
    """Info about an open SI station port."""
    port:   str  = ""
    baud:   int  = 38400
    mode:   int  = 0       # station mode
    is_open: bool = False
