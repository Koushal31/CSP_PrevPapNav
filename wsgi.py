"""Production entry point for WSGI servers, e.g. ``gunicorn wsgi:app``."""
from papersnav import create_app

app = create_app()
