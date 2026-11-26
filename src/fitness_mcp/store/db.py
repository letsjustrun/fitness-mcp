"""SQLite connection management.

One connection per process is enough for a local POC. WAL mode lets reads and
writes interleave without blocking each other. The module-level connection is
created on first use; tests reset it via `reset_connection()` after pointing
the settings at a temp DB.
"""
from __future__ import annotations

import logging
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from ..config import get_settings

log = logging.getLogger(__name__)
SCHEMA_PATH = Path(__file__).with_name("schema.sql")

_connection: sqlite3.Connection | None = None


def _open() -> sqlite3.Connection:
    s = get_settings()
    s.db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(
        s.db_path,
        isolation_level=None,  # autocommit; we manage transactions explicitly
        check_same_thread=False,
    )
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA_PATH.read_text())
    log.info("sqlite ready at %s", s.db_path)
    return conn


def _get_connection() -> sqlite3.Connection:
    global _connection
    if _connection is None:
        _connection = _open()
    return _connection


def reset_connection() -> None:
    """Test hook: close + drop the cached connection."""
    global _connection
    if _connection is not None:
        try:
            _connection.close()
        except sqlite3.Error:
            pass
        _connection = None


@contextmanager
def get_db() -> Iterator[sqlite3.Connection]:
    yield _get_connection()


@contextmanager
def transaction() -> Iterator[sqlite3.Connection]:
    conn = _get_connection()
    conn.execute("BEGIN")
    try:
        yield conn
    except Exception:
        conn.execute("ROLLBACK")
        raise
    else:
        conn.execute("COMMIT")
