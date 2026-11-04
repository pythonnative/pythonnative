"""The journal's SQLite file: its schema, its migrations, and the thread it lives on.

SQLite connections belong to the thread that opened them, and a slow disk
shouldn't hold up the application thread that renders. So one connection lives on
one worker thread, and ``await database.run(work)`` sends it a function to call.
That also serializes every read and write without any further locking.
"""

from __future__ import annotations

import asyncio
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Callable, Optional, TypeVar

T = TypeVar("T")

MIGRATIONS: tuple[str, ...] = (
    """
    CREATE TABLE entries (
        id TEXT PRIMARY KEY,
        title TEXT NOT NULL DEFAULT '',
        body TEXT NOT NULL DEFAULT '',
        conditions TEXT NOT NULL DEFAULT '',
        latitude REAL,
        longitude REAL,
        accuracy REAL,
        place_name TEXT NOT NULL DEFAULT '',
        created_at REAL NOT NULL,
        updated_at REAL NOT NULL,
        device TEXT NOT NULL DEFAULT '',
        deleted_at REAL,
        dirty INTEGER NOT NULL DEFAULT 1
    );
    CREATE INDEX entries_by_recency ON entries (deleted_at, created_at DESC);
    CREATE INDEX entries_to_push ON entries (dirty);

    CREATE TABLE entry_tags (
        entry_id TEXT NOT NULL REFERENCES entries (id) ON DELETE CASCADE,
        tag TEXT NOT NULL,
        position INTEGER NOT NULL,
        PRIMARY KEY (entry_id, tag)
    );
    CREATE INDEX entry_tags_by_tag ON entry_tags (tag);

    CREATE TABLE attachments (
        id TEXT PRIMARY KEY,
        entry_id TEXT NOT NULL REFERENCES entries (id) ON DELETE CASCADE,
        kind TEXT NOT NULL CHECK (kind IN ('photo', 'voice', 'video')),
        path TEXT NOT NULL DEFAULT '',
        mime_type TEXT NOT NULL DEFAULT 'application/octet-stream',
        name TEXT NOT NULL DEFAULT '',
        size INTEGER NOT NULL DEFAULT 0,
        duration REAL NOT NULL DEFAULT 0,
        created_at REAL NOT NULL,
        remote_path TEXT NOT NULL DEFAULT '',
        deleted_at REAL
    );
    CREATE INDEX attachments_by_entry ON attachments (entry_id, created_at);

    CREATE TABLE settings (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL
    );
    """,
    """
    CREATE TABLE reminders (
        entry_id TEXT PRIMARY KEY REFERENCES entries (id) ON DELETE CASCADE,
        fire_at REAL NOT NULL
    );
    """,
)
"""Each item moves the schema up one version. Only ever append, since these have run on devices."""


def _fold(text: Optional[str]) -> str:
    """SQLite's ``LIKE`` only folds ASCII, which fails a journal written in Norwegian."""
    return (text or "").casefold()


def migrate(connection: sqlite3.Connection) -> None:
    """Bring a connection's file up to the latest schema, one transaction per version."""
    version: int = connection.execute("PRAGMA user_version").fetchone()[0]
    for number, script in enumerate(MIGRATIONS[version:], start=version + 1):
        # A transaction makes each step all or nothing. ``executescript`` commits
        # first, so the script opens its own and sets the version inside it.
        connection.executescript(f"BEGIN; {script} PRAGMA user_version = {number}; COMMIT;")


class Database:
    """One SQLite file, on its own thread.

    Args:
        path: The file, created with its directory if missing.
    """

    def __init__(self, path: Path) -> None:
        self.path = path
        self._connection: Optional[sqlite3.Connection] = None
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="fieldnotes-db")

    def _connect(self) -> sqlite3.Connection:
        if self._connection is None:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            connection = sqlite3.connect(self.path)
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA foreign_keys = ON")
            # The background task and the app can both be running in one process.
            connection.execute("PRAGMA journal_mode = WAL")
            connection.create_function("folded", 1, _fold, deterministic=True)
            migrate(connection)
            self._connection = connection
        return self._connection

    async def run(self, work: Callable[[sqlite3.Connection], T]) -> T:
        """Call ``work`` with the connection on the database thread.

        Args:
            work: A function to run. A write wraps itself in ``with connection:``
                so that it commits or rolls back whole.

        Returns:
            Whatever ``work`` returned.

        Raises:
            sqlite3.Error: Whatever ``work`` raised.
        """

        def call() -> T:
            return work(self._connect())

        return await asyncio.get_running_loop().run_in_executor(self._executor, call)

    def close(self) -> None:
        """Close the file. Only tests need this, since the app's file lives as long as it does."""

        def shut() -> None:
            if self._connection is not None:
                self._connection.close()
                self._connection = None

        self._executor.submit(shut).result()
        self._executor.shutdown()
