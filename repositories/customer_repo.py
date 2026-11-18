"""Customer + usage-record persistence."""

from __future__ import annotations

import sqlite3

CUSTOMER_FIELDS = [
    "customer_id", "age", "gender", "region", "subscriber_type", "tenure_months",
    "device", "network", "current_tariff", "months_on_tariff", "price_azn",
    "plan_data_gb", "plan_allnet_min", "plan_onnet_min", "plan_offnet_min",
    "plan_sms", "plan_unlimited_apps", "avg_data_gb", "avg_minutes",
    "data_utilization", "minute_utilization", "avg_spend_azn", "extra_gb_6m",
    "tariff_end_date", "tariff_end_source", "notification_opt_in",
]

USAGE_FIELDS = [
    "customer_id", "month", "tariff", "data_gb", "total_minutes", "onnet_min",
    "offnet_min", "sms", "extra_gb", "out_of_bundle_min", "roaming_days",
    "topup_count", "callcenter_contacts", "spend_azn",
]


def upsert_customer(conn: sqlite3.Connection, c: dict) -> None:
    cols = [f for f in CUSTOMER_FIELDS if f in c]
    placeholders = ", ".join(f":{c_}" for c_ in cols)
    updates = ", ".join(
        f"{c_} = excluded.{c_}" for c_ in cols if c_ != "customer_id"
    )
    conn.execute(
        f"""
        INSERT INTO customers ({', '.join(cols)}) VALUES ({placeholders})
        ON CONFLICT(customer_id) DO UPDATE SET {updates}
        """,
        {k: c.get(k) for k in cols},
    )


def upsert_usage(conn: sqlite3.Connection, u: dict) -> None:
    cols = [f for f in USAGE_FIELDS if f in u]
    placeholders = ", ".join(f":{c_}" for c_ in cols)
    updates = ", ".join(f"{c_} = excluded.{c_}" for c_ in cols if c_ not in ("customer_id", "month"))
    conn.execute(
        f"""
        INSERT INTO usage_records ({', '.join(cols)}) VALUES ({placeholders})
        ON CONFLICT(customer_id, month) DO UPDATE SET {updates}
        """,
        {k: u.get(k) for k in cols},
    )


def get_customer(conn: sqlite3.Connection, customer_id: str) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM customers WHERE customer_id = ?", (customer_id,)
    ).fetchone()


def all_customers(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute("SELECT * FROM customers ORDER BY customer_id").fetchall()


def usage_for(conn: sqlite3.Connection, customer_id: str) -> list[sqlite3.Row]:
    """All months for a customer, ascending by month."""
    return conn.execute(
        "SELECT * FROM usage_records WHERE customer_id = ? ORDER BY month",
        (customer_id,),
    ).fetchall()


def set_tariff_end(
    conn: sqlite3.Connection, customer_id: str, end_date: str | None, source: str
) -> None:
    conn.execute(
        "UPDATE customers SET tariff_end_date = ?, tariff_end_source = ? WHERE customer_id = ?",
        (end_date, source, customer_id),
    )
    conn.commit()


def set_opt_in(conn: sqlite3.Connection, customer_id: str, opt_in: bool) -> None:
    conn.execute(
        "UPDATE customers SET notification_opt_in = ? WHERE customer_id = ?",
        (1 if opt_in else 0, customer_id),
    )
    conn.commit()


def apply_tariff_change(
    conn: sqlite3.Connection, customer_id: str, tariff: dict, *, from_tariff: str | None
) -> None:
    """Point a customer at a catalog tariff and record the change.

    Plan attributes are copied from the catalog (source-supported only).
    Utilization ratios are recomputed against the new allowance using the
    observed 6-month averages (same formula the workbook uses).
    The renewal/end date is reset: the source has no end-date field, so a new
    plan's period end is unknown (provenance back to ``missing_in_source``).
    """
    data_gb = tariff.get("data_gb")
    allnet = tariff.get("allnet_min") or 0
    onnet = tariff.get("onnet_min") or 0
    offnet = tariff.get("offnet_min") or 0
    minutes_total = allnet if allnet > 0 else onnet + offnet

    conn.execute(
        """
        UPDATE customers
        SET current_tariff = ?, price_azn = ?, plan_data_gb = ?, plan_allnet_min = ?,
            plan_onnet_min = ?, plan_offnet_min = ?, plan_sms = ?,
            plan_unlimited_apps = ?, months_on_tariff = 0,
            data_utilization = CASE WHEN ? > 0 AND avg_data_gb IS NOT NULL
                                    THEN avg_data_gb / ? ELSE NULL END,
            minute_utilization = CASE WHEN ? > 0 AND avg_minutes IS NOT NULL
                                      THEN avg_minutes / ? ELSE NULL END,
            tariff_end_date = NULL, tariff_end_source = 'missing_in_source'
        WHERE customer_id = ?
        """,
        (
            tariff["name"], tariff.get("price_azn"), data_gb, tariff.get("allnet_min"),
            tariff.get("onnet_min"), tariff.get("offnet_min"), tariff.get("sms"),
            tariff.get("unlimited_apps"),
            data_gb or 0, data_gb or 0,
            minutes_total, minutes_total,
            customer_id,
        ),
    )
    from datetime import datetime, timezone

    conn.execute(
        "INSERT INTO tariff_changes (customer_id, from_tariff, to_tariff, changed_at, source) "
        "VALUES (?, ?, ?, ?, 'demo_user_action')",
        (
            customer_id, from_tariff, tariff["name"],
            datetime.now(timezone.utc).isoformat(timespec="seconds"),
        ),
    )
    conn.commit()


def last_tariff_change(conn: sqlite3.Connection, customer_id: str) -> dict | None:
    row = conn.execute(
        "SELECT * FROM tariff_changes WHERE customer_id = ? "
        "ORDER BY changed_at DESC, id DESC LIMIT 1",
        (customer_id,),
    ).fetchone()
    return dict(row) if row else None
