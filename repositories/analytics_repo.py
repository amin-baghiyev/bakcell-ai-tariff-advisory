"""Aggregate queries for the admin dashboard.

Every query is filter-aware (month range + tariff) and returns ``None`` for
metrics that cannot be computed rather than pretending the value is zero.
"""

from __future__ import annotations

import sqlite3


def _usage_filters(month_from: str | None, month_to: str | None, tariff: str | None):
    clauses, params = [], []
    if month_from:
        clauses.append("u.month >= ?")
        params.append(month_from)
    if month_to:
        clauses.append("u.month <= ?")
        params.append(month_to)
    if tariff:
        clauses.append("u.tariff = ?")
        params.append(tariff)
    return clauses, params


def customer_count(conn: sqlite3.Connection, tariff: str | None = None) -> int:
    if tariff:
        row = conn.execute(
            "SELECT COUNT(*) AS n FROM customers WHERE current_tariff = ?", (tariff,)
        ).fetchone()
    else:
        row = conn.execute("SELECT COUNT(*) AS n FROM customers").fetchone()
    return int(row["n"])


def tariff_distribution(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        """
        SELECT current_tariff AS name, COUNT(*) AS n
        FROM customers GROUP BY current_tariff ORDER BY n DESC, name
        """
    ).fetchall()
    return [dict(r) for r in rows]


def usage_summary(
    conn: sqlite3.Connection,
    month_from: str | None = None,
    month_to: str | None = None,
    tariff: str | None = None,
) -> dict:
    """Usage-versus-allowance and spend metrics for the filtered window."""
    clauses, params = _usage_filters(month_from, month_to, tariff)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    rows = conn.execute(
        f"""
        SELECT u.*, c.plan_data_gb, c.plan_allnet_min, c.plan_onnet_min,
               c.plan_offnet_min
        FROM usage_records u
        JOIN customers c ON c.customer_id = u.customer_id
        {where}
        """,
        params,
    ).fetchall()

    if not rows:
        # language-neutral key; the analytics layer renders it in the active locale
        return {"available": False, "reason_key": "analytics.no_rows_reason"}

    total_rows = len(rows)
    data_exceed = 0
    minute_exceed = 0
    total_extra_gb = 0
    buyer_rows = 0
    spends = []
    for r in rows:
        plan_gb = r["plan_data_gb"]
        if plan_gb is not None:
            if (r["data_gb"] or 0) > plan_gb:
                data_exceed += 1
        capacity = (
            r["plan_allnet_min"]
            if (r["plan_allnet_min"] or 0) > 0
            else (r["plan_onnet_min"] or 0) + (r["plan_offnet_min"] or 0)
        )
        if capacity:
            if (r["total_minutes"] or 0) > capacity:
                minute_exceed += 1
        extra = r["extra_gb"] or 0
        total_extra_gb += extra
        if extra > 0:
            buyer_rows += 1
        if r["spend_azn"] is not None:
            spends.append(r["spend_azn"])

    months = sorted({r["month"] for r in rows})
    return {
        "available": True,
        "rows": total_rows,
        "customers": len({r["customer_id"] for r in rows}),
        "months": months,
        "data_exceed_rows": data_exceed,
        "minute_exceed_rows": minute_exceed,
        "data_exceed_pct": round(100 * data_exceed / total_rows, 1),
        "minute_exceed_pct": round(100 * minute_exceed / total_rows, 1),
        "extra_gb_total": total_extra_gb,
        "extra_buyer_rows": buyer_rows,
        "avg_spend": round(sum(spends) / len(spends), 2) if spends else None,
        "total_spend": round(sum(spends), 2) if spends else None,
    }


def over_allowance_customers(conn: sqlite3.Connection, tariff: str | None = None) -> dict:
    """Customers whose 6-month average data usage exceeds the plan allowance."""
    extra_where = " AND c.current_tariff = ?" if tariff else ""
    params = (tariff,) if tariff else ()
    rows = conn.execute(
        f"""
        SELECT c.customer_id, c.current_tariff, c.plan_data_gb, c.avg_data_gb,
               c.data_utilization
        FROM customers c
        WHERE c.plan_data_gb IS NOT NULL AND c.avg_data_gb > c.plan_data_gb
        {extra_where}
        ORDER BY c.customer_id
        """,
        params,
    ).fetchall()
    unknown = conn.execute(
        f"""
        SELECT COUNT(*) AS n FROM customers c
        WHERE c.data_utilization IS NULL {extra_where}
        """,
        params,
    ).fetchone()["n"]
    return {
        "customers": [dict(r) for r in rows],
        "count": len(rows),
        "unknown_utilization": int(unknown),
    }


def spend_breakdown(
    conn: sqlite3.Connection,
    month_from: str | None = None,
    month_to: str | None = None,
    tariff: str | None = None,
) -> dict | None:
    """Decompose observed spend using the catalog's own unit prices."""
    clauses, params = _usage_filters(month_from, month_to, tariff)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    row = conn.execute(
        f"""
        SELECT COALESCE(SUM(u.extra_gb), 0) AS extra_gb,
               COALESCE(SUM(u.out_of_bundle_min), 0) AS oob_min,
               COALESCE(SUM(u.roaming_days), 0) AS roaming_days,
               COALESCE(SUM(u.spend_azn), 0) AS spend,
               COUNT(*) AS rows
        FROM usage_records u {where}
        """,
        params,
    ).fetchone()
    if not row or not row["rows"]:
        return None
    prices = {
        r["price_key"]: r["value_azn"]
        for r in conn.execute("SELECT * FROM tariff_prices").fetchall()
    }
    extra_price = prices.get("extra_1gb_azn")
    oob_price = prices.get("out_of_bundle_1min_azn")
    roam_price = prices.get("roaming_day_azn")
    breakdown = {
        "rows": row["rows"],
        "total_spend": round(row["spend"], 2),
        "extra_gb": row["extra_gb"],
        "oob_min": row["oob_min"],
        "roaming_days": row["roaming_days"],
        "unit_prices_known": all(v is not None for v in (extra_price, oob_price, roam_price)),
    }
    if breakdown["unit_prices_known"]:
        breakdown["extra_cost"] = round(row["extra_gb"] * extra_price, 2)
        breakdown["oob_cost"] = round(row["oob_min"] * oob_price, 2)
        breakdown["roaming_cost"] = round(row["roaming_days"] * roam_price, 2)
        breakdown["addon_cost"] = round(
            breakdown["extra_cost"] + breakdown["oob_cost"] + breakdown["roaming_cost"], 2
        )
    return breakdown


def recommendation_distribution(conn: sqlite3.Connection) -> list[dict] | None:
    """Top-1 recommendation counts from the latest snapshot per customer."""
    rows = conn.execute(
        """
        WITH latest AS (
            SELECT customer_id, MAX(id) AS mid FROM recommendations GROUP BY customer_id
        )
        SELECT json_extract(r.ranked_json, '$[0].name') AS name, COUNT(*) AS n
        FROM recommendations r JOIN latest l ON r.id = l.mid
        GROUP BY name ORDER BY n DESC, name
        """
    ).fetchall()
    if not rows:
        return None
    return [dict(r) for r in rows]


def unsupported_metrics(conn: sqlite3.Connection) -> list[dict]:
    """Metrics the loaded dataset cannot support — shown as unavailable, not 0.

    Returns i18n keys + params; the caller renders them in the active locale.
    """
    no_end_date = conn.execute(
        "SELECT COUNT(*) AS n FROM customers WHERE tariff_end_date IS NULL"
    ).fetchone()["n"]
    return [
        {
            "name_key": "unsup.push_name",
            "status_key": "common.unavailable",
            "reason_key": "unsup.push_reason",
            "params": {},
        },
        {
            "name_key": "unsup.apps_name",
            "status_key": "common.unavailable",
            "reason_key": "unsup.apps_reason",
            "params": {},
        },
        {
            "name_key": "unsup.end_name",
            "status_key": "common.partial_unavailable",
            "reason_key": "unsup.end_reason",
            "params": {"n": no_end_date},
        },
        {
            "name_key": "unsup.churn_name",
            "status_key": "common.unavailable",
            "reason_key": "unsup.churn_reason",
            "params": {},
        },
    ]


def usage_by_month(conn: sqlite3.Connection, customer_id: str | None = None) -> list[dict]:
    where = "WHERE customer_id = ?" if customer_id else ""
    params = (customer_id,) if customer_id else ()
    rows = conn.execute(
        f"SELECT month, COUNT(*) AS n, AVG(spend_azn) AS avg_spend, "
        f"SUM(extra_gb) AS extra_gb FROM usage_records {where} "
        f"GROUP BY month ORDER BY month",
        params,
    ).fetchall()
    return [dict(r) for r in rows]
