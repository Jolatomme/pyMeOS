"""
models/runner.py
================
A single competitor (oRunner / oAbstractRunner equivalent).

The Runner holds:
  • personal data (name, club, class)
  • start / finish times
  • result (status, time, place)
  • reference to the SI card
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, List, TYPE_CHECKING

from .base import Base
from .enums import RunnerStatus, Sex, TransferFlag, RUNNER_STATUS_ORDER
from utils.time_utils import NO_TIME, format_time, parse_time

if TYPE_CHECKING:
    from .card import Card
    from .team import Team
    from .event import Event


@dataclass
class TempResult:
    """
    Computed result for a runner (used by GeneralResult).

    This mirrors the C++ TempResult inner class.
    """
    status: RunnerStatus = RunnerStatus.Unknown
    start_time: int = NO_TIME
    running_time: int = NO_TIME
    time_after: int = NO_TIME
    points: int = 0
    place: int = 0
    output_times: List[int] = field(default_factory=list)
    output_numbers: List[int] = field(default_factory=list)

    def finish_time(self) -> int:
        if self.running_time > 0 and self.start_time != NO_TIME:
            return self.start_time + self.running_time
        return NO_TIME

    def is_ok(self) -> bool:
        return (self.status == RunnerStatus.OK or
                (self.status in (RunnerStatus.OutOfCompetition,
                                 RunnerStatus.NoTiming)
                 and self.running_time > 0))


@dataclass
class Runner(Base):
    """A single individual competitor."""

    # ---- Personal data -------------------------------------------------
    first_name: str = ""
    last_name: str = ""
    sex: Sex = Sex.Unknown

    # ---- Competition assignments ---------------------------------------
    club_id: int = 0
    class_id: int = 0
    course_id: int = 0   # 0 = use class default

    # ---- Bib / start number -------------------------------------------
    start_no: int = 0
    bib: str = ""

    # ---- Card ----------------------------------------------------------
    card_number: int = 0
    card_id: int = 0          # FK to Card object in event

    # ---- Times (internal units, 0 = not set) ---------------------------
    start_time: int = NO_TIME        # scheduled / drawn start
    finish_time: int = NO_TIME       # recorded finish
    # Computed start (may differ from scheduled for Pursuit etc.)
    t_start_time: int = NO_TIME

    # ---- Status --------------------------------------------------------
    status: RunnerStatus = RunnerStatus.Unknown
    # Transient computed status (from card evaluation)
    t_status: RunnerStatus = RunnerStatus.Unknown

    # ---- Result --------------------------------------------------------
    tmp_result: TempResult = field(default_factory=TempResult)
    place: int = 0

    # ---- Multi-day / cumulative input ----------------------------------
    input_time: int = NO_TIME
    input_status: RunnerStatus = RunnerStatus.OK
    input_points: int = 0
    input_place: int = 0

    # ---- Flags (TransferFlag bitmask) ----------------------------------
    flags: int = 0

    # ---- Relay ---------------------------------------------------------
    team_id: int = 0
    leg_number: int = 0   # 0-based leg index in a relay

    # ---- Ranking -------------------------------------------------------
    rank: int = 0

    # ---- Entry metadata ------------------------------------------------
    entry_date: str = ""    # ISO date string
    nationality: str = ""

    def __post_init__(self) -> None:
        super().__init__()

    # ------------------------------------------------------------------
    # Name helpers
    # ------------------------------------------------------------------

    @property
    def name(self) -> str:
        parts = [self.first_name, self.last_name]
        return " ".join(p for p in parts if p)

    @property
    def sort_name(self) -> str:
        """Last, First  – for alphabetic sorting."""
        if self.last_name:
            return f"{self.last_name}, {self.first_name}"
        return self.first_name

    # ------------------------------------------------------------------
    # Flag helpers
    # ------------------------------------------------------------------

    def has_flag(self, flag: TransferFlag) -> bool:
        return bool(self.flags & int(flag))

    def set_flag(self, flag: TransferFlag, state: bool) -> None:
        if state:
            self.flags |= int(flag)
        else:
            self.flags &= ~int(flag)
        self.mark_changed()

    def no_timing(self) -> bool:
        return self.has_flag(TransferFlag.NoTiming)

    def is_out_of_competition(self) -> bool:
        return self.has_flag(TransferFlag.OutsideComp)

    def is_vacant(self) -> bool:
        return not bool(self.first_name or self.last_name)

    # ------------------------------------------------------------------
    # Status helpers
    # ------------------------------------------------------------------

    def set_status(self, st: RunnerStatus) -> None:
        self.status = st
        self.mark_changed()

    def is_started(self) -> bool:
        return (self.start_time != NO_TIME and
                self.status not in (RunnerStatus.DNS, RunnerStatus.CANCEL,
                                    RunnerStatus.Unknown))

    # ------------------------------------------------------------------
    # Time helpers
    # ------------------------------------------------------------------

    def get_running_time(self) -> int:
        """Return computed running time, or NO_TIME."""
        if (self.finish_time != NO_TIME and
                self.t_start_time != NO_TIME and
                self.finish_time > self.t_start_time):
            return self.finish_time - self.t_start_time
        return NO_TIME

    def get_running_time_string(self, sub_second: bool = False) -> str:
        rt = self.get_running_time()
        return format_time(rt, sub_second) if rt != NO_TIME else ""

    def get_start_time_string(self, sub_second: bool = False) -> str:
        return format_time(self.start_time, sub_second)

    def get_finish_time_string(self, sub_second: bool = False) -> str:
        return format_time(self.finish_time, sub_second)

    def set_start_time_from_string(self, s: str) -> None:
        self.start_time = parse_time(s)
        self.mark_changed()

    def set_finish_time_from_string(self, s: str) -> None:
        self.finish_time = parse_time(s)
        self.mark_changed()

    # ------------------------------------------------------------------
    # Input data helpers (multi-day)
    # ------------------------------------------------------------------

    def has_input_data(self) -> bool:
        return (self.input_time != NO_TIME or
                self.input_status != RunnerStatus.OK or
                self.input_points > 0)

    def reset_input_data(self) -> None:
        self.input_time   = NO_TIME
        self.input_status = RunnerStatus.NotCompeting
        self.input_points = 0
        self.input_place  = 0
        self.mark_changed()

    # ------------------------------------------------------------------
    # Base interface
    # ------------------------------------------------------------------

    def get_info(self) -> str:
        return (f"Runner '{self.name}' (id={self._id}, "
                f"card={self.card_number}, status={self.status.name})")

    def remove(self) -> None:
        self._removed = True
        self.mark_changed()

    def can_remove(self) -> bool:
        return self.team_id == 0   # can't remove if part of a team

    # ------------------------------------------------------------------
    # Sorting key
    # ------------------------------------------------------------------

    def result_sort_key(self) -> tuple:
        """Key for sorting by result (status, time, name)."""
        order = RUNNER_STATUS_ORDER.get(self.status, 99)
        rt    = self.get_running_time()
        rt    = rt if rt != NO_TIME else 999999999
        return (order, rt, self.sort_name)
