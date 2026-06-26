"""Public, content-light pages: landing, about, contact, plus a health probe."""
import re

from flask import (
    Blueprint,
    current_app,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

from ..db import db
from ..utils import send_email, utcnow

main_bp = Blueprint("main", __name__)

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


@main_bp.route("/healthz")
def healthz():
    """Lightweight liveness/readiness probe — verifies the DB responds."""
    try:
        db.handle.command("ping")
        return jsonify({"status": "ok", "database": "up"})
    except Exception:
        return jsonify({"status": "degraded", "database": "down"}), 503


@main_bp.route("/")
def home():
    total_papers = db.papers.count_documents({"status": "approved"})
    total_colleges = db.colleges.count_documents({})
    total_users = db.users.count_documents({})
    colleges = list(db.colleges.find({}, {"_id": 0, "name": 1, "code": 1}).sort("name", 1))
    branches = list(
        db.branches.find({}, {"_id": 0, "name": 1, "code": 1, "college_code": 1}).sort(
            [("college_code", 1), ("name", 1)]
        )
    )
    return render_template(
        "home.html",
        total_papers=total_papers,
        total_colleges=total_colleges,
        total_users=total_users,
        colleges=colleges,
        branches=branches,
        semesters=list(range(1, 9)),
    )


@main_bp.route("/about")
def about():
    return render_template("about.html")


@main_bp.route("/contact", methods=["GET", "POST"])
def contact():
    prefill = {"name": session.get("name", ""), "email": session.get("email", "")}

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        subject = request.form.get("subject", "").strip()
        message = request.form.get("message", "").strip()

        if not name or not email or not message:
            flash("Please fill in your name, email and message.", "error")
            return render_template("contact.html", form={"name": name, "email": email, "subject": subject, "message": message})
        if not EMAIL_RE.match(email):
            flash("Please enter a valid email address.", "error")
            return render_template("contact.html", form={"name": name, "email": email, "subject": subject, "message": message})
        if len(message) > 4000:
            flash("Message is too long (max 4000 characters).", "error")
            return render_template("contact.html", form={"name": name, "email": email, "subject": subject, "message": message})

        db.messages.insert_one(
            {
                "name": name,
                "email": email,
                "subject": subject or "(no subject)",
                "message": message,
                "user_id": session.get("user_id"),
                "resolved": False,
                "created_at": utcnow(),
            }
        )
        # Best-effort notify the admins.
        admins = current_app.config.get("ADMIN_EMAILS") or []
        send_email(
            f"[PapersNav contact] {subject or 'New message'}",
            admins,
            f"From: {name} <{email}>\n\n{message}",
        )
        flash("Thanks! Your message has been sent to the admin.", "success")
        return redirect(url_for("main.contact"))

    return render_template("contact.html", form=prefill)
