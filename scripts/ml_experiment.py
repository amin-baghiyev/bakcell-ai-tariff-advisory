"""Optional ML experiment: demand estimation vs the rule-based baseline.

Predicts NEXT-MONTH internet demand (never the customer's current tariff —
existing choices are not ground truth labels). Uses a time-aware split:
train on months up to T-1, test on the final month T.

Models: mean-baseline (persistence), Linear Regression, RandomForest.
Reported as EXPLORATORY: n is small and results are not claimed as a
production model.

Usage: python scripts/ml_experiment.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor, RandomForestRegressor
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, mean_squared_error

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config import Config
from repositories.db import setup


def load_frame(conn) -> pd.DataFrame:
    rows = conn.execute(
        "SELECT customer_id, month, data_gb, total_minutes, extra_gb, spend_azn "
        "FROM usage_records ORDER BY customer_id, month"
    ).fetchall()
    df = pd.DataFrame([dict(r) for r in rows])
    df["month_idx"] = df.groupby("customer_id").cumcount()
    return df


def build_dataset(df: pd.DataFrame) -> pd.DataFrame:
    """Feature rows: history up to month t → target = data_gb at month t+1."""
    feats = []
    for cid, g in df.groupby("customer_id"):
        g = g.sort_values("month_idx").reset_index(drop=True)
        for t in range(1, len(g)):
            hist = g.iloc[:t]
            feats.append({
                "customer_id": cid,
                "test_month": int(g.loc[t, "month_idx"]),
                "hist_mean_gb": hist["data_gb"].mean(),
                "hist_std_gb": hist["data_gb"].std(ddof=0) if len(hist) > 1 else 0.0,
                "hist_last_gb": hist["data_gb"].iloc[-1],
                "hist_mean_min": hist["total_minutes"].mean(),
                "hist_mean_spend": hist["spend_azn"].mean(),
                "hist_mean_extra": hist["extra_gb"].mean(),
                "hist_n": len(hist),
                "target_gb": float(g.loc[t, "data_gb"]),
            })
    return pd.DataFrame(feats)


def main() -> int:
    conn = setup()
    try:
        df = load_frame(conn)
    finally:
        conn.close()
    if df.empty:
        print("No usage rows — run scripts/import_data.py first.")
        return 1

    data = build_dataset(df)
    # time-aware split: predict only the final month per customer (month_idx == 5)
    test = data[data["test_month"] == data["test_month"].max()]
    train = data[data["test_month"] < data["test_month"].max()]
    features = ["hist_mean_gb", "hist_std_gb", "hist_last_gb", "hist_mean_min",
                "hist_mean_spend", "hist_mean_extra", "hist_n"]

    X_train, y_train = train[features], train["target_gb"]
    X_test, y_test = test[features], test["target_gb"]

    models = {
        "mean-baseline": None,  # predicted with train mean
        "linear_regression": LinearRegression(),
        "random_forest": RandomForestRegressor(
            n_estimators=200, max_depth=6, random_state=42, n_jobs=-1
        ),
        # gradient-boosting stand-in (lightgbm/catboost are not installed here)
        "hist_gradient_boosting": HistGradientBoostingRegressor(
            max_iter=200, max_depth=4, random_state=42
        ),
    }

    results = {}
    baseline_pred = np.full(len(y_test), y_train.mean())
    results["mean-baseline"] = _metrics(y_test, baseline_pred)

    for name in ("linear_regression", "random_forest", "hist_gradient_boosting"):
        model = models[name]
        model.fit(X_train, y_train)
        results[name] = _metrics(y_test, model.predict(X_test))

    report = {
        "task": "predict next-month internet demand (GB) — exploratory only",
        "train_rows": int(len(train)),
        "test_rows": int(len(test)),
        "test_definition": "final observed month per customer (time-aware, no shuffle)",
        "metrics": results,
        "limitations": [
            "single synthetic dataset, 100 customers, 6 months",
            "no hyperparameter tuning; results are exploratory, not production-grade",
            "current tariff is deliberately NOT used as a label",
        ],
    }
    out = Path(Config.RESULTS_DIR)
    out.mkdir(parents=True, exist_ok=True)
    (out / "ml_experiment.json").write_text(json.dumps(report, indent=2), encoding="utf-8")

    print(f"train={len(train)} test={len(test)}  (predicting final-month GB)")
    for name, m in results.items():
        print(f"  {name:20s} MAE={m['mae']:.3f}  RMSE={m['rmse']:.3f}  R2={m['r2']:.3f}")
    print(f"Written: {out / 'ml_experiment.json'}")
    print("NOTE: exploratory only — no claim of a reliable trained model.")
    return 0


def _metrics(y_true, y_pred) -> dict:
    y_true, y_pred = np.asarray(y_true, float), np.asarray(y_pred, float)
    ss_res = float(((y_true - y_pred) ** 2).sum())
    ss_tot = float(((y_true - y_true.mean()) ** 2).sum())
    return {
        "mae": round(float(mean_absolute_error(y_true, y_pred)), 4),
        "rmse": round(float(np.sqrt(mean_squared_error(y_true, y_pred))), 4),
        "r2": round(1 - ss_res / ss_tot, 4) if ss_tot else None,
    }


if __name__ == "__main__":
    raise SystemExit(main())
