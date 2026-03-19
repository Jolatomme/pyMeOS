"""
models/course.py
================
An orienteering course: ordered sequence of controls (oCourse equivalent).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, TYPE_CHECKING

from .base import Base

if TYPE_CHECKING:
    from .control import Control
    from .event import Event


@dataclass
class Course(Base):
    """Represents one orienteering course."""

    name: str = ""
    # Ordered list of control IDs (including start/finish if applicable)
    control_ids: List[int] = field(default_factory=list)
    # Map length in metres
    length: int = 0
    # Total climb in metres
    climb: int = 0

    def __post_init__(self) -> None:
        super().__init__()

    # ------------------------------------------------------------------
    # Control access
    # ------------------------------------------------------------------

    @property
    def num_controls(self) -> int:
        """Number of *ordinary* controls (excluding start/finish codes)."""
        return len(self.control_ids)

    def controls(self, event: Optional["Event"] = None) -> List["Control"]:
        """Resolve control IDs to Control objects.

        Requires ``event`` or self._event to be set.
        """
        ev = event or self._event
        if ev is None:
            return []
        return [ev.controls[cid] for cid in self.control_ids
                if cid in ev.controls]

    def has_control(self, control_id: int) -> bool:
        return control_id in self.control_ids

    def add_control(self, control_id: int, position: Optional[int] = None) -> None:
        if position is None:
            self.control_ids.append(control_id)
        else:
            self.control_ids.insert(position, control_id)
        self.mark_changed()

    def remove_control_at(self, position: int) -> None:
        if 0 <= position < len(self.control_ids):
            self.control_ids.pop(position)
            self.mark_changed()

    def move_control(self, from_pos: int, to_pos: int) -> None:
        if from_pos == to_pos:
            return
        cid = self.control_ids.pop(from_pos)
        self.control_ids.insert(to_pos, cid)
        self.mark_changed()

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def is_valid(self) -> bool:
        """A course is valid if it has at least one control."""
        return len(self.control_ids) > 0

    # ------------------------------------------------------------------
    # Base interface
    # ------------------------------------------------------------------

    def get_info(self) -> str:
        return (f"Course '{self.name}': {self.num_controls} controls, "
                f"{self.length}m, {self.climb}m climb")

    def remove(self) -> None:
        self._removed = True
        self.mark_changed()

    def can_remove(self) -> bool:
        if self._event is None:
            return True
        for cls in self._event.classes.values():
            if cls.course_id == self._id:
                return False
        return True
