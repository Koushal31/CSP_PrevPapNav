"""Authentication and account pages.

Two ways to sign in:
  1. "Continue with Google" (OAuth) — the only way to authenticate with an
     actual Google password, which happens on Google's own page.
  2. Manual email + password — the password is set with PapersNav and stored
     hashed (it is NOT the user's Google password, which no site can verify).

New accounts (either method) are limited to the allowed college email domains.
"""
import datetime
import logging
import random
import re

from flask import (
    Blueprint,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from werkzeug.security import check_password_hash, generate_password_hash

from ..db import db
from ..decorators import login_required
from ..extensions import oauth
from ..models import enrich_paper, get_user_by_email
from ..utils import email_domain_allowed, is_admin_email, send_email, to_object_id, utcnow

logger = logging.getLogger("papersnav")

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

logger = logging.getLogger("papersnav")

auth_bp = Blueprint("auth", __name__)


def _establish_session(user):
    email = user["email"]
    role = user.get("role", "student")
    # Configured admin emails always get the admin role, whichever way they
    # signed in (manual or Google). Persist the promotion the first time.
    if role != "admin" and is_admin_email(email):
        db.users.update_one({"_id": user["_id"]}, {"$set": {"role": "admin"}})
        role = "admin"
    session["user_id"] = str(user["_id"])
    session["email"] = email
    session["name"] = user.get("name", email)
    session["role"] = role


def _post_login_redirect():
    nxt = request.args.get("next") or request.form.get("next")
    if nxt and nxt.startswith("/"):
        return redirect(nxt)
    if session.get("role") == "admin":
        return redirect(url_for("admin.dashboard"))
    return redirect(url_for("main.home"))


def _login_ctx(**extra):
    ctx = {
        "google_enabled": current_app.config.get("GOOGLE_ENABLED", False),
        "allowed_domains": current_app.config.get("ALLOWED_EMAIL_DOMAINS", []),
    }
    ctx.update(extra)
    return ctx


# ── Manual login ─────────────────────────────────────────────────────────────
@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if "user_id" in session:
        return _post_login_redirect()

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        user = get_user_by_email(email)
        if user and user.get("password") and check_password_hash(user["password"], password):
            _establish_session(user)
            return _post_login_redirect()
        return render_template(
            "login.html", **_login_ctx(error="Invalid email or password.", email=email, active_tab="login")
        )

    return render_template("login.html", **_login_ctx(active_tab="login"))


# ── Manual registration (email + app-managed password) ───────────────────────
@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if "user_id" in session:
        return _post_login_redirect()

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        def reg_error(msg):
            return render_template(
                "login.html",
                **_login_ctx(reg_error=msg, active_tab="register", form_data=request.form),
            )

        if not name or not email or not password:
            return reg_error("All fields are required.")
        if not EMAIL_RE.match(email):
            return reg_error("Please enter a valid email address.")
        if len(password) < 6:
            return reg_error("Password must be at least 6 characters.")
        if not email_domain_allowed(email):
            return reg_error("Please register with your college email address.")
        if get_user_by_email(email):
            return reg_error("That email is already registered — try logging in.")

        # Don't create the account yet — email an OTP and verify it first.
        return _start_email_verification(name, email, password)

    return render_template("login.html", **_login_ctx(active_tab="register"))


# ── Email verification (OTP) ─────────────────────────────────────────────────
def _generate_otp():
    return f"{random.randint(0, 999999):06d}"


def _send_otp(email, otp):
    return send_email(
        "Your PapersNav verification code",
        email,
        f"Your PapersNav verification code is: {otp}\n\n"
        "It expires in 10 minutes. If you didn't request this, ignore this email.",
    )


def _start_email_verification(name, email, password):
    otp = _generate_otp()
    db.otp_requests.replace_one(
        {"email": email, "purpose": "register"},
        {
            "email": email,
            "purpose": "register",
            "name": name,
            "password": generate_password_hash(password),
            "otp": otp,
            "attempts": 0,
            "created_at": utcnow(),
            "expires_at": utcnow() + datetime.timedelta(seconds=current_app.config["OTP_TTL"]),
        },
        upsert=True,
    )
    sent = _send_otp(email, otp)
    session["pending_email"] = email
    # In development without SMTP configured, surface the code so the flow is testable.
    if not sent and current_app.config.get("FLASK_ENV") == "development":
        flash(f"[dev] Your verification code is {otp}", "warning")
    return render_template("verify_otp.html", email=email, delivered=sent)


@auth_bp.route("/verify-otp", methods=["GET", "POST"])
def verify_otp():
    email = (request.values.get("email") or session.get("pending_email") or "").strip().lower()
    key = {"email": email, "purpose": "register"}
    pending = db.otp_requests.find_one(key) if email else None
    if not pending:
        flash("No pending verification was found. Please register again.", "error")
        return redirect(url_for("auth.register"))

    exp = pending["expires_at"]
    if exp.tzinfo is None:
        exp = exp.replace(tzinfo=datetime.timezone.utc)
    if exp < utcnow():
        db.otp_requests.delete_one(key)
        flash("Your verification code expired. Please register again.", "error")
        return redirect(url_for("auth.register"))

    if request.method == "POST":
        code = request.form.get("otp", "").strip()
        if pending.get("attempts", 0) >= 5:
            db.otp_requests.delete_one(key)
            flash("Too many incorrect attempts. Please register again.", "error")
            return redirect(url_for("auth.register"))
        if code != pending["otp"]:
            db.otp_requests.update_one(key, {"$inc": {"attempts": 1}})
            return render_template("verify_otp.html", email=email, error="Incorrect code. Try again.")

        # Verified — create the account now (guard against a race).
        if not get_user_by_email(email):
            db.users.insert_one(
                {
                    "name": pending["name"],
                    "email": email,
                    "password": pending["password"],
                    "role": "student",
                    "college": "",
                    "bookmarks": [],
                    "created_at": utcnow(),
                    "auth_provider": "password",
                    "email_verified": True,
                }
            )
        db.otp_requests.delete_one(key)
        session.pop("pending_email", None)
        flash("Email verified! Your account is ready — please log in.", "success")
        return redirect(url_for("auth.login"))

    return render_template("verify_otp.html", email=email, delivered=True)


@auth_bp.route("/resend-otp", methods=["POST"])
def resend_otp():
    email = (request.form.get("email") or session.get("pending_email") or "").strip().lower()
    key = {"email": email, "purpose": "register"}
    pending = db.otp_requests.find_one(key) if email else None
    if not pending:
        flash("No pending verification was found. Please register again.", "error")
        return redirect(url_for("auth.register"))
    otp = _generate_otp()
    db.otp_requests.update_one(
        key,
        {
            "$set": {
                "otp": otp,
                "attempts": 0,
                "expires_at": utcnow() + datetime.timedelta(seconds=current_app.config["OTP_TTL"]),
            }
        },
    )
    sent = _send_otp(email, otp)
    if not sent and current_app.config.get("FLASK_ENV") == "development":
        flash(f"[dev] Your verification code is {otp}", "warning")
    else:
        flash("A new verification code has been sent.", "success")
    return render_template("verify_otp.html", email=email, delivered=sent)


# ── Forgot / reset password (OTP-based) ──────────────────────────────────────
@auth_bp.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if "user_id" in session:
        return _post_login_redirect()

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        user = get_user_by_email(email)
        # Only accounts that have a password can reset one (Google-only accounts
        # don't have a PapersNav password — they should use "Continue with Google").
        if user and user.get("password"):
            otp = _generate_otp()
            db.otp_requests.replace_one(
                {"email": email, "purpose": "reset"},
                {
                    "email": email,
                    "purpose": "reset",
                    "otp": otp,
                    "attempts": 0,
                    "created_at": utcnow(),
                    "expires_at": utcnow() + datetime.timedelta(seconds=current_app.config["OTP_TTL"]),
                },
                upsert=True,
            )
            sent = send_email(
                "Your PapersNav password reset code",
                email,
                f"Your password reset code is: {otp}\n\nIt expires in 10 minutes.\n"
                "If you didn't request this, you can ignore this email.",
            )
            if not sent and current_app.config.get("FLASK_ENV") == "development":
                flash(f"[dev] Your password reset code is {otp}", "warning")
        session["reset_email"] = email
        flash("If an account with that email exists, a reset code has been sent.", "success")
        return redirect(url_for("auth.reset_password"))

    return render_template("forgot_password.html")


@auth_bp.route("/reset-password", methods=["GET", "POST"])
def reset_password():
    email = (request.values.get("email") or session.get("reset_email") or "").strip().lower()
    key = {"email": email, "purpose": "reset"}
    pending = db.otp_requests.find_one(key) if email else None

    if request.method == "POST":
        if not pending:
            flash("Your reset code is invalid or expired. Please request a new one.", "error")
            return redirect(url_for("auth.forgot_password"))

        exp = pending["expires_at"]
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=datetime.timezone.utc)
        if exp < utcnow():
            db.otp_requests.delete_one(key)
            flash("Your reset code expired. Please request a new one.", "error")
            return redirect(url_for("auth.forgot_password"))

        if pending.get("attempts", 0) >= 5:
            db.otp_requests.delete_one(key)
            flash("Too many incorrect attempts. Please request a new code.", "error")
            return redirect(url_for("auth.forgot_password"))

        code = request.form.get("otp", "").strip()
        new = request.form.get("new_password", "")
        confirm = request.form.get("confirm_password", "")

        if code != pending["otp"]:
            db.otp_requests.update_one(key, {"$inc": {"attempts": 1}})
            return render_template("reset_password.html", email=email, error="Incorrect code. Try again.")
        if len(new) < 6:
            return render_template("reset_password.html", email=email, error="Password must be at least 6 characters.")
        if new != confirm:
            return render_template("reset_password.html", email=email, error="Passwords do not match.")

        user = get_user_by_email(email)
        if user:
            db.users.update_one({"_id": user["_id"]}, {"$set": {"password": generate_password_hash(new)}})
        db.otp_requests.delete_one(key)
        session.pop("reset_email", None)
        flash("Password reset successfully. Please log in.", "success")
        return redirect(url_for("auth.login"))

    return render_template("reset_password.html", email=email)


@auth_bp.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("main.home"))


# ── Google OAuth ─────────────────────────────────────────────────────────────
@auth_bp.route("/login/google")
def login_google():
    if "user_id" in session:
        return _post_login_redirect()
    if not current_app.config.get("GOOGLE_ENABLED"):
        flash("Google login is not configured on the server.", "error")
        return redirect(url_for("auth.login"))
    redirect_uri = current_app.config.get("GOOGLE_REDIRECT_URI") or url_for(
        "auth.google_callback", _external=True
    )
    return oauth.google.authorize_redirect(redirect_uri)


@auth_bp.route("/auth/google/callback")
def google_callback():
    if not current_app.config.get("GOOGLE_ENABLED"):
        flash("Google login is not configured on the server.", "error")
        return redirect(url_for("auth.login"))
    try:
        token = oauth.google.authorize_access_token()
        info = token.get("userinfo") or oauth.google.userinfo(token=token)
        email = (info.get("email") or "").strip().lower()
        name = info.get("name")
        if not email:
            raise ValueError("Google account did not return an email")

        user = get_user_by_email(email)
        if not user:
            # New account — only allowed (college) email domains may sign up.
            # Existing accounts (incl. admin) are never blocked by this rule.
            if not email_domain_allowed(email):
                flash("Please sign in with your college email address.", "error")
                return redirect(url_for("auth.login"))
            db.users.insert_one(
                {
                    "name": name or email.split("@")[0],
                    "email": email,
                    "role": "student",
                    "college": "",
                    "bookmarks": [],
                    "created_at": utcnow(),
                    "auth_provider": "google",
                }
            )
            user = get_user_by_email(email)

        _establish_session(user)
        return _post_login_redirect()
    except Exception as exc:
        logger.error("Google OAuth callback error: %s", exc)
        flash("Google login failed. Please try again.", "error")
        return redirect(url_for("auth.login"))


# ── Profile (my uploads + bookmarks) ─────────────────────────────────────────
@auth_bp.route("/profile")
@login_required
def profile():
    email = session.get("email")
    user = db.users.find_one({"_id": to_object_id(session["user_id"])}, {"password": 0})
    if not user:
        session.clear()
        flash("Your session has expired. Please sign in again.", "warning")
        return redirect(url_for("auth.login"))

    my_uploads = list(db.papers.find({"uploaded_by": email}).sort("uploaded_at", -1))
    for p in my_uploads:
        enrich_paper(p)

    bookmark_ids = [oid for oid in (to_object_id(b) for b in user.get("bookmarks", [])) if oid]
    saved = list(db.papers.find({"_id": {"$in": bookmark_ids}, "status": "approved"}))
    for p in saved:
        enrich_paper(p)

    counts = {
        "total": len(my_uploads),
        "approved": sum(1 for p in my_uploads if p.get("status") == "approved"),
        "pending": sum(1 for p in my_uploads if p.get("status") == "pending"),
        "rejected": sum(1 for p in my_uploads if p.get("status") == "rejected"),
    }
    return render_template(
        "profile.html", user=user, my_uploads=my_uploads, saved=saved, counts=counts
    )


# ── Account settings ─────────────────────────────────────────────────────────
@auth_bp.route("/account")
@login_required
def account():
    user = db.users.find_one(
        {"_id": to_object_id(session["user_id"])},
        {"password": 1, "name": 1, "email": 1, "college": 1, "role": 1, "auth_provider": 1},
    )
    if not user:
        session.clear()
        flash("Your session has expired. Please sign in again.", "warning")
        return redirect(url_for("auth.login"))
    colleges = list(db.colleges.find({}, {"_id": 0, "name": 1}).sort("name", 1))
    has_password = bool(user.get("password"))
    return render_template("account.html", user=user, colleges=colleges, has_password=has_password)


@auth_bp.route("/account/profile", methods=["POST"])
@login_required
def update_profile():
    name = request.form.get("name", "").strip()
    college = request.form.get("college", "").strip()
    if not name:
        flash("Name cannot be empty.", "error")
        return redirect(url_for("auth.account"))
    db.users.update_one(
        {"_id": to_object_id(session["user_id"])},
        {"$set": {"name": name, "college": college}},
    )
    session["name"] = name
    flash("Profile updated.", "success")
    return redirect(url_for("auth.account"))


@auth_bp.route("/account/password", methods=["POST"])
@login_required
def change_password():
    user = db.users.find_one({"_id": to_object_id(session["user_id"])})
    if not user:
        session.clear()
        return redirect(url_for("auth.login"))
    current = request.form.get("current_password", "")
    new = request.form.get("new_password", "")
    confirm = request.form.get("confirm_password", "")
    has_password = bool(user.get("password"))

    if has_password and not check_password_hash(user["password"], current):
        flash("Your current password is incorrect.", "error")
        return redirect(url_for("auth.account"))
    if len(new) < 6:
        flash("New password must be at least 6 characters.", "error")
        return redirect(url_for("auth.account"))
    if new != confirm:
        flash("New passwords do not match.", "error")
        return redirect(url_for("auth.account"))

    db.users.update_one(
        {"_id": user["_id"]}, {"$set": {"password": generate_password_hash(new)}}
    )
    flash("Password updated successfully.", "success")
    return redirect(url_for("auth.account"))
