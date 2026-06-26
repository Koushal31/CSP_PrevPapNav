"""Application factory for PapersNav.

Usage:
    from papersnav import create_app
    app = create_app()
"""
import logging
import os
import sys

from dotenv import load_dotenv
from flask import render_template, session

from .config import Config
from .db import db
from .extensions import csrf, mail, oauth

__version__ = "2.0.0"

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def _configure_logging():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
        stream=sys.stdout,
    )


def create_app(config_object=None):
    load_dotenv()
    _configure_logging()
    logger = logging.getLogger("papersnav")

    from flask import Flask

    app = Flask(
        __name__,
        template_folder=os.path.join(BASE_DIR, "templates"),
        static_folder=os.path.join(BASE_DIR, "static"),
    )
    app.config.from_object(config_object or Config)

    # ── Required secrets ──────────────────────────────────────────────────
    if not app.config.get("SECRET_KEY"):
        raise ValueError("SECRET_KEY environment variable is required")

    # ── Resolve + create the upload folder ────────────────────────────────
    upload_folder = app.config.get("UPLOAD_FOLDER") or os.path.join(
        BASE_DIR, "static", "uploads"
    )
    app.config["UPLOAD_FOLDER"] = upload_folder
    os.makedirs(upload_folder, exist_ok=True)

    # ── Extensions ────────────────────────────────────────────────────────
    db.init_app(app)
    oauth.init_app(app)
    csrf.init_app(app)
    if mail is not None:
        mail.init_app(app)

    _register_google_oauth(app, logger)

    # ── Blueprints ────────────────────────────────────────────────────────
    from .blueprints.main import main_bp
    from .blueprints.auth import auth_bp
    from .blueprints.papers import papers_bp
    from .blueprints.admin import admin_bp
    from .blueprints.community import community_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(papers_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(community_bp)

    _register_context(app)
    _register_error_handlers(app)
    _register_cli(app)

    # ── Startup bootstrap ─────────────────────────────────────────────────
    from .seed import sync_admins

    with app.app_context():
        sync_admins(app)

    logger.info("PapersNav %s ready (env=%s)", __version__, app.config.get("FLASK_ENV"))
    return app


def _register_google_oauth(app, logger):
    cfg = app.config
    if cfg.get("GOOGLE_CLIENT_ID") and cfg.get("GOOGLE_CLIENT_SECRET") and cfg.get("GOOGLE_REDIRECT_URI"):
        oauth.register(
            name="google",
            client_id=cfg["GOOGLE_CLIENT_ID"],
            client_secret=cfg["GOOGLE_CLIENT_SECRET"],
            server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
            client_kwargs={"scope": "openid email profile"},
        )
        app.config["GOOGLE_ENABLED"] = True
    else:
        app.config["GOOGLE_ENABLED"] = False
        logger.warning(
            "Google OAuth not configured. Set GOOGLE_CLIENT_ID, "
            "GOOGLE_CLIENT_SECRET and GOOGLE_REDIRECT_URI to enable it."
        )


def _register_cli(app):
    @app.cli.command("seed")
    def seed():
        """Populate the database with starter colleges, branches and subjects."""
        from .seed_data import seed_database

        created = seed_database()
        print("Seeded:", created)

    @app.cli.command("seed-viit")
    def seed_viit_cmd():
        """Add all VIIT (Vignan's IIT, Visakhapatnam) branches and subjects."""
        from .seed_viit import seed_viit

        created = seed_viit()
        print("Seeded VIIT:", created)

    @app.cli.command("seed-view")
    def seed_view_cmd():
        """Add all VIEW (Vignan's Engineering for Women) branches and subjects."""
        from .seed_view import seed_view

        created = seed_view()
        print("Seeded VIEW:", created)

    @app.cli.command("reset-academic")
    def reset_academic_cmd():
        """Delete all colleges, branches and subjects (keeps users and papers)."""
        from .reset_db import reset_academic

        result = reset_academic()
        print("Reset academic data (deleted):", result)


def _register_context(app):
    @app.context_processor
    def inject_globals():
        pending_count = 0
        if session.get("role") == "admin":
            try:
                pending_count = db.papers.count_documents({"status": "pending"})
            except Exception:
                pending_count = 0
        return {
            "admin_pending_count": pending_count,
            "google_enabled": app.config.get("GOOGLE_ENABLED", False),
            "app_version": __version__,
        }


def _register_error_handlers(app):
    @app.errorhandler(404)
    def not_found(_error):
        return render_template("error.html", code=404, message="Page not found"), 404

    @app.errorhandler(403)
    def forbidden(_error):
        return render_template("error.html", code=403, message="Access denied"), 403

    @app.errorhandler(500)
    def server_error(error):
        logging.getLogger("papersnav").error("Internal server error: %s", error)
        return render_template("error.html", code=500, message="Server error"), 500

    from flask_wtf.csrf import CSRFError

    @app.errorhandler(CSRFError)
    def handle_csrf_error(error):
        return render_template(
            "error.html", code=400, message="Your session expired or the form token was invalid. Please go back and try again."
        ), 400
