"""
persistence/database.py
========================
SQLAlchemy session factory.

Supports SQLite (default, single-file), MySQL, and PostgreSQL.
The database URL is set once via ``init_db()``.
"""
from __future__ import annotations

from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine, event as sa_event, text
from sqlalchemy.orm import sessionmaker, Session, DeclarativeBase

_engine = None
_SessionLocal = None


class Base(DeclarativeBase):
    """All ORM mapped classes inherit from this."""
    pass


def init_db(url: str = "sqlite:///pymeos.db", echo: bool = False) -> None:
    """Initialise the database engine.

    Parameters
    ----------
    url : str
        SQLAlchemy connection URL.
        Examples:
          - ``sqlite:///pymeos.db``              (relative file)
          - ``sqlite:///:memory:``               (in-memory)
          - ``mysql+pymysql://user:pw@host/db``  (MySQL)
    echo : bool
        If True, log all SQL statements (useful for debugging).
    """
    global _engine, _SessionLocal

    connect_args = {}
    if url.startswith("sqlite"):
        connect_args["check_same_thread"] = False

    _engine = create_engine(url, echo=echo, connect_args=connect_args)

    # Enable WAL mode for SQLite (much better concurrency)
    if url.startswith("sqlite"):
        @sa_event.listens_for(_engine, "connect")
        def set_wal(dbapi_conn, _conn_record):
            dbapi_conn.execute("PRAGMA journal_mode=WAL")
            dbapi_conn.execute("PRAGMA foreign_keys=ON")

    _SessionLocal = sessionmaker(bind=_engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(_engine)


def get_engine():
    if _engine is None:
        raise RuntimeError("init_db() has not been called")
    return _engine


@contextmanager
def get_session() -> Generator[Session, None, None]:
    """Context manager that yields a SQLAlchemy session and handles
    commit / rollback automatically.

    Usage::

        with get_session() as session:
            session.add(obj)
    """
    if _SessionLocal is None:
        raise RuntimeError("init_db() has not been called")
    session: Session = _SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
