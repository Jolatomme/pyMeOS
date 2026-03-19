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
