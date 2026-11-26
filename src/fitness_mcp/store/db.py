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


# Bump whenever schema.sql changes incompatibly. On mismatch we drop the
# user's cache file and recreate from scratch — cache-aside sync re-fetches
# on next use so this is a latency hit, not data loss.
SCHEMA_VERSION = 3


def _open() -> sqlite3.Connection:
    s = get_settings()
    s.db_path.parent.mkdir(parents=True, exist_ok=True)
    _maybe_reset_on_schema_change(s.db_path)
    conn = sqlite3.connect(
        s.db_path,
        isolation_level=None,  # autocommit; we manage transactions explicitly
        check_same_thread=False,
    )
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA_PATH.read_text())
    conn.execute(
        "CREATE TABLE IF NOT EXISTS _schema (version INTEGER NOT NULL)"
    )
    cur = conn.execute("SELECT version FROM _schema LIMIT 1")
    row = cur.fetchone()
    if row is None:
        conn.execute("INSERT INTO _schema(version) VALUES (?)", (SCHEMA_VERSION,))
    log.info("sqlite ready at %s (schema v%s)", s.db_path, SCHEMA_VERSION)
    return conn


def _maybe_reset_on_schema_change(db_path: Path) -> None:
    """If the on-disk DB is from an older schema, remove it. Cache will
    rebuild on the next tool call."""
    if not db_path.exists():
        return
    try:
        probe = sqlite3.connect(db_path)
        probe.row_factory = sqlite3.Row
        cur = probe.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='_schema'"
        )
        if cur.fetchone() is None:
            log.warning("sqlite at %s has no _schema table — resetting cache", db_path)
            probe.close()
            db_path.unlink()
            for suffix in ("-wal", "-shm"):
                sibling = db_path.with_name(db_path.name + suffix)
                if sibling.exists():
                    sibling.unlink()
            return
        version = probe.execute("SELECT version FROM _schema LIMIT 1").fetchone()
        probe.close()
        if version is None or version["version"] != SCHEMA_VERSION:
            log.warning(
                "sqlite schema v%s != expected v%s — resetting cache at %s",
                (version or {}).get("version"), SCHEMA_VERSION, db_path,
            )
            db_path.unlink()
            for suffix in ("-wal", "-shm"):
                sibling = db_path.with_name(db_path.name + suffix)
                if sibling.exists():
                    sibling.unlink()
    except sqlite3.Error as e:
        log.warning("sqlite probe failed (%s); resetting cache at %s", e, db_path)
        db_path.unlink()
        for suffix in ("-wal", "-shm"):
            sibling = db_path.with_name(db_path.name + suffix)
            if sibling.exists():
                sibling.unlink()


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
