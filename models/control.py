"""
models/control.py
=================
A control point on an orienteering map (oControl equivalent).

A control can carry multiple SI station numbers (up to 32 in MeOS).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, List, TYPE_CHECKING

from .base import Base
from .enums import ControlStatus

if TYPE_CHECKING:
    from .event import Event


# Special punch codes (mirrors oPunch::SpecialPunch)
PUNCH_START  = 1
PUNCH_FINISH = 2
PUNCH_CHECK  = 3


@dataclass
class Control(Base):
    """Represents a single control point."""

    name: str = ""
    status: ControlStatus = ControlStatus.OK
    # Up to 32 SI station numbers accepted at this control
    numbers: List[int] = field(default_factory=list)
    # Coordinate in arbitrary map units (optional)
    x: float = 0.0
    y: float = 0.0
    # Time adjustment applied to all punches at this control (internal units)
    time_adjustment: int = 0
    # Rogaining point value (0 if not rogaining)
    rogaining_points: int = 0

    def __post_init__(self) -> None:
        # Base.__init__ is NOT called via dataclass; call manually
        super().__init__()

    # ------------------------------------------------------------------
    # Identity helpers
    # ------------------------------------------------------------------

    def is_start(self) -> bool:
        return self.status == ControlStatus.Start

    def is_finish(self) -> bool:
        return self.status == ControlStatus.Finish

    def is_check(self) -> bool:
        return self.status == ControlStatus.Check

    def is_rogaining(self) -> bool:
        return self.status in (ControlStatus.Rogaining, ControlStatus.RogainingReq)

    def is_special(self) -> bool:
        return self.status.is_special()

    # ------------------------------------------------------------------
    # Number helpers
    # ------------------------------------------------------------------

    def has_number(self, code: int) -> bool:
        return code in self.numbers

    def min_number(self) -> int:
        return min(self.numbers) if self.numbers else 0

    def add_number(self, code: int) -> None:
        if code not in self.numbers:
            self.numbers.append(code)
            self.mark_changed()

    def remove_number(self, code: int) -> None:
        if code in self.numbers:
            self.numbers.remove(code)
            self.mark_changed()

    def set_numbers_from_string(self, s: str) -> bool:
        """Parse a comma/semicolon separated list of SI numbers.

        Returns True on success.

        >>> c = Control(); c.set_numbers_from_string("31,32")
        True
        >>> c.numbers
        [31, 32]
        """
        s = s.strip()
        if not s:
            self.numbers = []
            return True
        result: List[int] = []
        for part in s.replace(";", ",").split(","):
            part = part.strip()
            if part:
                try:
                    result.append(int(part))
                except ValueError:
                    return False
        self.numbers = result
        self.mark_changed()
        return True

    def numbers_as_string(self) -> str:
        """Return numbers as a comma-separated string."""
        return ", ".join(str(n) for n in self.numbers)

    # ------------------------------------------------------------------
    # Base interface
    # ------------------------------------------------------------------

    def get_info(self) -> str:
        return f"Control {self.name} [{self.numbers_as_string()}] ({self.status.name})"

    def remove(self) -> None:
        self._removed = True
        self.mark_changed()

    def can_remove(self) -> bool:
        if self._event is None:
            return True
        # A control can be removed only if no course references it
        for course in self._event.courses.values():
            if self._id in course.control_ids:
                return False
        return True

    # ------------------------------------------------------------------
    # Comparison (for sorting by SI number)
    # ------------------------------------------------------------------

    def __lt__(self, other: "Control") -> bool:
        return self.min_number() < other.min_number()
