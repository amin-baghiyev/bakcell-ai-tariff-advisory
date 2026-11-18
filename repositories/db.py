"""Database access helpers (stdlib sqlite3, zero extra dependencies)."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from config import Config
from models.schema import init_db


def connect(db_path: str | None = None) -> sqlite3.Connection:
    """Open a connection with sensible defaults (row dicts, FK on)."""
    path = db_path or Config.DATABASE_PATH
    if path != ":memory:":
        Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def setup(db_path: str | None = None) -> sqlite3.Connection:
    """Open a connection and ensure the schema exists."""
    conn = connect(db_path)
    init_db(conn)
    return conn
