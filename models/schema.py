"""SQLite schema for the Tariff Advisor demo.

Entities follow documentation.md §8. Phone numbers are deliberately *not*
part of the schema: the workbook's ``Nömrə`` column is excluded at import.
"""

from __future__ import annotations

SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    email         TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    role          TEXT NOT NULL CHECK (role IN ('customer', 'admin')),
    customer_id   TEXT REFERENCES customers(customer_id),
    active        INTEGER NOT NULL DEFAULT 1,
    created_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS customers (
    customer_id        TEXT PRIMARY KEY,
    age                INTEGER,
    gender             TEXT,
    region             TEXT,
    subscriber_type    TEXT,
    tenure_months      INTEGER,
    device             TEXT,
    network            TEXT,
    current_tariff     TEXT NOT NULL,
    months_on_tariff   INTEGER,
    price_azn          REAL,
    plan_data_gb       REAL,
    plan_allnet_min    INTEGER,
    plan_onnet_min     INTEGER,
    plan_offnet_min    INTEGER,
    plan_sms           INTEGER,
    plan_unlimited_apps TEXT,
    avg_data_gb        REAL,
    avg_minutes        REAL,
    data_utilization   REAL,      -- NULL when source said "-"
    minute_utilization REAL,
    avg_spend_azn      REAL,
    extra_gb_6m        INTEGER,
    tariff_end_date    TEXT,      -- ISO date; NULL when missing in source
    tariff_end_source  TEXT,      -- 'missing_in_source' | 'demo_mock'
    notification_opt_in INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS tariffs (
    name            TEXT PRIMARY KEY,
    family          TEXT,
    price_azn       REAL,
    data_gb         REAL,
    allnet_min      INTEGER,
    onnet_min       INTEGER,
    offnet_min      INTEGER,
    sms             INTEGER,
    unlimited_apps  TEXT,         -- NULL = unknown, never invented
    source          TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS tariff_prices (      -- ancillary prices from catalog sheet
    price_key TEXT PRIMARY KEY,
    value_azn REAL NOT NULL,
    source    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS usage_records (
    customer_id        TEXT NOT NULL,
    month              TEXT NOT NULL,          -- 'YYYY-MM'
    tariff             TEXT,
    data_gb            REAL,
    total_minutes      INTEGER,
    onnet_min          INTEGER,
    offnet_min         INTEGER,
    sms                INTEGER,
    extra_gb           INTEGER,
    out_of_bundle_min  INTEGER,
    roaming_days       INTEGER,
    topup_count        INTEGER,
    callcenter_contacts INTEGER,
    spend_azn          REAL,
    PRIMARY KEY (customer_id, month)
);

CREATE TABLE IF NOT EXISTS recommendations (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id     TEXT NOT NULL,
    generated_at    TEXT NOT NULL,
    current_tariff  TEXT,
    ranked_json     TEXT NOT NULL,   -- top-3 with score components + facts
    explanation_json TEXT NOT NULL,
    window_start    TEXT,
    window_end      TEXT,
    model_version   TEXT NOT NULL,
    weights_json    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS notifications (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id TEXT NOT NULL,
    type        TEXT NOT NULL,
    period_key  TEXT NOT NULL,        -- e.g. tariff end date
    due_at      TEXT,                 -- ISO timestamp of the reminder moment
    created_at  TEXT NOT NULL,
    status      TEXT NOT NULL DEFAULT 'pending',
    message     TEXT NOT NULL,
    params_json TEXT,                 -- structured fields for localized rendering
    UNIQUE (customer_id, type, period_key)   -- idempotency guard
);

CREATE TABLE IF NOT EXISTS notification_skips (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id TEXT,
    period_key  TEXT,
    reason      TEXT NOT NULL,
    created_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS tariff_changes (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id  TEXT NOT NULL,
    from_tariff  TEXT,
    to_tariff    TEXT NOT NULL,
    changed_at   TEXT NOT NULL,
    source       TEXT NOT NULL DEFAULT 'demo_user_action'
);

CREATE TABLE IF NOT EXISTS import_runs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at  TEXT NOT NULL,
    finished_at TEXT,
    status      TEXT NOT NULL,
    report_json TEXT
);

CREATE INDEX IF NOT EXISTS idx_usage_month ON usage_records(month);
CREATE INDEX IF NOT EXISTS idx_notifications_customer ON notifications(customer_id);
CREATE INDEX IF NOT EXISTS idx_recommendations_customer ON recommendations(customer_id);
"""


def init_db(conn) -> None:
    """Apply the schema (idempotent, including additive migrations)."""
    conn.executescript(SCHEMA)
    # additive migration: notifications.params_json (added for i18n rendering)
    cols = {r[1] for r in conn.execute("PRAGMA table_info(notifications)").fetchall()}
    if "params_json" not in cols:
        conn.execute("ALTER TABLE notifications ADD COLUMN params_json TEXT")
    conn.commit()
