"""
models/punch.py
===============
A single SI punch (oPunch equivalent).

A punch records which SI station (control code) was visited and at what time.
Times are stored in internal units (1 unit = 0.1 s).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, TYPE_CHECKING

from .base import Base
from .enums import SpecialPunchType
from utils.time_utils import format_time, parse_time, NO_TIME

if TYPE_CHECKING:
    from .event import Event


@dataclass
class Punch(Base):
    """Represents a single punch on a SI card."""

    # SI station code (control number, or SpecialPunchType value)
    type_code: int = 0
    # Raw recorded time in internal units (1 unit = 0.1 s); 0 = not set
    time_raw: int = NO_TIME
    # Time after unit-level adjustment (e.g. wrong clock correction)
    time_adjust_fixed: int = 0
    # Dynamic adjustment (minimum time between controls)
    time_adjust_dynamic: int = 0
    # Index in the card's punch list
    card_index: int = -1
    # Matched control index in the course (-1 if unmatched)
    course_index: int = -1
    # Matched control ID in the course
    matched_control_id: int = 0
    # Was played in the speaker system
    has_been_played: bool = False
    # Is used in the course evaluation
    is_used: bool = False
    # Rogaining index / points
    rogaining_index: int = -1
    rogaining_points: int = 0
    # SI unit (station unit identifier)
    punch_unit: int = 0

    def __post_init__(self) -> None:
        super().__init__()

    # ------------------------------------------------------------------
    # Type helpers
    # ------------------------------------------------------------------

    def is_start(self) -> bool:
        return self.type_code == SpecialPunchType.Start

    def is_finish(self) -> bool:
        return self.type_code == SpecialPunchType.Finish

    def is_check(self) -> bool:
        return self.type_code == SpecialPunchType.Check

    def is_hired_card(self) -> bool:
        return self.type_code == SpecialPunchType.HiredCard

    @property
    def control_number(self) -> int:
        """Return the ordinary control number (0 if special punch)."""
        return self.type_code if self.type_code >= 30 else 0

    # ------------------------------------------------------------------
    # Time access
    # ------------------------------------------------------------------

    @property
    def time(self) -> int:
        """Return the punch time after the unit-level fixed adjustment."""
        if self.time_raw == NO_TIME:
            return NO_TIME
        return self.time_raw + self.time_adjust_fixed

    @property
    def adjusted_time(self) -> int:
        """Return the punch time including both fixed and dynamic adjustments."""
        t = self.time
        if t == NO_TIME:
            return NO_TIME
        return t + self.time_adjust_dynamic

    def has_time(self) -> bool:
        return self.time_raw != NO_TIME and self.time_raw > 0

    def set_time_from_string(self, s: str) -> None:
        self.time_raw = parse_time(s)
        self.mark_changed()

    def get_time_string(self, sub_second: bool = False) -> str:
        return format_time(self.time, sub_second)

    def get_running_time_string(self, start_time: int, sub_second: bool = False) -> str:
        t = self.time
        if t == NO_TIME or start_time == NO_TIME or t < start_time:
            return ""
        return format_time(t - start_time, sub_second)

    # ------------------------------------------------------------------
    # Base interface
    # ------------------------------------------------------------------

    def get_info(self) -> str:
        tstr = format_time(self.time)
        return f"Punch code={self.type_code} time={tstr}"

    def remove(self) -> None:
        self._removed = True
        self.mark_changed()

    def can_remove(self) -> bool:
        return True


@dataclass
class SIPunch:
    """Raw punch data read directly from a SI card (mirrors C++ SIPunch struct)."""
    code: int = 0
    time: int = 0    # raw SI time in internal units

    def analyse_hour12_time(self, zero_time: int) -> None:
        """Adjust 12-hour SI time to 24-hour based on zero_time."""
        half_day = 12 * 3600 * 10   # 12h in internal units
        full_day = 24 * 3600 * 10
        if self.time == 0:
            return
        # Try to match against zero_time
        candidate = self.time
        while candidate + half_day < zero_time:
            candidate += half_day
        # Pick nearest
        if abs(candidate - zero_time) > abs(candidate + half_day - zero_time):
            candidate += half_day
        self.time = candidate % full_day
