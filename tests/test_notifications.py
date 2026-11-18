"""Notification job tests: idempotency, missing end dates, opt-out."""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

from repositories import notification_repo
from repositories.db import connect
from models.schema import init_db
from services.notification_service import run_reminders


@pytest.fixture()
def conn(tmp_path):
    c = connect(str(tmp_path / "test.sqlite3"))
    init_db(c)
    yield c
    c.close()


def _add_customer(conn, cid, end_date, opt_in=1, tariff="Klass 10"):
    conn.execute(
        "INSERT INTO customers (customer_id, current_tariff, tariff_end_date, "
        "tariff_end_source, notification_opt_in) VALUES (?, ?, ?, ?, ?)",
        (cid, tariff, end_date, "demo_mock" if end_date else "missing_in_source", opt_in),
    )
    conn.commit()


TODAY = date(2026, 11, 16)


def test_creates_reminder_five_days_out(conn):
    _add_customer(conn, "BKC-1001", "2026-11-21")
    report = run_reminders(conn, today=TODAY)
    assert report["totals"]["created"] == 1
    rows = notification_repo.for_customer(conn, "BKC-1001")
    assert len(rows) == 1
    assert rows[0]["type"] == "tariff_end_reminder"
    assert rows[0]["period_key"] == "2026-11-21"


def test_idempotent_repeat_runs(conn):
    _add_customer(conn, "BKC-1001", "2026-11-21")
    run_reminders(conn, today=TODAY)
    second = run_reminders(conn, today=TODAY)
    third = run_reminders(conn, today=TODAY)
    assert second["totals"]["created"] == 0
    assert second["totals"]["already_existed"] == 1
    assert third["totals"]["already_existed"] == 1
    assert len(notification_repo.for_customer(conn, "BKC-1001")) == 1


def test_missing_end_date_recorded_not_created(conn):
    _add_customer(conn, "BKC-1002", None)
    report = run_reminders(conn, today=TODAY)
    assert report["totals"]["created"] == 0
    reasons = [s["reason"] for s in report["skipped"]]
    assert "missing_end_date" in reasons
    skips = notification_repo.recent_skips(conn)
    assert any(s["reason"] == "missing_end_date" and s["customer_id"] == "BKC-1002"
               for s in skips)


def test_opt_out_respected(conn):
    _add_customer(conn, "BKC-1003", "2026-11-20", opt_in=0)
    report = run_reminders(conn, today=TODAY)
    assert report["totals"]["created"] == 0
    assert any(s["reason"] == "opted_out" for s in report["skipped"])
    assert notification_repo.for_customer(conn, "BKC-1003") == []


def test_outside_window_not_created(conn):
    _add_customer(conn, "BKC-1004", "2026-12-07")
    report = run_reminders(conn, today=TODAY)
    assert report["totals"]["created"] == 0
    assert report["outside_window"] == 1
    assert notification_repo.for_customer(conn, "BKC-1004") == []


def test_skip_log_deduplicates(conn):
    _add_customer(conn, "BKC-1002", None)
    run_reminders(conn, today=TODAY)
    run_reminders(conn, today=TODAY)
    skips = [s for s in notification_repo.recent_skips(conn)
             if s["customer_id"] == "BKC-1002" and s["reason"] == "missing_end_date"]
    assert len(skips) == 1
