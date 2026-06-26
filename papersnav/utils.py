"""Small, dependency-light helpers shared across blueprints."""
import datetime
import logging

from bson.objectid import ObjectId
from flask import current_app

from .extensions import mail

logger = logging.getLogger("papersnav")


def utcnow():
    """Timezone-aware UTC timestamp."""
    return datetime.datetime.now(datetime.timezone.utc)


def allowed_file(filename):
    exts = current_app.config["ALLOWED_EXTENSIONS"]
    return "." in filename and filename.rsplit(".", 1)[1].lower() in exts


def email_domain_allowed(email):
    """True if the email's domain is permitted.

    When ALLOWED_EMAIL_DOMAINS is empty, any domain is allowed. Otherwise the
    domain (or a subdomain of it) must be in the list — e.g. "vit.ac.in" also
    permits "student.vit.ac.in".
    """
    domains = current_app.config.get("ALLOWED_EMAIL_DOMAINS") or []
    if not domains:
        return True
    part = (email or "").strip().lower().rsplit("@", 1)[-1]
    return any(part == d or part.endswith("." + d) for d in domains)


def is_admin_email(email):
    """True if this email is configured as an admin (ADMIN_EMAILS)."""
    admins = current_app.config.get("ADMIN_EMAILS") or []
    return (email or "").strip().lower() in admins


def to_object_id(value):
    """Parse a string into an ObjectId, returning None when invalid."""
    try:
        return ObjectId(value)
    except Exception:
        return None


def stringify_id(doc):
    """Mutate a Mongo document so its ``_id`` is a plain string. Returns it."""
    if doc and "_id" in doc:
        doc["_id"] = str(doc["_id"])
    return doc


def send_email(subject, recipients, body, html=None):
    """Send an email if SMTP is configured; otherwise log and skip.

    Never raises — email is best-effort so it can't break a request.
    """
    if isinstance(recipients, str):
        recipients = [recipients]
    recipients = [r for r in recipients if r]
    if not recipients:
        return False

    if not current_app.config.get("MAIL_SERVER") or mail is None:
        logger.info("Email skipped (SMTP not configured): %s -> %s", subject, recipients)
        return False

    try:
        from flask_mail import Message

        msg = Message(subject=subject, recipients=recipients, body=body, html=html)
        mail.send(msg)
        logger.info("Email sent: %s -> %s", subject, recipients)
        return True
    except Exception as exc:  # pragma: no cover
        logger.error("Failed to send email '%s': %s", subject, exc)
        return False
