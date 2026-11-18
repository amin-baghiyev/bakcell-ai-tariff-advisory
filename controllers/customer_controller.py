"""Customer-facing routes (all role-protected, scoped to the session's customer)."""

from __future__ import annotations

from flask import (
    Blueprint, abort, flash, redirect, render_template, request, url_for,
)

from controllers.security import current_user, login_required
from i18n import get_locale, tx
from repositories import catalog_repo, customer_repo, notification_repo
from repositories.db import connect
from services import analytics
from services.account_service import TariffChangeError, change_tariff as do_change_tariff
from services.notification_service import REMINDER_WINDOW_DAYS

customer_bp = Blueprint("customer", __name__, url_prefix="/customer")


def _db():
    return connect()


def _customer_id() -> str:
    user = current_user() or {}
    cid = user.get("customer_id")
    if not cid:
        abort(403, description="This account is not linked to a customer profile.")
    return cid


@customer_bp.route("/")
@login_required("customer")
def dashboard():
    conn = _db()
    try:
        cid = _customer_id()
        lang = get_locale()
        data = analytics.customer_dashboard(conn, cid, lang=lang)
        if data is None:
            abort(404, description="Customer profile not found.")
        reminders = notification_repo.for_customer(conn, cid)
        # latest 5-day reminder, if any
        reminder = next((n for n in reminders if n["type"] == "tariff_end_reminder"), None)
        return render_template(
            "customer/dashboard.html",
            data=data,
            reminder=reminder,
            reminders=reminders,
            reminder_window=REMINDER_WINDOW_DAYS,
            usage_bars=_usage_bars(data, lang),
            unread=data["unread_notifications"],
            active_nav="home",
        )
    finally:
        conn.close()


@customer_bp.route("/change-tariff", methods=["POST"])
@login_required("customer")
def change_tariff():
    """Switch the signed-in customer to another catalog tariff (demo action)."""
    conn = _db()
    try:
        cid = _customer_id()
        try:
            result = do_change_tariff(conn, cid, request.form.get("tariff") or "")
        except TariffChangeError as exc:
            flash(tx(str(exc)), "error")
            return redirect(url_for("customer.recommendations"))
        if result["changed"]:
            flash(
                tx(
                    "flash.changed",
                    old=result["from"],
                    new=result["to"],
                    price=f"{result['price_azn']:g}",
                ),
                "success",
            )
        else:
            flash(tx("flash.already", tariff=result["tariff"]), "info")
        return redirect(url_for("customer.dashboard"))
    finally:
        conn.close()


def _usage_bars(data: dict, lang: str = "az") -> list[dict]:
    """Usage-vs-allowance bars (values straight from the source columns)."""
    p = data["profile"]
    avg = data["averages"]
    min_allow = (p["plan_allnet_min"] or 0) or (
        (p["plan_onnet_min"] or 0) + (p["plan_offnet_min"] or 0)
    )

    def bar(value, allowance, unit):
        pct = 0
        if allowance:
            pct = min(100, round(100 * (value or 0) / allowance))
        return {
            "value": value,
            "allowance": allowance,
            "unit": unit,
            "pct": pct,
            "over": bool(allowance and (value or 0) > allowance),
        }

    from i18n import translate

    return [
        {"label": translate(lang, "unit.min_month"), **bar(avg["total_minutes"], min_allow, "min")},
        {"label": translate(lang, "unit.gb_month"), **bar(avg["data_gb"], p["plan_data_gb"], "GB")},
        {"label": translate(lang, "unit.sms_month"), **bar(avg["sms"], p["plan_sms"], "SMS")},
    ]


@customer_bp.route("/recommendations")
@login_required("customer")
def recommendations():
    conn = _db()
    try:
        cid = _customer_id()
        lang = get_locale()
        data = analytics.customer_dashboard(conn, cid, lang=lang)
        if data is None:
            abort(404, description="Customer profile not found.")
        rec = data["recommendation"]
        comparison = None
        if rec:
            comparison = _build_comparison(data, rec)
        catalog = [dict(r) for r in catalog_repo.all_tariffs(conn)]
        return render_template(
            "customer/recommendations.html",
            data=data,
            rec=rec,
            comparison=comparison,
            catalog=catalog,
            current_tariff=data["profile"]["current_tariff"],
            unread=data["unread_notifications"],
            active_nav="tariffs",
        )
    finally:
        conn.close()


def _build_comparison(data: dict, rec: dict) -> list[dict]:
    """Row-per-plan comparison: observed usage vs allowance, price delta, trade-offs."""
    profile = data["profile"]
    ranked = rec["ranked"]
    current = next((p for p in ranked if p.get("is_current")), None)
    rows = []
    for plan in ranked:
        facts = plan.get("facts", {})
        price = plan.get("price_azn")
        cur_price = facts.get("current_price_azn")
        price_diff = (
            round(price - cur_price, 2)
            if (price is not None and cur_price is not None and not plan.get("is_current"))
            else (0 if plan.get("is_current") else None)
        )
        est = plan.get("est_total_cost")
        tradeoffs = []
        if plan.get("shortfall"):
            tradeoffs.append(tx("trade.shortfall", v=plan["shortfall"]))
        if plan.get("excess_gb"):
            tradeoffs.append(tx("trade.excess", x=f"{plan['excess_gb']:g}"))
        if plan.get("adequacy_calls") is not None and plan["adequacy_calls"] < 1:
            tradeoffs.append(tx("trade.calls"))
        if not tradeoffs:
            tradeoffs.append(tx("trade.none"))
        rows.append(
            {
                "plan": plan,
                "price": price,
                "price_diff_vs_current": price_diff,
                "est_total_cost": est,
                "used_data": facts.get("est_data_gb"),
                "allowance_data": plan.get("data_gb"),
                "used_minutes": facts.get("est_total_min"),
                "allowance_minutes": facts.get("plan_total_min"),
                "tradeoffs": tradeoffs,
                "extra_cost": (plan.get("cost_parts") or {}).get("extra_data_cost"),
            }
        )
    return rows


@customer_bp.route("/history")
@login_required("customer")
def history():
    conn = _db()
    try:
        cid = _customer_id()
        rows = analytics.customer_history(conn, cid)
        profile = analytics.customer_profile(conn, cid)
        # chart series: month-by-month observed values (source fields only)
        max_data = max([r["data_gb"] or 0 for r in rows], default=0) or 1
        max_min = max([r["total_minutes"] or 0 for r in rows], default=0) or 1
        max_spend = max([r["spend_azn"] or 0 for r in rows], default=0) or 1
        series = [
            {
                "month": r["month"],
                "data_gb": r["data_gb"],
                "data_pct": round(100 * (r["data_gb"] or 0) / max_data),
                "minutes": r["total_minutes"],
                "min_pct": round(100 * (r["total_minutes"] or 0) / max_min),
                "spend": r["spend_azn"],
                "spend_pct": round(100 * (r["spend_azn"] or 0) / max_spend),
                "extra_gb": r["extra_gb"],
                "out_of_bundle_min": r["out_of_bundle_min"],
                "topups": r["topup_count"],
                "roaming_days": r["roaming_days"],
                "callcenter": r["callcenter_contacts"],
                "sms": r["sms"],
                "tariff": r["tariff"],
            }
            for r in rows
        ]
        totals = {
            "extra_gb": sum(r["extra_gb"] or 0 for r in rows),
            "topups": sum(r["topup_count"] or 0 for r in rows),
            "roaming_days": sum(r["roaming_days"] or 0 for r in rows),
            "callcenter": sum(r["callcenter_contacts"] or 0 for r in rows),
            "spend": round(sum(r["spend_azn"] or 0 for r in rows), 2),
        }
        return render_template(
            "customer/history.html",
            profile=profile,
            series=series,
            totals=totals,
            unread=analytics.unread_notification_count(conn, cid),
            active_nav="history",
            allowance_gb=profile["plan_data_gb"] if profile else None,
            allowance_min=(
                (profile["plan_allnet_min"] or 0)
                or ((profile["plan_onnet_min"] or 0) + (profile["plan_offnet_min"] or 0))
                if profile
                else None
            ),
        )
    finally:
        conn.close()


@customer_bp.route("/notifications")
@login_required("customer")
def notifications():
    conn = _db()
    try:
        cid = _customer_id()
        items = notification_repo.for_customer(conn, cid)
        profile = analytics.customer_profile(conn, cid)
        skips = [
            dict(r)
            for r in conn.execute(
                "SELECT * FROM notification_skips WHERE customer_id = ? "
                "ORDER BY created_at DESC LIMIT 20",
                (cid,),
            ).fetchall()
        ]
        return render_template(
            "customer/notifications.html",
            items=items,
            skips=skips,
            profile=profile,
            reminder_window=REMINDER_WINDOW_DAYS,
            unread=analytics.unread_notification_count(conn, cid),
            active_nav="alerts",
        )
    finally:
        conn.close()


@customer_bp.route("/notifications/preferences", methods=["POST"])
@login_required("customer")
def notification_preferences():
    conn = _db()
    try:
        cid = _customer_id()
        enabled = request.form.get("in_app") == "on"
        customer_repo.set_opt_in(conn, cid, enabled)
        return redirect(url_for("customer.notifications"))
    finally:
        conn.close()


@customer_bp.route("/notifications/<int:nid>/read", methods=["POST"])
@login_required("customer")
def mark_read(nid: int):
    conn = _db()
    try:
        notification_repo.mark_read(conn, nid, _customer_id())
        return redirect(url_for("customer.notifications"))
    finally:
        conn.close()
