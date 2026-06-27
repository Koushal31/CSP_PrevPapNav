"""Everything centred on papers: browsing/search, viewing, uploading,
downloading, voting, bookmarking, commenting and rating, plus the small
JSON endpoints that power the dependent dropdowns.
"""
import datetime
import logging
import math
import os
import uuid

from flask import (
    Blueprint,
    Response,
    abort,
    current_app,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    send_from_directory,
    session,
    url_for,
)
from werkzeug.utils import secure_filename

from ..db import db
from ..decorators import login_required
from ..models import (
    add_comment,
    enrich_paper,
    get_bookmarks,
    list_comments,
    set_rating,
    toggle_bookmark,
    user_rating,
)
from ..utils import allowed_file, to_object_id, utcnow

logger = logging.getLogger("papersnav")

papers_bp = Blueprint("papers", __name__)


def serve_paper_pdf(paper, as_attachment):
    """Return a Flask response streaming a paper's PDF.

    Prefers GridFS (persistent, used for all new uploads); falls back to a
    legacy file on disk for older papers. Returns None if no file is found.
    """
    file_id = paper.get("file_id")
    if file_id:
        gid = to_object_id(file_id)
        if gid is not None and db.fs.exists(gid):
            data = db.fs.get(gid).read()
            fname = secure_filename(paper.get("filename") or "paper.pdf")
            disposition = "attachment" if as_attachment else "inline"
            return Response(
                data,
                mimetype="application/pdf",
                headers={"Content-Disposition": f'{disposition}; filename="{fname}"'},
            )
    # Legacy: file stored on disk
    if paper.get("filename"):
        safe = secure_filename(paper["filename"])
        filepath = os.path.join(current_app.config["UPLOAD_FOLDER"], safe)
        if os.path.exists(filepath):
            return send_from_directory(
                current_app.config["UPLOAD_FOLDER"], safe, as_attachment=as_attachment
            )
    return None


def delete_paper_file(paper):
    """Remove a paper's stored PDF from GridFS (or legacy disk). Best-effort."""
    file_id = paper.get("file_id")
    if file_id:
        gid = to_object_id(file_id)
        if gid is not None:
            try:
                db.fs.delete(gid)
            except Exception as exc:
                logger.warning("GridFS delete failed: %s", exc)
    elif paper.get("filename"):
        filepath = os.path.join(current_app.config["UPLOAD_FOLDER"], paper["filename"])
        if os.path.exists(filepath):
            os.remove(filepath)


# ── Browse / search ─────────────────────────────────────────────────────────
@papers_bp.route("/papers")
def browse():
    colleges = list(db.colleges.find({}, {"_id": 0, "name": 1, "code": 1}))
    branches = list(db.branches.find({}, {"_id": 0, "name": 1, "code": 1}))

    f = {
        "college": request.args.get("college", "").strip(),
        "branch": request.args.get("branch", "").strip(),
        "semester": request.args.get("semester", "").strip(),
        "subject": request.args.get("subject", "").strip(),
        "year": request.args.get("year", "").strip(),
        "q": request.args.get("q", "").strip(),
    }

    query = {"status": "approved"}
    if f["college"]:
        query["college"] = f["college"]
    if f["branch"]:
        query["branch"] = f["branch"]
    if f["semester"]:
        try:
            query["semester"] = int(f["semester"])
        except ValueError:
            pass
    if f["subject"]:
        query["subject"] = {"$regex": f["subject"], "$options": "i"}
    if f["year"]:
        try:
            query["year"] = int(f["year"])
        except ValueError:
            pass
    if f["q"]:
        regex = {"$regex": f["q"], "$options": "i"}
        query["$or"] = [{"subject": regex}, {"college": regex}, {"branch": regex}]

    # ── Pagination ────────────────────────────────────────────────────────
    per_page = current_app.config["PAPERS_PER_PAGE"]
    try:
        page = max(1, int(request.args.get("page", 1)))
    except ValueError:
        page = 1

    total = db.papers.count_documents(query)
    total_pages = max(1, math.ceil(total / per_page))
    page = min(page, total_pages)

    results = list(
        db.papers.find(query)
        .sort("year", -1)
        .skip((page - 1) * per_page)
        .limit(per_page)
    )
    for p in results:
        enrich_paper(p)

    bookmarks = get_bookmarks(session.get("user_id")) if session.get("user_id") else []
    searched = any(f.values())

    return render_template(
        "papers.html",
        colleges=colleges,
        branches=branches,
        semesters=list(range(1, 9)),
        years=list(range(datetime.datetime.now().year + 1, 2004, -1)),
        results=results,
        searched=searched,
        filters=f,
        bookmarks=bookmarks,
        page=page,
        total_pages=total_pages,
        total=total,
    )


# ── Dependent dropdown data ──────────────────────────────────────────────────
@papers_bp.route("/api/branches")
def api_branches():
    try:
        college = request.args.get("college", "").strip()
        query = {"college_code": college} if college else {}
        branches = list(
            db.branches.find(query, {"_id": 0, "name": 1, "code": 1, "college_code": 1})
        )
        return jsonify(branches)
    except Exception as exc:
        logger.error("Error fetching branches: %s", exc)
        return jsonify([]), 500


@papers_bp.route("/api/subjects")
def api_subjects():
    try:
        branch = request.args.get("branch", "").strip()
        semester = request.args.get("semester", "").strip()
        college = request.args.get("college", "").strip()
        query = {}
        if branch:
            query["branch_code"] = branch
        if college:
            query["college_code"] = college
        if semester:
            try:
                query["semester"] = int(semester)
            except ValueError:
                pass
        # Dedupe names (the same subject can exist across colleges) and sort.
        names = sorted({s["name"] for s in db.subjects.find(query, {"_id": 0, "name": 1})})
        return jsonify(names)
    except Exception as exc:
        logger.error("Error fetching subjects: %s", exc)
        return jsonify([]), 500


# ── Upload ───────────────────────────────────────────────────────────────────
@papers_bp.route("/upload", methods=["GET", "POST"])
@login_required
def upload():
    colleges = list(db.colleges.find({}, {"_id": 0, "name": 1, "code": 1}).sort("name", 1))
    branches = list(
        db.branches.find({}, {"_id": 0, "name": 1, "code": 1, "college_code": 1}).sort(
            [("college_code", 1), ("name", 1)]
        )
    )
    semesters = list(range(1, 9))
    years = list(range(datetime.datetime.now().year + 1, 2004, -1))

    def render(error=None, form_data=None):
        return render_template(
            "upload.html",
            colleges=colleges,
            branches=branches,
            semesters=semesters,
            years=years,
            form_data=form_data or {},
            error=error,
        )

    if request.method != "POST":
        return render()

    form = request.form
    college_code = form.get("college")
    branch = form.get("branch")
    semester = form.get("semester")
    subject = form.get("subject")
    year = form.get("year")
    file = request.files.get("pdf")

    college_doc = db.colleges.find_one({"code": college_code}) if college_code else None
    valid_branches = [b["code"] for b in branches if b.get("college_code") == college_code]

    if not all([college_code, branch, semester, subject, year, file]):
        return render("All fields are required.", form)
    if not college_doc or branch not in valid_branches:
        return render("Please select a valid college and branch for the selected college.", form)

    try:
        semester_num = int(semester)
        year_num = int(year)
    except ValueError:
        return render("Semester and year must be valid numbers.", form)

    if not 1 <= semester_num <= 8:
        return render("Semester must be between 1 and 8.", form)

    current_year = datetime.datetime.now().year
    if year_num < 2000 or year_num > current_year + 1:
        return render("Please enter a valid year.", form)

    if not (file and allowed_file(file.filename)):
        return render("Only PDF files are allowed.", form)

    try:
        college_name = college_doc["name"]
        suffix = uuid.uuid4().hex[:8]
        filename = secure_filename(
            f"{college_name}_{branch}_sem{semester}_{subject}_{year}_{suffix}.pdf"
        )
        # Store the PDF in GridFS (MongoDB) so it persists across deploys.
        file_id = db.fs.put(
            file.read(),
            filename=filename,
            content_type="application/pdf",
            uploaded_by=session.get("email"),
        )

        db.papers.insert_one(
            {
                "subject": subject,
                "branch": branch,
                "semester": semester_num,
                "year": year_num,
                "college": college_name,
                "filename": filename,
                "file_id": str(file_id),
                "status": "pending",
                "uploaded_by": session.get("email"),
                "uploaded_at": utcnow(),
                "downloads": 0,
                "upvotes_count": 0,
                "upvoted_by": [],
                "ratings": [],
            }
        )
        logger.info("Paper uploaded by %s: %s", session.get("email"), filename)
        flash("Paper uploaded successfully! It will be visible after admin approval.", "success")
        return render(form_data={})
    except IOError as exc:
        logger.error("File save error: %s", exc)
        return render("Error saving file. Please try again.", form)
    except Exception as exc:
        logger.error("Error uploading paper: %s", exc)
        return render("An error occurred during upload. Please try again.", form)


# ── View a single paper ──────────────────────────────────────────────────────
@papers_bp.route("/paper/<paper_id>")
def view(paper_id):
    oid = to_object_id(paper_id)
    if oid is None:
        return redirect(url_for("papers.browse"))

    paper = db.papers.find_one({"_id": oid, "status": "approved"})
    if not paper:
        return redirect(url_for("papers.browse"))

    raw_ratings = paper.get("ratings", [])
    enrich_paper(paper)

    user_id = session.get("user_id")
    my_bookmarks = get_bookmarks(user_id) if user_id else []
    is_bookmarked = paper_id in my_bookmarks
    my_rating = user_rating({"ratings": raw_ratings}, user_id) if user_id else None
    has_upvoted = user_id in paper["upvoted_by"] if user_id else False

    return render_template(
        "view_paper.html",
        paper=paper,
        comments=list_comments(paper_id),
        is_bookmarked=is_bookmarked,
        my_rating=my_rating,
        has_upvoted=has_upvoted,
    )


# ── Inline file (for the in-page PDF viewer) ─────────────────────────────────
@papers_bp.route("/paper/<paper_id>/file")
def file(paper_id):
    oid = to_object_id(paper_id)
    paper = db.papers.find_one({"_id": oid, "status": "approved"}) if oid else None
    if not paper:
        abort(404)
    resp = serve_paper_pdf(paper, as_attachment=False)
    if resp is None:
        abort(404)
    return resp


# ── Download ─────────────────────────────────────────────────────────────────
@papers_bp.route("/download/<paper_id>")
def download(paper_id):
    try:
        oid = to_object_id(paper_id)
        if oid is None:
            return jsonify({"error": "Not found"}), 404

        paper = db.papers.find_one({"_id": oid, "status": "approved"})
        if not paper:
            return jsonify({"error": "Not found"}), 404

        resp = serve_paper_pdf(paper, as_attachment=True)
        if resp is not None:
            db.papers.update_one({"_id": oid}, {"$inc": {"downloads": 1}})
            return resp

        flash("This paper does not have an attached PDF.", "warning")
        return redirect(url_for("papers.view", paper_id=paper_id))
    except Exception as exc:
        logger.error("Error in download: %s", exc)
        flash("An error occurred while downloading the paper.", "error")
        return redirect(url_for("papers.browse"))


# ── Upvote (AJAX) ────────────────────────────────────────────────────────────
@papers_bp.route("/paper/<paper_id>/upvote", methods=["POST"])
def upvote(paper_id):
    oid = to_object_id(paper_id)
    if oid is None:
        return jsonify({"error": "Not found"}), 404

    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"error": "Unauthorized"}), 401

    paper = db.papers.find_one({"_id": oid, "status": "approved"}, {"upvoted_by": 1})
    if not paper:
        return jsonify({"error": "Not found"}), 404

    if user_id in paper.get("upvoted_by", []):
        db.papers.update_one(
            {"_id": oid}, {"$pull": {"upvoted_by": user_id}, "$inc": {"upvotes_count": -1}}
        )
        upvoted = False
    else:
        db.papers.update_one(
            {"_id": oid}, {"$addToSet": {"upvoted_by": user_id}, "$inc": {"upvotes_count": 1}}
        )
        upvoted = True

    count = max(int((db.papers.find_one({"_id": oid}) or {}).get("upvotes_count", 0)), 0)
    return jsonify({"upvoted": upvoted, "upvotes_count": count})


# ── Bookmark (AJAX) ──────────────────────────────────────────────────────────
@papers_bp.route("/paper/<paper_id>/bookmark", methods=["POST"])
def bookmark(paper_id):
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"error": "Unauthorized"}), 401
    oid = to_object_id(paper_id)
    if oid is None or not db.papers.find_one({"_id": oid}, {"_id": 1}):
        return jsonify({"error": "Not found"}), 404
    saved = toggle_bookmark(user_id, paper_id)
    return jsonify({"bookmarked": saved})


# ── Rate ─────────────────────────────────────────────────────────────────────
@papers_bp.route("/paper/<paper_id>/rate", methods=["POST"])
@login_required
def rate(paper_id):
    oid = to_object_id(paper_id)
    if oid is None or not db.papers.find_one({"_id": oid, "status": "approved"}, {"_id": 1}):
        abort(404)
    try:
        value = int(request.form.get("value", 0))
    except ValueError:
        value = 0
    if not 1 <= value <= 5:
        flash("Rating must be between 1 and 5 stars.", "error")
        return redirect(url_for("papers.view", paper_id=paper_id))
    set_rating(oid, session["user_id"], value)
    flash("Thanks for rating this paper!", "success")
    return redirect(url_for("papers.view", paper_id=paper_id))


# ── Comment ──────────────────────────────────────────────────────────────────
@papers_bp.route("/paper/<paper_id>/comment", methods=["POST"])
@login_required
def comment(paper_id):
    oid = to_object_id(paper_id)
    if oid is None or not db.papers.find_one({"_id": oid, "status": "approved"}, {"_id": 1}):
        abort(404)
    text = request.form.get("text", "").strip()
    if not text:
        flash("Comment cannot be empty.", "error")
    elif len(text) > 1000:
        flash("Comment is too long (max 1000 characters).", "error")
    else:
        add_comment(paper_id, session["user_id"], session.get("name", "User"), text)
        flash("Comment posted.", "success")
    return redirect(url_for("papers.view", paper_id=paper_id))


# ── Delete own upload ────────────────────────────────────────────────────────
@papers_bp.route("/paper/<paper_id>/delete-mine", methods=["POST"])
@login_required
def delete_mine(paper_id):
    oid = to_object_id(paper_id)
    if oid is None:
        abort(404)
    paper = db.papers.find_one({"_id": oid})
    if not paper:
        abort(404)
    # Only the uploader may delete their own submission.
    if paper.get("uploaded_by") != session.get("email"):
        abort(403)
    delete_paper_file(paper)
    db.papers.delete_one({"_id": oid})
    db.comments.delete_many({"paper_id": paper_id})
    flash("Your paper was deleted.", "success")
    return redirect(url_for("auth.profile"))
