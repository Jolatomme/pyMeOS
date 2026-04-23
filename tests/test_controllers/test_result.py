"""Tests for controllers/result.py - Core result calculation logic"""
import pytest
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from models import Event, Runner, Card, Course, Control, Class, RunnerStatus, Team
from models.card import SICard
from models.punch import Punch, SIPunch
from models.enums import SpecialPunchType, ControlStatus
from controllers.result import (
    evaluate_card, compute_class_results, compute_team_results,
    compute_all_results, _find_start_time, _find_finish_time, _check_controls
)
from utils.time_utils import encode, NO_TIME


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def event_with_course():
    """Event with a 3-control course and basic setup."""
    ev = Event()
    ev.name = "Test Event"
    
    # Controls
    c31 = ev.add_control("C31", [31])
    c32 = ev.add_control("C32", [32])
    c33 = ev.add_control("C33", [33])
    
    # Course
    course = ev.add_course("Orange")
    course.control_ids = [c31.id, c32.id, c33.id]
    
    # Class
    cls = ev.add_class("M21")
    cls.course_id = course.id
    
    return ev, cls, course, (c31, c32, c33)


def _make_card(ev, card_number, codes_times, start=3600, finish=None):
    """Helper to build a Card with given punch codes and times."""
    si = SICard()
    si.card_number = card_number
    si.start_punch.code = SpecialPunchType.Start
    si.start_punch.time = encode(start)
    for code, t in codes_times:
        from models.punch import SIPunch
        si.punches.append(SIPunch(code=code, time=encode(t)))
    if finish is not None:
        si.finish_punch.code = SpecialPunchType.Finish
        si.finish_punch.time = encode(finish)
    
    card = Card.from_si_card(si, ev)
    card.id = ev._next_id("card")
    ev.cards[card.id] = card
    return card


def _make_runner(ev, cls, first_name="Test", last_name="Runner", 
                 card_number=None, start_time=NO_TIME):
    """Helper to create a runner."""
    runner = ev.add_runner(first_name=first_name, last_name=last_name, class_id=cls.id)
    if card_number:
        runner.card_number = card_number
    if start_time != NO_TIME:
        runner.start_time = encode(start_time)
    return runner


# ---------------------------------------------------------------------------
# Tests for _find_start_time
# ---------------------------------------------------------------------------

class TestFindStartTime:
    def test_drawn_start_time_preferred(self, event_with_course):
        ev, cls, course, _ = event_with_course
        runner = _make_runner(ev, cls, start_time=3600)
        card = _make_card(ev, 123, [])
        
        result = _find_start_time(runner, card)
        assert result == encode(3600)
    
    def test_card_start_punch_used_when_no_drawn_time(self, event_with_course):
        ev, cls, course, _ = event_with_course
        runner = _make_runner(ev, cls)
        card = _make_card(ev, 123, [], start=3600)
        
        result = _find_start_time(runner, card)
        assert result == encode(3600)
    
    def test_check_punch_used_as_start(self, event_with_course):
        ev, cls, course, _ = event_with_course
        runner = _make_runner(ev, cls)
        # Create card with check punch as start
        si = SICard()
        si.card_number = 123
        si.start_punch.code = SpecialPunchType.Check
        si.start_punch.time = encode(3600)
        si.punches.append(SIPunch(code=31, time=encode(3610)))
        
        card = Card.from_si_card(si, ev)
        card.id = ev._next_id("card")
        ev.cards[card.id] = card
        
        result = _find_start_time(runner, card)
        assert result == encode(3600)
    
    def test_no_start_time_found(self, event_with_course):
        ev, cls, course, _ = event_with_course
        runner = _make_runner(ev, cls)
        # Create card with no start punch
        si = SICard()
        si.card_number = 123
        si.start_punch.code = SpecialPunchType.Unused
        si.punches.append(SIPunch(code=31, time=encode(3610)))
        
        card = Card.from_si_card(si, ev)
        card.id = ev._next_id("card")
        ev.cards[card.id] = card
        
        result = _find_start_time(runner, card)
        assert result == NO_TIME


# ---------------------------------------------------------------------------
# Tests for _find_finish_time
# ---------------------------------------------------------------------------

class TestFindFinishTime:
    def test_finish_punch_found(self, event_with_course):
        ev, cls, course, _ = event_with_course
        card = _make_card(ev, 123, [(31, 3610)], finish=3800)
        
        result = _find_finish_time(card)
        assert result == encode(3800)
    
    def test_no_finish_punch(self, event_with_course):
        ev, cls, course, _ = event_with_course
        card = _make_card(ev, 123, [(31, 3610)])
        
        result = _find_finish_time(card)
        assert result == NO_TIME


# ---------------------------------------------------------------------------
# Tests for _check_controls
# ---------------------------------------------------------------------------

class TestCheckControls:
    def test_all_controls_punched_in_order(self, event_with_course):
        ev, cls, course, controls = event_with_course
        card = _make_card(ev, 123, [(31, 3610), (32, 3620), (33, 3630)], finish=3800)
        
        result = _check_controls(card, course, ev)
        assert result == RunnerStatus.OK
    
    def test_missing_control(self, event_with_course):
        ev, cls, course, controls = event_with_course
        # Missing control 32
        card = _make_card(ev, 123, [(31, 3610), (33, 3630)], finish=3800)
        
        result = _check_controls(card, course, ev)
        assert result == RunnerStatus.MP
    
    def test_controls_out_of_order(self, event_with_course):
        ev, cls, course, controls = event_with_course
        # Controls punched out of order: 31, 33, 32
        card = _make_card(ev, 123, [(31, 3610), (33, 3620), (32, 3630)], finish=3800)
        
        result = _check_controls(card, course, ev)
        assert result == RunnerStatus.MP
    
    def test_extra_controls_ignored(self, event_with_course):
        ev, cls, course, controls = event_with_course
        # Extra control 99 punched but not required
        card = _make_card(ev, 123, [(31, 3610), (99, 3615), (32, 3620), (33, 3630)], finish=3800)
        
        result = _check_controls(card, course, ev)
        assert result == RunnerStatus.OK


# ---------------------------------------------------------------------------
# Tests for evaluate_card
# ---------------------------------------------------------------------------

class TestEvaluateCard:
    def test_ok_runner(self, event_with_course):
        ev, cls, course, _ = event_with_course
        runner = _make_runner(ev, cls, card_number=123, start_time=3600)
        card = _make_card(ev, 123, [(31, 3610), (32, 3620), (33, 3630)], finish=3800)
        
        evaluate_card(runner, card, ev)
        
        assert runner.t_status == RunnerStatus.OK
        assert runner.t_start_time == encode(3600)
        assert runner.finish_time == encode(3800)
        assert runner.tmp_result.running_time == encode(200)  # 3800 - 3600 = 200
    
    def test_dns_runner(self, event_with_course):
        ev, cls, course, _ = event_with_course
        runner = _make_runner(ev, cls, card_number=123)
        runner.status = RunnerStatus.DNS
        card = _make_card(ev, 123, [(31, 3610)], finish=3800)
        
        evaluate_card(runner, card, ev)
        
        assert runner.t_status == RunnerStatus.DNS
    
    def test_dnf_runner(self, event_with_course):
        ev, cls, course, _ = event_with_course
        runner = _make_runner(ev, cls, card_number=123, start_time=3600)
        # All controls but no finish punch
        card = _make_card(ev, 123, [(31, 3610), (32, 3620), (33, 3630)], finish=None)
        
        evaluate_card(runner, card, ev)
        
        assert runner.t_status == RunnerStatus.DNF
        assert runner.finish_time == NO_TIME
    
    def test_mp_runner(self, event_with_course):
        ev, cls, course, _ = event_with_course
        runner = _make_runner(ev, cls, card_number=123, start_time=3600)
        # Missing control 32
        card = _make_card(ev, 123, [(31, 3610), (33, 3630)], finish=3800)
        
        evaluate_card(runner, card, ev)
        
        assert runner.t_status == RunnerStatus.MP
    
    def test_no_card_runner(self, event_with_course):
        ev, cls, course, _ = event_with_course
        runner = _make_runner(ev, cls, card_number=123)
        
        evaluate_card(runner, None, ev)
        
        assert runner.t_status == RunnerStatus.Unknown
    
    def test_cancel_runner(self, event_with_course):
        ev, cls, course, _ = event_with_course
        runner = _make_runner(ev, cls, card_number=123)
        runner.status = RunnerStatus.CANCEL
        card = _make_card(ev, 123, [(31, 3610)], finish=3800)
        
        evaluate_card(runner, card, ev)
        
        assert runner.t_status == RunnerStatus.CANCEL


# ---------------------------------------------------------------------------
# Tests for compute_class_results
# ---------------------------------------------------------------------------

class TestComputeClassResults:
    def test_single_runner_class(self, event_with_course):
        ev, cls, course, _ = event_with_course
        runner = _make_runner(ev, cls, card_number=123, start_time=3600)
        card = _make_card(ev, 123, [(31, 3610), (32, 3620), (33, 3630)], finish=3800)
        
        runners = compute_class_results(ev, cls.id)
        
        assert len(runners) == 1
        assert runners[0].place == 1
        assert runners[0].t_status == RunnerStatus.OK
    
    def test_multiple_runners_sorted(self, event_with_course):
        ev, cls, course, _ = event_with_course
        # Runner 1: 200 units
        r1 = _make_runner(ev, cls, card_number=123, start_time=3600)
        card1 = _make_card(ev, 123, [(31, 3610), (32, 3620), (33, 3630)], finish=3800)
        
        # Runner 2: 150 units (faster)
        r2 = _make_runner(ev, cls, card_number=124, start_time=3600)
        card2 = _make_card(ev, 124, [(31, 3610), (32, 3620), (33, 3625)], finish=3750)
        
        runners = compute_class_results(ev, cls.id)
        
        assert len(runners) == 2
        assert runners[0].place == 1  # r2 should be first
        assert runners[1].place == 2  # r1 should be second
        assert runners[0].get_running_time() == encode(150)
        assert runners[1].get_running_time() == encode(200)
    
    def test_tied_runners(self, event_with_course):
        ev, cls, course, _ = event_with_course
        # Both runners with same time
        r1 = _make_runner(ev, cls, card_number=123, start_time=3600)
        card1 = _make_card(ev, 123, [(31, 3610), (32, 3620), (33, 3630)], finish=3800)
        
        r2 = _make_runner(ev, cls, card_number=124, start_time=3600)
        card2 = _make_card(ev, 124, [(31, 3610), (32, 3620), (33, 3630)], finish=3800)
        
        runners = compute_class_results(ev, cls.id)
        
        assert len(runners) == 2
        assert runners[0].place == 1  # Both get place 1 (tie)
        assert runners[1].place == 1
    
    def test_dnf_runners_no_place(self, event_with_course):
        ev, cls, course, _ = event_with_course
        r1 = _make_runner(ev, cls, card_number=123, start_time=3600)
        # All controls but no finish = DNF
        card1 = _make_card(ev, 123, [(31, 3610), (32, 3620), (33, 3630)], finish=None)
        
        runners = compute_class_results(ev, cls.id)
        
        assert len(runners) == 1
        assert runners[0].place == 0  # DNF runners get place 0
        assert runners[0].t_status == RunnerStatus.DNF


# ---------------------------------------------------------------------------
# Tests for compute_team_results
# ---------------------------------------------------------------------------

class TestComputeTeamResults:
    def test_simple_relay_team(self, event_with_course):
        ev, cls, course, _ = event_with_course
        
        # Create a relay class
        from models.enums import ClassType
        relay_cls = ev.add_class("Relay")
        relay_cls.class_type = ClassType.Relay
        relay_cls.course_id = course.id
        
        # Create team
        team = ev.add_team("Team A", relay_cls.id)
        team.class_id = relay_cls.id  # Ensure class_id is set
        
        # Add runners to team
        r1 = _make_runner(ev, relay_cls, "Runner", "1", card_number=101, start_time=3600)
        r2 = _make_runner(ev, relay_cls, "Runner", "2", card_number=102, start_time=3700)
        
        team.runner_ids = [r1.id, r2.id]
        
        # Create cards
        card1 = _make_card(ev, 101, [(31, 3610), (32, 3620), (33, 3630)], finish=3800)
        card2 = _make_card(ev, 102, [(31, 3710), (32, 3720), (33, 3730)], finish=3900)
        
        teams = compute_team_results(ev, relay_cls.id)
        
        assert len(teams) == 1
        assert teams[0].t_status == RunnerStatus.OK
        assert teams[0].t_total_time == encode(400)  # 200 + 200
        assert teams[0].place == 1
    
    def test_team_with_dnf_runner(self, event_with_course):
        ev, cls, course, _ = event_with_course
        
        # Create a relay class
        from models.enums import ClassType
        relay_cls = ev.add_class("Relay")
        relay_cls.class_type = ClassType.Relay
        relay_cls.course_id = course.id
        
        # Create team
        team = ev.add_team("Team B", relay_cls.id)
        team.class_id = relay_cls.id  # Ensure class_id is set
        
        # Add runners to team
        r1 = _make_runner(ev, relay_cls, "Runner", "1", card_number=101, start_time=3600)
        r2 = _make_runner(ev, relay_cls, "Runner", "2", card_number=102, start_time=3700)
        
        team.runner_ids = [r1.id, r2.id]
        
        # First runner OK, second MP (missing controls)
        card1 = _make_card(ev, 101, [(31, 3610), (32, 3620), (33, 3630)], finish=3800)
        card2 = _make_card(ev, 102, [(31, 3710)], finish=3800)  # MP - missing 32, 33
        
        teams = compute_team_results(ev, relay_cls.id)
        
        assert len(teams) == 1
        assert teams[0].t_status == RunnerStatus.MP
        assert teams[0].t_total_time == NO_TIME
        assert teams[0].place == 0


# ---------------------------------------------------------------------------
# Tests for compute_all_results
# ---------------------------------------------------------------------------

class TestComputeAllResults:
    def test_compute_all_empty_event(self):
        ev = Event()
        compute_all_results(ev)
        # Should not crash
        assert True
    
    def test_compute_all_multiple_classes(self, event_with_course):
        ev, cls, course, _ = event_with_course
        
        # Add second class
        cls2 = ev.add_class("M35")
        cls2.course_id = course.id
        
        # Add runners to both classes
        r1 = _make_runner(ev, cls, "Alice", "Smith", 101, 3600)
        r2 = _make_runner(ev, cls2, "Bob", "Jones", 102, 3600)
        
        card1 = _make_card(ev, 101, [(31, 3610), (32, 3620), (33, 3630)], finish=3800)
        card2 = _make_card(ev, 102, [(31, 3610), (32, 3620), (33, 3630)], finish=3900)
        
        compute_all_results(ev)
        
        # Check both runners have results
        assert r1.place == 1
        assert r2.place == 1
        assert r1.t_status == RunnerStatus.OK
        assert r2.t_status == RunnerStatus.OK
