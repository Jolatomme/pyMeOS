"""
models/base.py
==============
Abstract base for every MeOS domain object (oBase equivalent).

All objects have:
  • id        – integer primary key
  • modified  – UTC datetime of last local modification
  • changed   – flag: locally changed, not yet written to DB
  • removed   – soft-delete flag
  • event     – back-reference to the owning Event (set after construction)

Sub-classes must implement:
  • get_info() -> str
  • remove()
  • can_remove() -> bool
"""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .event import Event   # avoid circular imports


class Base(ABC):
    """Abstract base class for all orienteering domain objects."""

    def __init__(self, event: Optional["Event"] = None) -> None:
        self._id: int = 0
        self._modified: datetime = datetime.now(timezone.utc)
        self._changed: bool = False
        self._removed: bool = False
        self._event: Optional["Event"] = event
        # External identifier (IOF / federation ID)
        self._ext_id: int = 0

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def id(self) -> int:
        return self._id

    @id.setter
    def id(self, value: int) -> None:
        self._id = value

    @property
    def event(self) -> Optional["Event"]:
        return self._event

    @event.setter
    def event(self, evt: Optional["Event"]) -> None:
        self._event = evt

    @property
    def modified(self) -> datetime:
        return self._modified

    @property
    def changed(self) -> bool:
        return self._changed

    @property
    def removed(self) -> bool:
        return self._removed

    @property
    def ext_id(self) -> int:
        return self._ext_id

    @ext_id.setter
    def ext_id(self, value: int) -> None:
        self._ext_id = value

    # ------------------------------------------------------------------
    # Mutation helpers
    # ------------------------------------------------------------------

    def mark_changed(self) -> None:
        """Mark this object as locally modified."""
        self._changed = True
        self._modified = datetime.now(timezone.utc)
        self._on_changed()

    def clear_changed(self) -> None:
        """Clear the changed flag after the object has been persisted."""
        self._changed = False

    def _on_changed(self) -> None:
        """Hook called whenever the object is marked changed.

        Subclasses may override to notify controllers/views.
        """

    # ------------------------------------------------------------------
    # Abstract interface
    # ------------------------------------------------------------------

    @abstractmethod
    def get_info(self) -> str:
        """Return a human-readable description of the object."""

    @abstractmethod
    def remove(self) -> None:
        """Remove / soft-delete the object."""

    @abstractmethod
    def can_remove(self) -> bool:
        """Return True if the object is safe to remove."""

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} id={self._id}>"

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Base):
            return NotImplemented
        return self.__class__ is other.__class__ and self._id == other._id

    def __hash__(self) -> int:
        return hash((self.__class__, self._id))
