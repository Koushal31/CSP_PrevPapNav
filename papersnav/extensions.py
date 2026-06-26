"""Shared extension instances.

These are created unbound here and wired to the app inside the factory
(create_app). Importing them from a single module avoids circular imports
between blueprints and the application package.
"""
import logging

from authlib.integrations.flask_client import OAuth
from flask_wtf import CSRFProtect

try:
    from flask_mail import Mail
except Exception:  # pragma: no cover - Flask-Mail is optional at import time
    Mail = None

logger = logging.getLogger("papersnav")

oauth = OAuth()
mail = Mail() if Mail else None
csrf = CSRFProtect()
