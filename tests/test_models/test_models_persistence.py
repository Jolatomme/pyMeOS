"""Tests for persistence/event_repo.py – DB round-trip."""
import pytest
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from models import Event, RunnerStatus
from models.enums import ClassType
from persistence import init_db, EventRepository
from utils.time_utils import encode


@pytest.fixture(autouse=True)
def memory_db():
    init_db("sqlite:///:memory:")


@pytest.fixture
def repo():
    return EventRepository()


@pytest.fixture
def full_event():
    ev = Event()
    ev.name = "DB Test Event"
    ev.date = "2024-08-15"

    ctrl   = ev.add_control("C31", [31])
    course = ev.add_course("Blue")
    course.control_ids = [ctrl.id]
    course.length = 5000

    club = ev.add_club("OK Club")
    cls  = ev.add_class("M21")
    cls.course_id = course.id

    r1 = ev.add_runner("Alice", "A", club_id=club.id, class_id=cls.id)
    r1.card_number = 100001
    r1.start_time  = encode(3600)
    r1.status      = RunnerStatus.OK

    r2 = ev.add_runner("Bob", "B", club_id=club.id, class_id=cls.id)
    r2.card_number = 100002
    r2.status      = RunnerStatus.DNS

    team = ev.add_team("Alpha", club_id=club.id, class_id=cls.id)
    team.runner_ids = [r1.id, r2.id]

    return ev


class TestEventRepo:
    def test_save_returns_id(self, repo, full_event):
        eid = repo.save_event(full_event)
        assert eid > 0

    def test_load_basic_fields(self, repo, full_event):
        repo.save_event(full_event)
        ev2 = repo.load_event(full_event.id)
        assert ev2 is not None
        assert ev2.name == "DB Test Event"
        assert ev2.date == "2024-08-15"

    def test_controls_persisted(self, repo, full_event):
        repo.save_event(full_event)
        ev2 = repo.load_event(full_event.id)
        ctrls = [c for c in ev2.controls.values() if not c.removed]
        assert len(ctrls) == 1
        assert 31 in ctrls[0].numbers

    def test_courses_persisted(self, repo, full_event):
        repo.save_event(full_event)
        ev2 = repo.load_event(full_event.id)
        courses = [c for c in ev2.courses.values() if not c.removed]
        assert len(courses) == 1
        assert courses[0].name == "Blue"
        assert courses[0].length == 5000

    def test_runners_persisted(self, repo, full_event):
        repo.save_event(full_event)
        ev2 = repo.load_event(full_event.id)
        runners = [r for r in ev2.runners.values() if not r.removed]
        assert len(runners) == 2
        names = {r.first_name for r in runners}
        assert "Alice" in names
        assert "Bob" in names

    def test_runner_status_persisted(self, repo, full_event):
        repo.save_event(full_event)
        ev2 = repo.load_event(full_event.id)
        alice = next(r for r in ev2.runners.values() if r.first_name == "Alice")
        bob   = next(r for r in ev2.runners.values() if r.first_name == "Bob")
        assert alice.status == RunnerStatus.OK
        assert bob.status   == RunnerStatus.DNS

    def test_runner_card_number_persisted(self, repo, full_event):
        repo.save_event(full_event)
        ev2 = repo.load_event(full_event.id)
        alice = next(r for r in ev2.runners.values() if r.first_name == "Alice")
        assert alice.card_number == 100001

    def test_clubs_persisted(self, repo, full_event):
        repo.save_event(full_event)
        ev2 = repo.load_event(full_event.id)
        clubs = [c for c in ev2.clubs.values() if not c.removed]
        assert len(clubs) == 1
        assert clubs[0].name == "OK Club"

    def test_teams_persisted(self, repo, full_event):
        repo.save_event(full_event)
        ev2 = repo.load_event(full_event.id)
        teams = [t for t in ev2.teams.values() if not t.removed]
        assert len(teams) == 1
        assert teams[0].name == "Alpha"
        assert len(teams[0].runner_ids) == 2

    def test_list_events(self, repo, full_event):
        repo.save_event(full_event)
        events = repo.list_events()
        assert any(e["name"] == "DB Test Event" for e in events)

    def test_delete_event(self, repo, full_event):
        repo.save_event(full_event)
        eid = full_event.id
        ok  = repo.delete_event(eid)
        assert ok
        ev2 = repo.load_event(eid)
        assert ev2 is None

    def test_update_event(self, repo, full_event):
        repo.save_event(full_event)
        full_event.name = "Updated Name"
        repo.save_event(full_event)
        ev2 = repo.load_event(full_event.id)
        assert ev2.name == "Updated Name"

    def test_multiple_events(self, repo):
        ev1 = Event(); ev1.name = "Event One"
        ev2 = Event(); ev2.name = "Event Two"
        repo.save_event(ev1)
        repo.save_event(ev2)
        all_events = repo.list_events()
        names = {e["name"] for e in all_events}
        assert "Event One" in names
        assert "Event Two" in names
