"""Generate rule-based recommendation snapshots for every usable customer.

Usage: python scripts/generate_recommendations.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from repositories.db import setup
from services.pipeline import build_recommendations


def main() -> int:
    conn = setup()
    try:
        result = build_recommendations(conn)
    finally:
        conn.close()
    print(f"Recommendations created: {result['created']} | failed: {result['failed']} | "
          f"skipped: {len(result['skipped'])} | model: {result['model_version']}")
    for s in result["skipped"]:
        print(f"  skipped {s['customer_id']}: {s['reason']}")
    return 0 if result["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
