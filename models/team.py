"""
models/team.py
==============
A relay team (oTeam equivalent).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, TYPE_CHECKING

from .base import Base
from .enums import RunnerStatus, RUNNER_STATUS_ORDER
from utils.time_utils import NO_TIME, format_time

if TYPE_CHECKING:
    from .runner import Runner
    from .event import Event


@dataclass
class Team(Base):
    """A relay team comprising multiple runners on sequential legs."""

    name: str = ""
    club_id: int = 0
    class_id: int = 0

    # Ordered list of runner IDs (one per leg; 0 = no runner assigned)
    runner_ids: List[int] = field(default_factory=list)

    start_no: int = 0
    bib: str = ""
    start_time: int = NO_TIME
    finish_time: int = NO_TIME

    status: RunnerStatus = RunnerStatus.Unknown
    # Cumulative computed result
    t_total_time: int = NO_TIME
    t_status: RunnerStatus = RunnerStatus.Unknown
    place: int = 0

    # Multi-day input
    input_time: int = NO_TIME
    input_status: RunnerStatus = RunnerStatus.OK
    input_points: int = 0
    input_place: int = 0

    flags: int = 0
    entry_date: str = ""

    def __post_init__(self) -> None:
        super().__init__()

    # ------------------------------------------------------------------
    # Runner access
    # ------------------------------------------------------------------

    @property
    def num_legs(self) -> int:
        return len(self.runner_ids)

    def get_runner_id(self, leg: int) -> int:
        """Return runner id for 0-based leg, or 0."""
        if 0 <= leg < len(self.runner_ids):
            return self.runner_ids[leg]
        return 0

    def set_runner_id(self, leg: int, runner_id: int) -> None:
        while len(self.runner_ids) <= leg:
            self.runner_ids.append(0)
        self.runner_ids[leg] = runner_id
        self.mark_changed()

    # ------------------------------------------------------------------
    # Time helpers
    # ------------------------------------------------------------------

    def get_total_running_time(self) -> int:
        return self.t_total_time

    def get_total_running_time_string(self, sub_second: bool = False) -> str:
        t = self.t_total_time
        return format_time(t, sub_second) if t != NO_TIME else ""

    # ------------------------------------------------------------------
    # Sorting
    # ------------------------------------------------------------------

    def result_sort_key(self) -> tuple:
        order = RUNNER_STATUS_ORDER.get(self.status, 99)
        t = self.t_total_time
        t = t if t != NO_TIME else 999999999
        return (order, t, self.name)

    # ------------------------------------------------------------------
    # Base interface
    # ------------------------------------------------------------------

    def get_info(self) -> str:
        return f"Team '{self.name}' (id={self._id}, legs={self.num_legs})"

    def remove(self) -> None:
        self._removed = True
        self.mark_changed()

    def can_remove(self) -> bool:
        return True
