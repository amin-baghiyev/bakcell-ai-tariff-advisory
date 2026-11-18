"""User/account persistence (demo login accounts only — never the workbook)."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone


def find_user(conn: sqlite3.Connection, email: str) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM users WHERE email = ? AND active = 1", (email,)
    ).fetchone()


def create_user(
    conn: sqlite3.Connection,
    email: str,
    password_hash: str,
    role: str,
    customer_id: str | None = None,
) -> int:
    cur = conn.execute(
        """
        INSERT INTO users (email, password_hash, role, customer_id, active, created_at)
        VALUES (?, ?, ?, ?, 1, ?)
        ON CONFLICT(email) DO UPDATE SET
            password_hash = excluded.password_hash,
            role = excluded.role,
            customer_id = excluded.customer_id,
            active = 1
        """,
        (
            email,
            password_hash,
            role,
            customer_id,
            datetime.now(timezone.utc).isoformat(timespec="seconds"),
        ),
    )
    conn.commit()
    return int(cur.lastrowid or 0)
