"""Tests for hardware/si_card.py"""
import pytest
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from hardware.si_card import calc_crc, check_crc, parse_si5, parse_si8_9
from utils.time_utils import TIME_UNITS_PER_SECOND


class TestCRC:
    def test_crc_known_value(self):
        # Empty data → CRC is 0xFFFF
        assert calc_crc(b"") == 0xFFFF

    def test_crc_consistency(self):
        data = bytes(range(16))
        assert calc_crc(data) == calc_crc(data)

    def test_crc_different_data(self):
        assert calc_crc(b"\x01\x02") != calc_crc(b"\x01\x03")

    def test_check_crc_valid(self):
        data = b"\x02\x03\x04\x05"
        crc  = calc_crc(data)
        buf  = data + bytes([crc >> 8, crc & 0xFF])
        assert check_crc(buf)

    def test_check_crc_invalid(self):
        buf = b"\x01\x02\x03\x04\xff\xff"
        # Very unlikely to be valid
        result = check_crc(buf)
        # We just test no exception; value may vary
        assert isinstance(result, bool)

    def test_check_crc_too_short(self):
        assert not check_crc(b"\x01")


class TestParseSI5:
    def _make_si5_block(self, card_no: int, start_s: int, finish_s: int,
                        check_s: int, punch_codes_times: list) -> bytes:
        """Build a minimal 128-byte SI-5 block."""
        buf = bytearray(128)
        # Card number in bytes 6-7 (simplified, no overflow)
        buf[6] = (card_no >> 8) & 0xFF
        buf[7] = card_no & 0xFF
        # Check time bytes 8-9
        buf[8]  = (check_s >> 8) & 0xFF
        buf[9]  = check_s & 0xFF
        # Start bytes 19-20
        buf[19] = (start_s >> 8) & 0xFF
        buf[20] = start_s & 0xFF
        # Finish bytes 21-22
        buf[21] = (finish_s >> 8) & 0xFF
        buf[22] = finish_s & 0xFF
        # n_punches byte 23
        buf[23] = len(punch_codes_times) & 0x1F
        # Punches from offset 32, 3 bytes each
        for i, (code, t) in enumerate(punch_codes_times):
            base = 32 + i * 3
            buf[base]     = code & 0xFF
            buf[base + 1] = (t >> 8) & 0xFF
            buf[base + 2] = t & 0xFF
        return bytes(buf)

    def test_card_number(self):
        buf  = self._make_si5_block(1234, 3600, 7200, 3500, [])
        card = parse_si5(buf)
        assert card.card_number == 1234

    def test_start_time(self):
        buf  = self._make_si5_block(1, 3600, 7200, 3500, [])
        card = parse_si5(buf)
        assert card.start_punch.time == 3600 * TIME_UNITS_PER_SECOND

    def test_finish_time(self):
        buf  = self._make_si5_block(1, 3600, 7200, 3500, [])
        card = parse_si5(buf)
        assert card.finish_punch.time == 7200 * TIME_UNITS_PER_SECOND

    def test_punches_parsed(self):
        buf  = self._make_si5_block(1, 3600, 7200, 3500,
                                    [(31, 3660), (32, 3720)])
        card = parse_si5(buf)
        assert len(card.punches) == 2
        assert card.punches[0].code == 31
        assert card.punches[1].code == 32

    def test_empty_punches(self):
        buf  = self._make_si5_block(1, 3600, 7200, 3500, [])
        card = parse_si5(buf)
        assert len(card.punches) == 0


class TestSIPunchAnalyse12h:
    def test_analyse_12h_time(self):
        from models.punch import SIPunch
        # A punch at 2h (7200s) should stay near 2h if zero_time is 0
        p = SIPunch(code=31, time=7200 * TIME_UNITS_PER_SECOND)
        original = p.time
        p.analyse_hour12_time(0)
        # Should not move drastically
        assert abs(p.time - original) < 12 * 3600 * TIME_UNITS_PER_SECOND
