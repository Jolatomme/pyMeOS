"""
persistence/event_repo.py
=========================
Repository that maps between the domain Event model and the ORM tables.

Usage::

    repo = EventRepository()
    event = repo.load_event(1)
    repo.save_event(event)
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import List, Optional

from .database import get_session
from .orm_models import (
    OrmEvent, OrmControl, OrmCourse, OrmClass, OrmClub,
    OrmRunner, OrmTeam, OrmCard
)
from models import (
    Event, Control, Course, Class, Club, Runner, Team, Card, Punch,
    ControlStatus, RunnerStatus, ClassType, StartType, Sex, LegInfo
)
from models.enums import SpecialPunchType
from utils.time_utils import NO_TIME


class EventRepository:
    """CRUD operations for Event objects backed by SQLAlchemy."""

    # ------------------------------------------------------------------
    # List / load
    # ------------------------------------------------------------------

    def list_events(self) -> List[dict]:
        """Return summary dicts for all events."""
        with get_session() as s:
            rows = s.query(OrmEvent).all()
            return [{"id": r.id, "name": r.name, "date": r.date} for r in rows]

    def load_event(self, event_id: int) -> Optional[Event]:
        with get_session() as s:
            orm = s.query(OrmEvent).filter_by(id=event_id).first()
            if orm is None:
                return None
            return self._orm_to_event(orm)

    # ------------------------------------------------------------------
    # Save
    # ------------------------------------------------------------------

    def save_event(self, event: Event) -> int:
        """Persist the event. Returns the assigned event id."""
        with get_session() as s:
            if event.id:
                orm = s.query(OrmEvent).filter_by(id=event.id).first()
                if orm is None:
                    orm = OrmEvent()
                    s.add(orm)
            else:
                orm = OrmEvent()
                s.add(orm)

            self._event_to_orm(event, orm)
            s.flush()
            event.id = orm.id

            # Persist child collections
            self._save_controls(s, event, orm.id)
            self._save_courses(s, event, orm.id)
            self._save_classes(s, event, orm.id)
            self._save_clubs(s, event, orm.id)
            self._save_runners(s, event, orm.id)
            self._save_teams(s, event, orm.id)
            self._save_cards(s, event, orm.id)

        return event.id

    def delete_event(self, event_id: int) -> bool:
        with get_session() as s:
            orm = s.query(OrmEvent).filter_by(id=event_id).first()
            if orm:
                s.delete(orm)
                return True
        return False

    # ------------------------------------------------------------------
    # Internal conversion helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _event_to_orm(ev: Event, orm: OrmEvent) -> None:
        orm.name       = ev.name
        orm.annotation = ev.annotation
        orm.date       = ev.date
        orm.zero_time  = ev.zero_time
        orm.organiser  = ev.organiser
        orm.country    = ev.country
        orm.currency   = ev.currency
        orm.properties = json.dumps(ev.properties)
        orm.modified   = datetime.now(timezone.utc)

    @staticmethod
    def _orm_to_event(orm: OrmEvent) -> Event:
        ev = Event()
        ev.id         = orm.id
        ev.name       = orm.name or ""
        ev.annotation = orm.annotation or ""
        ev.date       = orm.date or ""
        ev.zero_time  = orm.zero_time or 0
        ev.organiser  = orm.organiser or ""
        ev.country    = orm.country or ""
        ev.currency   = orm.currency or "SEK"
        try:
            ev.properties = json.loads(orm.properties or "{}")
        except (json.JSONDecodeError, TypeError):
            ev.properties = {}

        # Controls
        for row in orm.controls:
            c = Control()
            c.id             = row.id
            c.name           = row.name or ""
            c.status         = ControlStatus(row.status)
            c.numbers        = [int(x) for x in (row.numbers or "").split(",") if x.strip()]
            c.time_adjustment= row.time_adjust or 0
            c.rogaining_points = row.rog_points or 0
            c.event          = ev
            ev.controls[c.id] = c

        # Courses
        for row in orm.courses:
            c = Course()
            c.id         = row.id
            c.name       = row.name or ""
            c.length     = row.length or 0
            c.climb      = row.climb or 0
            try:
                c.control_ids = json.loads(row.control_ids or "[]")
            except (json.JSONDecodeError, TypeError):
                c.control_ids = []
            c.event      = ev
            ev.courses[c.id] = c

        # Classes
        for row in orm.classes:
            c = Class()
            c.id           = row.id
            c.name         = row.name or ""
            c.course_id    = row.course_id or 0
            c.class_type   = ClassType(row.class_type or "individual")
            c.start_type   = StartType(row.start_type or 2)
            c.first_start  = row.first_start or 0
            c.start_interval= row.start_interval or 0
            c.entry_fee    = row.entry_fee or 0
            c.late_entry_fee= row.late_fee or 0
            c.no_timing    = bool(row.no_timing)
            c.result_module_id = row.result_module or ""
            try:
                legs_data = json.loads(row.legs_json or "[]")
                c.legs = [LegInfo(**l) for l in legs_data]
            except Exception:
                c.legs = []
            c.event        = ev
            ev.classes[c.id] = c

        # Clubs
        for row in orm.clubs:
            c = Club()
            c.id            = row.id
            c.name          = row.name or ""
            c.short_name    = row.short_name or ""
            c.country       = row.country or ""
            c.nationality_code = row.nationality or ""
            c.event         = ev
            ev.clubs[c.id]  = c

        # Runners
        for row in orm.runners:
            r = Runner()
            r.id           = row.id
            r.first_name   = row.first_name or ""
            r.last_name    = row.last_name or ""
            r.sex          = Sex(row.sex or "unknown")
            r.club_id      = row.club_id or 0
            r.class_id     = row.class_id or 0
            r.course_id    = row.course_id or 0
            r.start_no     = row.start_no or 0
            r.bib          = row.bib or ""
            r.card_number  = row.card_number or 0
            r.start_time   = row.start_time or NO_TIME
            r.finish_time  = row.finish_time or NO_TIME
            r.status       = RunnerStatus(row.status or 0)
            r.flags        = row.flags or 0
            r.team_id      = row.team_id or 0
            r.leg_number   = row.leg_number or 0
            r.rank         = row.rank or 0
            r.entry_date   = row.entry_date or ""
            r.nationality  = row.nationality or ""
            r.input_time   = row.input_time or NO_TIME
            r.input_status = RunnerStatus(row.input_status or 1)
            r.input_points = row.input_points or 0
            r.input_place  = row.input_place or 0
            r.ext_id       = row.ext_id or 0
            r.event        = ev
            ev.runners[r.id] = r

        # Teams
        for row in orm.teams:
            t = Team()
            t.id         = row.id
            t.name       = row.name or ""
            t.club_id    = row.club_id or 0
            t.class_id   = row.class_id or 0
            t.start_no   = row.start_no or 0
            t.bib        = row.bib or ""
            t.start_time = row.start_time or NO_TIME
            t.status     = RunnerStatus(row.status or 0)
            try:
                t.runner_ids = json.loads(row.runner_ids or "[]")
            except Exception:
                t.runner_ids = []
            t.flags      = row.flags or 0
            t.entry_date = row.entry_date or ""
            t.event      = ev
            ev.teams[t.id] = t

        # Cards
        for row in orm.cards:
            c = Card()
            c.id              = row.id
            c.card_number     = row.card_number or 0
            c.owner_runner_id = row.owner_runner_id or 0
            c.mili_volt       = row.mili_volt or 0
            c.battery_date    = row.battery_date or 0
            try:
                punches_data = json.loads(row.punches_json or "[]")
                c.punches = [_dict_to_punch(pd) for pd in punches_data]
            except Exception:
                c.punches = []
            c.event = ev
            ev.cards[c.id] = c

        ev._recalc_free_ids()
        return ev

    # ------------------------------------------------------------------
    # Child-collection savers
    # ------------------------------------------------------------------

    @staticmethod
    def _save_controls(s, ev: Event, event_id: int) -> None:
        existing = {r.id: r for r in s.query(OrmControl).filter_by(event_id=event_id)}
        for obj in ev.controls.values():
            if obj.removed:
                if obj.id in existing:
                    s.delete(existing[obj.id])
                continue
            orm = existing.get(obj.id) or OrmControl(event_id=event_id)
            orm.event_id    = event_id
            orm.name        = obj.name
            orm.status      = obj.status.value
            orm.numbers     = ",".join(str(n) for n in obj.numbers)
            orm.time_adjust = obj.time_adjustment
            orm.rog_points  = obj.rogaining_points
            orm.modified    = datetime.now(timezone.utc)
            s.add(orm)

    @staticmethod
    def _save_courses(s, ev: Event, event_id: int) -> None:
        existing = {r.id: r for r in s.query(OrmCourse).filter_by(event_id=event_id)}
        for obj in ev.courses.values():
            if obj.removed:
                if obj.id in existing:
                    s.delete(existing[obj.id])
                continue
            orm = existing.get(obj.id) or OrmCourse(event_id=event_id)
            orm.event_id    = event_id
            orm.name        = obj.name
            orm.control_ids = json.dumps(obj.control_ids)
            orm.length      = obj.length
            orm.climb       = obj.climb
            orm.modified    = datetime.now(timezone.utc)
            s.add(orm)

    @staticmethod
    def _save_classes(s, ev: Event, event_id: int) -> None:
        existing = {r.id: r for r in s.query(OrmClass).filter_by(event_id=event_id)}
        for obj in ev.classes.values():
            if obj.removed:
                if obj.id in existing:
                    s.delete(existing[obj.id])
                continue
            orm = existing.get(obj.id) or OrmClass(event_id=event_id)
            orm.event_id       = event_id
            orm.name           = obj.name
            orm.course_id      = obj.course_id
            orm.class_type     = obj.class_type.value
            orm.start_type     = obj.start_type.value
            orm.first_start    = obj.first_start
            orm.start_interval = obj.start_interval
            orm.entry_fee      = obj.entry_fee
            orm.late_fee       = obj.late_entry_fee
            orm.no_timing      = obj.no_timing
            orm.result_module  = obj.result_module_id
            orm.legs_json      = json.dumps([l.__dict__ for l in obj.legs])
            orm.modified       = datetime.now(timezone.utc)
            s.add(orm)

    @staticmethod
    def _save_clubs(s, ev: Event, event_id: int) -> None:
        existing = {r.id: r for r in s.query(OrmClub).filter_by(event_id=event_id)}
        for obj in ev.clubs.values():
            if obj.removed:
                if obj.id in existing:
                    s.delete(existing[obj.id])
                continue
            orm = existing.get(obj.id) or OrmClub(event_id=event_id)
            orm.event_id   = event_id
            orm.name       = obj.name
            orm.short_name = obj.short_name
            orm.country    = obj.country
            orm.nationality= obj.nationality_code
            orm.ext_id     = obj.ext_id
            orm.modified   = datetime.now(timezone.utc)
            s.add(orm)

    @staticmethod
    def _save_runners(s, ev: Event, event_id: int) -> None:
        existing = {r.id: r for r in s.query(OrmRunner).filter_by(event_id=event_id)}
        for obj in ev.runners.values():
            if obj.removed:
                if obj.id in existing:
                    s.delete(existing[obj.id])
                continue
            orm = existing.get(obj.id) or OrmRunner(event_id=event_id)
            orm.event_id    = event_id
            orm.first_name  = obj.first_name
            orm.last_name   = obj.last_name
            orm.sex         = obj.sex.value
            orm.club_id     = obj.club_id
            orm.class_id    = obj.class_id
            orm.course_id   = obj.course_id
            orm.start_no    = obj.start_no
            orm.bib         = obj.bib
            orm.card_number = obj.card_number
            orm.start_time  = obj.start_time
            orm.finish_time = obj.finish_time
            orm.status      = obj.status.value
            orm.flags       = obj.flags
            orm.team_id     = obj.team_id
            orm.leg_number  = obj.leg_number
            orm.rank        = obj.rank
            orm.entry_date  = obj.entry_date
            orm.nationality = obj.nationality
            orm.input_time  = obj.input_time
            orm.input_status= obj.input_status.value
            orm.input_points= obj.input_points
            orm.input_place = obj.input_place
            orm.ext_id      = obj.ext_id
            orm.modified    = datetime.now(timezone.utc)
            s.add(orm)

    @staticmethod
    def _save_teams(s, ev: Event, event_id: int) -> None:
        existing = {r.id: r for r in s.query(OrmTeam).filter_by(event_id=event_id)}
        for obj in ev.teams.values():
            if obj.removed:
                if obj.id in existing:
                    s.delete(existing[obj.id])
                continue
            orm = existing.get(obj.id) or OrmTeam(event_id=event_id)
            orm.event_id   = event_id
            orm.name       = obj.name
            orm.club_id    = obj.club_id
            orm.class_id   = obj.class_id
            orm.start_no   = obj.start_no
            orm.bib        = obj.bib
            orm.start_time = obj.start_time
            orm.status     = obj.status.value
            orm.runner_ids = json.dumps(obj.runner_ids)
            orm.flags      = obj.flags
            orm.entry_date = obj.entry_date
            orm.modified   = datetime.now(timezone.utc)
            s.add(orm)

    @staticmethod
    def _save_cards(s, ev: Event, event_id: int) -> None:
        existing = {r.id: r for r in s.query(OrmCard).filter_by(event_id=event_id)}
        for obj in ev.cards.values():
            if obj.removed:
                if obj.id in existing:
                    s.delete(existing[obj.id])
                continue
            orm = existing.get(obj.id) or OrmCard(event_id=event_id)
            orm.event_id        = event_id
            orm.card_number     = obj.card_number
            orm.owner_runner_id = obj.owner_runner_id
            orm.mili_volt       = obj.mili_volt
            orm.battery_date    = obj.battery_date
            orm.punches_json    = json.dumps([_punch_to_dict(p) for p in obj.punches])
            orm.modified        = datetime.now(timezone.utc)
            s.add(orm)


# ---------------------------------------------------------------------------
# Punch serialisation helpers
# ---------------------------------------------------------------------------

def _punch_to_dict(p: Punch) -> dict:
    return {
        "type_code":   p.type_code,
        "time_raw":    p.time_raw,
        "time_adjust": p.time_adjust_fixed,
        "card_index":  p.card_index,
    }


def _dict_to_punch(d: dict) -> Punch:
    p = Punch()
    p.type_code         = d.get("type_code", 0)
    p.time_raw          = d.get("time_raw", 0)
    p.time_adjust_fixed = d.get("time_adjust", 0)
    p.card_index        = d.get("card_index", -1)
    return p
