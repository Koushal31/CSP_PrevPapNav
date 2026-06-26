"""Admin panel: review queue, paper moderation, and management of colleges,
branches, subjects and users.
"""
import logging
import os

from flask import (
    Blueprint,
    abort,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    send_from_directory,
    session,
    url_for,
)

from ..db import db
from ..decorators import admin_required
from ..models import enrich_paper
from ..utils import send_email, stringify_id, to_object_id

logger = logging.getLogger("papersnav")

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


def _notify_uploader(paper, decision):
    """Best-effort email to the uploader when a paper is approved/rejected."""
    email = paper.get("uploaded_by")
    if not email:
        return
    verb = "approved and is now live" if decision == "approved" else "reviewed and not approved"
    send_email(
        f"Your paper upload was {decision}",
        email,
        f"Hi,\n\nYour upload \"{paper.get('subject')}\" "
        f"({paper.get('college')} · {paper.get('branch')} · Sem {paper.get('semester')} · "
        f"{paper.get('year')}) has been {verb}.\n\n— PapersNav",
    )


# ── Dashboard ────────────────────────────────────────────────────────────────
@admin_bp.route("/")
@admin_required
def dashboard():
    recent_pending = list(db.papers.find({"status": "pending"}).sort("uploaded_at", -1).limit(10))
    for p in recent_pending:
        stringify_id(p)
    return render_template(
        "admin/dashboard.html",
        total_papers=db.papers.count_documents({"status": "approved"}),
        pending_papers=db.papers.count_documents({"status": "pending"}),
        total_users=db.users.count_documents({}),
        total_branches=db.branches.count_documents({}),
        total_colleges=db.colleges.count_documents({}),
        total_subjects=db.subjects.count_documents({}),
        recent_pending=recent_pending,
    )


# ── Papers ───────────────────────────────────────────────────────────────────
@admin_bp.route("/papers")
@admin_required
def papers():
    status_filter = request.args.get("status", "all")
    query = {} if status_filter == "all" else {"status": status_filter}
    rows = list(db.papers.find(query).sort("uploaded_at", -1))
    for p in rows:
        stringify_id(p)
    return render_template("admin/papers.html", papers=rows, status_filter=status_filter)


@admin_bp.route("/paper/<paper_id>")
@admin_required
def view_paper(paper_id):
    oid = to_object_id(paper_id)
    if oid is None:
        abort(404)
    paper = db.papers.find_one({"_id": oid})
    if not paper:
        abort(404)
    enrich_paper(paper)
    return render_template("admin/view_paper.html", paper=paper)


@admin_bp.route("/paper/<paper_id>/approve", methods=["POST"])
@admin_required
def approve_paper(paper_id):
    oid = to_object_id(paper_id)
    if oid is None:
        abort(404)
    paper = db.papers.find_one({"_id": oid})
    if paper:
        db.papers.update_one({"_id": oid}, {"$set": {"status": "approved"}})
        _notify_uploader(paper, "approved")
    return redirect(request.referrer or url_for("admin.dashboard"))


@admin_bp.route("/paper/<paper_id>/reject", methods=["POST"])
@admin_required
def reject_paper(paper_id):
    oid = to_object_id(paper_id)
    if oid is None:
        abort(404)
    paper = db.papers.find_one({"_id": oid})
    if paper:
        db.papers.update_one({"_id": oid}, {"$set": {"status": "rejected"}})
        _notify_uploader(paper, "rejected")
    return redirect(request.referrer or url_for("admin.dashboard"))


@admin_bp.route("/paper/<paper_id>/delete", methods=["POST"])
@admin_required
def delete_paper(paper_id):
    oid = to_object_id(paper_id)
    if oid is None:
        abort(404)
    paper = db.papers.find_one({"_id": oid})
    if paper and paper.get("filename"):
        filepath = os.path.join(current_app.config["UPLOAD_FOLDER"], paper["filename"])
        if os.path.exists(filepath):
            os.remove(filepath)
    db.papers.delete_one({"_id": oid})
    db.comments.delete_many({"paper_id": paper_id})
    return redirect(request.referrer or url_for("admin.papers"))


@admin_bp.route("/paper/<paper_id>/download")
@admin_required
def download_paper(paper_id):
    oid = to_object_id(paper_id)
    if oid is None:
        abort(404)
    paper = db.papers.find_one({"_id": oid})
    if not paper or not paper.get("filename"):
        abort(404)
    filepath = os.path.join(current_app.config["UPLOAD_FOLDER"], paper["filename"])
    if not os.path.exists(filepath):
        abort(404)
    return send_from_directory(current_app.config["UPLOAD_FOLDER"], paper["filename"], as_attachment=True)


# ── Colleges ─────────────────────────────────────────────────────────────────
@admin_bp.route("/colleges", methods=["GET", "POST"])
@admin_required
def colleges():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        code = request.form.get("code", "").strip().upper()
        city = request.form.get("city", "").strip()
        if not name or not code:
            flash("College name and code are required.", "error")
        elif db.colleges.find_one({"code": code}):
            flash(f"College code '{code}' already exists.", "error")
        else:
            db.colleges.insert_one({"name": name, "code": code, "city": city})
            flash(f"College '{name}' added successfully.", "success")
        return redirect(url_for("admin.colleges"))

    rows = list(db.colleges.find().sort("name", 1))
    for c in rows:
        stringify_id(c)
        c["paper_count"] = db.papers.count_documents({"college": c["name"], "status": "approved"})
    return render_template("admin/colleges.html", colleges=rows)


@admin_bp.route("/college/<college_id>/delete", methods=["POST"])
@admin_required
def delete_college(college_id):
    oid = to_object_id(college_id)
    college = db.colleges.find_one({"_id": oid}) if oid else None
    if not college:
        abort(404)
    if db.papers.count_documents({"college": college["name"]}) or db.branches.count_documents(
        {"college_code": college["code"]}
    ):
        flash("Cannot delete this college because branches or papers are still associated with it.", "error")
        return redirect(url_for("admin.colleges"))
    db.colleges.delete_one({"_id": oid})
    flash(f"College '{college['name']}' deleted successfully.", "success")
    return redirect(url_for("admin.colleges"))


# ── Branches ─────────────────────────────────────────────────────────────────
@admin_bp.route("/branches", methods=["GET", "POST"])
@admin_required
def branches():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        code = request.form.get("code", "").strip().upper()
        college_code = request.form.get("college_code", "").strip().upper()
        if not name or not code or not college_code:
            flash("Branch name, code, and college are required.", "error")
        elif not db.colleges.find_one({"code": college_code}):
            flash(f"College code '{college_code}' does not exist.", "error")
        elif db.branches.find_one({"code": code, "college_code": college_code}):
            flash(f"Branch code '{code}' already exists for this college.", "error")
        else:
            db.branches.insert_one({"name": name, "code": code, "college_code": college_code})
            flash(f"Branch '{name}' added successfully.", "success")
        return redirect(url_for("admin.branches"))

    rows = list(db.branches.find().sort([("college_code", 1), ("name", 1)]))
    college_map = {c["code"]: c["name"] for c in db.colleges.find({}, {"code": 1, "name": 1})}
    for b in rows:
        stringify_id(b)
        b["college_name"] = college_map.get(b.get("college_code"), "Unknown")
    college_list = list(db.colleges.find({}, {"_id": 0, "name": 1, "code": 1}).sort("name", 1))
    return render_template("admin/branches.html", branches=rows, colleges=college_list)


@admin_bp.route("/branches/<branch_id>/delete", methods=["POST"])
@admin_required
def delete_branch(branch_id):
    oid = to_object_id(branch_id)
    branch = db.branches.find_one({"_id": oid}) if oid else None
    if not branch:
        abort(404)
    if db.papers.count_documents({"branch": branch["code"]}) or db.subjects.count_documents(
        {"branch_code": branch["code"]}
    ):
        flash("Cannot delete this branch because papers or subjects are still associated with it.", "error")
        return redirect(url_for("admin.branches"))
    db.branches.delete_one({"_id": oid})
    flash(f"Branch '{branch['name']}' deleted successfully.", "success")
    return redirect(url_for("admin.branches"))


# ── Subjects ─────────────────────────────────────────────────────────────────
@admin_bp.route("/subjects", methods=["GET", "POST"])
@admin_required
def subjects():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        college_code = request.form.get("college_code", "").strip().upper()
        branch_code = request.form.get("branch_code", "").strip().upper()
        semester = request.form.get("semester", "").strip()

        if not name or not college_code or not branch_code or not semester:
            flash("Subject name, college, branch, and semester are required.", "error")
            return redirect(url_for("admin.subjects"))
        try:
            semester_num = int(semester)
        except ValueError:
            flash("Semester must be a number.", "error")
            return redirect(url_for("admin.subjects"))
        if not 1 <= semester_num <= 10:
            flash("Semester must be between 1 and 10.", "error")
        elif not db.colleges.find_one({"code": college_code}):
            flash(f"College code '{college_code}' does not exist.", "error")
        elif not db.branches.find_one({"code": branch_code, "college_code": college_code}):
            flash(f"Branch code '{branch_code}' does not exist for the selected college.", "error")
        elif db.subjects.find_one(
            {"name": name, "college_code": college_code, "branch_code": branch_code, "semester": semester_num}
        ):
            flash("This subject already exists for the selected college, branch, and semester.", "error")
        else:
            db.subjects.insert_one(
                {"name": name, "college_code": college_code, "branch_code": branch_code, "semester": semester_num}
            )
            flash(f"Subject '{name}' added successfully.", "success")
        return redirect(url_for("admin.subjects"))

    college_list = list(db.colleges.find({}, {"_id": 0, "name": 1, "code": 1}).sort("name", 1))
    branch_list = list(
        db.branches.find({}, {"_id": 0, "name": 1, "code": 1, "college_code": 1}).sort(
            [("college_code", 1), ("name", 1)]
        )
    )
    rows = list(db.subjects.find().sort([("college_code", 1), ("branch_code", 1), ("semester", 1), ("name", 1)]))

    college_map = {c["code"]: c["name"] for c in college_list}
    branch_map = {(b["college_code"], b["code"]): b for b in branch_list}
    for s in rows:
        stringify_id(s)
        college_key = s.get("college_code", "")
        branch = branch_map.get((college_key, s.get("branch_code", "")))
        if not branch:
            fallback = next((b for b in branch_list if b["code"] == s.get("branch_code")), None)
            if fallback:
                branch = fallback
                college_key = branch.get("college_code", "")
                s["college_code"] = college_key
        s["branch_name"] = branch["name"] if branch else "Unknown"
        s["college_name"] = college_map.get(college_key, "Unknown")

    return render_template("admin/subjects.html", subjects=rows, branches=branch_list, colleges=college_list)


@admin_bp.route("/subjects/<subject_id>/delete", methods=["POST"])
@admin_required
def delete_subject(subject_id):
    oid = to_object_id(subject_id)
    subject = db.subjects.find_one({"_id": oid}) if oid else None
    if not subject:
        abort(404)
    db.subjects.delete_one({"_id": oid})
    flash(f"Subject '{subject['name']}' deleted successfully.", "success")
    return redirect(url_for("admin.subjects"))


# ── Users ────────────────────────────────────────────────────────────────────
@admin_bp.route("/users")
@admin_required
def users():
    rows = list(db.users.find({}, {"password": 0}).sort("created_at", -1))
    for u in rows:
        stringify_id(u)
    return render_template("admin/users.html", users=rows)


@admin_bp.route("/user/<user_id>/delete", methods=["POST"])
@admin_required
def delete_user(user_id):
    oid = to_object_id(user_id)
    if oid is None:
        abort(404)
    if str(oid) == session.get("user_id"):
        flash("You cannot delete your own account.", "error")
        return redirect(url_for("admin.users"))
    db.users.delete_one({"_id": oid})
    return redirect(url_for("admin.users"))


@admin_bp.route("/user/<user_id>/promote", methods=["POST"])
@admin_required
def promote_to_admin(user_id):
    oid = to_object_id(user_id)
    if oid is None:
        abort(404)
    db.users.update_one({"_id": oid}, {"$set": {"role": "admin"}})
    return redirect(url_for("admin.users"))


# ── Contact messages ─────────────────────────────────────────────────────────
@admin_bp.route("/messages")
@admin_required
def messages():
    rows = list(db.messages.find().sort("created_at", -1))
    for m in rows:
        stringify_id(m)
    return render_template("admin/messages.html", messages=rows)


@admin_bp.route("/message/<message_id>/resolve", methods=["POST"])
@admin_required
def resolve_message(message_id):
    oid = to_object_id(message_id)
    if oid is None:
        abort(404)
    msg = db.messages.find_one({"_id": oid})
    new_state = not (msg or {}).get("resolved", False)
    db.messages.update_one({"_id": oid}, {"$set": {"resolved": new_state}})
    return redirect(url_for("admin.messages"))


@admin_bp.route("/message/<message_id>/delete", methods=["POST"])
@admin_required
def delete_message(message_id):
    oid = to_object_id(message_id)
    if oid is None:
        abort(404)
    db.messages.delete_one({"_id": oid})
    return redirect(url_for("admin.messages"))
