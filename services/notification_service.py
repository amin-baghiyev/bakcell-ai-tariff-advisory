"""Five-day tariff-end reminders (in-app demo notifications).

Behaviour (documentation.md §7):

* Runs daily (CLI / ``flask reminders``); finds tariff periods ending within
  five calendar days and creates **one** reminder per (customer, type, period).
* Idempotent: the ``UNIQUE (customer_id, type, period_key)`` constraint plus
  ``INSERT OR IGNORE`` guarantee repeat runs never duplicate a reminder.
* Respects the customer's notification preference (opt-out).
* Missing end dates are skipped **with a recorded reason**.
* Delivery is in-app only. A provider interface is defined for future
  web-push/SMS, but nothing is claimed as delivered without credentials.
"""

from __future__ import annotations

import sqlite3
from datetime import date, datetime, timedelta, timezone

from repositories import customer_repo, notification_repo

REMINDER_TYPE = "tariff_end_reminder"
REMINDER_WINDOW_DAYS = 5
DEFAULT_TZ = "Asia/Baku"


class NotificationProvider:
    """Provider interface for future web-push / SMS delivery.

    The demo implementation stores nothing outside the database: delivery is
    in-app only. Implement ``deliver`` to integrate a real provider, and only
    then claim delivery anywhere in the UI.
    """

    name = "in-app (demo)"

    def deliver(self, notification: dict) -> bool:  # pragma: no cover - interface
        return False


def localized_message(notification, lang: str = "az") -> str:
    """Render a notification's body in ``lang`` from its stored params.

    Rows created before params existed (or without params) fall back to the
    stored English message, so nothing ever renders blank.
    """
    from i18n import translate

    params = None
    try:
        raw = notification["params_json"]
    except (KeyError, IndexError, TypeError):
        raw = getattr(notification, "params_json", None)
    if raw:
        import json

        try:
            params = json.loads(raw)
        except (ValueError, TypeError):
            params = None

    if params and params.get("end") is not None:
        days = int(params.get("days_left") or 0)
        day_word = translate(lang, "notif.day_one" if days == 1 else "notif.day_many")
        return translate(
            lang,
            "notif.reminder_body",
            tariff=params.get("tariff", ""),
            end=params.get("end", ""),
            days=days,
            day=day_word,
        )
    return str(notification["message"] if "message" in notification.keys()
               else getattr(notification, "message", ""))


def today_in(tz_name: str = DEFAULT_TZ) -> date:
    """Today's date in the configured timezone (falls back to local time)."""
    try:
        from zoneinfo import ZoneInfo

        return datetime.now(ZoneInfo(tz_name)).date()
    except Exception:
        return datetime.now(timezone.utc).date()


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def run_reminders(
    conn: sqlite3.Connection,
    *,
    today: date | None = None,
    tz_name: str = DEFAULT_TZ,
    window_days: int = REMINDER_WINDOW_DAYS,
) -> dict:
    """Create due reminders. Safe to run any number of times (idempotent)."""
    today = today or today_in(tz_name)
    provider = NotificationProvider()

    report = {
        "today": today.isoformat(),
        "timezone": tz_name,
        "window_days": window_days,
        "provider": provider.name,
        "delivery_claim": "in-app demo notification only — no push/SMS provider configured",
        "created": [],
        "already_existed": [],
        "skipped": [],
        "not_due": 0,
        "outside_window": 0,
    }

    customers = customer_repo.all_customers(conn)
    for row in customers:
        cid = row["customer_id"]
        tariff = row["current_tariff"]
        end_raw = row["tariff_end_date"]
        period_key = str(end_raw)[:10] if end_raw else "unknown"

        # --- missing / invalid end date ---------------------------------- #
        end = _parse_date(end_raw)
        if end is None:
            reason = "missing_end_date" if not end_raw else "invalid_end_date"
            notification_repo.record_skip(conn, cid, None, reason)
            report["skipped"].append({"customer_id": cid, "reason": reason})
            continue

        # --- opt-out ------------------------------------------------------ #
        if not row["notification_opt_in"]:
            notification_repo.record_skip(conn, cid, period_key, "opted_out")
            report["skipped"].append({"customer_id": cid, "period_key": period_key, "reason": "opted_out"})
            continue

        days_left = (end - today).days
        if days_left < 0:
            notification_repo.record_skip(conn, cid, period_key, "period_already_ended")
            report["skipped"].append({"customer_id": cid, "period_key": period_key, "reason": "period_already_ended"})
            continue
        if days_left > window_days:
            report["outside_window"] += 1
            continue

        message = (
            f"Demo reminder: your tariff {tariff} period ends on {end.isoformat()} "
            f"(in {days_left} day{'s' if days_left != 1 else ''}). "
            "This is an in-app demo notification — push/SMS delivery is not configured."
        )
        created = notification_repo.create_once(
            conn,
            cid,
            REMINDER_TYPE,
            period_key,
            message,
            due_at=f"{end.isoformat()}T09:00:00+04:00",
            params={
                "tariff": tariff,
                "end": end.isoformat(),
                "days_left": days_left,
            },
        )
        entry = {"customer_id": cid, "period_key": period_key, "days_left": days_left}
        if created:
            report["created"].append(entry)
        else:
            report["already_existed"].append(entry)

    report["totals"] = {
        "customers_scanned": len(customers),
        "created": len(report["created"]),
        "already_existed": len(report["already_existed"]),
        "skipped": len(report["skipped"]),
        "outside_window": report["outside_window"],
    }
    return report
