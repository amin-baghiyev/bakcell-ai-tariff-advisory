"""Business + customer analytics assembly (thin layer over repositories).

Unsupported metrics are returned with ``available=False`` and a reason so the
UI can render an explicit empty/unavailable state instead of a zero.
Texts are localized at assembly time (``lang`` = ``az`` | ``en``); the
recommendation explanation is re-rendered from stored facts in the active
language whenever it is displayed.
"""

from __future__ import annotations

import json
import sqlite3

from config import Config
from i18n import describe_reasons, translate
from repositories import analytics_repo, customer_repo, recommendation_repo
from services import explanation as expl
from services import recommendation as reco


def customer_profile(conn: sqlite3.Connection, customer_id: str) -> dict | None:
    row = customer_repo.get_customer(conn, customer_id)
    if row is None:
        return None
    return dict(row)


def customer_history(conn: sqlite3.Connection, customer_id: str) -> list[dict]:
    return [dict(r) for r in customer_repo.usage_for(conn, customer_id)]


def latest_recommendation(conn: sqlite3.Connection, customer_id: str) -> dict | None:
    row = recommendation_repo.latest_for(conn, customer_id)
    if row is None:
        return None
    d = dict(row)
    d["ranked"] = json.loads(d.pop("ranked_json"))
    d["explanation"] = json.loads(d.pop("explanation_json"))
    d["weights"] = json.loads(d.pop("weights_json"))
    return d


def unread_notification_count(conn: sqlite3.Connection, customer_id: str) -> int:
    return int(
        conn.execute(
            "SELECT COUNT(*) AS n FROM notifications WHERE customer_id = ? AND status != 'read'",
            (customer_id,),
        ).fetchone()["n"]
    )


def customer_dashboard(conn: sqlite3.Connection, customer_id: str,
                       lang: str | None = None) -> dict | None:
    profile = customer_profile(conn, customer_id)
    if profile is None:
        return None
    history = customer_history(conn, customer_id)
    rec = latest_recommendation(conn, customer_id)
    if rec is not None and lang:
        rec["explanation"] = _render_explanation(conn, profile, history, rec, lang)

    months = [h["month"] for h in history]
    avg = lambda key: (  # noqa: E731 - tiny local helper
        round(sum(h[key] or 0 for h in history) / len(history), 2) if history else None
    )
    totals = {
        "data_gb": avg("data_gb"),
        "total_minutes": avg("total_minutes"),
        "sms": avg("sms"),
        "spend_azn": avg("spend_azn"),
        "extra_gb_total": sum(h["extra_gb"] or 0 for h in history),
        "topups_total": sum(h["topup_count"] or 0 for h in history),
        "roaming_days_total": sum(h["roaming_days"] or 0 for h in history),
        "callcenter_total": sum(h["callcenter_contacts"] or 0 for h in history),
        "months": months,
    }
    return {
        "profile": profile,
        "history": history,
        "averages": totals,
        "recommendation": rec,
        "unread_notifications": unread_notification_count(conn, customer_id),
        "unit_prices": _unit_prices(conn),
    }


def _unit_prices(conn: sqlite3.Connection) -> dict:
    return {
        r["price_key"]: r["value_azn"]
        for r in conn.execute("SELECT * FROM tariff_prices").fetchall()
    }


def _render_explanation(conn, profile, history, rec, lang: str) -> dict:
    """Re-render the stored snapshot's explanation in the active language.

    Only display-time text changes: the ranked plans, scores and facts stay
    exactly as persisted. Falls back to the stored (archival) explanation if
    the demand window cannot be recomputed.
    """
    try:
        prices = _unit_prices(conn)
        demand = reco.summarize_history(
            history,
            window_months=Config.HISTORY_WINDOW_MONTHS,
            buffer_ratio=Config.DEMAND_BUFFER_RATIO,
            extra_unit_price=prices.get("extra_1gb_azn"),
        )
        if demand is None:
            return rec["explanation"]
        flags = {
            "window": [rec.get("window_start"), rec.get("window_end")],
            "weights": rec.get("weights") or {},
            "model_version": rec.get("model_version", ""),
            "current_is_best": bool(rec["ranked"]) and bool(rec["ranked"][0].get("is_current")),
            "current_included": any(p.get("is_current") for p in rec["ranked"]),
            "shortfall_any": any(p.get("shortfall") for p in rec["ranked"]),
        }
        return expl.explain_ranked(
            {"ranked": rec["ranked"], "flags": flags},
            demand, profile["current_tariff"], lang=lang,
        )
    except Exception:  # noqa: BLE001 — display must never 500
        return rec["explanation"]


# --------------------------------------------------------------------------- #
# Admin
# --------------------------------------------------------------------------- #

def admin_dashboard(
    conn: sqlite3.Connection,
    *,
    month_from: str | None = None,
    month_to: str | None = None,
    tariff: str | None = None,
    lang: str = "en",
) -> dict:
    usage = analytics_repo.usage_summary(conn, month_from, month_to, tariff)
    if not usage.get("available", False) and usage.get("reason_key"):
        usage["reason"] = translate(lang, usage["reason_key"])
    over = analytics_repo.over_allowance_customers(conn, tariff)
    breakdown = analytics_repo.spend_breakdown(conn, month_from, month_to, tariff)
    rec_dist = analytics_repo.recommendation_distribution(conn)

    # usage vs allowance: average utilization across customers with known allowance
    util_rows = conn.execute(
        """
        SELECT AVG(data_utilization) AS d, AVG(minute_utilization) AS m,
               SUM(CASE WHEN data_utilization IS NULL THEN 1 ELSE 0 END) AS unknown_d
        FROM customers WHERE (? IS NULL OR current_tariff = ?)
        """,
        (tariff, tariff),
    ).fetchone()

    months_available = [
        r["month"]
        for r in conn.execute("SELECT DISTINCT month FROM usage_records ORDER BY month")
    ]

    return {
        "filters": {
            "month_from": month_from,
            "month_to": month_to,
            "tariff": tariff,
            "months_available": months_available,
        },
        "total_customers": analytics_repo.customer_count(conn, tariff),
        "tariff_distribution": analytics_repo.tariff_distribution(conn),
        "usage": usage,
        "over_allowance": over,
        "spend_breakdown": breakdown,
        "avg_utilization": {
            "available": usage.get("available", False),
            "data_pct": round(util_rows["d"] * 100, 1) if util_rows["d"] is not None else None,
            "minutes_pct": round(util_rows["m"] * 100, 1) if util_rows["m"] is not None else None,
            "unknown_data_rows": int(util_rows["unknown_d"] or 0),
        },
        "recommendation_distribution": rec_dist,
        "unsupported": [
            {
                "name": translate(lang, u["name_key"]),
                "status": translate(lang, u["status_key"]),
                "reason": translate(lang, u["reason_key"], **u.get("params", {})),
            }
            for u in analytics_repo.unsupported_metrics(conn)
        ],
        "catalog": _catalog(conn),
        "demo_mode": True,
    }


def _catalog(conn: sqlite3.Connection) -> list[dict]:
    return [
        dict(r)
        for r in conn.execute(
            "SELECT * FROM tariffs ORDER BY price_azn, name"
        ).fetchall()
    ]


def customer_table(
    conn: sqlite3.Connection,
    *,
    tariff: str | None = None,
    search: str | None = None,
    page: int = 1,
    per_page: int = 20,
    lang: str = "en",
) -> dict:
    """Paginated customer + latest-recommendation table (no phone numbers)."""
    clauses, params = [], []
    if tariff:
        clauses.append("c.current_tariff = ?")
        params.append(tariff)
    if search:
        clauses.append("c.customer_id LIKE ?")
        params.append(f"%{search}%")
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""

    total = conn.execute(
        f"SELECT COUNT(*) AS n FROM customers c {where}", params
    ).fetchone()["n"]
    page = max(1, int(page))
    offset = (page - 1) * per_page

    rows = conn.execute(
        f"""
        SELECT c.customer_id, c.current_tariff, c.price_azn,
               r.ranked_json, r.generated_at
        FROM customers c
        LEFT JOIN recommendations r
          ON r.id = (SELECT MAX(id) FROM recommendations WHERE customer_id = c.customer_id)
        {where}
        ORDER BY c.customer_id
        LIMIT ? OFFSET ?
        """,
        [*params, per_page, offset],
    ).fetchall()

    items = []
    for r in rows:
        ranked = json.loads(r["ranked_json"]) if r["ranked_json"] else []
        best = ranked[0] if ranked else None
        items.append(
            {
                "customer_id": r["customer_id"],
                "current_tariff": r["current_tariff"],
                "current_price": r["price_azn"],
                "recommended_tariff": best["name"] if best else None,
                "recommended_price": best.get("price_azn") if best else None,
                "reason": _reason_text(best, lang) if best else None,
                "generated_at": r["generated_at"],
                "ranked": ranked,
            }
        )

    return {
        "rows": items,
        "total": total,
        "page": page,
        "per_page": per_page,
        "pages": max(1, -(-total // per_page)),
    }


def _reason_text(plan: dict | None, lang: str = "en") -> str | None:
    """Plain-language reason sentence for the admin table (never keywords)."""
    if not plan:
        return None
    return describe_reasons(plan.get("reason_codes"), lang)
