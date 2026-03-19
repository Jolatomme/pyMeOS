"""
models/club.py
==============
A club / organisation (oClub equivalent).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from .base import Base


@dataclass
class Club(Base):
    """Represents a club or organisation."""

    name: str = ""
    short_name: str = ""
    country: str = ""
    nationality_code: str = ""
    # IOF / federation identifier string
    ext_id_str: str = ""

    def __post_init__(self) -> None:
        super().__init__()

    # ------------------------------------------------------------------
    # Derived display name helpers
    # ------------------------------------------------------------------

    @property
    def display_name(self) -> str:
        return self.name or self.short_name

    @property
    def compact_name(self) -> str:
        return self.short_name or self.name

    def set_name(self, name: str) -> None:
        self.name = name.strip()
        self.mark_changed()

    # ------------------------------------------------------------------
    # Base interface
    # ------------------------------------------------------------------

    def get_info(self) -> str:
        return f"Club '{self.name}' [{self.country}]"

    def remove(self) -> None:
        self._removed = True
        self.mark_changed()

    def can_remove(self) -> bool:
        if self._event is None:
            return True
        for runner in self._event.runners.values():
            if runner.club_id == self._id:
                return False
        for team in self._event.teams.values():
            if team.club_id == self._id:
                return False
        return True
