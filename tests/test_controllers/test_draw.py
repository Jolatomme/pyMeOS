"""Tests for controllers/draw.py"""
import pytest
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from models import Event, RunnerStatus, Class
from controllers.draw import assign_start_times, assign_pursuit_starts, draw_lots
from controllers.result import compute_class_results
from utils.time_utils import encode, NO_TIME


@pytest.fixture
def event_with_class():
    ev  = Event()
    cls = ev.add_class("M21")
    club = ev.add_club("OKA")
    for name in ["Alice", "Bob", "Carol", "Dave", "Eve"]:
        r = ev.add_runner(name, "X", club_id=club.id, class_id=cls.id)
    return ev, cls


@pytest.fixture
def event_with_multiple_clubs():
    """Event with runners from multiple clubs for club separation tests."""
    ev = Event()
    cls = ev.add_class("M21")
    club1 = ev.add_club("ClubA")
    club2 = ev.add_club("ClubB")
    club3 = ev.add_club("ClubC")
    for name, club_id in [("A1", club1), ("A2", club1), ("B1", club2), 
                          ("B2", club2), ("C1", club3)]:
        ev.add_runner(name, "X", club_id=club_id, class_id=cls.id)
    return ev, cls


@pytest.fixture
def event_for_pursuit():
    """Event with runners having results for pursuit start testing."""
    ev = Event()
    cls = ev.add_class("M21")
    club = ev.add_club("Test")
    for name, time_sec in [("Winner", 1800), ("Second", 2000), ("Third", 2200), ("Fourth", 2500)]:
        r = ev.add_runner(name, "X", club_id=club.id, class_id=cls.id)
        r.start_time = encode(3600)
        r.status = RunnerStatus.OK
        r._running_time = encode(time_sec)
    return ev, cls


class TestAssignStartTimes:
    def test_assigns_all_runners(self, event_with_class):
        ev, cls = event_with_class
        runners = assign_start_times(
            ev, cls.id, first_start=encode(3600),
            interval=encode(120), scramble=False, seed=42)
        assert len(runners) == 5
        for r in runners:
            assert r.start_time != NO_TIME

    def test_sequential_without_scramble(self, event_with_class):
        ev, cls = event_with_class
        runners = assign_start_times(
            ev, cls.id, first_start=encode(3600),
            interval=encode(120), scramble=False)
        times = [r.start_time for r in runners]
        assert times == sorted(times)
        assert times[0] == encode(3600)
        assert times[1] == encode(3720)  # +2min

    def test_scramble_produces_start_times(self, event_with_class):
        ev, cls = event_with_class
        runners = assign_start_times(
            ev, cls.id, first_start=encode(3600),
            interval=encode(60), scramble=True, seed=0)
        for r in runners:
            assert r.start_time >= encode(3600)

    def test_start_numbers_assigned(self, event_with_class):
        ev, cls = event_with_class
        runners = assign_start_times(
            ev, cls.id, first_start=encode(3600),
            interval=encode(60), scramble=False)
        start_nos = sorted(r.start_no for r in runners)
        assert start_nos == list(range(1, 6))

    def test_two_per_slot(self, event_with_class):
        ev, cls = event_with_class
        runners = assign_start_times(
            ev, cls.id, first_start=encode(3600),
            interval=encode(120), scramble=False,
            n_before_interval=2)
        # Slot 0 → runners 0,1; Slot 1 → runners 2,3; Slot 2 → runner 4
        times = [r.start_time for r in runners]
        assert times[0] == times[1] == encode(3600)
        assert times[2] == times[3] == encode(3720)
        assert times[4] == encode(3840)

    def test_dns_runners_excluded(self, event_with_class):
        ev, cls = event_with_class
        runners_all = list(ev.runners.values())
        runners_all[0].status = RunnerStatus.DNS
        result = assign_start_times(
            ev, cls.id, first_start=encode(3600),
            interval=encode(60), scramble=False)
        assert len(result) == 4

    def test_empty_class_returns_empty(self, event_with_class):
        ev, cls = event_with_class
        cls2 = ev.add_class("W21")
        result = assign_start_times(
            ev, cls2.id, first_start=encode(3600), interval=encode(60))
        assert result == []

    def test_cancel_status_excluded(self, event_with_class):
        ev, cls = event_with_class
        runners_all = list(ev.runners.values())
        runners_all[0].status = RunnerStatus.CANCEL
        result = assign_start_times(
            ev, cls.id, first_start=encode(3600),
            interval=encode(60), scramble=False)
        assert len(result) == 4

    def test_removed_runners_excluded(self, event_with_class):
        ev, cls = event_with_class
        runners_all = list(ev.runners.values())
        runners_all[0].remove()
        result = assign_start_times(
            ev, cls.id, first_start=encode(3600),
            interval=encode(60), scramble=False)
        assert len(result) == 4

    def test_separate_clubs_enabled(self, event_with_multiple_clubs):
        ev, cls = event_with_multiple_clubs
        runners = assign_start_times(
            ev, cls.id, first_start=encode(3600),
            interval=encode(60), scramble=True, seed=42,
            separate_clubs=True)
        assert len(runners) == 5


class TestAssignPursuitStarts:
    def test_pursuit_basic(self, event_for_pursuit):
        ev, cls = event_for_pursuit
        runners = assign_pursuit_starts(ev, cls.id, nominal_first=encode(3600))
        assert len(runners) == 4
        times = [r.start_time for r in runners if r.status == RunnerStatus.OK]
        assert times[0] == encode(3600)

    def test_pursuit_empty_class(self, event_with_class):
        ev, cls = event_with_class
        cls2 = ev.add_class("W21")
        result = assign_pursuit_starts(ev, cls2.id, nominal_first=encode(3600))
        assert result == []

    def test_pursuit_no_valid_results(self, event_with_class):
        ev, cls = event_with_class
        runners = list(ev.runners.values())
        for r in runners:
            r.status = RunnerStatus.DNF
        result = assign_pursuit_starts(ev, cls.id, nominal_first=encode(3600))
        assert len(result) == 5


class TestDrawLots:
    def test_assigns_start_numbers(self, event_with_class):
        ev, cls = event_with_class
        runners = draw_lots(ev, cls.id)
        assert len(runners) == 5
        start_nos = sorted(r.start_no for r in runners)
        assert start_nos == list(range(1, 6))

    def test_draw_lots_empty_class(self, event_with_class):
        ev, cls = event_with_class
        cls2 = ev.add_class("W21")
        result = draw_lots(ev, cls2.id)
        assert result == []

    def test_draw_lots_removed_excluded(self, event_with_class):
        ev, cls = event_with_class
        runners_all = list(ev.runners.values())
        runners_all[0].remove()
        result = draw_lots(ev, cls.id)
        assert len(result) == 4
