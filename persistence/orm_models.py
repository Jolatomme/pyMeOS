"""
persistence/orm_models.py
=========================
SQLAlchemy ORM tables that persist the event model to a relational database.

The schema mirrors the MySQL schema used by MeOS (MeosSQL.cpp) but is expressed
as SQLAlchemy mapped classes so that it also works on SQLite and PostgreSQL.
"""
from __future__ import annotations

from sqlalchemy import (
    Column, Integer, String, Text, Boolean, DateTime, ForeignKey, Index,
    BigInteger, Float
)
from sqlalchemy.orm import relationship

from .database import Base


class OrmEvent(Base):
    __tablename__ = "events"

    id          = Column(Integer, primary_key=True, autoincrement=True)
    name        = Column(String(255), nullable=False, default="")
    annotation  = Column(String(512), default="")
    date        = Column(String(20),  default="")
    zero_time   = Column(Integer,     default=0)
    organiser   = Column(String(255), default="")
    country     = Column(String(64),  default="")
    currency    = Column(String(10),  default="SEK")
    properties  = Column(Text,        default="")
    modified    = Column(DateTime)

    controls    = relationship("OrmControl", back_populates="event", cascade="all, delete-orphan")
    courses     = relationship("OrmCourse",  back_populates="event", cascade="all, delete-orphan")
    classes     = relationship("OrmClass",   back_populates="event", cascade="all, delete-orphan")
    clubs       = relationship("OrmClub",    back_populates="event", cascade="all, delete-orphan")
    runners     = relationship("OrmRunner",  back_populates="event", cascade="all, delete-orphan")
    teams       = relationship("OrmTeam",    back_populates="event", cascade="all, delete-orphan")
    cards       = relationship("OrmCard",    back_populates="event", cascade="all, delete-orphan")


class OrmControl(Base):
    __tablename__ = "controls"

    id          = Column(Integer, primary_key=True, autoincrement=True)
    event_id    = Column(Integer, ForeignKey("events.id"), nullable=False)
    name        = Column(String(64), default="")
    status      = Column(Integer, default=0)
    numbers     = Column(String(256), default="")   # comma-separated
    time_adjust = Column(Integer, default=0)
    rog_points  = Column(Integer, default=0)
    modified    = Column(DateTime)

    event       = relationship("OrmEvent", back_populates="controls")

    __table_args__ = (Index("ix_controls_event", "event_id"),)


class OrmCourse(Base):
    __tablename__ = "courses"

    id          = Column(Integer, primary_key=True, autoincrement=True)
    event_id    = Column(Integer, ForeignKey("events.id"), nullable=False)
    name        = Column(String(128), default="")
    control_ids = Column(Text, default="")   # JSON / comma-separated
    length      = Column(Integer, default=0)
    climb       = Column(Integer, default=0)
    modified    = Column(DateTime)

    event       = relationship("OrmEvent", back_populates="courses")


class OrmClass(Base):
    __tablename__ = "classes"

    id              = Column(Integer, primary_key=True, autoincrement=True)
    event_id        = Column(Integer, ForeignKey("events.id"), nullable=False)
    name            = Column(String(128), default="")
    course_id       = Column(Integer, default=0)
    class_type      = Column(String(32), default="individual")
    start_type      = Column(Integer, default=2)   # Drawn
    first_start     = Column(Integer, default=0)
    start_interval  = Column(Integer, default=0)
    entry_fee       = Column(Integer, default=0)
    late_fee        = Column(Integer, default=0)
    no_timing       = Column(Boolean, default=False)
    result_module   = Column(String(128), default="")
    legs_json       = Column(Text, default="")
    modified        = Column(DateTime)

    event           = relationship("OrmEvent", back_populates="classes")


class OrmClub(Base):
    __tablename__ = "clubs"

    id          = Column(Integer, primary_key=True, autoincrement=True)
    event_id    = Column(Integer, ForeignKey("events.id"), nullable=False)
    name        = Column(String(255), default="")
    short_name  = Column(String(64),  default="")
    country     = Column(String(64),  default="")
    nationality = Column(String(8),   default="")
    ext_id      = Column(BigInteger,  default=0)
    modified    = Column(DateTime)

    event       = relationship("OrmEvent", back_populates="clubs")

    __table_args__ = (Index("ix_clubs_event", "event_id"),)


class OrmRunner(Base):
    __tablename__ = "runners"

    id          = Column(Integer, primary_key=True, autoincrement=True)
    event_id    = Column(Integer, ForeignKey("events.id"), nullable=False)
    first_name  = Column(String(128), default="")
    last_name   = Column(String(128), default="")
    sex         = Column(String(8),   default="unknown")
    club_id     = Column(Integer, default=0)
    class_id    = Column(Integer, default=0)
    course_id   = Column(Integer, default=0)
    start_no    = Column(Integer, default=0)
    bib         = Column(String(16), default="")
    card_number = Column(Integer, default=0)
    start_time  = Column(Integer, default=0)
    finish_time = Column(Integer, default=0)
    status      = Column(Integer, default=0)
    flags       = Column(Integer, default=0)
    team_id     = Column(Integer, default=0)
    leg_number  = Column(Integer, default=0)
    rank        = Column(Integer, default=0)
    entry_date  = Column(String(20), default="")
    nationality = Column(String(8),  default="")
    input_time   = Column(Integer, default=0)
    input_status = Column(Integer, default=1)
    input_points = Column(Integer, default=0)
    input_place  = Column(Integer, default=0)
    ext_id      = Column(BigInteger, default=0)
    modified    = Column(DateTime)

    event       = relationship("OrmEvent", back_populates="runners")

    __table_args__ = (
        Index("ix_runners_event",       "event_id"),
        Index("ix_runners_card",        "card_number"),
        Index("ix_runners_class",       "class_id"),
    )


class OrmTeam(Base):
    __tablename__ = "teams"

    id          = Column(Integer, primary_key=True, autoincrement=True)
    event_id    = Column(Integer, ForeignKey("events.id"), nullable=False)
    name        = Column(String(255), default="")
    club_id     = Column(Integer, default=0)
    class_id    = Column(Integer, default=0)
    start_no    = Column(Integer, default=0)
    bib         = Column(String(16), default="")
    start_time  = Column(Integer, default=0)
    finish_time = Column(Integer, default=0)
    status      = Column(Integer, default=0)
    runner_ids  = Column(Text, default="")   # JSON list
    flags       = Column(Integer, default=0)
    entry_date  = Column(String(20), default="")
    input_time   = Column(Integer, default=0)
    input_status = Column(Integer, default=1)
    ext_id      = Column(BigInteger, default=0)
    modified    = Column(DateTime)

    event       = relationship("OrmEvent", back_populates="teams")

    __table_args__ = (Index("ix_teams_event", "event_id"),)


class OrmCard(Base):
    __tablename__ = "cards"

    id              = Column(Integer, primary_key=True, autoincrement=True)
    event_id        = Column(Integer, ForeignKey("events.id"), nullable=False)
    card_number     = Column(Integer, default=0)
    owner_runner_id = Column(Integer, default=0)
    mili_volt       = Column(Integer, default=0)
    battery_date    = Column(Integer, default=0)
    punches_json    = Column(Text,    default="")   # JSON encoded punches
    modified        = Column(DateTime)

    event           = relationship("OrmEvent", back_populates="cards")

    __table_args__ = (Index("ix_cards_event", "event_id"),)
