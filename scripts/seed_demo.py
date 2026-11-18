"""Seed demo-only data that the workbook does not contain.

The source has NO tariff end/renewal date column, so imported customers keep
``tariff_end_date = NULL`` (the reminder job records ``missing_end_date``).

To make the five-day reminder flow demonstrable, this script assigns clearly
labelled *demo-mock* end dates to a few customers (provenance ``demo_mock``),
and opts one customer out of notifications. Nothing else is altered.

Usage: python scripts/seed_demo.py
"""

from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config import Config
from repositories import customer_repo
from repositories.db import setup


def main() -> int:
    conn = setup()
    try:
        today = date.today()
        seeded, opted_out = 0, 0
        for cid, offset in Config.DEMO_TARIFF_END_OFFSETS_DAYS.items():
            if customer_repo.get_customer(conn, cid) is None:
                print(f"  {cid}: not imported yet — run scripts/import_data.py first")
                continue
            end = (today + timedelta(days=offset)).isoformat()
            customer_repo.set_tariff_end(conn, cid, end, "demo_mock")
            seeded += 1
            print(f"  {cid}: demo-mock tariff end = {end} (+{offset} days)")
        for cid in Config.DEMO_OPTED_OUT_CUSTOMERS:
            if customer_repo.get_customer(conn, cid) is None:
                continue
            customer_repo.set_opt_in(conn, cid, False)
            opted_out += 1
            print(f"  {cid}: notification opt-out set (demo)")
        print(f"Seeded {seeded} demo-mock end date(s), {opted_out} opt-out(s).")
        print("All other customers keep tariff_end_date = NULL (as in the source).")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
