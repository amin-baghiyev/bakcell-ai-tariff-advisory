"""Auth/session/CSRF security helpers shared by all controllers."""

from __future__ import annotations

import hmac
import secrets
from functools import wraps

from flask import abort, redirect, request, session, url_for


# --------------------------------------------------------------------------- #
# CSRF
# --------------------------------------------------------------------------- #

def csrf_token() -> str:
    """Return (and create) a per-session CSRF token."""
    token = session.get("_csrf")
    if not token:
        token = secrets.token_urlsafe(32)
        session["_csrf"] = token
    return token


def check_csrf() -> None:
    """Reject state-changing requests without a valid token (400)."""
    if request.method != "POST":
        return
    sent = request.form.get("_csrf") or request.headers.get("X-CSRF-Token")
    expected = session.get("_csrf")
    if not expected or not sent or not hmac.compare_digest(str(sent), str(expected)):
        abort(400, description="CSRF token missing or invalid.")


def regenerate_session_on_login() -> None:
    """Prevent session fixation: drop everything issued before authentication.

    The chosen UI language survives the reset (it carries no authority).
    """
    lang = session.get("lang")
    session.clear()
    session["_csrf"] = secrets.token_urlsafe(32)
    if lang:
        session["lang"] = lang


# --------------------------------------------------------------------------- #
# Access control
# --------------------------------------------------------------------------- #

def current_user() -> dict | None:
    return session.get("user")


def login_required(role: str):
    """Enforce authentication *and* role on every protected route."""

    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            user = current_user()
            if not user:
                target = "auth.admin_login" if role == "admin" else "auth.customer_login"
                return redirect(url_for(target, next=request.path))
            if user.get("role") != role:
                abort(403)
            return view(*args, **kwargs)

        return wrapped

    return decorator


def safe_next(target: str | None, default: str) -> str:
    """Only allow local, single-slash redirects (open-redirect protection)."""
    if not target:
        return default
    if not target.startswith("/") or target.startswith("//") or "\\" in target:
        return default
    return target


def csrf_protect_app(app) -> None:
    """Global CSRF validation for every POST request."""
    app.before_request(check_csrf)
