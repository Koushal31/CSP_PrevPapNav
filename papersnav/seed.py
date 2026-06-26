"""Startup bootstrap for admins.

Admins are defined purely by the ADMIN_EMAILS config. There is no seeded
password account: an admin simply signs in (Google or manual) and is granted
the admin role automatically (see auth._establish_session). On startup we also
promote any *existing* user whose email is in ADMIN_EMAILS, in case they had
already registered as a student.
"""
import logging

from .db import db

logger = logging.getLogger("papersnav")


def sync_admins(app):
    emails = app.config.get("ADMIN_EMAILS") or []
    if not emails:
        logger.warning("No ADMIN_EMAILS configured — no one will have admin access.")
        return
    try:
        result = db.users.update_many(
            {"email": {"$in": emails}, "role": {"$ne": "admin"}},
            {"$set": {"role": "admin"}},
        )
        if result.modified_count:
            logger.info("Promoted %s existing user(s) to admin", result.modified_count)
        logger.info("Admin emails: %s", ", ".join(emails))
    except Exception as exc:  # non-fatal
        logger.error("Error syncing admins: %s", exc)
