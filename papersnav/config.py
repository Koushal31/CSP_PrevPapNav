"""Application configuration.

All settings are read from environment variables (loaded from a .env file in
development). Keeping config in one place makes the rest of the codebase free
of os.environ lookups.
"""
import os

from dotenv import load_dotenv

# Load the project's .env BEFORE the Config values below are evaluated.
# (Config attributes are read at import time, so the .env must be loaded first.)
_ENV_PATH = os.path.join(os.path.dirname(__file__), "..", ".env")
load_dotenv(_ENV_PATH)


def _as_bool(value, default=False):
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


class Config:
    # ── Core Flask ────────────────────────────────────────────────────────
    SECRET_KEY = os.environ.get("SECRET_KEY")
    FLASK_ENV = os.environ.get("FLASK_ENV", "production")
    DEBUG = FLASK_ENV == "development"

    # ── Sessions / cookies ────────────────────────────────────────────────
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = FLASK_ENV == "production"

    # ── Uploads ───────────────────────────────────────────────────────────
    UPLOAD_FOLDER = os.environ.get("UPLOAD_FOLDER")  # resolved in create_app
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16 MB
    ALLOWED_EXTENSIONS = {"pdf"}

    # ── Database ──────────────────────────────────────────────────────────
    MONGO_URI = os.environ.get("MONGO_URI")
    MONGO_DB_NAME = os.environ.get("MONGO_DB_NAME", "previous_papers_navigator")

    # ── Pagination ────────────────────────────────────────────────────────
    PAPERS_PER_PAGE = int(os.environ.get("PAPERS_PER_PAGE", "9"))

    # ── Allowed email domains ─────────────────────────────────────────────
    # Comma-separated list (e.g. "vit.ac.in,annauniv.edu"). When set, only
    # these domains may register or sign in with Google. Empty = allow any.
    ALLOWED_EMAIL_DOMAINS = [
        d.strip().lower().lstrip("@")
        for d in os.environ.get("ALLOWED_EMAIL_DOMAINS", "").split(",")
        if d.strip()
    ]

    # ── Admins ────────────────────────────────────────────────────────────
    # Any email listed here is granted the admin role automatically whenever
    # they sign in (manual or Google). Comma-separated for multiple admins.
    ADMIN_EMAILS = [
        e.strip().lower()
        for e in os.environ.get("ADMIN_EMAILS", "").split(",")
        if e.strip()
    ]

    # ── Google OAuth ──────────────────────────────────────────────────────
    GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID")
    GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET")
    GOOGLE_REDIRECT_URI = os.environ.get("GOOGLE_REDIRECT_URI")

    # ── Email (SMTP, used for password reset + upload notifications) ───────
    MAIL_SERVER = os.environ.get("MAIL_SERVER")
    MAIL_PORT = int(os.environ.get("MAIL_PORT", "587"))
    MAIL_USE_TLS = _as_bool(os.environ.get("MAIL_USE_TLS"), True)
    MAIL_USE_SSL = _as_bool(os.environ.get("MAIL_USE_SSL"), False)
    MAIL_USERNAME = os.environ.get("MAIL_USERNAME")
    MAIL_PASSWORD = os.environ.get("MAIL_PASSWORD")
    MAIL_DEFAULT_SENDER = os.environ.get("MAIL_DEFAULT_SENDER") or os.environ.get("MAIL_USERNAME")

    # Token lifetime for password-reset links (seconds)
    RESET_TOKEN_TTL = int(os.environ.get("RESET_TOKEN_TTL", str(60 * 60)))  # 1 hour

    # Email verification OTP lifetime (seconds)
    OTP_TTL = int(os.environ.get("OTP_TTL", "600"))  # 10 minutes

    @property
    def google_enabled(self):
        return bool(self.GOOGLE_CLIENT_ID and self.GOOGLE_CLIENT_SECRET and self.GOOGLE_REDIRECT_URI)

    @property
    def mail_enabled(self):
        return bool(self.MAIL_SERVER and self.MAIL_USERNAME and self.MAIL_PASSWORD)
