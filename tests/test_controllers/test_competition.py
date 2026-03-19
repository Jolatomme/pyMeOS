"""Tests for controllers/competition.py – CompetitionController.

Qt-free tests use a lightweight mock controller that doesn't need PySide6.
Qt tests are marked and skipped when PySide6 / pytest-qt is not available.
"""
import pytest
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

# ── Optional Qt ──────────────────────────────────────────────────────────────
try:
    from PySide6.QtCore import QObject
    _HAS_QT = True
except ImportError:
    _HAS_QT = False

qt_only = pytest.mark.skipif(not _HAS_QT, reason="PySide6 not installed")

# ── Shared DB init ───────────────────────────────────────────────────────────
from persistence import init_db, EventRepository
from models import Event, RunnerStatus
from models.card import SICard
from models.punch import SIPunch
from hardware.si_reader import SICardReadEvent
from utils.time_utils import encode, NO_TIME


def _make_ctrl():
    """Create a CompetitionController with an in-memory DB."""
    init_db("sqlite:///:memory:")
    from controllers.competition import CompetitionController
    return CompetitionController()


# ============================================================
# Qt-FREE tests  (no qtbot)
# ============================================================

class TestNewEventNoQt:
    def test_new_event_sets_name(self):
        ctrl = _make_ctrl()
        ctrl.new_event("Spring Race")
        assert ctrl.event.name == "Spring Race"

    def test_event_starts_empty(self):
        ctrl = _make_ctrl()
        ctrl.new_event("Empty")
        assert ctrl.event.statistics()["runners"] == 0

    def test_new_event_date_defaults_to_today(self):
        from datetime import date
        ctrl = _make_ctrl()
        ctrl.new_event("Today")
        assert ctrl.event.date == date.today().isoformat()


class TestAddRunnerNoQt:
    def test_add_runner_basic(self):
        ctrl = _make_ctrl()
        ctrl.new_event("E")
        r = ctrl.add_runner("Alice", "Smith", card_number=12345)
        assert r is not None
        assert r.first_name == "Alice"
        assert r.card_number == 12345

    def test_add_runner_creates_club(self):
        ctrl = _make_ctrl()
        ctrl.new_event("E")
        ctrl.add_runner("Bob", "B", club_name="OK Alpha")
        assert any("OK Alpha" in c.name for c in ctrl.event.clubs.values())

    def test_add_runner_creates_class(self):
        ctrl = _make_ctrl()
        ctrl.new_event("E")
        ctrl.add_runner("Carol", "C", class_name="M21")
        assert any("M21" in c.name for c in ctrl.event.classes.values())

    def test_delete_runner(self):
        ctrl = _make_ctrl()
        ctrl.new_event("E")
        r = ctrl.add_runner("Dave", "D")
        rid = r.id
        assert ctrl.delete_runner(rid)
        assert ctrl.event.runners[rid].removed


class TestSetStatusNoQt:
    def test_set_runner_status(self):
        ctrl = _make_ctrl()
        ctrl.new_event("E")
        cls = ctrl.event.add_class("M21")
        r = ctrl.event.add_runner("X", "Y", class_id=cls.id)
        assert ctrl.set_runner_status(r.id, RunnerStatus.DNS)
        assert ctrl.event.runners[r.id].status == RunnerStatus.DNS

    def test_set_status_nonexistent_runner(self):
        ctrl = _make_ctrl()
        ctrl.new_event("E")
        assert not ctrl.set_runner_status(9999, RunnerStatus.OK)


class TestSaveLoadNoQt:
    def test_save_returns_positive_id(self):
        ctrl = _make_ctrl()
        ctrl.new_event("Saved")
        ctrl.save_event_to_db()
        assert ctrl.event.id > 0

    def test_save_preserves_runners(self):
        ctrl = _make_ctrl()
        ctrl.new_event("Persist")
        ctrl.add_runner("Alice", "A")
        ctrl.add_runner("Bob", "B")
        ctrl.save_event_to_db()
        eid = ctrl.event.id

        repo = EventRepository()
        ev2 = repo.load_event(eid)
        assert ev2 is not None
        live = [r for r in ev2.runners.values() if not r.removed]
        assert len(live) == 2

    def test_open_nonexistent_db_event(self):
        ctrl = _make_ctrl()
        result = ctrl.open_event_from_db(99999)
        assert result is False


class TestXMLRoundTripNoQt:
    def test_xml_save_load(self, tmp_path):
        ctrl = _make_ctrl()
        ctrl.new_event("XML Test")
        ctrl.add_runner("Eve", "E", class_name="W21")
        path = str(tmp_path / "event.mexml")
        assert ctrl.save_event_to_xml(path)

        ctrl2 = _make_ctrl()
        assert ctrl2.open_event_from_xml(path)
        assert ctrl2.event.name == "XML Test"
        runners = [r for r in ctrl2.event.runners.values() if not r.removed]
        assert len(runners) == 1
        assert runners[0].first_name == "Eve"


class TestProcessSICardNoQt:
    def _make_si(self, card_number, start=3600, finish=None):
        si = SICard()
        si.card_number = card_number
        si.start_punch = SIPunch(code=1, time=encode(start))
        if finish is not None:
            si.finish_punch = SIPunch(code=2, time=encode(finish))
        return si

    def test_unknown_card_stored_unmatched(self):
        ctrl = _make_ctrl()
        ctrl.new_event("E")
        si = self._make_si(999999)
        ctrl.on_card_read(SICardReadEvent(card=si, port="TEST"))
        # Card should be stored even though no runner matches
        assert any(c.card_number == 999999 for c in ctrl.event.cards.values())

    def test_known_card_evaluates_runner(self):
        ctrl = _make_ctrl()
        ctrl.new_event("E")
        cls = ctrl.event.add_class("M21")
        course = ctrl.event.add_course("Test")
        cls.course_id = course.id

        runner = ctrl.add_runner("Alice", "A", class_name="M21",
                                 card_number=111222)
        runner.start_time = encode(3600)

        si = self._make_si(111222, start=3600, finish=3600 + 300)
        ctrl.on_card_read(SICardReadEvent(card=si, port="TEST"))

        assert ctrl.event.runners[runner.id].card_id > 0

    def test_draw_starts(self):
        ctrl = _make_ctrl()
        ctrl.new_event("E")
        cls = ctrl.event.add_class("M21")
        for i in range(5):
            ctrl.event.add_runner(f"R{i}", "X", class_id=cls.id)
        ctrl.draw_starts(cls.id, first_start=encode(3600),
                         interval=encode(120), scramble=False)
        times = [r.start_time for r in ctrl.event.runners.values()
                 if r.class_id == cls.id]
        assert all(t > 0 for t in times)


# ============================================================
# Qt-DEPENDENT tests  (require PySide6 + pytest-qt)
# ============================================================

@qt_only
class TestSignalsQt:
    def test_new_event_emits_signal(self, qtbot):
        ctrl = _make_ctrl()
        with qtbot.waitSignal(ctrl.event_loaded, timeout=1000):
            ctrl.new_event("Test")

    def test_status_emits_runner_updated(self, qtbot):
        ctrl = _make_ctrl()
        ctrl.new_event("E")
        cls = ctrl.event.add_class("M21")
        r = ctrl.event.add_runner("X", "Y", class_id=cls.id)
        with qtbot.waitSignal(ctrl.runner_updated, timeout=1000):
            ctrl.set_runner_status(r.id, RunnerStatus.OK)

    def test_card_processed_signal_unknown(self, qtbot):
        ctrl = _make_ctrl()
        ctrl.new_event("E")
        si = SICard(); si.card_number = 999999
        ev = SICardReadEvent(card=si, port="TEST")
        with qtbot.waitSignal(ctrl.card_processed, timeout=1000):
            ctrl.on_card_read(ev)

    def test_save_emits_event_saved(self, qtbot):
        ctrl = _make_ctrl()
        ctrl.new_event("Saved")
        with qtbot.waitSignal(ctrl.event_saved, timeout=1000):
            ctrl.save_event_to_db()
