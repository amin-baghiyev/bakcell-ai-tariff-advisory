"""Customer-initiated tariff change (demo user action).

The workbook itself never changes: this service records an explicit
*user action* (audit table ``tariff_changes``), copies the new plan's
attributes from the catalog (source-supported only), resets plan tenure,
recomputes utilization vs the new allowance, clears the now-stale renewal
date, and regenerates the customer's recommendation so the dashboard
reflects the new plan immediately.
"""

from __future__ import annotations

import sqlite3

from repositories import catalog_repo, customer_repo
from services.pipeline import build_for_customer


class TariffChangeError(ValueError):
    pass


def change_tariff(conn: sqlite3.Connection, customer_id: str, tariff_name: str) -> dict:
    """Switch a customer to a catalog tariff (demo user action, audited).

    Error messages are i18n keys — the controller renders them in the
    active locale.
    """
    customer = customer_repo.get_customer(conn, customer_id)
    if customer is None:
        raise TariffChangeError("error.customer_not_found")

    tariff_name = (tariff_name or "").strip()
    tariff = catalog_repo.tariff_map(conn).get(tariff_name)
    if tariff is None:
        raise TariffChangeError("error.bad_tariff")

    current = customer["current_tariff"]
    if current == tariff_name:
        return {"changed": False, "reason": "already_current", "tariff": tariff_name}

    customer_repo.apply_tariff_change(
        conn, customer_id, dict(tariff), from_tariff=current
    )
    rec = build_for_customer(conn, customer_id)
    return {
        "changed": True,
        "from": current,
        "to": tariff_name,
        "price_azn": tariff["price_azn"],
        "recommendation": rec,
    }
