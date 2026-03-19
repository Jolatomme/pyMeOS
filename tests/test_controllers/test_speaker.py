"""Tests for controllers/speaker.py"""
import pytest
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from models import Event, RunnerStatus
from controllers.speaker import (
    SpeakerController, TimeLineEvent, TimeLineType, Priority, SpeakerEntry
)
from utils.time_utils import encode, NO_TIME


@pytest.fixture
def ev_with_finished_runner():
    ev   = Event()
    club = ev.add_club("OK")
    cls  = ev.add_class("M21")
    r    = ev.add_runner("Alice", "A", club_id=club.id, class_id=cls.id)
    r.start_time    = encode(3600)
    r.t_start_time  = encode(3600)
    r.finish_time   = encode(3600 + 3000)
    r.status        = RunnerStatus.OK
    r.t_status      = RunnerStatus.OK
    r.place         = 1
    return ev, cls, r


class TestTimeLineEvent:
    def test_create(self):
        ev = TimeLineEvent(
            time=encode(3600),
            type=TimeLineType.Finish,
            priority=Priority.High,
            runner_id=1,
            class_id=1,
            message="Alice finished",
        )
        assert ev.time == encode(3600)
        assert ev.message == "Alice finished"
        assert ev.type == TimeLineType.Finish


class TestSpeakerController:
    def test_create(self, ev_with_finished_runner):
        ev, cls, r = ev_with_finished_runner
        sc = SpeakerController(ev)
        assert sc is not None

    def test_on_runner_finished_adds_timeline(self, ev_with_finished_runner):
        ev, cls, r = ev_with_finished_runner
        sc = SpeakerController(ev)
        sc.on_runner_finished(r.id, r.finish_time)
        timeline = sc.get_recent_timeline()
        assert len(timeline) >= 1
        assert any(e.type == TimeLineType.Finish for e in timeline)

    def test_on_runner_started_adds_timeline(self, ev_with_finished_runner):
        ev, cls, r = ev_with_finished_runner
        sc = SpeakerController(ev)
        sc.on_runner_started(r.id, r.start_time)
        timeline = sc.get_recent_timeline()
        assert any(e.type == TimeLineType.Start for e in timeline)

    def test_on_radio_punch_adds_timeline(self, ev_with_finished_runner):
        ev, cls, r = ev_with_finished_runner
        sc = SpeakerController(ev)
        sc.on_radio_punch(r.id, control_id=31, punch_time=encode(3700))
        timeline = sc.get_recent_timeline()
        assert any(e.type == TimeLineType.Radio for e in timeline)

    def test_get_display_returns_entries(self, ev_with_finished_runner):
        ev, cls, r = ev_with_finished_runner
        sc = SpeakerController(ev)
        sc.on_runner_finished(r.id, r.finish_time)
        entries = sc.get_display(cls.id)
        assert isinstance(entries, list)

    def test_display_has_runner_name(self, ev_with_finished_runner):
        ev, cls, r = ev_with_finished_runner
        sc = SpeakerController(ev)
        sc.on_runner_finished(r.id, r.finish_time)
        entries = sc.get_display(cls.id)
        if entries:
            assert "Alice" in entries[0].runner_name

    def test_unknown_runner_id_ignored(self, ev_with_finished_runner):
        ev, cls, r = ev_with_finished_runner
        sc = SpeakerController(ev)
        # Should not raise
        sc.on_runner_finished(99999, encode(7000))
        sc.on_runner_started(99999, encode(3600))
        sc.on_radio_punch(99999, 31, encode(3700))

    def test_recent_timeline_limit(self, ev_with_finished_runner):
        ev, cls, r = ev_with_finished_runner
        sc = SpeakerController(ev)
        for _ in range(30):
            sc.on_runner_finished(r.id, r.finish_time)
        recent = sc.get_recent_timeline(n=10)
        assert len(recent) <= 10

    def test_set_update_callback(self, ev_with_finished_runner):
        ev, cls, r = ev_with_finished_runner
        sc  = SpeakerController(ev)
        called = []
        sc.set_update_callback(lambda: called.append(1))
        sc.on_runner_finished(r.id, r.finish_time)
        assert len(called) >= 1

    def test_max_entries_per_class(self, ev_with_finished_runner):
        ev, cls, r = ev_with_finished_runner
        sc = SpeakerController(ev)
        sc.max_entries_per_class = 2
        # Add 5 runners with results
        for i in range(5):
            ri = ev.add_runner(f"R{i}", "X", class_id=cls.id)
            ri.start_time   = encode(3600 + i * 60)
            ri.t_start_time = ri.start_time
            ri.finish_time  = encode(3600 + i * 60 + 3000 + i * 10)
            ri.status = ri.t_status = RunnerStatus.OK
            ri.place  = i + 1
            sc.on_runner_finished(ri.id, ri.finish_time)
        entries = sc.get_display(cls.id)
        assert len(entries) <= 2
