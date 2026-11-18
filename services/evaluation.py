"""Recommendation evaluation (documentation.md §6, §10).

Reports, for every usable customer:
* demand coverage of the ranked plans,
* estimated spend difference vs the current plan (labelled as an estimate),
* estimated extra-data purchase effect (catalog pack price × estimated packs),
* comparison against the current tariff.

Nothing here claims guaranteed savings: every number carries an
``estimate`` label and the assumptions are printed with the report.
"""

from __future__ import annotations

import csv
import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from config import Config, DEFAULT_WEIGHTS
from repositories import catalog_repo, customer_repo
from services import recommendation as reco
from services import explanation as expl


@dataclass
class EvalRow:
    customer_id: str
    current_tariff: str | None
    current_price: float | None
    best_tariff: str | None
    best_price: float | None
    best_est_cost: float | None
    current_est_cost: float | None
    est_cost_diff: float | None
    observed_extra_cost: float | None
    est_extra_cost_best: float | None
    extra_cost_delta: float | None
    covered_data: bool | None
    covered_calls: bool | None
    keep_current: bool
    shortfall: str | None


def _plans(conn) -> list[reco.Plan]:
    return [reco.Plan.from_mapping(dict(r)) for r in catalog_repo.all_tariffs(conn)]


def evaluate_customer(
    conn: sqlite3.Connection, customer_id: str, *, weights=DEFAULT_WEIGHTS
) -> EvalRow | None:
    profile = customer_repo.get_customer(conn, customer_id)
    if profile is None:
        return None
    history = customer_repo.usage_for(conn, customer_id)
    prices = catalog_repo.prices(conn)
    unit_extra = prices.get("extra_1gb_azn")
    unit_min = prices.get("out_of_bundle_1min_azn")

    demand = reco.summarize_history(
        history,
        window_months=Config.HISTORY_WINDOW_MONTHS,
        buffer_ratio=Config.DEMAND_BUFFER_RATIO,
        extra_unit_price=unit_extra,
    )
    if demand is None:
        return None

    result = reco.recommend(
        _plans(conn),
        demand,
        current_tariff=profile["current_tariff"],
        weights=weights,
        unit_extra_gb=unit_extra,
        unit_minute=unit_min,
        pack_size_gb=Config.EXTRA_PACK_SIZE_GB,
    )
    ranked = result["ranked"]
    if not ranked:
        return None
    best = ranked[0]
    current = next((p for p in ranked if p.get("is_current")), None)

    cur_cost = current.get("est_total_cost") if current else None
    best_cost = best.get("est_total_cost")
    diff = round(best_cost - cur_cost, 2) if (best_cost is not None and cur_cost is not None) else None

    observed_extra_cost = round(demand.extra_gb_mean * unit_extra, 2) if unit_extra else None
    best_extra = (best.get("cost_parts") or {}).get("extra_data_cost")
    extra_delta = (
        round(best_extra - observed_extra_cost, 2)
        if (best_extra is not None and observed_extra_cost is not None)
        else None
    )

    return EvalRow(
        customer_id=customer_id,
        current_tariff=profile["current_tariff"],
        current_price=profile["price_azn"],
        best_tariff=best["name"],
        best_price=best.get("price_azn"),
        best_est_cost=best_cost,
        current_est_cost=cur_cost,
        est_cost_diff=diff,
        observed_extra_cost=observed_extra_cost,
        est_extra_cost_best=best_extra,
        extra_cost_delta=extra_delta,
        covered_data=best.get("adequacy_data"),
        covered_calls=best.get("adequacy_calls"),
        keep_current=bool(best.get("is_current")),
        shortfall=best.get("shortfall"),
    )


def evaluate_all(conn: sqlite3.Connection, *, weights=DEFAULT_WEIGHTS) -> dict:
    customers = customer_repo.all_customers(conn)
    rows = [r for cid in (c["customer_id"] for c in customers)
            if (r := evaluate_customer(conn, cid, weights=weights)) is not None]

    n = len(rows)
    covered_data = sum(1 for r in rows if r.covered_data is not None and r.covered_data >= 1.0)
    known_data = sum(1 for r in rows if r.covered_data is not None)
    covered_calls = sum(1 for r in rows if r.covered_calls is not None and r.covered_calls >= 1.0)
    known_calls = sum(1 for r in rows if r.covered_calls is not None)
    cheaper = sum(1 for r in rows if r.est_cost_diff is not None and r.est_cost_diff < 0)
    dearer = sum(1 for r in rows if r.est_cost_diff is not None and r.est_cost_diff > 0)
    same = sum(1 for r in rows if r.est_cost_diff is not None and r.est_cost_diff == 0)
    keep = sum(1 for r in rows if r.keep_current)
    shortfall = sum(1 for r in rows if r.shortfall)
    extra_better = sum(1 for r in rows if r.extra_cost_delta is not None and r.extra_cost_delta < 0)
    extra_known = sum(1 for r in rows if r.extra_cost_delta is not None)

    return {
        "customers_evaluated": n,
        "customers_total": len(customers),
        "coverage": {
            "data_covered": covered_data,
            "data_known": known_data,
            "calls_covered": covered_calls,
            "calls_known": known_calls,
            "with_shortfall": shortfall,
        },
        "estimated_spend_vs_current": {
            "cheaper": cheaper,
            "dearer": dearer,
            "same": same,
            "unknown": n - cheaper - dearer - same,
            "note": "Estimates include catalog price + likely extra-data packs + out-of-bundle minutes; roaming excluded (plan-independent). Not a guaranteed saving.",
        },
        "extra_data_effect": {
            "customers_with_measurable_delta": extra_known,
            "estimated_lower_extra_cost": extra_better,
            "note": "Compares observed average extra-data spend with estimated packs under the recommended plan at the catalog price of "
                    f"{catalog_repo.prices(conn).get('extra_1gb_azn', 'unknown')} AZN/GB.",
        },
        "keep_current": keep,
        "assumptions": [
            f"history window = last {Config.HISTORY_WINDOW_MONTHS} complete months",
            f"demand buffer = mean + {Config.DEMAND_BUFFER_RATIO} × std",
            f"extra-data purchases modelled as {Config.EXTRA_PACK_SIZE_GB:g} GB packs at catalog unit price",
            f"scoring weights = {DEFAULT_WEIGHTS.as_dict()}",
            "current plan is always part of the comparison when its catalog data exists",
        ],
        "rows": rows,
    }


def write_reports(result: dict, results_dir: str | Path | None = None) -> dict[str, Path]:
    """Write ``evaluation_report.md`` and ``recommendations.csv`` to results/."""
    out = Path(results_dir or Config.RESULTS_DIR)
    out.mkdir(parents=True, exist_ok=True)

    csv_path = out / "recommendations.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow([
            "Customer ID", "Current Package", "Recommended Package", "Current Price",
            "Recommended Price", "Est. monthly cost (recommended)", "Est. cost diff vs current",
            "Reason",
        ])
        for r in result["rows"]:
            w.writerow([
                r.customer_id, r.current_tariff, r.best_tariff, r.current_price,
                r.best_price, r.best_est_cost, r.est_cost_diff,
                ("keeps current plan" if r.keep_current else "")
                + ("; covers estimated data" if r.covered_data == 1.0 else "")
                + ("; data shortfall risk" if r.covered_data is not None and r.covered_data < 1 else ""),
            ])

    md_path = out / "evaluation_report.md"
    c = result["coverage"]
    s = result["estimated_spend_vs_current"]
    lines = [
        "# Recommendation evaluation",
        "",
        f"- Customers evaluated: **{result['customers_evaluated']}** / {result['customers_total']}",
        f"- Top-ranked plan covers estimated data demand: {c['data_covered']} / {c['data_known']} (known allowances)",
        f"- Top-ranked plan covers estimated call demand: {c['calls_covered']} / {c['calls_known']} (known allowances)",
        f"- Customers with a shortfall warning on the top pick: {c['with_shortfall']}",
        f"- Estimated cheaper than current plan: {s['cheaper']}; dearer: {s['dearer']}; same: {s['same']}; unknown: {s['unknown']}",
        f"- Top pick IS the current plan (keep recommendation): {result['keep_current']}",
        f"- Estimated lower extra-data cost under top pick: {result['extra_data_effect']['estimated_lower_extra_cost']} "
        f"of {result['extra_data_effect']['customers_with_measurable_delta']} measurable",
        "",
        "## Assumptions (all estimates, no guaranteed savings)",
    ]
    lines += [f"- {a}" for a in result["assumptions"]]
    lines += [
        "",
        "## Per-customer rows",
        "",
        "| Customer | Current | Recommended | Cur. price | Rec. price | Est. cost | Δ vs current |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in result["rows"]:
        lines.append(
            f"| {r.customer_id} | {r.current_tariff} | {r.best_tariff} | {r.current_price} | "
            f"{r.best_price} | {r.best_est_cost} | {r.est_cost_diff} |"
        )
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"csv": csv_path, "markdown": md_path}
