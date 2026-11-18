"""Run the five-day tariff-end reminder job (idempotent — safe to repeat).

Usage: python scripts/run_reminders.py [--today YYYY-MM-DD]
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config import Config
from repositories.db import setup
from services.notification_service import run_reminders


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--today", default=None, help="override today's date (demo/testing)")
    args = ap.parse_args()

    today = date.fromisoformat(args.today) if args.today else None
    conn = setup()
    try:
        report = run_reminders(conn, today=today)
    finally:
        conn.close()

    out = Path(Config.RESULTS_DIR)
    out.mkdir(parents=True, exist_ok=True)
    (out / "reminder_run.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    t = report["totals"]
    print(f"[{report['today']}] created={t['created']} already_existed={t['already_existed']} "
          f"skipped={t['skipped']} outside_window={t['outside_window']}")
    by_reason: dict[str, int] = {}
    for s in report["skipped"]:
        by_reason[s["reason"]] = by_reason.get(s["reason"], 0) + 1
    for reason, n in sorted(by_reason.items()):
        print(f"  skipped: {reason} × {n}")
    for s in report["skipped"][:5]:
        if s["reason"] not in ("missing_end_date",):
            print(f"  e.g. {s['customer_id']}: {s['reason']}")
    print(f"Delivery: {report['delivery_claim']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
