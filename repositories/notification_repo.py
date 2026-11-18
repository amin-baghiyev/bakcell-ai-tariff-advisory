"""Notification persistence (in-app demo reminders + skip log)."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def create_once(
    conn: sqlite3.Connection,
    customer_id: str,
    ntype: str,
    period_key: str,
    message: str,
    due_at: str | None = None,
    params: dict | None = None,
) -> bool:
    """Insert a notification if (customer, type, period) does not exist yet.

    Returns True when a new row was created, False when it already existed
    (idempotency guarantee). ``params`` carries the structured fields used to
    render the message in the viewer's language; existing rows get the params
    backfilled once so old notifications become localizable too.
    """
    import json

    params_json = json.dumps(params, ensure_ascii=False) if params else None
    cur = conn.execute(
        """
        INSERT OR IGNORE INTO notifications
            (customer_id, type, period_key, due_at, created_at, status, message, params_json)
        VALUES (?, ?, ?, ?, ?, 'pending', ?, ?)
        """,
        (customer_id, ntype, period_key, due_at, _now(), message, params_json),
    )
    if cur.rowcount == 0 and params_json:
        conn.execute(
            "UPDATE notifications SET params_json = ? "
            "WHERE customer_id = ? AND type = ? AND period_key = ? AND params_json IS NULL",
            (params_json, customer_id, ntype, period_key),
        )
    conn.commit()
    return cur.rowcount > 0


def record_skip(
    conn: sqlite3.Connection,
    customer_id: str | None,
    period_key: str | None,
    reason: str,
) -> None:
    """Record a skip reason (one row per customer+period+reason, latest kept)."""
    cid = customer_id or "-"
    pk = period_key or "-"
    conn.execute(
        "DELETE FROM notification_skips WHERE COALESCE(customer_id, '-') = ? "
        "AND COALESCE(period_key, '-') = ? AND reason = ?",
        (cid, pk, reason),
    )
    conn.execute(
        "INSERT INTO notification_skips (customer_id, period_key, reason, created_at) "
        "VALUES (?, ?, ?, ?)",
        (customer_id, period_key, reason, _now()),
    )
    conn.commit()


def for_customer(conn: sqlite3.Connection, customer_id: str) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM notifications WHERE customer_id = ? ORDER BY created_at DESC, id DESC",
        (customer_id,),
    ).fetchall()


def all_recent(conn: sqlite3.Connection, limit: int = 50) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM notifications ORDER BY created_at DESC, id DESC LIMIT ?",
        (limit,),
    ).fetchall()


def recent_skips(conn: sqlite3.Connection, limit: int = 50) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM notification_skips ORDER BY created_at DESC, id DESC LIMIT ?",
        (limit,),
    ).fetchall()


def mark_read(conn: sqlite3.Connection, notification_id: int, customer_id: str) -> bool:
    cur = conn.execute(
        "UPDATE notifications SET status = 'read' WHERE id = ? AND customer_id = ?",
        (notification_id, customer_id),
    )
    conn.commit()
    return cur.rowcount > 0
