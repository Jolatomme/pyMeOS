"""Tests for models/event.py"""
import pytest
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from models import Event, Runner, Team, Class, Course, Control, Club, RunnerStatus
from models.enums import ClassType


@pytest.fixture
def event():
    return Event()


class TestEventCreation:
    def test_event_starts_empty(self, event):
        s = event.statistics()
        assert s["runners"] == 0
        assert s["classes"] == 0
        assert s["controls"] == 0

    def test_event_name(self, event):
        event.name = "Summer Sprint"
        assert event.name == "Summer Sprint"


class TestAddObjects:
    def test_add_control(self, event):
        c = event.add_control("Control 31", [31])
        assert c.id > 0
        assert c.id in event.controls
        assert event.controls[c.id].name == "Control 31"
        assert 31 in event.controls[c.id].numbers

    def test_add_course(self, event):
        course = event.add_course("Short")
        assert course.id > 0
        assert course.name == "Short"

    def test_add_class(self, event):
        cls = event.add_class("M21")
        assert cls.id > 0
        assert cls.name == "M21"

    def test_add_club(self, event):
        club = event.add_club("OK Alpha")
        assert club.id > 0
        assert club.name == "OK Alpha"

    def test_add_club_deduplication(self, event):
        c1 = event.add_club("OK Beta")
        c2 = event.add_club("ok beta")   # case-insensitive
        assert c1.id == c2.id

    def test_add_runner(self, event):
        runner = event.add_runner("Alice", "Smith")
        assert runner.id > 0
        assert runner.first_name == "Alice"
        assert runner.last_name  == "Smith"

    def test_add_team(self, event):
        team = event.add_team("Alpha Team")
        assert team.id > 0
        assert team.name == "Alpha Team"


class TestLookups:
    def test_get_runner_by_card(self, event):
        r = event.add_runner("Bob", "Jones")
        r.card_number = 123456
        found = event.get_runner_by_card(123456)
        assert found is not None
        assert found.id == r.id

    def test_get_runner_by_card_not_found(self, event):
        assert event.get_runner_by_card(999999) is None

    def test_get_runners_by_class(self, event):
        cls = event.add_class("W21")
        r1  = event.add_runner("Carol", "A", class_id=cls.id)
        r2  = event.add_runner("Diana", "B", class_id=cls.id)
        r3  = event.add_runner("Eve",   "C")               # different class
        runners = event.get_runners_by_class(cls.id)
        ids = {r.id for r in runners}
        assert r1.id in ids
        assert r2.id in ids
        assert r3.id not in ids

    def test_get_class_by_name(self, event):
        event.add_class("H10")
        cls = event.get_class_by_name("h10")
        assert cls is not None
        assert cls.name == "H10"


class TestDeletion:
    def test_remove_runner(self, event):
        r = event.add_runner("X", "Y")
        rid = r.id
        ok  = event.remove_runner(rid)
        assert ok
        assert event.runners[rid].removed

    def test_remove_club_with_runners_blocked(self, event):
        club = event.add_club("Blocked Club")
        r    = event.add_runner("Z", "Q", club_id=club.id)
        ok   = event.remove_club(club.id)
        assert not ok  # has runners → cannot remove

    def test_remove_empty_club(self, event):
        club = event.add_club("Empty Club")
        ok   = event.remove_club(club.id)
        assert ok

    def test_remove_control_used_in_course(self, event):
        ctrl   = event.add_control("C1", [31])
        course = event.add_course("Test Course")
        course.control_ids = [ctrl.id]
        ok = event.remove_control(ctrl.id)
        assert not ok

    def test_remove_unused_control(self, event):
        ctrl = event.add_control("Free", [99])
        ok   = event.remove_control(ctrl.id)
        assert ok


class TestRevision:
    def test_revision_increments_on_add(self, event):
        rev0 = event.data_revision
        event.add_runner("A", "B")
        assert event.data_revision > rev0

    def test_clear_resets(self, event):
        event.add_runner("A", "B")
        event.clear()
        assert len(event.runners) == 0
        assert event.data_revision == 0


class TestNotifications:
    def test_subscriber_called_on_add(self, event):
        received = []
        event.subscribe("runners_changed", lambda t, p: received.append(p))
        r = event.add_runner("Notify", "Me")
        assert len(received) == 1
        assert received[0].id == r.id

    def test_unsubscribe(self, event):
        received = []
        cb = lambda t, p: received.append(p)
        event.subscribe("runners_changed", cb)
        event.unsubscribe("runners_changed", cb)
        event.add_runner("Ghost", "Runner")
        assert len(received) == 0
