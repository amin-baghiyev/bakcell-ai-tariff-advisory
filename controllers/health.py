"""Health check route (public, no sensitive data)."""

from __future__ import annotations

from flask import Blueprint, jsonify

from repositories.db import connect

health_bp = Blueprint("health", __name__)


@health_bp.route("/health")
def health():
    status = {"status": "ok", "checks": {}}
    try:
        conn = connect()
        try:
            conn.execute("SELECT 1").fetchone()
            status["checks"]["database"] = "ok"
            n = conn.execute("SELECT COUNT(*) AS n FROM customers").fetchone()["n"]
            status["checks"]["customers"] = n
            r = conn.execute("SELECT COUNT(*) AS n FROM tariffs").fetchone()["n"]
            status["checks"]["tariffs"] = r
        finally:
            conn.close()
    except Exception as exc:  # noqa: BLE001 - health must not 500
        status["status"] = "degraded"
        status["checks"]["database"] = f"error: {type(exc).__name__}"
    return jsonify(status), (200 if status["status"] == "ok" else 503)
