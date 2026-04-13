"""Tests for formats/csv_parser.py – CSV import/export."""
import io
import os
import tempfile
import pytest
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from models import Event, RunnerStatus
from formats.csv_parser import CSVImporter, CSVExporter, CSVFormat
from utils.time_utils import encode, format_time


@pytest.fixture
def populated_event():
    ev = Event()
    ev.name = "CSV Test"
    club = ev.add_club("OK Alpha")
    cls  = ev.add_class("M21")
    r1 = ev.add_runner("Alice", "Smith", club_id=club.id, class_id=cls.id)
    r1.card_number = 12345
    r1.start_time  = encode(3600)
    r1.finish_time = encode(3600 + 3723)
    r1.status = r1.t_status = RunnerStatus.OK
    r1.place   = 1
    r2 = ev.add_runner("Bob", "Jones", club_id=club.id, class_id=cls.id)
    r2.card_number = 67890
    r2.start_time  = encode(3720)
    r2.finish_time = encode(3720 + 3900)
    r2.status = r2.t_status = RunnerStatus.OK
    r2.place   = 2
    return ev


# ---------------------------------------------------------------------------
# CSVExporter
# ---------------------------------------------------------------------------

class TestCSVExporter:
    def test_export_startlist_creates_file(self, populated_event):
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "start.csv")
            CSVExporter.export_startlist(populated_event, path)
            assert os.path.exists(path)
            assert os.path.getsize(path) > 0

    def test_export_startlist_has_header(self, populated_event):
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "start.csv")
            CSVExporter.export_startlist(populated_event, path)
            with open(path, encoding="utf-8-sig") as f:
                lines = f.read().strip().splitlines()
            # header + 2 runners
            assert len(lines) >= 3

    def test_export_startlist_contains_names(self, populated_event):
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "start.csv")
            CSVExporter.export_startlist(populated_event, path)
            content = Path(path).read_text(encoding="utf-8-sig")
            assert "Alice" in content or "Smith" in content

    def test_export_startlist_contains_card_number(self, populated_event):
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "start.csv")
            CSVExporter.export_startlist(populated_event, path)
            content = Path(path).read_text(encoding="utf-8-sig")
            assert "12345" in content

    def test_export_results_creates_file(self, populated_event):
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "results.csv")
            CSVExporter.export_results(populated_event, path)
            assert os.path.exists(path)

    def test_export_results_has_places(self, populated_event):
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "results.csv")
            CSVExporter.export_results(populated_event, path)
            content = Path(path).read_text(encoding="utf-8-sig")
            assert "1" in content

    def test_class_filter(self, populated_event):
        cls_id = next(iter(populated_event.classes)).id if hasattr(
            next(iter(populated_event.classes)), "id") else list(
            populated_event.classes.keys())[0]
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "filtered.csv")
            CSVExporter.export_startlist(populated_event, path, class_id=cls_id)
            content = Path(path).read_text(encoding="utf-8-sig")
            assert len(content.strip().splitlines()) >= 2


# ---------------------------------------------------------------------------
# CSVImporter
# ---------------------------------------------------------------------------

class TestCSVImporter:
    def _simple_csv(self) -> str:
        return (
            "FirstName;LastName;Club;Class;Card\n"
            "Carol;Clark;OK Beta;W21;54321\n"
            "Dave;Davis;OK Beta;M21;98765\n"
        )

    def test_import_text_adds_runners(self):
        ev = Event()
        ev.add_class("W21")
        ev.add_class("M21")
        imp = CSVImporter(ev)
        ok  = imp.import_text(self._simple_csv())
        assert ok
        assert imp.imported_count == 2

    def test_import_sets_name(self):
        ev = Event()
        ev.add_class("W21"); ev.add_class("M21")
        CSVImporter(ev).import_text(self._simple_csv())
        names = [(r.first_name, r.last_name) for r in ev.runners.values()]
        assert ("Carol", "Clark") in names

    def test_import_sets_card_number(self):
        ev = Event()
        ev.add_class("W21"); ev.add_class("M21")
        CSVImporter(ev).import_text(self._simple_csv())
        cards = [r.card_number for r in ev.runners.values()]
        assert 54321 in cards

    def test_import_creates_club(self):
        ev = Event()
        ev.add_class("W21"); ev.add_class("M21")
        CSVImporter(ev).import_text(self._simple_csv())
        club_names = [c.name for c in ev.clubs.values()]
        assert "OK Beta" in club_names

    def test_import_empty_string(self):
        ev  = Event()
        imp = CSVImporter(ev)
        ok  = imp.import_text("")
        assert imp.imported_count == 0

    def test_import_header_only(self):
        ev  = Event()
        imp = CSVImporter(ev)
        ok  = imp.import_text("FirstName;LastName;Club;Class;Card\n")
        assert imp.imported_count == 0

    def test_import_from_file(self):
        ev = Event()
        ev.add_class("W21"); ev.add_class("M21")
        with tempfile.NamedTemporaryFile(
                mode="w", suffix=".csv", encoding="utf-8-sig",
                delete=False) as tf:
            tf.write(self._simple_csv())
            fname = tf.name
        try:
            imp = CSVImporter(ev)
            ok  = imp.import_file(fname)
            assert ok
            assert imp.imported_count == 2
        finally:
            os.unlink(fname)

    def test_comma_delimiter_auto_detect(self):
        csv_data = "FirstName,LastName,Club,Class,Card\nEve,Evans,OKC,M21,11111\n"
        ev = Event(); ev.add_class("M21")
        imp = CSVImporter(ev)
        imp.import_text(csv_data, CSVFormat.Auto)
        assert imp.imported_count == 1
        assert ev.runners and next(iter(ev.runners.values())).first_name == "Eve"

    def test_import_nonexistent_file(self):
        ev = Event()
        imp = CSVImporter(ev)
        ok = imp.import_file("/nonexistent/path/to/file.csv")
        assert ok is False
        assert len(imp.errors) > 0

    def test_import_invalid_csv_strict(self):
        csv_data = "FirstName,LastName\nTest,User\n"
        ev = Event()
        imp = CSVImporter(ev)
        ok = imp.import_text(csv_data)
        assert ok


class TestFormatDetection:
    def test_detect_results_format(self):
        row = {"place": "1", "running time": "1800", "firstname": "Test"}
        fmt = CSVImporter._detect_format(row)
        assert fmt == CSVFormat.Results

    def test_detect_startlist_format(self):
        row = {"start": "10:00", "firstname": "Test"}
        fmt = CSVImporter._detect_format(row)
        assert fmt == CSVFormat.StartList

    def test_detect_courses_format(self):
        row = {"course": "A", "controls": "31,32,33"}
        fmt = CSVImporter._detect_format(row)
        assert fmt == CSVFormat.Courses

    def test_detect_entries_format_default(self):
        row = {"firstname": "Test", "lastname": "User"}
        fmt = CSVImporter._detect_format(row)
        assert fmt == CSVFormat.Entries


class TestStartlistImport:
    def test_startlist_import_with_card_and_time(self):
        csv_data = (
            "FirstName;LastName;Card;Start\n"
            "Alice;Smith;12345;10:00\n"
        )
        ev = Event()
        imp = CSVImporter(ev)
        ok = imp.import_text(csv_data, CSVFormat.StartList)
        assert ok
        assert imp.imported_count == 1

    def test_startlist_import_bib_number(self):
        csv_data = (
            "FirstName;LastName;Card;Bib\n"
            "Bob;Jones;67890;42\n"
        )
        ev = Event()
        imp = CSVImporter(ev)
        ok = imp.import_text(csv_data, CSVFormat.StartList)
        assert ok
        assert imp.imported_count == 1
        runner = ev.get_runner_by_card(67890)
        assert runner is not None
        assert runner.bib == "42"

    def test_startlist_missing_card_continues(self):
        csv_data = (
            "FirstName;LastName\n"
            "NoCard;User\n"
        )
        ev = Event()
        imp = CSVImporter(ev)
        ok = imp.import_text(csv_data, CSVFormat.StartList)
        assert ok
        assert imp.imported_count == 1


class TestResultsImport:
    def test_results_import_with_time(self):
        csv_data = (
            "FirstName;LastName;Card;Running Time\n"
            "Alice;Smith;12345;25:30\n"
        )
        ev = Event()
        imp = CSVImporter(ev)
        ok = imp.import_text(csv_data, CSVFormat.Results)
        assert ok
        runner = ev.get_runner_by_card(12345)
        assert runner is not None
        assert runner.tmp_result.running_time > 0

    def test_results_import_with_status(self):
        csv_data = (
            "FirstName;LastName;Card;Status\n"
            "Bob;Jones;67890;DNS\n"
        )
        ev = Event()
        imp = CSVImporter(ev)
        ok = imp.import_text(csv_data, CSVFormat.Results)
        assert ok
        runner = ev.get_runner_by_card(67890)
        assert runner is not None
        assert runner.status == RunnerStatus.DNS


class TestCoursesImport:
    def test_courses_import_basic(self):
        csv_data = (
            "Course;Length;Climb;31;32;33\n"
            "A;2500;50;31;32;33\n"
        )
        ev = Event()
        imp = CSVImporter(ev)
        ok = imp.import_text(csv_data, CSVFormat.Courses)
        assert ok
        course = ev.get_course_by_name("A")
        assert course is not None
        assert course.length == 2500
        assert course.climb == 50

    def test_courses_import_adds_controls(self):
        csv_data = (
            "Course;Length;31;32\n"
            "B;2000;31;32\n"
        )
        ev = Event()
        imp = CSVImporter(ev)
        ok = imp.import_text(csv_data, CSVFormat.Courses)
        assert ok
        course = ev.get_course_by_name("B")
        assert course is not None
        controls_list = course.controls(ev)
        assert len(controls_list) >= 2


class TestEdgeCases:
    def test_empty_first_and_last_skipped(self):
        csv_data = "FirstName;LastName;Club\n; ;SomeClub\n"
        ev = Event()
        imp = CSVImporter(ev)
        ok = imp.import_text(csv_data)
        assert ok
        assert imp.imported_count == 0

    def test_invalid_card_number_ignored(self):
        csv_data = "FirstName;LastName;Card\nTest;User;NOTANUMBER\n"
        ev = Event()
        imp = CSVImporter(ev)
        ok = imp.import_text(csv_data)
        assert ok
        runner = next(iter(ev.runners.values()), None)
        assert runner is not None
        assert runner.card_number == 0

    def test_class_auto_created(self):
        csv_data = "FirstName;LastName;Class\nNew;Runner;NewClass\n"
        ev = Event()
        imp = CSVImporter(ev)
        ok = imp.import_text(csv_data)
        assert ok
        cls = ev.get_class_by_name("NewClass")
        assert cls is not None

    def test_semicolon_detected(self):
        csv_data = "FirstName;LastName\nTest;User\n"
        ev = Event()
        imp = CSVImporter(ev)
        ok = imp.import_text(csv_data)
        assert ok
        assert imp.imported_count == 1


class TestExporterEdgeCases:
    def test_export_results_all_classes(self, populated_event):
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "results.csv")
            CSVExporter.export_results(populated_event, path)
            content = Path(path).read_text(encoding="utf-8-sig")
            assert "Alice" in content or "Smith" in content

    def test_export_with_no_classes(self):
        ev = Event()
        ev.name = "Empty"
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "start.csv")
            CSVExporter.export_startlist(ev, path)
            assert os.path.getsize(path) > 0
