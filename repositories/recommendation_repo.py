"""Recommendation snapshot persistence."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone


def save(
    conn: sqlite3.Connection,
    customer_id: str,
    ranked: list[dict],
    explanation: dict,
    window_start: str,
    window_end: str,
    model_version: str,
    weights: dict,
) -> int:
    cur = conn.execute(
        """
        INSERT INTO recommendations (customer_id, generated_at, current_tariff,
                                     ranked_json, explanation_json, window_start,
                                     window_end, model_version, weights_json)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            customer_id,
            datetime.now(timezone.utc).isoformat(timespec="seconds"),
            ranked[0].get("current_tariff") if ranked else None,
            json.dumps(ranked, ensure_ascii=False),
            json.dumps(explanation, ensure_ascii=False),
            window_start,
            window_end,
            model_version,
            json.dumps(weights, ensure_ascii=False),
        ),
    )
    conn.commit()
    return int(cur.lastrowid)


def latest_for(conn: sqlite3.Connection, customer_id: str) -> sqlite3.Row | None:
    return conn.execute(
        """
        SELECT * FROM recommendations
        WHERE customer_id = ?
        ORDER BY generated_at DESC, id DESC LIMIT 1
        """,
        (customer_id,),
    ).fetchone()


def latest_all(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """Most recent snapshot per customer (one row each)."""
    return conn.execute(
        """
        SELECT r.* FROM recommendations r
        JOIN (SELECT customer_id, MAX(id) AS mid FROM recommendations
              GROUP BY customer_id) m
          ON r.id = m.mid
        ORDER BY r.customer_id
        """
    ).fetchall()


def count(conn: sqlite3.Connection) -> int:
    return conn.execute("SELECT COUNT(*) AS n FROM recommendations").fetchone()["n"]
