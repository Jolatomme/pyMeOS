"""Tests for formats/iof30.py – IOF XML 3.0 round-trip."""
import pytest
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from models import Event, RunnerStatus
from formats.iof30 import (
    export_entry_list, export_result_list, export_course_data,
    import_entry_list, import_course_data,
)
from utils.time_utils import encode


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def populated_event():
    ev = Event()
    ev.name = "Test Event"
    ev.date = "2024-06-01"

    c31 = ev.add_control("31", [31])
    c32 = ev.add_control("32", [32])
    c33 = ev.add_control("33", [33])

    course = ev.add_course("Orange")
    course.control_ids = [c31.id, c32.id, c33.id]
    course.length = 3200
    course.climb  = 80

    club = ev.add_club("OK Alpha")
    club.short_name = "OKA"

    cls = ev.add_class("M21")
    cls.course_id = course.id

    r1 = ev.add_runner("Alice", "Smith", club_id=club.id, class_id=cls.id)
    r1.card_number = 123456
    r1.start_time  = encode(3600)
    r1.finish_time = encode(3600 + 3723)
    r1.t_status    = RunnerStatus.OK
    r1.status      = RunnerStatus.OK
    r1.place       = 1

    r2 = ev.add_runner("Bob", "Jones", club_id=club.id, class_id=cls.id)
    r2.card_number = 654321
    r2.start_time  = encode(3660)
    r2.finish_time = encode(3660 + 3900)
    r2.t_status    = RunnerStatus.OK
    r2.status      = RunnerStatus.OK
    r2.place       = 2

    return ev


# ---------------------------------------------------------------------------
# Course data export
# ---------------------------------------------------------------------------

class TestExportCourseData:
    def test_produces_bytes(self, populated_event):
        data = export_course_data(populated_event)
        assert isinstance(data, bytes)
        assert len(data) > 0

    def test_contains_course_name(self, populated_event):
        data = export_course_data(populated_event)
        assert b"Orange" in data

    def test_contains_control_ids(self, populated_event):
        data = export_course_data(populated_event)
        assert b"31" in data
        assert b"32" in data
        assert b"33" in data

    def test_valid_xml(self, populated_event):
        data = export_course_data(populated_event)
        try:
            from lxml import etree as ET
        except ImportError:
            import xml.etree.ElementTree as ET
        root = ET.fromstring(data)
        assert root is not None


# ---------------------------------------------------------------------------
# Entry list export
# ---------------------------------------------------------------------------

class TestExportEntryList:
    def test_produces_bytes(self, populated_event):
        data = export_entry_list(populated_event)
        assert isinstance(data, bytes)

    def test_contains_runner_names(self, populated_event):
        data = export_entry_list(populated_event)
        assert b"Alice" in data or b"Smith" in data

    def test_contains_club(self, populated_event):
        data = export_entry_list(populated_event)
        assert b"OK Alpha" in data or b"OKA" in data


# ---------------------------------------------------------------------------
# Result list export
# ---------------------------------------------------------------------------

class TestExportResultList:
    def test_produces_bytes(self, populated_event):
        data = export_result_list(populated_event)
        assert isinstance(data, bytes)

    def test_contains_ok_status(self, populated_event):
        data = export_result_list(populated_event)
        assert b"OK" in data or b"ok" in data.lower()

    def test_contains_class_name(self, populated_event):
        data = export_result_list(populated_event)
        assert b"M21" in data

    def test_valid_xml(self, populated_event):
        data = export_result_list(populated_event)
        try:
            from lxml import etree as ET
        except ImportError:
            import xml.etree.ElementTree as ET
        root = ET.fromstring(data)
        assert root is not None


# ---------------------------------------------------------------------------
# Course data import round-trip
# ---------------------------------------------------------------------------

class TestImportCourseData:
    def test_round_trip_controls(self, populated_event):
        # Export then re-import into fresh event
        data = export_course_data(populated_event)
        ev2  = Event()
        result = import_course_data(data, ev2)
        assert result["controls"] >= 3

    def test_round_trip_courses(self, populated_event):
        data = export_course_data(populated_event)
        ev2  = Event()
        result = import_course_data(data, ev2)
        assert result["courses"] >= 1
        course_names = [c.name for c in ev2.courses.values()]
        assert "Orange" in course_names


# ---------------------------------------------------------------------------
# Entry list import
# ---------------------------------------------------------------------------

class TestImportEntryList:
    def _make_entry_xml(self) -> bytes:
        return b"""<?xml version="1.0" encoding="utf-8"?>
<EntryList xmlns="http://www.orienteering.org/datastandard/3.0" iofVersion="3.0">
  <Event><Name>Test</Name></Event>
  <PersonEntry>
    <Person sex="M">
      <Name><Family>Doe</Family><Given>John</Given></Name>
    </Person>
    <Organisation><ShortName>OKB</ShortName><Name>OK Beta</Name></Organisation>
    <Class><Name>M21</Name></Class>
    <ControlCard punchingSystem="SI">987654</ControlCard>
    <StartTimeAllocationRequest/>
  </PersonEntry>
</EntryList>"""

    def test_imports_runner(self):
        ev = Event()
        ev.add_class("M21")
        n = import_entry_list(self._make_entry_xml(), ev)
        assert n >= 1
        names = [r.last_name for r in ev.runners.values()]
        assert "Doe" in names

    def test_creates_club(self):
        ev = Event()
        ev.add_class("M21")
        import_entry_list(self._make_entry_xml(), ev)
        club_names = [c.name for c in ev.clubs.values()]
        assert any("Beta" in n for n in club_names)

    def test_card_number_assigned(self):
        ev = Event()
        ev.add_class("M21")
        import_entry_list(self._make_entry_xml(), ev)
        cards = [r.card_number for r in ev.runners.values()]
        assert 987654 in cards
