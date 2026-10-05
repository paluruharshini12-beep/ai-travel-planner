"""SQLite persistence and schema management."""

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from src.config import get_settings


class DatabaseError(RuntimeError):
    """Raised when a database operation cannot be completed."""


def _connect() -> sqlite3.Connection:
    path = get_settings().database_path
    try:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(path, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection
    except sqlite3.Error as exc:
        raise DatabaseError("The local database could not be opened.") from exc


@contextmanager
def connection() -> Iterator[sqlite3.Connection]:
    """Open a transaction and reliably commit or roll it back."""
    db = _connect()
    try:
        yield db
        db.commit()
    except sqlite3.Error as exc:
        db.rollback()
        raise DatabaseError("A database operation failed.") from exc
    finally:
        db.close()


def initialize_database() -> None:
    """Create application tables when the database is first used."""
    with connection() as db:
        db.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE COLLATE NOCASE,
                password_hash TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                google_sub TEXT UNIQUE
            );
            CREATE TABLE IF NOT EXISTS trips (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                destination TEXT NOT NULL,
                country TEXT NOT NULL,
                state TEXT NOT NULL DEFAULT '',
                budget REAL NOT NULL,
                currency TEXT NOT NULL,
                start_date TEXT NOT NULL DEFAULT '',
                days INTEGER NOT NULL,
                travelers INTEGER NOT NULL,
                travel_style TEXT NOT NULL,
                interests TEXT NOT NULL,
                itinerary TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS password_reset_tokens (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                token_hash TEXT NOT NULL UNIQUE,
                expires_at TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            """
        )
        columns = {
            row["name"] for row in db.execute("PRAGMA table_info(trips)").fetchall()
        }
        if "start_date" not in columns:
            db.execute("ALTER TABLE trips ADD COLUMN start_date TEXT NOT NULL DEFAULT ''")
            db.execute(
                "UPDATE trips SET start_date = substr(created_at, 1, 10) WHERE start_date = ''"
            )
