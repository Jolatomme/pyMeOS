"""Tests for controllers/result.py (evaluate_card, compute_class_results)"""
import pytest
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from models import Event, Runner, Card, Course, Control, Class, RunnerStatus
from models.card import SICard
from models.punch import Punch
from models.enums import SpecialPunchType, ControlStatus
from controllers.result import evaluate_card, compute_class_results, compute_team_results
from utils.time_utils import encode, NO_TIME


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def event_with_course():
    """Event with a 3-control course and 3 runners."""
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
    si.card_number  = card_number
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


# ---------------------------------------------------------------------------
# evaluate_card tests
# ---------------------------------------------------------------------------

class TestEvaluateCard:
    def test_ok_result(self, event_with_course):
        ev, cls, course, (c31, c32, c33) = event_with_course
        runner = ev.add_runner("Alice", "A", class_id=cls.id)
        runner.start_time = encode(3600)
        card = _make_card(ev, 1001, [(31, 3660), (32, 3720), (33, 3780)],
                          start=3600, finish=3600+300)
        runner.card_id = card.id

        evaluate_card(runner, card, ev)

        assert runner.t_status == RunnerStatus.OK
        assert runner.finish_time == encode(3600 + 300)

    def test_mispunch(self, event_with_course):
        ev, cls, course, (c31, c32, c33) = event_with_course
        runner = ev.add_runner("Bob", "B", class_id=cls.id)
        runner.start_time = encode(3600)
        # Missing control 32
        card = _make_card(ev, 1002, [(31, 3660), (33, 3780)],
                          start=3600, finish=3600+300)
        runner.card_id = card.id

        evaluate_card(runner, card, ev)
        assert runner.t_status == RunnerStatus.MP

    def test_dnf_no_finish(self, event_with_course):
        ev, cls, course, (c31, c32, c33) = event_with_course
        runner = ev.add_runner("Carol", "C", class_id=cls.id)
        runner.start_time = encode(3600)
        # All controls but no finish
        card = _make_card(ev, 1003, [(31, 3660), (32, 3720), (33, 3780)],
                          start=3600, finish=None)
        runner.card_id = card.id

        evaluate_card(runner, card, ev)
        assert runner.t_status == RunnerStatus.DNF

    def test_dns_not_re_evaluated(self, event_with_course):
        ev, cls, course, _ = event_with_course
        runner = ev.add_runner("Dave", "D", class_id=cls.id)
        runner.status = RunnerStatus.DNS
        card = _make_card(ev, 1004, [(31, 3660), (32, 3720), (33, 3780)],
                          start=3600, finish=3600+300)
        runner.card_id = card.id

        evaluate_card(runner, card, ev)
        assert runner.t_status == RunnerStatus.DNS

    def test_no_card(self, event_with_course):
        ev, cls, course, _ = event_with_course
        runner = ev.add_runner("Eve", "E", class_id=cls.id)
        evaluate_card(runner, None, ev)
        assert runner.t_status == RunnerStatus.Unknown


# ---------------------------------------------------------------------------
# compute_class_results tests
# ---------------------------------------------------------------------------

class TestComputeClassResults:
    def _setup_class(self, ev, cls, course, runners_data):
        """Add runners with complete cards."""
        results = []
        for name, running_time in runners_data:
            r = ev.add_runner(name, "X", class_id=cls.id)
            r.start_time = encode(3600)
            card = _make_card(
                ev, hash(name) % 100000,
                [(31, 3660), (32, 3720), (33, 3780)],
                start=3600, finish=3600 + running_time,
            )
            r.card_id = card.id
            results.append(r)
        return results

    def test_places_assigned(self, event_with_course):
        ev, cls, course, _ = event_with_course
        self._setup_class(ev, cls, course, [
            ("Alice", 300), ("Bob", 250), ("Carol", 400)])
        runners = compute_class_results(ev, cls.id)
        ok = [r for r in runners if r.t_status == RunnerStatus.OK]
        assert len(ok) == 3
        # Sort should be fastest first
        times = [r.get_running_time() for r in ok]
        assert times == sorted(times)
        assert ok[0].place == 1
        assert ok[1].place == 2
        assert ok[2].place == 3

    def test_tied_place(self, event_with_course):
        ev, cls, course, _ = event_with_course
        self._setup_class(ev, cls, course, [("A", 300), ("B", 300)])
        runners = compute_class_results(ev, cls.id)
        ok = [r for r in runners if r.t_status == RunnerStatus.OK]
        assert ok[0].place == 1
        assert ok[1].place == 1

    def test_mp_gets_no_place(self, event_with_course):
        ev, cls, course, (c31, c32, c33) = event_with_course
        r = ev.add_runner("MP Runner", "X", class_id=cls.id)
        r.start_time = encode(3600)
        card = _make_card(ev, 9999, [(31, 3660)],  # missing c32, c33
                          start=3600, finish=3600+300)
        r.card_id = card.id
        runners = compute_class_results(ev, cls.id)
        mp = next(x for x in runners if x.id == r.id)
        assert mp.place == 0


# ---------------------------------------------------------------------------
# Relay team result tests
# ---------------------------------------------------------------------------

class TestComputeTeamResults:
    def test_relay_total_time(self, event_with_course):
        ev, cls, course, (c31, c32, c33) = event_with_course
        cls.class_type = __import__("models.enums", fromlist=["ClassType"]).ClassType.Relay

        r1 = ev.add_runner("Leg1", "X", class_id=cls.id)
        r2 = ev.add_runner("Leg2", "X", class_id=cls.id)

        for runner, running_time in [(r1, 300), (r2, 360)]:
            runner.start_time = encode(3600)
            card = _make_card(ev, hash(runner.name) % 100000,
                              [(31, 3660), (32, 3720), (33, 3780)],
                              start=3600, finish=3600+running_time)
            runner.card_id = card.id

        team = ev.add_team("Alpha", class_id=cls.id)
        team.runner_ids = [r1.id, r2.id]

        teams = compute_team_results(ev, cls.id)
        t = next(x for x in teams if x.id == team.id)
        assert t.t_status == RunnerStatus.OK
        assert t.t_total_time == encode(300 + 360)
