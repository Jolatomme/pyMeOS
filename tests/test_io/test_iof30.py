"""Tests for formats/iof30.py – IOF XML 3.0 round-trip."""
import pytest
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from models import Event, RunnerStatus, Sex, ClassType
from formats.iof30 import (
    export_entry_list, export_result_list, export_course_data,
    import_entry_list, import_course_data, import_iof30,
    _iof_time, _parse_iof_time, _status_to_iof,
)
from utils.time_utils import encode, NO_TIME


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


@pytest.fixture
def event_with_rogaining():
    """Event with rogaining control (has rogaining_points)."""
    ev = Event()
    c = ev.add_control("101", [101])
    c.rogaining_points = 10
    return ev


@pytest.fixture
def event_with_removed():
    """Event with removed runners/classes."""
    ev = Event()
    cls = ev.add_class("M21")
    r = ev.add_runner("ToRemove", "X", class_id=cls.id)
    r.remove()
    return ev


# ---------------------------------------------------------------------------
# Helper function tests
# ---------------------------------------------------------------------------

class TestHelperFunctions:
    def test_iof_time_zero(self):
        assert _iof_time(0) == ""
        assert _iof_time(NO_TIME) == ""

    def test_iof_time_hours(self):
        result = _iof_time(encode(3600 * 2))  # 2 hours
        assert "2H" in result

    def test_iof_time_minutes(self):
        result = _iof_time(encode(60 * 30))  # 30 minutes
        assert "30M" in result

    def test_iof_time_seconds(self):
        result = _iof_time(encode(45))  # 45 seconds
        assert "45" in result

    def test_parse_iof_time_empty(self):
        assert _parse_iof_time("") == NO_TIME
        assert _parse_iof_time("PT") == NO_TIME

    def test_parse_iof_time_hours(self):
        result = _parse_iof_time("PT2H30M15S")
        assert result == encode(2*3600 + 30*60 + 15)

    def test_parse_iof_time_minutes(self):
        result = _parse_iof_time("PT45M30S")
        assert result == encode(45*60 + 30)

    def test_parse_iof_time_seconds(self):
        result = _parse_iof_time("PT30.5S")
        assert result > 0

    def test_status_to_iof_ok(self):
        assert _status_to_iof(RunnerStatus.OK) == "OK"

    def test_status_to_iof_dns(self):
        assert _status_to_iof(RunnerStatus.DNS) == "DidNotStart"

    def test_status_to_iof_dnf(self):
        assert _status_to_iof(RunnerStatus.DNF) == "DidNotFinish"

    def test_status_to_iof_mp(self):
        assert _status_to_iof(RunnerStatus.MP) == "MissingPunch"

    def test_status_to_iof_dq(self):
        assert _status_to_iof(RunnerStatus.DQ) == "Disqualified"

    def test_status_to_iof_max(self):
        assert _status_to_iof(RunnerStatus.MAX) == "OverTime"

    def test_status_to_iof_unknown(self):
        assert _status_to_iof(RunnerStatus.Unknown) == "Inactive"


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

    def test_excludes_removed(self, event_with_removed):
        data = export_course_data(event_with_removed)
        assert b"ToRemove" not in data

    def test_rogaining_points(self, event_with_rogaining):
        data = export_course_data(event_with_rogaining)
        assert b"10" in data


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

    def test_excludes_removed_runners(self, event_with_removed):
        data = export_entry_list(event_with_removed)
        assert b"ToRemove" not in data


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

    def test_no_class_excluded(self):
        ev = Event()
        r = ev.add_runner("Test", "User")
        data = export_result_list(ev)
        assert b"Test" not in data


# ---------------------------------------------------------------------------
# Course data import round-trip
# ---------------------------------------------------------------------------

class TestImportCourseData:
    def test_round_trip_controls(self, populated_event):
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


# ---------------------------------------------------------------------------
# import_iof30 function
# ---------------------------------------------------------------------------

class TestImportIof30:
    def test_import_iof30_entry_list(self, tmp_path):
        xml_data = b"""<?xml version="1.0" encoding="utf-8"?>
<EntryList xmlns="http://www.orienteering.org/datastandard/3.0" iofVersion="3.0">
  <Event><Name>Test</Name></Event>
  <PersonEntry>
    <Person><Name><Family>Test</Family><Given>User</Given></Name></Person>
    <Class><Name>M21</Name></Class>
  </PersonEntry>
</EntryList>"""
        f = tmp_path / "test.xml"
        f.write_bytes(xml_data)
        ev = Event()
        import_iof30(str(f), ev)
        assert len(ev.runners) > 0


class TestEdgeCases:
    def test_empty_event(self):
        ev = Event()
        ev.name = "Empty"
        data = export_entry_list(ev)
        assert b"Empty" in data

    def test_event_without_classes(self):
        ev = Event()
        ev.add_runner("Test", "User")
        data = export_result_list(ev)
        assert isinstance(data, bytes)
