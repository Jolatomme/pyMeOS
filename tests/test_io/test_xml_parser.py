"""
tests/test_io/test_xml_parser.py
================================
Tests for formats/xml_parser.py – covers:
  * PyMeOS native format round-trip  (<MeOS> root)
  * Real MeOS format loading         (<meosdata> root)
"""
import pytest
import sys
import tempfile
import os
import textwrap
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from models import Event, RunnerStatus
from formats.xml_parser import save_event_xml, load_event_xml
from utils.time_utils import encode, format_time, TIME_UNITS_PER_SECOND

_S = TIME_UNITS_PER_SECOND  # 10


# ===========================================================================
# Fixtures
# ===========================================================================

@pytest.fixture
def simple_event():
    ev = Event()
    ev.name = "Round Trip Event"
    ev.date = "2024-07-01"

    ctrl = ev.add_control("C31", [31])
    course = ev.add_course("Sprint")
    course.control_ids = [ctrl.id]
    course.length = 1500
    course.climb  = 50

    club = ev.add_club("OK Test")
    cls  = ev.add_class("W21")
    cls.course_id = course.id

    r = ev.add_runner("Eva", "Example", club_id=club.id, class_id=cls.id)
    r.card_number = 55555
    r.start_time  = encode(3600)
    r.status      = RunnerStatus.OK
    r.sex         = __import__("models").Sex.Female
    r.nationality = "FRA"
    return ev


# Minimal real-MeOS XML fixture (inline, no file dependency)
_MEOSDATA_XML = textwrap.dedent("""\
<?xml version="1.0" encoding="UTF-8"?>
<meosdata version="5.0">
<Name>Test Champ</Name>
<Date>2026-03-28</Date>
<ZeroTime>45000</ZeroTime>
<oData>
  <Organizer>COCS 7309</Organizer>
</oData>
<ControlList>
  <Control>
    <Id>31</Id>
    <Numbers>31</Numbers>
  </Control>
  <Control>
    <Id>32</Id>
    <Numbers>32</Numbers>
  </Control>
  <Control>
    <Id>33</Id>
    <Numbers>33</Numbers>
  </Control>
</ControlList>
<CourseList>
  <Course>
    <Id>1</Id>
    <Name>Orange</Name>
    <Length>3200</Length>
    <Controls>31;32;33;</Controls>
    <oData><Climb>80</Climb></oData>
  </Course>
</CourseList>
<ClassList>
  <Class>
    <Id>5</Id>
    <Name>H21</Name>
    <Course>1</Course>
    <oData>
      <FirstStart>3600</FirstStart>
      <StartInterval>120</StartInterval>
      <ClassFee>600</ClassFee>
    </oData>
  </Class>
</ClassList>
<ClubList>
  <Club>
    <Id>7309</Id>
    <Name>COCS</Name>
    <oData><ShortName>7309AR</ShortName></oData>
  </Club>
</ClubList>
<RunnerList>
  <Runner>
    <Id>101</Id>
    <Name>DUPONT, Jean</Name>
    <CardNo>123456</CardNo>
    <StartNo>1</StartNo>
    <Club>7309</Club>
    <Class>5</Class>
    <Start>3600</Start>
    <oData>
      <Sex>M</Sex>
      <Nationality>FRA</Nationality>
    </oData>
  </Runner>
  <Runner>
    <Id>102</Id>
    <Name>MARTIN, Claire</Name>
    <CardNo>654321</CardNo>
    <StartNo>2</StartNo>
    <Club>7309</Club>
    <Class>5</Class>
    <Start>3720</Start>
    <oData>
      <Sex>F</Sex>
      <Nationality>FRA</Nationality>
    </oData>
  </Runner>
  <Runner>
    <Id>103</Id>
    <Name>SANS CLUB</Name>
    <StartNo>3</StartNo>
    <Class>5</Class>
  </Runner>
</RunnerList>
<TeamList/>
</meosdata>
""").encode("utf-8")


@pytest.fixture
def meosdata_file(tmp_path):
    """Write the inline MeOS XML to a temp file and return the path."""
    p = tmp_path / "test.meosxml"
    p.write_bytes(_MEOSDATA_XML)
    return str(p)


# ===========================================================================
# PyMeOS native format – round-trip tests
# ===========================================================================

class TestPyMeOSRoundTrip:
    def test_save_creates_file(self, simple_event, tmp_path):
        path = str(tmp_path / "test.mexml")
        save_event_xml(simple_event, path)
        assert os.path.exists(path)
        assert os.path.getsize(path) > 0

    def test_load_after_save(self, simple_event, tmp_path):
        path = str(tmp_path / "test.mexml")
        save_event_xml(simple_event, path)
        ev2 = load_event_xml(path)
        assert ev2 is not None
        assert ev2.name == "Round Trip Event"
        assert ev2.date == "2024-07-01"

    def test_runners_preserved(self, simple_event, tmp_path):
        path = str(tmp_path / "test.mexml")
        save_event_xml(simple_event, path)
        ev2 = load_event_xml(path)
        live = [r for r in ev2.runners.values() if not r.removed]
        assert len(live) == 1
        r = live[0]
        assert r.first_name == "Eva"
        assert r.last_name  == "Example"
        assert r.card_number == 55555
        assert r.start_time  == encode(3600)
        assert r.status      == RunnerStatus.OK

    def test_runner_sex_and_nationality_preserved(self, simple_event, tmp_path):
        path = str(tmp_path / "test.mexml")
        save_event_xml(simple_event, path)
        ev2 = load_event_xml(path)
        r = next(iter(ev2.runners.values()))
        assert r.sex.value == "F"
        assert r.nationality == "FRA"

    def test_controls_preserved(self, simple_event, tmp_path):
        path = str(tmp_path / "test.mexml")
        save_event_xml(simple_event, path)
        ev2 = load_event_xml(path)
        ctrls = [c for c in ev2.controls.values() if not c.removed]
        assert len(ctrls) == 1
        assert 31 in ctrls[0].numbers

    def test_courses_preserved(self, simple_event, tmp_path):
        path = str(tmp_path / "test.mexml")
        save_event_xml(simple_event, path)
        ev2 = load_event_xml(path)
        courses = [c for c in ev2.courses.values() if not c.removed]
        assert len(courses) == 1
        assert courses[0].name   == "Sprint"
        assert courses[0].length == 1500
        assert courses[0].climb  == 50
        assert len(courses[0].control_ids) == 1

    def test_classes_preserved(self, simple_event, tmp_path):
        path = str(tmp_path / "test.mexml")
        save_event_xml(simple_event, path)
        ev2 = load_event_xml(path)
        assert any(c.name == "W21" for c in ev2.classes.values())

    def test_clubs_preserved(self, simple_event, tmp_path):
        path = str(tmp_path / "test.mexml")
        save_event_xml(simple_event, path)
        ev2 = load_event_xml(path)
        assert any(c.name == "OK Test" for c in ev2.clubs.values())

    def test_load_nonexistent_returns_none(self):
        ev = load_event_xml("/tmp/does_not_exist_pymeos.mexml")
        assert ev is None

    def test_multiple_runners(self, tmp_path):
        ev = Event()
        ev.name = "Multi"
        cls = ev.add_class("M21")
        for i in range(10):
            ev.add_runner(f"Runner{i}", "X", class_id=cls.id)
        path = str(tmp_path / "multi.mexml")
        save_event_xml(ev, path)
        ev2 = load_event_xml(path)
        assert len([r for r in ev2.runners.values() if not r.removed]) == 10

    def test_zero_time_preserved(self, simple_event, tmp_path):
        simple_event.zero_time = 45000 * _S
        path = str(tmp_path / "zt.mexml")
        save_event_xml(simple_event, path)
        ev2 = load_event_xml(path)
        assert ev2.zero_time == 45000 * _S


# ===========================================================================
# Real MeOS format loading  (<meosdata>)
# ===========================================================================

class TestMeosDataFormat:

    # ── Basic loading ────────────────────────────────────────────────────

    def test_load_returns_event(self, meosdata_file):
        ev = load_event_xml(meosdata_file)
        assert ev is not None

    def test_event_name(self, meosdata_file):
        ev = load_event_xml(meosdata_file)
        assert ev.name == "Test Champ"

    def test_event_date(self, meosdata_file):
        ev = load_event_xml(meosdata_file)
        assert ev.date == "2026-03-28"

    def test_organiser(self, meosdata_file):
        ev = load_event_xml(meosdata_file)
        assert "COCS" in ev.organiser

    # ── Zero time ───────────────────────────────────────────────────────

    def test_zero_time_converted_to_internal_units(self, meosdata_file):
        ev = load_event_xml(meosdata_file)
        # ZeroTime = 45000s → 450000 internal units (×10)
        assert ev.zero_time == 45000 * _S

    # ── Controls ────────────────────────────────────────────────────────

    def test_controls_count(self, meosdata_file):
        ev = load_event_xml(meosdata_file)
        assert len(ev.controls) == 3

    def test_control_numbers_parsed(self, meosdata_file):
        ev = load_event_xml(meosdata_file)
        all_numbers = set()
        for c in ev.controls.values():
            all_numbers.update(c.numbers)
        assert {31, 32, 33} == all_numbers

    # ── Courses ─────────────────────────────────────────────────────────

    def test_course_count(self, meosdata_file):
        ev = load_event_xml(meosdata_file)
        assert len(ev.courses) == 1

    def test_course_name(self, meosdata_file):
        ev = load_event_xml(meosdata_file)
        course = next(iter(ev.courses.values()))
        assert course.name == "Orange"

    def test_course_length(self, meosdata_file):
        ev = load_event_xml(meosdata_file)
        course = next(iter(ev.courses.values()))
        assert course.length == 3200

    def test_course_climb(self, meosdata_file):
        ev = load_event_xml(meosdata_file)
        course = next(iter(ev.courses.values()))
        assert course.climb == 80

    def test_course_control_ids_resolved(self, meosdata_file):
        ev = load_event_xml(meosdata_file)
        course = next(iter(ev.courses.values()))
        # 3 controls resolved
        assert len(course.control_ids) == 3
        # All IDs exist in the event
        for cid in course.control_ids:
            assert cid in ev.controls

    def test_course_controls_correct_order(self, meosdata_file):
        ev = load_event_xml(meosdata_file)
        course = next(iter(ev.courses.values()))
        resolved_numbers = [ev.controls[cid].numbers[0] for cid in course.control_ids]
        assert resolved_numbers == [31, 32, 33]

    # ── Classes ─────────────────────────────────────────────────────────

    def test_class_count(self, meosdata_file):
        ev = load_event_xml(meosdata_file)
        assert len(ev.classes) == 1

    def test_class_name(self, meosdata_file):
        ev = load_event_xml(meosdata_file)
        cls = next(iter(ev.classes.values()))
        assert cls.name == "H21"

    def test_class_course_id(self, meosdata_file):
        ev = load_event_xml(meosdata_file)
        cls = next(iter(ev.classes.values()))
        assert cls.course_id in ev.courses

    def test_class_first_start_is_absolute(self, meosdata_file):
        """
        FirstStart=3600s (relative) + ZeroTime=45000s = 48600s absolute.
        Internal units = 48600 × 10 = 486000.
        """
        ev = load_event_xml(meosdata_file)
        cls = next(iter(ev.classes.values()))
        expected = (45000 + 3600) * _S
        assert cls.first_start == expected

    def test_class_start_interval(self, meosdata_file):
        ev = load_event_xml(meosdata_file)
        cls = next(iter(ev.classes.values()))
        # StartInterval = 120s → 1200 internal units
        assert cls.start_interval == 120 * _S

    def test_class_entry_fee(self, meosdata_file):
        ev = load_event_xml(meosdata_file)
        cls = next(iter(ev.classes.values()))
        assert cls.entry_fee == 600

    # ── Clubs ───────────────────────────────────────────────────────────

    def test_club_count(self, meosdata_file):
        ev = load_event_xml(meosdata_file)
        assert len(ev.clubs) == 1

    def test_club_name(self, meosdata_file):
        ev = load_event_xml(meosdata_file)
        club = next(iter(ev.clubs.values()))
        assert club.name == "COCS"

    def test_club_short_name(self, meosdata_file):
        ev = load_event_xml(meosdata_file)
        club = next(iter(ev.clubs.values()))
        assert club.short_name == "7309AR"

    def test_club_id_preserved(self, meosdata_file):
        ev = load_event_xml(meosdata_file)
        assert 7309 in ev.clubs

    # ── Runners ─────────────────────────────────────────────────────────

    def test_runner_count(self, meosdata_file):
        ev = load_event_xml(meosdata_file)
        assert len(ev.runners) == 3

    def test_runner_name_comma_format(self, meosdata_file):
        """'DUPONT, Jean' → first='Jean' last='Dupont'"""
        ev = load_event_xml(meosdata_file)
        r = ev.runners[101]
        assert r.first_name == "Jean"
        assert r.last_name  == "Dupont"

    def test_runner_name_female(self, meosdata_file):
        """'MARTIN, Claire' → first='Claire' last='Martin'"""
        ev = load_event_xml(meosdata_file)
        r = ev.runners[102]
        assert r.first_name == "Claire"
        assert r.last_name  == "Martin"

    def test_runner_card_number(self, meosdata_file):
        ev = load_event_xml(meosdata_file)
        assert ev.runners[101].card_number == 123456
        assert ev.runners[102].card_number == 654321

    def test_runner_club_id(self, meosdata_file):
        ev = load_event_xml(meosdata_file)
        assert ev.runners[101].club_id == 7309

    def test_runner_class_id(self, meosdata_file):
        ev = load_event_xml(meosdata_file)
        assert ev.runners[101].class_id == 5

    def test_runner_start_no(self, meosdata_file):
        ev = load_event_xml(meosdata_file)
        assert ev.runners[101].start_no == 1
        assert ev.runners[102].start_no == 2

    def test_runner_start_time_absolute(self, meosdata_file):
        """
        Runner Start=3600s (relative) + ZeroTime=45000s = 48600s absolute.
        Internal units = 486000.
        """
        ev = load_event_xml(meosdata_file)
        r = ev.runners[101]
        expected = (45000 + 3600) * _S
        assert r.start_time   == expected
        assert r.t_start_time == expected

    def test_runner_start_time_second_runner(self, meosdata_file):
        ev = load_event_xml(meosdata_file)
        r = ev.runners[102]
        expected = (45000 + 3720) * _S
        assert r.start_time == expected

    def test_runner_no_start_gets_no_time(self, meosdata_file):
        """Runner 103 has no <Start> element → NO_TIME."""
        from utils.time_utils import NO_TIME
        ev = load_event_xml(meosdata_file)
        r = ev.runners[103]
        assert r.start_time == NO_TIME

    def test_runner_sex(self, meosdata_file):
        ev = load_event_xml(meosdata_file)
        assert ev.runners[101].sex.value == "M"
        assert ev.runners[102].sex.value == "F"

    def test_runner_nationality(self, meosdata_file):
        ev = load_event_xml(meosdata_file)
        assert ev.runners[101].nationality == "FRA"

    def test_runner_missing_club_is_zero(self, meosdata_file):
        ev = load_event_xml(meosdata_file)
        assert ev.runners[103].club_id == 0

    # ── Format detection ────────────────────────────────────────────────

    def test_unknown_root_returns_none(self, tmp_path):
        f = tmp_path / "bad.xml"
        f.write_text("<unknownroot><foo/></unknownroot>")
        assert load_event_xml(str(f)) is None

    def test_invalid_xml_returns_none(self, tmp_path):
        f = tmp_path / "bad.xml"
        f.write_text("not xml at all <<<")
        assert load_event_xml(str(f)) is None

    # ── id recalculation ────────────────────────────────────────────────

    def test_free_ids_recalculated(self, meosdata_file):
        ev = load_event_xml(meosdata_file)
        # Adding a new runner must not collide with existing ones
        new_r = ev.add_runner("New", "Runner")
        assert new_r.id not in {101, 102, 103}

    # ── Start time formatting ────────────────────────────────────────────

    def test_start_time_human_readable(self, meosdata_file):
        """The converted start time should format back to a legible HH:MM:SS."""
        ev = load_event_xml(meosdata_file)
        r = ev.runners[101]
        s = format_time(r.start_time)
        # 48600s = 13:30:00
        assert s == "13:30:00"


# ===========================================================================
# Stub-control creation for courses referencing undefined controls
# ===========================================================================

class TestStubControlCreation:
    def test_stub_created_for_unknown_control(self, tmp_path):
        """A course referencing SI number 999 (not in ControlList) → stub."""
        xml = textwrap.dedent("""\
        <?xml version="1.0" encoding="UTF-8"?>
        <meosdata version="5.0">
        <Name>Stub Test</Name>
        <Date>2026-01-01</Date>
        <ZeroTime>0</ZeroTime>
        <ControlList/>
        <CourseList>
          <Course>
            <Id>1</Id>
            <Name>Test</Name>
            <Length>1000</Length>
            <Controls>999;</Controls>
          </Course>
        </CourseList>
        <ClassList/>
        <ClubList/>
        <RunnerList/>
        <TeamList/>
        </meosdata>
        """).encode()
        f = tmp_path / "stub.meosxml"
        f.write_bytes(xml)
        ev = load_event_xml(str(f))
        assert ev is not None
        # Control 999 should have been auto-created
        all_numbers = set()
        for c in ev.controls.values():
            all_numbers.update(c.numbers)
        assert 999 in all_numbers
        # The course's control_ids should point to it
        course = next(iter(ev.courses.values()))
        assert len(course.control_ids) == 1
        ctrl = ev.controls[course.control_ids[0]]
        assert 999 in ctrl.numbers
