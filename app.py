"""Tariff Advisor — Flask application factory and entry point.

Run:  python app.py   (or  flask --app app run)
"""

from __future__ import annotations

import os
from datetime import date

from flask import Flask, render_template

from config import Config
from controllers.admin_controller import admin_bp
from controllers.auth_controller import auth_bp, ensure_demo_users
from controllers.customer_controller import customer_bp
from controllers.health import health_bp
from controllers.security import csrf_protect_app, csrf_token
from i18n import DEFAULT_LOCALE, describe_reasons, get_locale, translate
from repositories.db import setup
from services.import_service import import_workbook, inspect_workbook
from services.notification_service import localized_message, run_reminders
from services.pipeline import build_recommendations


def create_app(config_object=Config) -> Flask:
    app = Flask(__name__)
    app.config.from_object(config_object)
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    # SESSION_COOKIE_SECURE should be 1 in production (HTTPS); demo runs on http.
    app.config.setdefault("SESSION_COOKIE_SECURE", os.environ.get("SESSION_COOKIE_SECURE", "0") == "1")
    app.config["TEMPLATES_AUTO_RELOAD"] = True

    csrf_protect_app(app)
    app.jinja_env.globals["csrf_token"] = csrf_token
    # i18n: per-request translation helpers (locale comes from the session)
    app.jinja_env.globals["tr"] = lambda k, **params: translate(get_locale(), k, **params)
    app.jinja_env.globals["reasons"] = lambda codes: describe_reasons(codes, get_locale())
    app.jinja_env.globals["notif_text"] = lambda n: localized_message(n, get_locale())
    app.jinja_env.globals["demo_mode"] = bool(config_object.DEMO_MODE)
    app.jinja_env.globals["today_str"] = date.today().isoformat()

    @app.context_processor
    def _inject_locale():  # noqa: ANN202
        return {"locale": get_locale(), "default_locale": DEFAULT_LOCALE}

    # Ensure schema + documented demo accounts exist on every boot (demo mode).
    if config_object.DEMO_MODE:
        try:
            setup()
            ensure_demo_users()
        except Exception as exc:  # noqa: BLE001 — never block app start with a traceback
            app.logger.warning("demo user bootstrap skipped: %s", type(exc).__name__)

    app.register_blueprint(auth_bp)
    app.register_blueprint(customer_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(health_bp)

    @app.errorhandler(403)
    def forbidden(e):  # noqa: ANN001
        return render_template("errors/error.html", code=403,
                               message=translate(get_locale(), "error.403")), 403

    @app.errorhandler(404)
    def not_found(e):  # noqa: ANN001
        return render_template("errors/error.html", code=404,
                               message=translate(get_locale(), "error.404")), 404

    @app.errorhandler(400)
    def bad_request(e):  # noqa: ANN001
        return render_template("errors/error.html", code=400,
                               message=translate(get_locale(), "error.400")), 400

    @app.errorhandler(500)
    def internal(e):  # noqa: ANN001
        # never expose stack traces or secrets in the UI
        return render_template("errors/error.html", code=500,
                               message=translate(get_locale(), "error.500")), 500

    _register_cli(app)
    return app


def _register_cli(app: Flask) -> None:
    @app.cli.command("init-db")
    def init_db_command():
        """Create schema + demo login accounts."""
        setup()
        ensure_demo_users()
        print(f"Database ready: {app.config['DATABASE_PATH']}")

    @app.cli.command("import-data")
    def import_data_command():
        """Import the workbook and print the import report summary."""
        conn = setup()
        try:
            report = import_workbook(conn)
            print(f"customers={report['counts']['customers_imported']} "
                  f"tariffs={report['counts']['tariffs_imported']} "
                  f"usage_rows={report['counts']['usage_rows_imported']} "
                  f"rejected={report['counts']['rejected_rows']} "
                  f"checks_passed={report['checks']['passed']}")
        finally:
            conn.close()

    @app.cli.command("recommendations")
    def recommendations_command():
        """(Re)generate recommendation snapshots for every usable customer."""
        conn = setup()
        try:
            result = build_recommendations(conn)
            print(f"created={result['created']} failed={result['failed']} "
                  f"skipped={len(result['skipped'])} model={result['model_version']}")
        finally:
            conn.close()

    @app.cli.command("reminders")
    def reminders_command():
        """Run the five-day reminder job (idempotent)."""
        conn = setup()
        try:
            report = run_reminders(conn)
            print(f"created={report['totals']['created']} "
                  f"already_existed={report['totals']['already_existed']} "
                  f"skipped={report['totals']['skipped']} "
                  f"outside_window={report['totals']['outside_window']}")
        finally:
            conn.close()


app = create_app()  # module-level app for `flask --app app` and tests

if __name__ == "__main__":
    app.run(
        host=os.environ.get("HOST", "127.0.0.1"),
        port=int(os.environ.get("PORT", "5000")),
        debug=os.environ.get("FLASK_DEBUG", "0") == "1",
    )
