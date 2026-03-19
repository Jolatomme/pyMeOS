"""Tests for utils/time_utils.py"""
import pytest
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from utils.time_utils import (
    encode, decode, format_time, parse_time,
    time_diff, format_seconds, parse_time_seconds,
    NO_TIME, TIME_UNITS_PER_SECOND,
)


class TestEncodeDecode:
    def test_encode_whole_seconds(self):
        assert encode(60) == 600

    def test_encode_fractional(self):
        assert encode(1.5) == 15

    def test_encode_zero(self):
        assert encode(0) == 0

    def test_decode_round_trip(self):
        assert decode(encode(90)) == pytest.approx(90.0)

    def test_decode_zero(self):
        assert decode(0) == 0.0

    def test_time_units_per_second(self):
        assert TIME_UNITS_PER_SECOND == 10


class TestFormatTime:
    def test_no_time(self):
        assert format_time(NO_TIME) == ""

    def test_minutes_seconds(self):
        assert format_time(encode(90)) == "1:30"

    def test_hours(self):
        assert format_time(encode(3661)) == "1:01:01"

    def test_sub_second_on(self):
        result = format_time(encode(90) + 5, sub_second=True)
        assert result == "1:30.5"

    def test_sub_second_off(self):
        result = format_time(encode(90) + 5, sub_second=False)
        assert result == "1:30"

    def test_zero_minutes(self):
        assert format_time(encode(45)) == "0:45"

    def test_large_time(self):
        # 2h 30m 00s
        assert format_time(encode(9000)) == "2:30:00"


class TestParseTime:
    def test_mm_ss(self):
        assert parse_time("1:30") == encode(90)

    def test_hh_mm_ss(self):
        assert parse_time("1:01:01") == encode(3661)

    def test_sub_second(self):
        assert parse_time("1:30.5") == encode(90) + 5

    def test_empty_string(self):
        assert parse_time("") == NO_TIME

    def test_invalid_string(self):
        assert parse_time("notaime") == NO_TIME

    def test_zero_time(self):
        assert parse_time("0:00") == 0

    def test_round_trip(self):
        t = encode(3723)
        assert parse_time(format_time(t)) == t


class TestTimeDiff:
    def test_basic(self):
        assert time_diff(100, 500) == 400

    def test_no_time_start(self):
        assert time_diff(NO_TIME, 500) == NO_TIME

    def test_no_time_finish(self):
        assert time_diff(100, NO_TIME) == NO_TIME

    def test_both_no_time(self):
        assert time_diff(NO_TIME, NO_TIME) == NO_TIME


class TestFormatSeconds:
    def test_basic(self):
        assert format_seconds(3661) == "1:01:01"

    def test_zero(self):
        assert format_seconds(0) == ""


class TestParseTimeSeconds:
    def test_basic(self):
        assert parse_time_seconds("1:01:01") == 3661

    def test_empty(self):
        assert parse_time_seconds("") == 0
