"""Import the workbook into SQLite and print/write the import report.

Usage: python scripts/import_data.py [--workbook PATH]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config import Config
from repositories.db import setup
from services.import_service import import_workbook, render_report_markdown


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--workbook", default=None)
    args = ap.parse_args()

    conn = setup()
    try:
        report = import_workbook(conn, args.workbook)
    finally:
        conn.close()

    out = Path(Config.RESULTS_DIR)
    out.mkdir(parents=True, exist_ok=True)
    (out / "import_report.md").write_text(render_report_markdown(report), encoding="utf-8")
    (out / "import_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    c = report["counts"]
    print(f"Imported: {c['customers_imported']} customers, {c['tariffs_imported']} tariffs, "
          f"{c['usage_rows_imported']} usage rows.")
    print(f"Rejected rows: {c['rejected_rows']} | warnings: {c['warnings']}")
    print(f"Validation checks passed: {report['checks']['passed']}")
    print(f"Report written to {out / 'import_report.md'}")
    return 0 if report["checks"]["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
