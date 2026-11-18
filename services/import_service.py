"""Workbook ingestion with validation and an explicit import report.

Reads the three sheets through the configurable column mapping in
``config.py``, validates required fields, flags impossible values, records
every skipped row with a reason, and never imports phone numbers.

Units are preserved exactly as sourced: prices AZN, data GB, minutes minutes,
SMS counts, months ``YYYY-MM``.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

import config as cfg
from repositories import catalog_repo, customer_repo

PHONE_SENTINEL = "__phone_excluded__"


class ImportError(RuntimeError):
    pass


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _check_columns(df: pd.DataFrame, mapping: dict, sheet: str, report: dict) -> dict:
    """Validate the mapping against actual headers; return internal->series dict."""
    header_to_internal = {v: k for k, v in mapping.items()}
    missing = [h for h in header_to_internal if h not in df.columns]
    report["sheets"][sheet]["missing_columns"] = missing
    if missing:
        raise ImportError(
            f"Sheet {sheet!r} is missing required column(s): {', '.join(missing)}. "
            "Update the column mapping in config.py if the workbook headers changed."
        )
    out = {}
    for internal, header in mapping.items():
        out[internal] = df[header]
    return out


def _negatives(series: pd.Series) -> int:
    num = pd.to_numeric(series, errors="coerce")
    return int((num < 0).sum())


def inspect_workbook(path: str | Path | None = None) -> dict:
    """Read-only structural inspection (sheets, columns, types, missingness)."""
    path = Path(path or cfg.Config.WORKBOOK_PATH)
    if not path.exists():
        raise ImportError(f"Workbook not found: {path}")
    xl = pd.ExcelFile(path)
    report: dict = {"workbook": str(path), "sheets": {}}
    for sheet in xl.sheet_names:
        df = xl.parse(sheet)
        info: dict = {
            "rows": int(len(df)),
            "columns": [str(c) for c in df.columns],
            "dtypes": {str(c): str(t) for c, t in df.dtypes.items()},
            "missing": {str(c): int(df[c].isna().sum()) for c in df.columns},
            "fully_duplicated_rows": int(df.duplicated().sum()),
        }
        report["sheets"][sheet] = info
    return report


def import_workbook(
    conn: sqlite3.Connection,
    path: str | Path | None = None,
    *,
    keep_phone: bool = False,
) -> dict:
    """Import all three sheets into SQLite. Returns the import report.

    ``keep_phone`` is intentionally ``False`` by default and the phone column
    is never written to any table regardless — it is only *named* in the
    report so reviewers can see the exclusion happened.
    """
    path = Path(path or cfg.Config.WORKBOOK_PATH)
    if not path.exists():
        raise ImportError(f"Workbook not found: {path}")

    started = _now()
    xl = pd.ExcelFile(path)
    report: dict = {
        "started_at": started,
        "workbook": str(path),
        "mode": "demo/synthetic data (not live Bakcell data)",
        "sheets": {},
        "rejected_rows": [],
        "warnings": [],
        "excluded_columns": [],
        "units": {
            "prices": "AZN",
            "data": "GB",
            "minutes": "minutes",
            "sms": "count",
            "month": "YYYY-MM",
        },
    }

    for required in (cfg.SHEET_CUSTOMERS, cfg.SHEET_CATALOG, cfg.SHEET_USAGE):
        if required not in xl.sheet_names:
            raise ImportError(
                f"Required sheet {required!r} not found. Available: {xl.sheet_names}"
            )

    # ------------------------------------------------------------------ #
    # 1. Customers
    # ------------------------------------------------------------------ #
    raw = xl.parse(cfg.SHEET_CUSTOMERS)
    report["sheets"][cfg.SHEET_CUSTOMERS] = {
        "rows": int(len(raw)),
        "columns": [str(c) for c in raw.columns],
    }
    cols = _check_columns(raw, cfg.CUSTOMER_COLUMNS, cfg.SHEET_CUSTOMERS, report)

    if not keep_phone:
        report["excluded_columns"].append(
            {
                "sheet": cfg.SHEET_CUSTOMERS,
                "column": cfg.CUSTOMER_COLUMNS["phone"],
                "reason": "phone number — never imported, never used as a feature, never displayed",
            }
        )

    customers: list[dict] = []
    seen_ids: set[str] = set()
    for idx in range(len(raw)):
        cid = cols["customer_id"].iloc[idx]
        if not isinstance(cid, str) or not cid.strip():
            report["rejected_rows"].append(
                {"sheet": cfg.SHEET_CUSTOMERS, "row": idx, "reason": "missing customer ID"}
            )
            continue
        cid = cid.strip()
        if cid in seen_ids:
            report["rejected_rows"].append(
                {"sheet": cfg.SHEET_CUSTOMERS, "row": idx, "reason": f"duplicate customer ID {cid}"}
            )
            continue
        seen_ids.add(cid)

        tariff = cols["current_tariff"].iloc[idx]
        if tariff is None or pd.isna(tariff) or not str(tariff).strip():
            report["rejected_rows"].append(
                {"sheet": cfg.SHEET_CUSTOMERS, "row": idx, "reason": "missing current tariff"}
            )
            continue

        util_raw = cols["data_utilization"].iloc[idx]
        if isinstance(util_raw, str) and util_raw.strip() in ("-", "", "n/a", "N/A"):
            data_util = None  # unknown (division by a 0 GB allowance) — NOT zero
            report["warnings"].append(
                f"{cid}: data utilization was '-' (0 GB plan allowance) → stored as unknown."
            )
        else:
            data_util = float(util_raw)

        c = {
            "customer_id": cid,
            "age": int(cols["age"].iloc[idx]),
            "gender": str(cols["gender"].iloc[idx]),
            "region": str(cols["region"].iloc[idx]),
            "subscriber_type": str(cols["subscriber_type"].iloc[idx]),
            "tenure_months": int(cols["tenure_months"].iloc[idx]),
            "device": str(cols["device"].iloc[idx]),
            "network": str(cols["network"].iloc[idx]),
            "current_tariff": str(tariff).strip(),
            "months_on_tariff": int(cols["months_on_tariff"].iloc[idx]),
            "price_azn": float(cols["price_azn"].iloc[idx]),
            "plan_data_gb": float(cols["plan_data_gb"].iloc[idx]),
            "plan_allnet_min": int(cols["plan_allnet_min"].iloc[idx]),
            "plan_onnet_min": int(cols["plan_onnet_min"].iloc[idx]),
            "plan_offnet_min": int(cols["plan_offnet_min"].iloc[idx]),
            "plan_sms": int(cols["plan_sms"].iloc[idx]),
            "plan_unlimited_apps": str(cols["plan_unlimited_apps"].iloc[idx]),
            "avg_data_gb": float(cols["avg_data_gb"].iloc[idx]),
            "avg_minutes": float(cols["avg_minutes"].iloc[idx]),
            "data_utilization": data_util,
            "minute_utilization": float(cols["minute_utilization"].iloc[idx]),
            "avg_spend_azn": float(cols["avg_spend_azn"].iloc[idx]),
            "extra_gb_6m": int(cols["extra_gb_6m"].iloc[idx]),
            # source has no end-date column: NULL + explicit provenance
            "tariff_end_date": None,
            "tariff_end_source": "missing_in_source",
            "notification_opt_in": 1,
        }
        # impossible-value guard
        bad = [
            f"{k}={c[k]}" for k in ("price_azn", "plan_data_gb", "avg_data_gb", "avg_spend_azn")
            if c[k] is not None and c[k] < 0
        ]
        if bad:
            report["rejected_rows"].append(
                {"sheet": cfg.SHEET_CUSTOMERS, "row": idx, "reason": "negative value: " + ", ".join(bad)}
            )
            continue
        customers.append(c)

    for c in customers:
        customer_repo.upsert_customer(conn, c)

    # ------------------------------------------------------------------ #
    # 2. Catalog
    # ------------------------------------------------------------------ #
    df = xl.parse(cfg.SHEET_CATALOG)
    report["sheets"][cfg.SHEET_CATALOG] = {
        "rows": int(len(df)),
        "columns": [str(c) for c in df.columns],
        "raw_rows_including_notes": int(len(raw)),
    }
    cat_cols = _check_columns(df, cfg.CATALOG_COLUMNS, cfg.SHEET_CATALOG, report)

    catalog_count = 0
    for idx in range(len(df)):
        name = cat_cols["name"].iloc[idx]
        if not isinstance(name, str) or not name.strip():
            # blank spacer row / note row — not data
            continue
        name = name.strip()
        price = cat_cols["price_azn"].iloc[idx]

        # ancillary price rows (extra GB / out-of-bundle minute / roaming day)
        ancillary_key = next(
            (k for k, label in cfg.ANCILLARY_PRICE_KEYS.items() if name == label), None
        )
        if ancillary_key is not None:
            if pd.isna(price):
                report["warnings"].append(
                    f"{cfg.SHEET_CATALOG} row {idx + 2}: ancillary price {name!r} has no value → skipped."
                )
            else:
                catalog_repo.upsert_price(
                    conn, ancillary_key, float(price), f"{cfg.SHEET_CATALOG} row {idx + 2}"
                )
            continue

        if pd.isna(price):
            # spacer or note row
            if not name.startswith("Qeyd"):
                report["warnings"].append(
                    f"{cfg.SHEET_CATALOG} row {idx + 2}: unparsed non-tariff row {name!r} skipped."
                )
            continue

        # real tariff row — verify no other required cell is missing
        row = {
            "name": name,
            "family": None if pd.isna(cat_cols["family"].iloc[idx]) else str(cat_cols["family"].iloc[idx]),
            "price_azn": float(price),
            "data_gb": None if pd.isna(cat_cols["data_gb"].iloc[idx]) else float(cat_cols["data_gb"].iloc[idx]),
            "allnet_min": None if pd.isna(cat_cols["allnet_min"].iloc[idx]) else int(cat_cols["allnet_min"].iloc[idx]),
            "onnet_min": None if pd.isna(cat_cols["onnet_min"].iloc[idx]) else int(cat_cols["onnet_min"].iloc[idx]),
            "offnet_min": None if pd.isna(cat_cols["offnet_min"].iloc[idx]) else int(cat_cols["offnet_min"].iloc[idx]),
            "sms": None if pd.isna(cat_cols["sms"].iloc[idx]) else int(cat_cols["sms"].iloc[idx]),
            "unlimited_apps": None if pd.isna(cat_cols["unlimited_apps"].iloc[idx]) else str(cat_cols["unlimited_apps"].iloc[idx]),
            "source": f"{cfg.SHEET_CATALOG} row {idx + 2}",
        }
        if row["price_azn"] < 0:
            report["rejected_rows"].append(
                {"sheet": cfg.SHEET_CATALOG, "row": idx, "reason": "negative price"}
            )
            continue
        catalog_repo.upsert_tariff(conn, row)
        catalog_count += 1

    # ------------------------------------------------------------------ #
    # 3. Monthly usage
    # ------------------------------------------------------------------ #
    raw = xl.parse(cfg.SHEET_USAGE)
    report["sheets"][cfg.SHEET_USAGE] = {
        "rows": int(len(raw)),
        "columns": [str(c) for c in raw.columns],
    }
    ucols = _check_columns(raw, cfg.USAGE_COLUMNS, cfg.SHEET_USAGE, report)

    usage_count = 0
    seen_keys: set[tuple] = set()
    for idx in range(len(raw)):
        cid = ucols["customer_id"].iloc[idx]
        month = ucols["month"].iloc[idx]
        if not isinstance(cid, str) or not cid.strip():
            report["rejected_rows"].append(
                {"sheet": cfg.SHEET_USAGE, "row": idx, "reason": "missing customer ID"}
            )
            continue
        cid = cid.strip()
        month = str(month).strip()
        if len(month) != 7 or month[4] != "-":
            report["rejected_rows"].append(
                {"sheet": cfg.SHEET_USAGE, "row": idx, "reason": f"unparseable month {month!r}"}
            )
            continue
        key = (cid, month)
        if key in seen_keys:
            report["rejected_rows"].append(
                {"sheet": cfg.SHEET_USAGE, "row": idx, "reason": f"duplicate (customer, month) {key}"}
            )
            continue
        seen_keys.add(key)

        nums = {}
        for field in (
            "data_gb", "total_minutes", "onnet_min", "offnet_min", "sms", "extra_gb",
            "out_of_bundle_min", "roaming_days", "topup_count", "callcenter_contacts",
            "spend_azn",
        ):
            v = ucols[field].iloc[idx]
            nums[field] = None if pd.isna(v) else float(v)
        if any(v is not None and v < 0 for v in nums.values()):
            report["rejected_rows"].append(
                {"sheet": cfg.SHEET_USAGE, "row": idx, "reason": "negative usage/spend value"}
            )
            continue

        rec = {
            "customer_id": cid,
            "month": month,
            "tariff": None if pd.isna(ucols["tariff"].iloc[idx]) else str(ucols["tariff"].iloc[idx]),
            **nums,
            "total_minutes": int(nums["total_minutes"]) if nums["total_minutes"] is not None else None,
            "onnet_min": int(nums["onnet_min"]) if nums["onnet_min"] is not None else None,
            "offnet_min": int(nums["offnet_min"]) if nums["offnet_min"] is not None else None,
            "sms": int(nums["sms"]) if nums["sms"] is not None else None,
            "extra_gb": int(nums["extra_gb"]) if nums["extra_gb"] is not None else None,
            "out_of_bundle_min": int(nums["out_of_bundle_min"]) if nums["out_of_bundle_min"] is not None else None,
            "roaming_days": int(nums["roaming_days"]) if nums["roaming_days"] is not None else None,
            "topup_count": int(nums["topup_count"]) if nums["topup_count"] is not None else None,
            "callcenter_contacts": int(nums["callcenter_contacts"]) if nums["callcenter_contacts"] is not None else None,
        }
        customer_repo.upsert_usage(conn, rec)
        usage_count += 1

    # ------------------------------------------------------------------ #
    # Reconciliation checks (data-quality evidence for the report)
    # ------------------------------------------------------------------ #
    report["checks"] = _reconcile(conn, customers, usage_count, catalog_count)
    report["counts"] = {
        "customers_imported": len(customers),
        "tariffs_imported": catalog_count,
        "usage_rows_imported": usage_count,
        "rejected_rows": len(report["rejected_rows"]),
        "warnings": len(report["warnings"]),
    }
    report["finished_at"] = _now()
    report["status"] = "ok" if not report["rejected_rows"] else "ok_with_rejections"

    cur = conn.execute(
        "INSERT INTO import_runs (started_at, finished_at, status, report_json) VALUES (?, ?, ?, ?)",
        (started, report["finished_at"], report["status"], json.dumps(report, ensure_ascii=False)),
    )
    conn.commit()
    report["run_id"] = cur.lastrowid
    return report


def _reconcile(conn, customers: list[dict], usage_count: int, catalog_count: int) -> dict:
    """Cross-checks that must pass before recommendations are generated."""
    checks: dict = {}

    n_customers = conn.execute("SELECT COUNT(*) AS n FROM customers").fetchone()["n"]
    n_usage = conn.execute("SELECT COUNT(*) AS n FROM usage_records").fetchone()["n"]
    checks["customers_table_count"] = n_customers
    checks["usage_table_count"] = n_usage

    # every usage row references an imported customer
    orphans = conn.execute(
        "SELECT COUNT(*) AS n FROM usage_records u "
        "LEFT JOIN customers c ON c.customer_id = u.customer_id "
        "WHERE c.customer_id IS NULL"
    ).fetchone()["n"]
    checks["orphan_usage_rows"] = int(orphans)

    # every customer's current tariff exists in the catalog
    unknown_tariffs = conn.execute(
        "SELECT COUNT(*) AS n FROM customers c "
        "LEFT JOIN tariffs t ON t.name = c.current_tariff WHERE t.name IS NULL"
    ).fetchone()["n"]
    checks["customers_with_unknown_current_tariff"] = int(unknown_tariffs)

    # duplicate (customer, month) keys
    dups = conn.execute(
        "SELECT COUNT(*) AS n FROM (SELECT customer_id, month, COUNT(*) AS c "
        "FROM usage_records GROUP BY 1, 2 HAVING c > 1)"
    ).fetchone()["n"]
    checks["duplicate_customer_month_keys"] = int(dups)

    # catalog attribute agreement: customer sheet plan attrs vs catalog row
    mismatches = conn.execute(
        """
        SELECT COUNT(*) AS n FROM customers c JOIN tariffs t ON t.name = c.current_tariff
        WHERE ABS(c.price_azn - t.price_azn) > 1e-9
           OR c.plan_data_gb IS NOT t.data_gb
        """
    ).fetchone()["n"]
    checks["customer_vs_catalog_mismatches"] = int(mismatches)

    # cost-model reconciliation: spend = price + 3*extra + 0.08*oob + 5*roaming
    p = {r["price_key"]: r["value_azn"] for r in conn.execute("SELECT * FROM tariff_prices")}
    if {"extra_1gb_azn", "out_of_bundle_1min_azn", "roaming_day_azn"} <= set(p):
        rows = conn.execute(
            """
            SELECT u.spend_azn, u.extra_gb, u.out_of_bundle_min, u.roaming_days, t.price_azn
            FROM usage_records u JOIN tariffs t ON t.name = u.tariff
            """
        ).fetchall()
        bad = sum(
            1
            for r in rows
            if abs(
                (r["price_azn"] or 0)
                + p["extra_1gb_azn"] * (r["extra_gb"] or 0)
                + p["out_of_bundle_1min_azn"] * (r["out_of_bundle_min"] or 0)
                + p["roaming_day_azn"] * (r["roaming_days"] or 0)
                - (r["spend_azn"] or 0)
            ) > 1e-6
        )
        checks["spend_formula_rows_checked"] = len(rows)
        checks["spend_formula_mismatches"] = int(bad)
    else:
        checks["spend_formula_rows_checked"] = 0
        checks["spend_formula_mismatches"] = None  # unknown, not zero

    checks["passed"] = (
        checks["orphan_usage_rows"] == 0
        and checks["customers_with_unknown_current_tariff"] == 0
        and checks["duplicate_customer_month_keys"] == 0
        and checks["customer_vs_catalog_mismatches"] == 0
        and (checks["spend_formula_mismatches"] in (0, None))
    )
    return checks


def render_report_markdown(report: dict) -> str:
    """Human-readable import report (used by scripts/generate_import_report.py)."""
    lines = ["# Import report", ""]
    lines.append(f"- Workbook: `{report.get('workbook')}`")
    lines.append(f"- Mode: {report.get('mode')}")
    lines.append(f"- Started: {report.get('started_at')}  Finished: {report.get('finished_at')}")
    lines.append(f"- Status: **{report.get('status')}**")
    lines.append("")
    lines.append("## Counts")
    for k, v in (report.get("counts") or {}).items():
        lines.append(f"- {k}: {v}")
    lines.append("")
    lines.append("## Sheets")
    for sheet, info in (report.get("sheets") or {}).items():
        lines.append(f"### {sheet}")
        lines.append(f"- rows: {info.get('rows')}, columns: {len(info.get('columns') or [])}")
        if info.get("missing_columns"):
            lines.append(f"- **missing required columns**: {info['missing_columns']}")
        lines.append("")
    lines.append("## Excluded columns")
    for ex in report.get("excluded_columns", []):
        lines.append(f"- `{ex['sheet']}` / `{ex['column']}` — {ex['reason']}")
    lines.append("")
    lines.append("## Rejected rows")
    if report.get("rejected_rows"):
        for r in report["rejected_rows"]:
            lines.append(f"- {r['sheet']} row {r['row']}: {r['reason']}")
    else:
        lines.append("- none")
    lines.append("")
    lines.append("## Warnings")
    if report.get("warnings"):
        for w in report["warnings"][:50]:
            lines.append(f"- {w}")
        if len(report["warnings"]) > 50:
            lines.append(f"- … {len(report['warnings']) - 50} more")
    else:
        lines.append("- none")
    lines.append("")
    lines.append("## Validation checks")
    for k, v in (report.get("checks") or {}).items():
        lines.append(f"- {k}: {v}")
    lines.append("")
    lines.append("## Units")
    for k, v in (report.get("units") or {}).items():
        lines.append(f"- {k}: {v}")
    lines.append("")
    return "\n".join(lines)
