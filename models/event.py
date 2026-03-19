"""
models/event.py
===============
The central event model (oEvent equivalent).

Holds all collections (runners, teams, classes, courses, controls, clubs, cards)
and provides:
  • factory methods to create domain objects with auto-assigned IDs
  • lookup helpers
  • high-level result calculation trigger
  • XML/IOF import/export hooks
  • signals (via simple callback lists) for MVC notifications
"""
from __future__ import annotations

import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional, Callable, Any

from .base import Base
from .control import Control
from .course import Course
from .class_ import Class
from .club import Club
from .runner import Runner
from .team import Team
from .card import Card
from .punch import Punch
from .enums import RunnerStatus, SortOrder
from utils.time_utils import NO_TIME


# -------------------------------------------------------------------------
# Change notification subscriber type
# -------------------------------------------------------------------------
ChangeCallback = Callable[[str, Any], None]


# -------------------------------------------------------------------------
# Event model
# -------------------------------------------------------------------------

class Event(Base):
    """Central registry for an orienteering event."""

    def __init__(self) -> None:
        super().__init__(event=self)   # event is itself

        # ---- Event metadata -------------------------------------------
        self.name: str = ""
        self.annotation: str = ""
        self.date: str = ""           # ISO "YYYY-MM-DD"
        self.zero_time: int = 0       # day-zero in internal units
        self.organiser: str = ""
        self.country: str = ""
        self.currency: str = "SEK"
        self.currency_factor: int = 1

        # ---- Collections (keyed by id) ---------------------------------
        self.controls: Dict[int, Control] = {}
        self.courses:  Dict[int, Course]  = {}
        self.classes:  Dict[int, Class]   = {}
        self.clubs:    Dict[int, Club]    = {}
        self.runners:  Dict[int, Runner]  = {}
        self.teams:    Dict[int, Team]    = {}
        self.cards:    Dict[int, Card]    = {}
        self.punches:  Dict[int, Punch]   = {}

        # ---- Free-ID counters ------------------------------------------
        self._next_ids: Dict[str, int] = {
            k: 1 for k in ("control", "course", "class", "club",
                           "runner", "team", "card", "punch")
        }

        # ---- Sort order ------------------------------------------------
        self._sort_order: SortOrder = SortOrder.ClassResult

        # ---- Change tracking / data revision ---------------------------
        self._data_revision: int = 0
        self._lock: threading.Lock = threading.Lock()

        # ---- MVC notification callbacks --------------------------------
        # key: topic string, value: list of callables
        self._subscribers: Dict[str, List[ChangeCallback]] = {}

        # ---- Database / persistence info -------------------------------
        self.current_file: str = ""
        self.db_server: str = ""
        self.db_user: str = ""
        self.db_password: str = ""
        self.db_port: int = 3306
        self.is_connected_to_db: bool = False

        # ---- Properties map (arbitrary key-value pairs) ----------------
        self.properties: Dict[str, str] = {}

    # ------------------------------------------------------------------
    # Free-ID helpers
    # ------------------------------------------------------------------

    def _next_id(self, kind: str) -> int:
        with self._lock:
            nid = self._next_ids[kind]
            self._next_ids[kind] = nid + 1
            return nid

    def _recalc_free_ids(self) -> None:
        """Recompute the free-id counters after loading from file/DB."""
        mapping = [
            ("control", self.controls),
            ("course",  self.courses),
            ("class",   self.classes),
            ("club",    self.clubs),
            ("runner",  self.runners),
            ("team",    self.teams),
            ("card",    self.cards),
            ("punch",   self.punches),
        ]
        with self._lock:
            for kind, coll in mapping:
                self._next_ids[kind] = (max(coll.keys()) + 1) if coll else 1

    # ------------------------------------------------------------------
    # Factory methods
    # ------------------------------------------------------------------

    def add_control(self, name: str = "", numbers: Optional[List[int]] = None) -> Control:
        obj = Control(name=name, numbers=list(numbers or []))
        obj.id = self._next_id("control")
        obj.event = self
        self.controls[obj.id] = obj
        self._notify("controls_changed", obj)
        return obj

    def add_course(self, name: str = "") -> Course:
        obj = Course(name=name)
        obj.id = self._next_id("course")
        obj.event = self
        self.courses[obj.id] = obj
        self._notify("courses_changed", obj)
        return obj

    def add_class(self, name: str = "") -> Class:
        obj = Class(name=name)
        obj.id = self._next_id("class")
        obj.event = self
        self.classes[obj.id] = obj
        self._notify("classes_changed", obj)
        return obj

    def add_club(self, name: str = "") -> Club:
        # Reuse existing club with same name (case-insensitive)
        name_lower = name.strip().lower()
        for club in self.clubs.values():
            if club.name.lower() == name_lower:
                return club
        obj = Club(name=name.strip())
        obj.id = self._next_id("club")
        obj.event = self
        self.clubs[obj.id] = obj
        self._notify("clubs_changed", obj)
        return obj

    def add_runner(self,
                   first_name: str = "",
                   last_name: str = "",
                   club_id: int = 0,
                   class_id: int = 0) -> Runner:
        obj = Runner(first_name=first_name, last_name=last_name,
                     club_id=club_id, class_id=class_id)
        obj.id = self._next_id("runner")
        obj.event = self
        self.runners[obj.id] = obj
        self._notify("runners_changed", obj)
        return obj

    def add_team(self, name: str = "", club_id: int = 0, class_id: int = 0) -> Team:
        obj = Team(name=name, club_id=club_id, class_id=class_id)
        obj.id = self._next_id("team")
        obj.event = self
        self.teams[obj.id] = obj
        self._notify("teams_changed", obj)
        return obj

    def add_card(self, card_number: int) -> Card:
        obj = Card(card_number=card_number)
        obj.id = self._next_id("card")
        obj.event = self
        self.cards[obj.id] = obj
        self._notify("cards_changed", obj)
        return obj

    # ------------------------------------------------------------------
    # Lookup helpers
    # ------------------------------------------------------------------

    def get_runner_by_card(self, card_number: int) -> Optional[Runner]:
        for r in self.runners.values():
            if r.card_number == card_number and not r.removed:
                return r
        return None

    def get_runners_by_class(self, class_id: int) -> List[Runner]:
        return [r for r in self.runners.values()
                if r.class_id == class_id and not r.removed]

    def get_teams_by_class(self, class_id: int) -> List[Team]:
        return [t for t in self.teams.values()
                if t.class_id == class_id and not t.removed]

    def get_club_by_name(self, name: str) -> Optional[Club]:
        name_lower = name.strip().lower()
        for c in self.clubs.values():
            if c.name.lower() == name_lower:
                return c
        return None

    def get_class_by_name(self, name: str) -> Optional[Class]:
        name_lower = name.strip().lower()
        for c in self.classes.values():
            if c.name.lower() == name_lower:
                return c
        return None

    def get_course_by_name(self, name: str) -> Optional[Course]:
        name_lower = name.strip().lower()
        for c in self.courses.values():
            if c.name.lower() == name_lower:
                return c
        return None

    # ------------------------------------------------------------------
    # Deletion helpers
    # ------------------------------------------------------------------

    def remove_runner(self, runner_id: int) -> bool:
        r = self.runners.get(runner_id)
        if r and r.can_remove():
            r.remove()
            self._notify("runners_changed", r)
            return True
        return False

    def remove_team(self, team_id: int) -> bool:
        t = self.teams.get(team_id)
        if t and t.can_remove():
            t.remove()
            self._notify("teams_changed", t)
            return True
        return False

    def remove_course(self, course_id: int) -> bool:
        c = self.courses.get(course_id)
        if c and c.can_remove():
            c.remove()
            self._notify("courses_changed", c)
            return True
        return False

    def remove_class(self, class_id: int) -> bool:
        c = self.classes.get(class_id)
        if c and c.can_remove():
            c.remove()
            self._notify("classes_changed", c)
            return True
        return False

    def remove_club(self, club_id: int) -> bool:
        c = self.clubs.get(club_id)
        if c and c.can_remove():
            c.remove()
            self._notify("clubs_changed", c)
            return True
        return False

    def remove_control(self, control_id: int) -> bool:
        c = self.controls.get(control_id)
        if c and c.can_remove():
            c.remove()
            self._notify("controls_changed", c)
            return True
        return False

    # ------------------------------------------------------------------
    # Data revision (for cache invalidation)
    # ------------------------------------------------------------------

    def bump_revision(self) -> None:
        with self._lock:
            self._data_revision += 1

    @property
    def data_revision(self) -> int:
        return self._data_revision

    # ------------------------------------------------------------------
    # MVC notifications
    # ------------------------------------------------------------------

    def subscribe(self, topic: str, cb: ChangeCallback) -> None:
        self._subscribers.setdefault(topic, []).append(cb)

    def unsubscribe(self, topic: str, cb: ChangeCallback) -> None:
        listeners = self._subscribers.get(topic, [])
        if cb in listeners:
            listeners.remove(cb)

    def _notify(self, topic: str, payload: Any = None) -> None:
        self.bump_revision()
        for cb in self._subscribers.get(topic, []):
            try:
                cb(topic, payload)
            except Exception:
                pass   # Never let a UI callback crash the model

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    def clear(self) -> None:
        """Clear all competition data (but keep event metadata)."""
        self.controls.clear()
        self.courses.clear()
        self.classes.clear()
        self.clubs.clear()
        self.runners.clear()
        self.teams.clear()
        self.cards.clear()
        self.punches.clear()
        self._next_ids = {k: 1 for k in self._next_ids}
        self._data_revision = 0
        # Notify subscribers directly without bumping revision again
        for cb in self._subscribers.get("event_cleared", []):
            try:
                cb("event_cleared", None)
            except Exception:
                pass

    def statistics(self) -> dict:
        return {
            "runners":  sum(1 for r in self.runners.values() if not r.removed),
            "teams":    sum(1 for t in self.teams.values()   if not t.removed),
            "classes":  sum(1 for c in self.classes.values() if not c.removed),
            "courses":  sum(1 for c in self.courses.values() if not c.removed),
            "controls": sum(1 for c in self.controls.values() if not c.removed),
            "clubs":    sum(1 for c in self.clubs.values()   if not c.removed),
            "cards":    sum(1 for c in self.cards.values()   if not c.removed),
        }

    # ------------------------------------------------------------------
    # Base interface (oEvent inherits from oBase in C++)
    # ------------------------------------------------------------------

    def get_info(self) -> str:
        return f"Event '{self.name}' ({self.date})"

    def remove(self) -> None:
        pass  # Events are not removed via this method

    def can_remove(self) -> bool:
        return False

    def _on_changed(self) -> None:
        self.bump_revision()
