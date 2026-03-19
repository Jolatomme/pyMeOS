"""Tests for hardware/si_reader.py – simulation / injection mode."""
import time
import threading
import pytest
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from models.card import SICard
from models.punch import SIPunch
from hardware.si_reader import SIReaderManager, SICardReadEvent, SIPunchEvent, PortInfo
from hardware.si_card import calc_crc, check_crc
from utils.time_utils import encode


# ---------------------------------------------------------------------------
# CRC helpers (tested without Qt)
# ---------------------------------------------------------------------------

class TestCRCHelpers:
    def test_calc_crc_empty(self):
        crc = calc_crc(b"")
        assert isinstance(crc, int)
        assert 0 <= crc <= 0xFFFF

    def test_calc_crc_deterministic(self):
        data = bytes(range(8))
        assert calc_crc(data) == calc_crc(data)

    def test_crc_different_data(self):
        assert calc_crc(b"\x01\x02") != calc_crc(b"\x01\x03")

    def test_check_crc_round_trip(self):
        payload = b"\x10\x20\x30\x40"
        crc = calc_crc(payload)
        buf = payload + bytes([crc >> 8, crc & 0xFF])
        assert check_crc(buf)

    def test_check_crc_corrupt(self):
        payload = b"\x10\x20\x30\x40"
        crc = calc_crc(payload)
        buf = bytearray(payload + bytes([crc >> 8, crc & 0xFF]))
        buf[-1] ^= 0xFF   # flip last byte
        assert not check_crc(bytes(buf))

    def test_check_crc_too_short(self):
        assert not check_crc(b"\x01")


# ---------------------------------------------------------------------------
# SICardReadEvent / SIPunchEvent dataclasses
# ---------------------------------------------------------------------------

class TestEventDataclasses:
    def test_card_read_event(self):
        si = SICard()
        si.card_number = 12345
        ev = SICardReadEvent(card=si, port="COM1")
        assert ev.card.card_number == 12345
        assert ev.port == "COM1"

    def test_punch_event(self):
        ev = SIPunchEvent(code=31, time=encode(3600), card_number=99999, port="COM2")
        assert ev.code == 31
        assert ev.card_number == 99999

    def test_port_info(self):
        pi = PortInfo(port="COM3", baud=38400, mode=2, is_open=True)
        assert pi.is_open
        assert pi.baud == 38400


# ---------------------------------------------------------------------------
# SIReaderManager – list_serial_ports (no hardware needed)
# ---------------------------------------------------------------------------

class TestSIReaderManagerPorts:
    def test_list_ports_returns_list(self):
        ports = SIReaderManager.list_serial_ports()
        assert isinstance(ports, list)

    def test_open_ports_initially_empty(self, qtbot):
        mgr = SIReaderManager()
        assert mgr.open_ports == []
        mgr.close_all()


# ---------------------------------------------------------------------------
# TEST mode – card injection
# ---------------------------------------------------------------------------

class TestSIReaderManagerTestMode:
    def test_open_test_port(self, qtbot):
        mgr = SIReaderManager()
        ok = mgr.open_port("TEST", test_mode=True)
        assert ok
        assert "TEST" in mgr.open_ports
        mgr.close_all()

    def test_card_received_signal(self, qtbot):
        """Injecting a card via TEST mode emits card_received."""
        mgr = SIReaderManager()
        mgr.open_port("TEST", test_mode=True)

        received = []
        mgr.card_received.connect(lambda c: received.append(c))

        # SITestReader default interval is 500 ms; wait 1.5 s to be safe
        qtbot.wait(1500)
        mgr.close_all()

        assert len(received) >= 1

    def test_close_all_clears_ports(self, qtbot):
        mgr = SIReaderManager()
        mgr.open_port("TEST", test_mode=True)
        mgr.close_all()
        assert mgr.open_ports == []

    def test_multiple_cards_emitted(self, qtbot):
        """Over 1.5 s at 500 ms interval we expect at least 2 cards."""
        mgr = SIReaderManager()
        received = []
        mgr.open_port("TEST", test_mode=True)
        mgr.card_received.connect(lambda c: received.append(c))
        qtbot.wait(1500)
        mgr.close_all()
        assert len(received) >= 2

    def test_reopen_port(self, qtbot):
        """Opening the same port twice is a no-op (returns True)."""
        mgr = SIReaderManager()
        assert mgr.open_port("TEST", test_mode=True)
        assert mgr.open_port("TEST", test_mode=True)   # idempotent
        assert mgr.open_ports.count("TEST") == 1
        mgr.close_all()
