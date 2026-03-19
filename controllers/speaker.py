"""
controllers/speaker.py
======================
Speaker monitor controller (oEventSpeaker / speakermonitor.cpp equivalent).

Tracks live competitor progress and builds a timeline of notable events
(starts, radio punches, finish) that can be displayed on a speaker screen.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Dict, Optional, Callable, TYPE_CHECKING

from models import Event, Runner, Team, RunnerStatus
from utils.time_utils import NO_TIME, format_time

if TYPE_CHECKING:
    pass

log = logging.getLogger(__name__)


class TimeLineType(Enum):
    Start    = "start"
    Finish   = "finish"
    Radio    = "radio"
    Expected = "expected"


class Priority(Enum):
    Top    = 6
    High   = 5
    Medium = 4
    Low    = 3


@dataclass
class TimeLineEvent:
    """A single entry in the speaker timeline."""
    time: int                       # internal units
    type: TimeLineType
    priority: Priority
    runner_id: int = 0
    team_id: int   = 0
    class_id: int  = 0
    message: str   = ""
    detail: str    = ""
    control_id: int = 0


@dataclass
class SpeakerEntry:
    """Formatted entry ready for display on the speaker screen."""
    runner_name: str  = ""
    club_name: str    = ""
    class_name: str   = ""
    bib: str          = ""
    status: str       = ""
    time_str: str     = ""
    place_str: str    = ""
    message: str      = ""
    priority: int     = 3


class SpeakerController:
    """
    Maintains a rolling window of notable events for the speaker monitor.

    Observes the Event model and re-evaluates when runners finish or
    radio punches arrive.
    """

    def __init__(self, event: Event) -> None:
        self._event = event
        self._timeline: List[TimeLineEvent] = []
        # class_id -> list of entries currently shown
        self._display: Dict[int, List[SpeakerEntry]] = {}
        # Optional callback: called whenever display data changes
        self._on_update: Optional[Callable[[], None]] = None
        # How many entries to keep per class
        self.max_entries_per_class: int = 10
        # Which classes are monitored (empty = all)
        self.monitored_classes: set[int] = set()

    def set_update_callback(self, cb: Callable[[], None]) -> None:
        self._on_update = cb

    # ------------------------------------------------------------------
    # Event handling (called by the SI reader / card processor)
    # ------------------------------------------------------------------

    def on_runner_started(self, runner_id: int, start_time: int) -> None:
        runner = self._event.runners.get(runner_id)
        if runner is None:
            return
        entry = TimeLineEvent(
            time=start_time,
            type=TimeLineType.Start,
            priority=Priority.Low,
            runner_id=runner_id,
            class_id=runner.class_id,
            message=self._runner_label(runner),
        )
        self._add_timeline(entry)

    def on_runner_finished(self, runner_id: int, finish_time: int) -> None:
        runner = self._event.runners.get(runner_id)
        if runner is None:
            return
        rt_str = format_time(runner.get_running_time())
        entry = TimeLineEvent(
            time=finish_time,
            type=TimeLineType.Finish,
            priority=Priority.High,
            runner_id=runner_id,
            class_id=runner.class_id,
            message=self._runner_label(runner),
            detail=rt_str,
        )
        self._add_timeline(entry)
        self._rebuild_display(runner.class_id)

    def on_radio_punch(self, runner_id: int, control_id: int, punch_time: int) -> None:
        runner = self._event.runners.get(runner_id)
        if runner is None:
            return
        entry = TimeLineEvent(
            time=punch_time,
            type=TimeLineType.Radio,
            priority=Priority.Medium,
            runner_id=runner_id,
            class_id=runner.class_id,
            control_id=control_id,
            message=self._runner_label(runner),
        )
        self._add_timeline(entry)
        self._rebuild_display(runner.class_id)

    # ------------------------------------------------------------------
    # Display data
    # ------------------------------------------------------------------

    def get_display(self, class_id: int) -> List[SpeakerEntry]:
        if class_id not in self._display:
            self._rebuild_display(class_id)
        return self._display.get(class_id, [])

    def get_recent_timeline(self, n: int = 20) -> List[TimeLineEvent]:
        return sorted(self._timeline, key=lambda e: e.time, reverse=True)[:n]

    def _rebuild_display(self, class_id: int) -> None:
        runners = self._event.get_runners_by_class(class_id)
        # Sort: finished first (by place), then by start time
        finished = [r for r in runners
                    if r.status in (RunnerStatus.OK,
                                    RunnerStatus.OutOfCompetition,
                                    RunnerStatus.NoTiming,
                                    RunnerStatus.MP,
                                    RunnerStatus.DNF)]
        finished.sort(key=lambda r: r.result_sort_key())

        entries: List[SpeakerEntry] = []
        for r in finished[:self.max_entries_per_class]:
            club = self._event.clubs.get(r.club_id)
            cls  = self._event.classes.get(r.class_id)
            e = SpeakerEntry(
                runner_name=r.name,
                club_name=club.name if club else "",
                class_name=cls.name if cls else "",
                bib=r.bib,
                status=r.status.to_code(),
                time_str=r.get_running_time_string(),
                place_str=str(r.place) if r.place else "",
                priority=Priority.High.value if r.place == 1 else Priority.Medium.value,
            )
            entries.append(e)

        self._display[class_id] = entries
        if self._on_update:
            try:
                self._on_update()
            except Exception as exc:
                log.warning("Speaker update callback raised: %s", exc)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _add_timeline(self, entry: TimeLineEvent) -> None:
        self._timeline.append(entry)
        # Keep only last 500 events
        if len(self._timeline) > 500:
            self._timeline = self._timeline[-500:]

    def _runner_label(self, runner: Runner) -> str:
        club = self._event.clubs.get(runner.club_id)
        club_name = club.name if club else ""
        if club_name:
            return f"{runner.name} ({club_name})"
        return runner.name
