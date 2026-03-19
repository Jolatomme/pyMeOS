"""Tests for formats/xml_parser.py – MeOS native XML round-trip."""
import pytest
import sys
import tempfile
import os
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from models import Event, RunnerStatus
from formats.xml_parser import save_event_xml, load_event_xml
from utils.time_utils import encode


@pytest.fixture
def simple_event():
    ev = Event()
    ev.name = "Round Trip Event"
    ev.date = "2024-07-01"

    ctrl = ev.add_control("C31", [31])
    course = ev.add_course("Sprint")
    course.control_ids = [ctrl.id]
    course.length = 1500

    club = ev.add_club("OK Test")
    cls  = ev.add_class("W21")
    cls.course_id = course.id

    r = ev.add_runner("Eva", "Example", club_id=club.id, class_id=cls.id)
    r.card_number = 55555
    r.start_time  = encode(3600)
    r.status      = RunnerStatus.OK
    return ev


class TestXMLRoundTrip:
    def test_save_creates_file(self, simple_event):
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "test.mexml")
            save_event_xml(simple_event, path)
            assert os.path.exists(path)
            assert os.path.getsize(path) > 0

    def test_load_after_save(self, simple_event):
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "test.mexml")
            save_event_xml(simple_event, path)
            ev2 = load_event_xml(path)
            assert ev2 is not None
            assert ev2.name == "Round Trip Event"

    def test_runners_preserved(self, simple_event):
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "test.mexml")
            save_event_xml(simple_event, path)
            ev2 = load_event_xml(path)
            assert len([r for r in ev2.runners.values() if not r.removed]) == 1
            runner = next(iter(ev2.runners.values()))
            assert runner.first_name == "Eva"
            assert runner.last_name  == "Example"
            assert runner.card_number == 55555

    def test_controls_preserved(self, simple_event):
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "test.mexml")
            save_event_xml(simple_event, path)
            ev2 = load_event_xml(path)
            ctrls = [c for c in ev2.controls.values() if not c.removed]
            assert len(ctrls) == 1
            assert 31 in ctrls[0].numbers

    def test_courses_preserved(self, simple_event):
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "test.mexml")
            save_event_xml(simple_event, path)
            ev2 = load_event_xml(path)
            courses = [c for c in ev2.courses.values() if not c.removed]
            assert len(courses) == 1
            assert courses[0].name == "Sprint"
            assert courses[0].length == 1500

    def test_classes_preserved(self, simple_event):
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "test.mexml")
            save_event_xml(simple_event, path)
            ev2 = load_event_xml(path)
            classes = [c for c in ev2.classes.values() if not c.removed]
            assert any(c.name == "W21" for c in classes)

    def test_clubs_preserved(self, simple_event):
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "test.mexml")
            save_event_xml(simple_event, path)
            ev2 = load_event_xml(path)
            clubs = [c for c in ev2.clubs.values() if not c.removed]
            assert any(c.name == "OK Test" for c in clubs)

    def test_load_nonexistent_returns_none(self):
        ev = load_event_xml("/tmp/does_not_exist_pymeos.mexml")
        assert ev is None

    def test_multiple_runners(self):
        ev = Event()
        ev.name = "Multi"
        cls = ev.add_class("M21")
        for i in range(10):
            ev.add_runner(f"Runner{i}", "X", class_id=cls.id)
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "multi.mexml")
            save_event_xml(ev, path)
            ev2 = load_event_xml(path)
            assert len([r for r in ev2.runners.values() if not r.removed]) == 10
