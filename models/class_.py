"""
models/class_.py
================
A competition class (oClass equivalent).

A class groups runners/teams by category (age, sex, etc.) and defines
course assignment, start type, leg structure for relays, and result method.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Dict, TYPE_CHECKING

from .base import Base
from .enums import StartType, LegType, BibMode, ClassType, Sex

if TYPE_CHECKING:
    from .event import Event


@dataclass
class LegInfo:
    """Per-leg settings for relay classes."""
    start_type: StartType = StartType.Change
    leg_type: LegType = LegType.Normal
    course_id: int = 0
    start_after_leg: int = -1  # -1 = previous leg


@dataclass
class Class(Base):
    """Represents one competition class."""

    name: str = ""
    # Primary course (for individual classes or default relay leg)
    course_id: int = 0
    # For relay classes: list of per-leg settings
    legs: List[LegInfo] = field(default_factory=list)

    # Class category metadata
    class_type: ClassType = ClassType.Individual
    sex: Sex = Sex.Unknown
    age_lower: int = 0
    age_upper: int = 0

    # Start configuration
    start_type: StartType = StartType.Drawn
    first_start: int = 0          # internal time units
    start_interval: int = 0       # internal time units between runners
    n_before_interval: int = 1    # number of runners per interval slot

    # Bib numbering
    bib_mode: BibMode = BibMode.Undefined
    bib_gap: int = 0              # gap between bibs for relay teams

    # Entry fee (in currency sub-units, e.g. cents)
    entry_fee: int = 0
    late_entry_fee: int = 0
    # Age factor (percentage) for entry fee
    age_factor: int = 100

    # Number of places to show in results
    n_places: int = 0

    # Result module name / id
    result_module_id: str = ""

    # Should the class be shown in results list
    no_timing: bool = False

    def __post_init__(self) -> None:
        super().__init__()

    # ------------------------------------------------------------------
    # Relay helpers
    # ------------------------------------------------------------------

    @property
    def num_legs(self) -> int:
        return max(1, len(self.legs))

    def is_relay(self) -> bool:
        return self.class_type == ClassType.Relay

    def is_rogaining(self) -> bool:
        return self.class_type == ClassType.Rogaining

    def is_patrol(self) -> bool:
        return self.class_type == ClassType.Patrol

    def get_leg_course_id(self, leg: int) -> int:
        """Return the course ID for a given leg (0-based)."""
        if self.legs and 0 <= leg < len(self.legs) and self.legs[leg].course_id:
            return self.legs[leg].course_id
        return self.course_id

    # ------------------------------------------------------------------
    # Start helpers
    # ------------------------------------------------------------------

    def get_start_time(self, start_no: int) -> int:
        """Calculate the scheduled start time for runner/team with given start number (1-based)."""
        if self.start_interval == 0:
            return self.first_start
        slot = (start_no - 1) // max(1, self.n_before_interval)
        return self.first_start + slot * self.start_interval

    # ------------------------------------------------------------------
    # Base interface
    # ------------------------------------------------------------------

    def get_info(self) -> str:
        return f"Class '{self.name}' ({self.class_type.value})"

    def remove(self) -> None:
        self._removed = True
        self.mark_changed()

    def can_remove(self) -> bool:
        if self._event is None:
            return True
        for runner in self._event.runners.values():
            if runner.class_id == self._id:
                return False
        return True
