"""Admin routes (separate namespace, admin-role protected on every route)."""

from __future__ import annotations

from flask import Blueprint, abort, render_template, request, url_for

from controllers.security import login_required
from i18n import get_locale
from repositories import analytics_repo, recommendation_repo
from repositories.db import connect
from services import analytics

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


def _filters() -> dict:
    return {
        "month_from": (request.args.get("month_from") or "").strip() or None,
        "month_to": (request.args.get("month_to") or "").strip() or None,
        "tariff": (request.args.get("tariff") or "").strip() or None,
    }


@admin_bp.route("/")
@login_required("admin")
def dashboard():
    conn = connect()
    try:
        f = _filters()
        dash = analytics.admin_dashboard(
            conn, month_from=f["month_from"], month_to=f["month_to"],
            tariff=f["tariff"], lang=get_locale(),
        )
        tariffs = [r["name"] for r in analytics_repo.tariff_distribution(conn)]
        return render_template("admin/dashboard.html", dash=dash, tariffs=tariffs, f=f)
    finally:
        conn.close()


@admin_bp.route("/customers")
@login_required("admin")
def customers():
    conn = connect()
    try:
        f = _filters()
        page = request.args.get("page", 1, type=int)
        search = (request.args.get("q") or "").strip() or None
        table = analytics.customer_table(
            conn, tariff=f["tariff"], search=search, page=page, per_page=20,
            lang=get_locale(),
        )
        tariffs = [r["name"] for r in analytics_repo.tariff_distribution(conn)]
        query = {k: v for k, v in f.items() if v}
        if search:
            query["q"] = search

        def page_url(p: int) -> str:
            from urllib.parse import urlencode

            params = dict(query)
            params["page"] = p
            return url_for("admin.customers") + "?" + urlencode(params)

        return render_template(
            "admin/customers.html",
            table=table,
            tariffs=tariffs,
            f=f,
            search=search,
            base_query=query,
            prev_url=page_url(table["page"] - 1) if table["page"] > 1 else None,
            next_url=page_url(table["page"] + 1) if table["page"] < table["pages"] else None,
        )
    finally:
        conn.close()


@admin_bp.route("/customers/<customer_id>")
@login_required("admin")
def customer_detail(customer_id: str):
    conn = connect()
    try:
        # route-level authorisation: only existing IDs; phone numbers are not
        # stored anywhere, so they cannot be leaked here.
        profile = analytics.customer_profile(conn, customer_id)
        if profile is None:
            abort(404, description="Customer not found.")
        history = analytics.customer_history(conn, customer_id)
        rec = analytics.latest_recommendation(conn, customer_id)
        rec_decoded = None
        if rec:
            rec_decoded = dict(rec)
            rec_decoded["ranked"] = rec["ranked"]
        return render_template(
            "admin/customer_detail.html",
            profile=profile,
            history=history,
            rec=rec_decoded,
        )
    finally:
        conn.close()
