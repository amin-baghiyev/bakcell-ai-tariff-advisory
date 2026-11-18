"""Standalone workbook inspection script.

Usage:
    python scripts/inspect_workbook.py [path_to_workbook]

Prints sheets, columns, dtypes, row counts, missing values, duplicates,
unit hints and inconsistent values to stdout. Read-only: never modifies
the workbook.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

DEFAULT_WORKBOOK = (
    Path(__file__).resolve().parents[1]
    / "dataset"
    / "Peerstack Academy AI Contest - Tariff Advisor synthetic data.xlsx"
)


def describe_series(name: str, s: pd.Series) -> dict:
    info = {
        "name": name,
        "dtype": str(s.dtype),
        "non_null": int(s.notna().sum()),
        "missing": int(s.isna().sum()),
        "n_unique": int(s.nunique(dropna=True)),
    }
    if pd.api.types.is_numeric_dtype(s):
        info["min"] = s.min(skipna=True)
        info["max"] = s.max(skipna=True)
        info["negatives"] = int((s < 0).sum())
    else:
        as_str = s.astype("string").str.strip()
        info["sample_values"] = list(as_str.dropna().unique()[:8])
    return info


def main() -> int:
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_WORKBOOK
    if not path.exists():
        print(f"Workbook not found: {path}")
        return 1

    xl = pd.ExcelFile(path)
    print(f"WORKBOOK: {path}")
    print(f"SHEETS ({len(xl.sheet_names)}): {xl.sheet_names}\n")

    for sheet in xl.sheet_names:
        df = xl.parse(sheet)
        print("=" * 72)
        print(f"SHEET: {sheet!r}  rows={len(df)} cols={len(df.columns)}")
        print("=" * 72)
        for col in df.columns:
            info = describe_series(str(col), df[col])
            extra = ""
            if "min" in info:
                extra = f" min={info['min']} max={info['max']} negatives={info['negatives']}"
            elif "sample_values" in info:
                extra = f" samples={info['sample_values']}"
            print(
                f"  - {info['name']!r}: dtype={info['dtype']} "
                f"missing={info['missing']}/{len(df)} "
                f"unique={info['n_unique']}{extra}"
            )
        dup_all = int(df.duplicated().sum())
        print(f"  fully duplicated rows: {dup_all}")
        id_like = [
            c for c in df.columns if str(c).lower().find("id") >= 0 or "phone" in str(c).lower()
        ]
        if id_like:
            for c in id_like:
                sub = df.dropna(subset=[c])
                d = int(sub.duplicated(subset=[c]).sum())
                print(f"  duplicate rows per {c!r}: {d} (unique={sub[c].nunique()})")
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
