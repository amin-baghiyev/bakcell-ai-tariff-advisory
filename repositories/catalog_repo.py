"""Tariff catalog persistence."""

from __future__ import annotations

import sqlite3


def upsert_tariff(conn: sqlite3.Connection, t: dict) -> None:
    conn.execute(
        """
        INSERT INTO tariffs (name, family, price_azn, data_gb, allnet_min, onnet_min,
                             offnet_min, sms, unlimited_apps, source)
        VALUES (:name, :family, :price_azn, :data_gb, :allnet_min, :onnet_min,
                :offnet_min, :sms, :unlimited_apps, :source)
        ON CONFLICT(name) DO UPDATE SET
            family = excluded.family, price_azn = excluded.price_azn,
            data_gb = excluded.data_gb, allnet_min = excluded.allnet_min,
            onnet_min = excluded.onnet_min, offnet_min = excluded.offnet_min,
            sms = excluded.sms, unlimited_apps = excluded.unlimited_apps,
            source = excluded.source
        """,
        t,
    )


def upsert_price(conn: sqlite3.Connection, key: str, value: float, source: str) -> None:
    conn.execute(
        """
        INSERT INTO tariff_prices (price_key, value_azn, source) VALUES (?, ?, ?)
        ON CONFLICT(price_key) DO UPDATE SET value_azn = excluded.value_azn
        """,
        (key, value, source),
    )


def all_tariffs(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute("SELECT * FROM tariffs ORDER BY price_azn, name").fetchall()


def tariff_map(conn: sqlite3.Connection) -> dict[str, sqlite3.Row]:
    return {r["name"]: r for r in all_tariffs(conn)}


def prices(conn: sqlite3.Connection) -> dict[str, float]:
    return {
        r["price_key"]: r["value_azn"]
        for r in conn.execute("SELECT * FROM tariff_prices").fetchall()
    }
