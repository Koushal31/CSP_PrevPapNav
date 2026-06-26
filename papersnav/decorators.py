"""Route guards for authenticated and admin-only views."""
import functools
import logging

from flask import abort, flash, redirect, request, session, url_for

logger = logging.getLogger("papersnav")


def login_required(view):
    @functools.wraps(view)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in to access this page.", "warning")
            return redirect(url_for("auth.login", next=request.path))
        return view(*args, **kwargs)

    return wrapped


def admin_required(view):
    @functools.wraps(view)
    def wrapped(*args, **kwargs):
        if "user_id" not in session or session.get("role") != "admin":
            logger.warning("Unauthorized admin access attempt from %s", request.remote_addr)
            abort(403)
        return view(*args, **kwargs)

    return wrapped
