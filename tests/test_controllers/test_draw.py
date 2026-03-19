"""Tests for controllers/draw.py"""
import pytest
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from models import Event, RunnerStatus
from controllers.draw import assign_start_times, assign_pursuit_starts, draw_lots
from utils.time_utils import encode, NO_TIME


@pytest.fixture
def event_with_class():
    ev  = Event()
    cls = ev.add_class("M21")
    club = ev.add_club("OKA")
    for name in ["Alice", "Bob", "Carol", "Dave", "Eve"]:
        r = ev.add_runner(name, "X", club_id=club.id, class_id=cls.id)
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


class TestDrawLots:
    def test_assigns_start_numbers(self, event_with_class):
        ev, cls = event_with_class
        runners = draw_lots(ev, cls.id)
        assert len(runners) == 5
        start_nos = sorted(r.start_no for r in runners)
        assert start_nos == list(range(1, 6))
