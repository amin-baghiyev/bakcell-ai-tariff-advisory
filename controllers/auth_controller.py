"""Authentication controller: separate customer and admin sign-in flows."""

from __future__ import annotations

from datetime import datetime, timezone

from flask import (
    Blueprint, current_app, redirect, render_template, request, session, url_for,
)
from werkzeug.security import check_password_hash, generate_password_hash

from config import Config
from controllers.security import (
    current_user, regenerate_session_on_login, safe_next,
)
from i18n import LOCALES, tx
from repositories import auth_repo
from repositories.db import connect

auth_bp = Blueprint("auth", __name__)


def _verify(email: str, password: str, role: str) -> dict | None:
    conn = connect()
    try:
        row = auth_repo.find_user(conn, email)
        if row is None or row["role"] != role:
            return None
        if not check_password_hash(row["password_hash"], password):
            return None
        return {
            "email": row["email"],
            "role": row["role"],
            "customer_id": row["customer_id"],
        }
    finally:
        conn.close()


def _render_login(template: str, role: str, title: str, **extra):
    demo_cfg = {
        "demo_mode": Config.DEMO_MODE,
        "demo_email": current_app.config.get(f"DEMO_{role.upper()}_EMAIL"),
        "demo_password": current_app.config.get(f"DEMO_{role.upper()}_PASSWORD"),
    }
    demo_cfg.update(extra)

    if request.method == "GET":
        return render_template(
            template, title=title, role=role,
            next=request.args.get("next"), **demo_cfg,
        )

    email = (request.form.get("email") or "").strip().lower()
    password = request.form.get("password") or ""
    nxt = safe_next(request.form.get("next"), url_for(f"{role}.dashboard"))

    user = _verify(email, password, role)
    if user is None:
        return render_template(
            template, title=title, role=role, error=tx("auth.invalid"),
            next=request.form.get("next"), demo_mode=False,
            demo_email=None, demo_password=None,
        ), 401

    # session fixation defence: everything issued before auth is discarded
    regenerate_session_on_login()
    user["login_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    session["user"] = user
    return redirect(nxt)


@auth_bp.route("/")
def index():
    user = current_user()
    if user and user.get("role") == "admin":
        return redirect(url_for("admin.dashboard"))
    if user and user.get("role") == "customer":
        return redirect(url_for("customer.dashboard"))
    return redirect(url_for("auth.customer_login"))


@auth_bp.route("/customer/login", methods=["GET", "POST"])
def customer_login():
    # Admin access is never offered from this form.
    return _render_login("auth/customer_login.html", "customer", tx("auth.customer_signin"))


@auth_bp.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    return _render_login("auth/admin_login.html", "admin", tx("auth.admin_signin"))


@auth_bp.route("/lang/<code>")
def set_lang(code: str):
    """Switch the UI language (stored in the session, survives login)."""
    if code in LOCALES:
        session["lang"] = code
    nxt = safe_next(request.args.get("next"), url_for("auth.index"))
    return redirect(nxt)


@auth_bp.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return redirect(url_for("auth.customer_login"))


def ensure_demo_users() -> None:
    """Create/refresh the documented demo accounts (passwords always hashed)."""
    demo = [
        (Config.DEMO_CUSTOMER_EMAIL, Config.DEMO_CUSTOMER_PASSWORD, "customer", "BKC-0001"),
        (Config.DEMO_CUSTOMER2_EMAIL, Config.DEMO_CUSTOMER2_PASSWORD, "customer", "BKC-0002"),
        (Config.DEMO_ADMIN_EMAIL, Config.DEMO_ADMIN_PASSWORD, "admin", None),
    ]
    conn = connect()
    try:
        for email, password, role, customer_id in demo:
            auth_repo.create_user(
                conn, email.lower(), generate_password_hash(password), role, customer_id
            )
    finally:
        conn.close()
