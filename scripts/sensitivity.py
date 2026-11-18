"""Sensitivity analysis over scoring weights (documentation.md §6).

Runs the full ranking under several weight configurations and reports how
often the top-1 choice changes vs the default weights.

Usage: python scripts/sensitivity.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config import Config, Weights
from repositories import catalog_repo, customer_repo
from repositories.db import setup
from services import recommendation as reco

VARIANTS = {
    "default (0.40/0.30/0.15/0.15)": Weights(),
    "adequacy-heavy (0.60/0.20/0.10/0.10)": Weights(0.60, 0.20, 0.10, 0.10),
    "cost-heavy (0.25/0.50/0.15/0.10)": Weights(0.25, 0.50, 0.15, 0.10),
    "oversupply-heavy (0.35/0.25/0.30/0.10)": Weights(0.35, 0.25, 0.30, 0.10),
    "affordability-heavy (0.30/0.25/0.15/0.30)": Weights(0.30, 0.25, 0.15, 0.30),
}


def main() -> int:
    conn = setup()
    try:
        plans = [reco.Plan.from_mapping(dict(r)) for r in catalog_repo.all_tariffs(conn)]
        prices = catalog_repo.prices(conn)
        customers = customer_repo.all_customers(conn)

        top1: dict[str, dict[str, int]] = {name: {} for name in VARIANTS}
        agreement = {name: 0 for name in VARIANTS}
        evaluated = 0

        for row in customers:
            history = customer_repo.usage_for(conn, row["customer_id"])
            demand = reco.summarize_history(
                history, Config.HISTORY_WINDOW_MONTHS, Config.DEMAND_BUFFER_RATIO,
                prices.get("extra_1gb_azn"),
            )
            if demand is None:
                continue
            evaluated += 1
            baseline_top = None
            for name, w in VARIANTS.items():
                res = reco.recommend(
                    plans, demand, current_tariff=row["current_tariff"], weights=w,
                    unit_extra_gb=prices.get("extra_1gb_azn"),
                    unit_minute=prices.get("out_of_bundle_1min_azn"),
                    pack_size_gb=Config.EXTRA_PACK_SIZE_GB,
                )
                if not res["ranked"]:
                    continue
                top = res["ranked"][0]["name"]
                top1[name][top] = top1[name].get(top, 0) + 1
                if name == "default (0.40/0.30/0.15/0.15)":
                    baseline_top = top
                elif baseline_top is not None and top == baseline_top:
                    agreement[name] += 1
    finally:
        conn.close()

    lines = ["# Weight sensitivity analysis", "",
             f"Customers evaluated: {evaluated}", "",
             "| Variant | Top-1 counts | Agreement with default |",
             "|---|---|---|"]
    for name in VARIANTS:
        counts = ", ".join(f"{k}: {v}" for k, v in sorted(top1[name].items(), key=lambda kv: -kv[1]))
        agree = "—" if name.startswith("default") else f"{agreement[name]}/{evaluated} ({100 * agreement[name] / evaluated:.0f}%)"
        lines.append(f"| {name} | {counts} | {agree} |")
    lines += ["", "Trade-offs are intentionally visible: heavier cost weights shift top-1 "
                  "toward cheaper plans; heavier adequacy weights shift toward larger allowances."]
    text = "\n".join(lines) + "\n"

    out = Path(Config.RESULTS_DIR)
    out.mkdir(parents=True, exist_ok=True)
    (out / "sensitivity_report.md").write_text(text, encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
