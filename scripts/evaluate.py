"""Evaluate the rule-based recommendations and write results/ reports.

Usage: python scripts/evaluate.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config import Config
from repositories.db import setup
from services.evaluation import evaluate_all, write_reports


def main() -> int:
    conn = setup()
    try:
        result = evaluate_all(conn)
    finally:
        conn.close()

    paths = write_reports(result)
    rows = result.pop("rows")
    out = Path(Config.RESULTS_DIR)
    (out / "evaluation_summary.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    cov = result["coverage"]
    spend = result["estimated_spend_vs_current"]
    print(f"Evaluated {result['customers_evaluated']}/{result['customers_total']} customers")
    print(f"Top pick covers data demand: {cov['data_covered']}/{cov['data_known']} | "
          f"calls: {cov['calls_covered']}/{cov['calls_known']} | shortfall: {cov['with_shortfall']}")
    print(f"Est. cheaper: {spend['cheaper']} | dearer: {spend['dearer']} | same: {spend['same']} "
          f"| unknown: {spend['unknown']} | keep-current picks: {result['keep_current']}")
    print(f"Written: {paths['markdown']} and {paths['csv']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
