"""Tests for models/card.py and models/punch.py"""
import pytest
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from models import Card, SICard
from models.punch import Punch, SIPunch
from models.enums import SpecialPunchType
from utils.time_utils import encode, NO_TIME


@pytest.fixture
def si_card_with_data():
    si = SICard()
    si.card_number  = 123456
    si.check_punch  = SIPunch(code=3, time=encode(3550))
    si.start_punch  = SIPunch(code=1, time=encode(3600))
    si.finish_punch = SIPunch(code=2, time=encode(3600 + 3723))
    si.punches      = [
        SIPunch(code=31, time=encode(3660)),
        SIPunch(code=32, time=encode(3720)),
        SIPunch(code=33, time=encode(3780)),
    ]
    return si


class TestSICard:
    def test_empty(self):
        si = SICard()
        assert si.empty()

    def test_not_empty_after_number(self, si_card_with_data):
        assert not si_card_with_data.empty()

    def test_get_first_time(self, si_card_with_data):
        # check_punch at 3550 is earliest
        assert si_card_with_data.get_first_time() == encode(3550)

    def test_manual_input_flag(self):
        si = SICard()
        si.runner_id = 5
        assert si.is_manual_input()


class TestCardFromSICard:
    def test_card_number(self, si_card_with_data):
        card = Card.from_si_card(si_card_with_data)
        assert card.card_number == 123456

    def test_punches_count(self, si_card_with_data):
        card = Card.from_si_card(si_card_with_data)
        # check + start + 3 intermediate + finish = 6
        assert len(card.punches) == 6

    def test_start_punch_present(self, si_card_with_data):
        card = Card.from_si_card(si_card_with_data)
        sp = next((p for p in card.punches if p.is_start()), None)
        assert sp is not None
        assert sp.time == encode(3600)

    def test_finish_punch_present(self, si_card_with_data):
        card = Card.from_si_card(si_card_with_data)
        fp = next((p for p in card.punches if p.is_finish()), None)
        assert fp is not None

    def test_get_start_time(self, si_card_with_data):
        card = Card.from_si_card(si_card_with_data)
        assert card.get_start_time() == encode(3600)

    def test_get_finish_time(self, si_card_with_data):
        card = Card.from_si_card(si_card_with_data)
        assert card.get_finish_time() == encode(3600 + 3723)

    def test_intermediate_punches(self, si_card_with_data):
        card = Card.from_si_card(si_card_with_data)
        codes = [p.type_code for p in card.punches
                 if p.type_code not in (1, 2, 3)]
        assert sorted(codes) == [31, 32, 33]


class TestPunch:
    def test_is_start(self):
        p = Punch(type_code=SpecialPunchType.Start)
        assert p.is_start()
        assert not p.is_finish()

    def test_is_finish(self):
        p = Punch(type_code=SpecialPunchType.Finish)
        assert p.is_finish()

    def test_is_check(self):
        p = Punch(type_code=SpecialPunchType.Check)
        assert p.is_check()

    def test_control_number(self):
        p = Punch(type_code=42)
        assert p.control_number == 42

    def test_control_number_special(self):
        p = Punch(type_code=SpecialPunchType.Start)
        assert p.control_number == 0

    def test_adjusted_time(self):
        p = Punch(time_raw=encode(3600),
                  time_adjust_fixed=10,
                  time_adjust_dynamic=5)
        assert p.adjusted_time == encode(3600) + 15

    def test_has_time_true(self):
        p = Punch(time_raw=encode(3600))
        assert p.has_time()

    def test_has_time_false(self):
        p = Punch(time_raw=NO_TIME)
        assert not p.has_time()

    def test_set_time_from_string(self):
        p = Punch()
        p.set_time_from_string("1:00:00")
        assert p.time_raw == encode(3600)


class TestVoltage:
    def test_voltage_string(self):
        card = Card(mili_volt=3650)
        assert "3.65" in card.get_voltage_string()

    def test_no_voltage(self):
        card = Card(mili_volt=0)
        assert card.get_voltage_string() == ""
