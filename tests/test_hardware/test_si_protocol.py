"""Tests for hardware/si_protocol.py"""
import pytest
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from hardware.si_protocol import (
    STX, ETX, ACK, DLE, WAKEUP, NAK,
    CMD_GET_SYSTEM_VALUE, CMD_GET_BACKUP,
    CMD_READ_CARD5, CMD_READ_CARD6, CMD_READ_CARD9,
    CMD_TRANSMIT_RECORD, CMD_OLD_PUNCH,
    MODE_CONTROL, MODE_START, MODE_FINISH, MODE_READOUT, MODE_CHECK, MODE_CLEAR,
    SERIES_SICARD5, SERIES_SICARD6, SERIES_SICARD9, SERIES_SICARD10, SERIES_SICARD11,
    BAUD_38400, BAUD_4800,
    calc_crc, set_crc, check_crc,
    get_card_number, get_ext_card_number,
    decode_si_time, TIME_UNITS_PER_SECOND,
    build_wakeup_frame, build_get_system_request,
    StationData, parse_station_data
)


class TestProtocolConstants:
    def test_protocol_bytes(self):
        assert STX == 0x02
        assert ETX == 0x03
        assert ACK == 0x06
        assert DLE == 0x10
        assert WAKEUP == 0xFF
        assert NAK == 0x15

    def test_commands(self):
        assert CMD_GET_SYSTEM_VALUE == 0x83
        assert CMD_GET_BACKUP == 0x81
        assert CMD_READ_CARD5 == 0xB1
        assert CMD_READ_CARD6 == 0xE1
        assert CMD_READ_CARD9 == 0xEF
        assert CMD_TRANSMIT_RECORD == 0xD3
        assert CMD_OLD_PUNCH == 0x53

    def test_station_modes(self):
        assert MODE_CONTROL == 2
        assert MODE_START == 3
        assert MODE_FINISH == 4
        assert MODE_READOUT == 5
        assert MODE_CHECK == 10
        assert MODE_CLEAR == 7

    def test_card_series(self):
        assert SERIES_SICARD5 == 1
        assert SERIES_SICARD6 == 6
        assert SERIES_SICARD9 == 9
        assert SERIES_SICARD10 == 10
        assert SERIES_SICARD11 == 11

    def test_baud_rates(self):
        assert BAUD_38400 == 38400
        assert BAUD_4800 == 4800


class TestCRCCalculation:
    def test_empty_data(self):
        assert calc_crc(b"") == 0

    def test_single_byte(self):
        assert calc_crc(b"A") == 0

    def test_two_bytes(self):
        result = calc_crc(bytes([0x83, 0x02]))
        assert isinstance(result, int)
        assert result >= 0

    def test_known_crc(self):
        data = bytes([0x83, 0x02, 0x70, 0x06])
        result = calc_crc(data)
        assert isinstance(result, int)

    def test_multiple_bytes(self):
        data = bytes([0x01, 0x02, 0x03, 0x04, 0x05])
        result = calc_crc(data)
        assert isinstance(result, int)

    def test_even_length(self):
        data = bytes([0x00, 0x00, 0x01, 0x02])
        result = calc_crc(data)
        assert isinstance(result, int)

    def test_odd_length(self):
        data = bytes([0x01, 0x02, 0x03])
        result = calc_crc(data)
        assert isinstance(result, int)


class TestCRCSettersGetters:
    def test_set_crc_basic(self):
        frame = bytearray([0x01, 0x02, 0x03, 0x00, 0x00])
        set_crc(frame)
        assert frame[3] != 0 or frame[4] != 0

    def test_set_crc_extends_frame(self):
        frame = bytearray([STX, 0x01, 0x02])
        set_crc(frame)
        assert len(frame) >= 5

    def test_check_crc_valid(self):
        frame = bytearray([STX, 0x01, 0x02, 0x00, 0x00])
        set_crc(frame)
        assert check_crc(frame) is True

    def test_check_crc_invalid(self):
        data = bytes([STX, 0x01, 0x02, 0xFF, 0xFF])
        assert check_crc(data) is False

    def test_check_crc_too_short(self):
        assert check_crc(bytes([STX, 0x01])) is False
        assert check_crc(b"") is False


class TestCardNumber:
    def test_get_card_number_series_1(self):
        assert get_card_number(1, 12345) == 112345

    def test_get_card_number_series_2(self):
        assert get_card_number(2, 12345) == 212345

    def test_get_card_number_series_3(self):
        assert get_card_number(3, 12345) == 312345

    def test_get_card_number_series_4(self):
        assert get_card_number(4, 12345) == 412345

    def test_get_card_number_series_5_extended(self):
        assert get_card_number(5, 99999) == 99999

    def test_get_card_number_series_6(self):
        assert get_card_number(6, 12345) == 12345

    def test_get_card_number_invalid_series(self):
        assert get_card_number(0, 12345) == 12345
        assert get_card_number(10, 12345) == 12345


class TestExtendedCardNumber:
    def test_ext_card_number_series_1_4(self):
        data = bytes([1, 0x12, 0x34])
        assert get_ext_card_number(data, 0) == 0x1234 + 100000

    def test_ext_card_number_series_5_plus(self):
        data = bytes([5, 0x12, 0x34])
        result = get_ext_card_number(data, 0)
        assert result == (5 << 16) | (0x12 << 8) | 0x34

    def test_ext_card_number_offset(self):
        data = bytes([0, 0, 1, 0x12, 0x34, 0, 0])
        assert get_ext_card_number(data, 2) == 0x1234 + 100000


class TestTimeDecoding:
    def test_decode_si_time_basic(self):
        result = decode_si_time(0, 3600)
        assert result == 3600 * TIME_UNITS_PER_SECOND

    def test_decode_si_time_with_subsecond(self):
        result = decode_si_time(0, 3600, sub_second=128, use_subsecond=True)
        assert isinstance(result, int)

    def test_decode_si_time_pm_flag(self):
        result = decode_si_time(1, 3600)
        half_day = 12 * 3600 * TIME_UNITS_PER_SECOND
        assert result == 3600 * TIME_UNITS_PER_SECOND + half_day

    def test_decode_si_time_zero(self):
        result = decode_si_time(0, 0)
        assert result == 0


class TestFrameBuilders:
    def test_build_get_system_request(self):
        frame = build_get_system_request()
        assert len(frame) > 0
        assert frame[0] == STX
        assert frame[1] == CMD_GET_SYSTEM_VALUE
        assert frame[-1] == ETX

    def test_build_get_system_request_custom_params(self):
        frame = build_get_system_request(address=0x80, count=10)
        assert frame[3] == 0x80
        assert frame[4] == 10

    def test_build_wakeup_frame(self):
        frame = build_wakeup_frame()
        assert len(frame) > 0
        assert frame[0] == WAKEUP
        assert frame[1] == STX
        assert frame[-1] == ETX

    def test_build_wakeup_frame_has_crc(self):
        frame = build_wakeup_frame()
        # Check CRC bytes are present (at positions 4-5 after STX, cmd, len)
        assert frame[4] != 0 or frame[5] != 0


class TestStationData:
    def test_station_data_defaults(self):
        sd = StationData()
        assert sd.station_number == 0
        assert sd.station_mode == 0
        assert sd.extended is False
        assert sd.hand_shake is False
        assert sd.auto_send is False

    def test_station_data_custom(self):
        sd = StationData(station_number=42, station_mode=MODE_START,
                         extended=True, hand_shake=True, auto_send=True)
        assert sd.station_number == 42
        assert sd.station_mode == MODE_START
        assert sd.extended is True
        assert sd.hand_shake is True
        assert sd.auto_send is True

    def test_parse_station_data_invalid(self):
        result = parse_station_data(bytes([STX, 0x01]))
        assert result is None

    def test_parse_station_data_no_crc(self):
        data = bytes([STX, 0x02, 0x00, 0x00, 0x00, 0x00, ETX])
        result = parse_station_data(data)
        assert result is None