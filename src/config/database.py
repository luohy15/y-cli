"""SQLAlchemy database setup and migration."""

import sqlite3
from contextlib import contextmanager
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker, Session
from entity.base import Base


_engine = None
_SessionLocal = None


def init_db(sqlite_file: str):
    """Initialize the database engine and create tables."""
    global _engine, _SessionLocal
    _engine = create_engine(f"sqlite:///{sqlite_file}", echo=False)
    _SessionLocal = sessionmaker(bind=_engine)

    # Import entities so Base.metadata knows about them
    import entity.bot_config  # noqa: F401
    import entity.prompt_config  # noqa: F401
    import entity.chat  # noqa: F401

    Base.metadata.create_all(_engine)
    _migrate_schema(sqlite_file)


def _migrate_schema(sqlite_file: str):
    """Add created_at/updated_at columns to existing tables if missing."""
    conn = sqlite3.connect(sqlite_file)
    try:
        for table in ["bot_config", "prompt_config", "chat"]:
            cols = {row[1] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
            if "created_at" not in cols:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN created_at TEXT")
            if "updated_at" not in cols:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN updated_at TEXT")
        conn.commit()
    finally:
        conn.close()


@contextmanager
def get_db() -> Session:
    """Context manager that yields a SQLAlchemy session."""
    session = _SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
