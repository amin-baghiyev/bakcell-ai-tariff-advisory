"""End-to-end pipeline: import workbook → build recommendations for everyone.

Framework-independent so it can be driven from a CLI or the Flask app factory.
"""

from __future__ import annotations

import sqlite3

from config import Config, DEFAULT_WEIGHTS, Weights
from repositories import catalog_repo, customer_repo, recommendation_repo
from services import explanation as expl
from services import recommendation as reco
from services.import_service import import_workbook


def build_for_customer(
    conn: sqlite3.Connection, customer_id: str, *, weights: Weights = DEFAULT_WEIGHTS
) -> dict | None:
    """Build + persist a recommendation snapshot for one customer."""
    plans = [reco.Plan.from_mapping(dict(r)) for r in catalog_repo.all_tariffs(conn)]
    prices = catalog_repo.prices(conn)
    row = customer_repo.get_customer(conn, customer_id)
    if row is None:
        return None
    history = customer_repo.usage_for(conn, customer_id)
    demand = reco.summarize_history(
        history,
        window_months=Config.HISTORY_WINDOW_MONTHS,
        buffer_ratio=Config.DEMAND_BUFFER_RATIO,
        extra_unit_price=prices.get("extra_1gb_azn"),
    )
    if demand is None:
        return None
    result = reco.recommend(
        plans,
        demand,
        current_tariff=row["current_tariff"],
        weights=weights,
        unit_extra_gb=prices.get("extra_1gb_azn"),
        unit_minute=prices.get("out_of_bundle_1min_azn"),
        pack_size_gb=Config.EXTRA_PACK_SIZE_GB,
    )
    if not result["ranked"]:
        return None
    explanation = expl.explain_ranked(result, demand, row["current_tariff"])
    window_start, window_end = demand.window
    rec_id = recommendation_repo.save(
        conn, customer_id, result["ranked"], explanation,
        window_start, window_end, reco.MODEL_VERSION, weights.as_dict(),
    )
    return {"recommendation_id": rec_id, "top": result["ranked"][0]["name"]}


def build_recommendations(
    conn: sqlite3.Connection, *, weights: Weights = DEFAULT_WEIGHTS
) -> dict:
    """Generate + persist a recommendation snapshot for every usable customer."""
    created, failed, skipped = [], [], []
    for row in customer_repo.all_customers(conn):
        cid = row["customer_id"]
        try:
            out = build_for_customer(conn, cid, weights=weights)
        except Exception as exc:  # pragma: no cover - defensive
            failed.append({"customer_id": cid, "error": str(exc)})
            continue
        if out is None:
            skipped.append({"customer_id": cid, "reason": "no usage history or no ranked plans"})
            continue
        created.append({"customer_id": cid, **out})

    return {
        "created": len(created),
        "failed": len(failed),
        "skipped": skipped,
        "rows": created,
        "failed_rows": failed,
        "model_version": reco.MODEL_VERSION,
        "weights": weights.as_dict(),
    }


def run_pipeline(
    conn: sqlite3.Connection, *, weights: Weights = DEFAULT_WEIGHTS, import_first: bool = True
) -> dict:
    report: dict = {}
    if import_first:
        report["import"] = import_workbook(conn)
    report["recommendations"] = build_recommendations(conn, weights=weights)
    return report
