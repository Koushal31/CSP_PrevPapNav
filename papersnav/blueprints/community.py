"""Community board — a lightweight Reddit-style discussion space where
students can post, upvote and comment.
"""
import logging
import math

from flask import (
    Blueprint,
    abort,
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
from ..decorators import login_required
from ..utils import stringify_id, to_object_id, utcnow

logger = logging.getLogger("papersnav")

community_bp = Blueprint("community", __name__, url_prefix="/community")


def _enrich_post(post):
    post["upvotes_count"] = post.get("upvotes_count", 0)
    post["upvoted_by"] = post.get("upvoted_by", [])
    post["comments_count"] = post.get("comments_count", 0)
    stringify_id(post)
    return post


# ── List posts ───────────────────────────────────────────────────────────────
@community_bp.route("/")
def index():
    sort = request.args.get("sort", "new")
    sort_spec = [("upvotes_count", -1), ("created_at", -1)] if sort == "top" else [("created_at", -1)]

    per_page = current_app.config["PAPERS_PER_PAGE"]
    try:
        page = max(1, int(request.args.get("page", 1)))
    except ValueError:
        page = 1

    total = db.posts.count_documents({})
    total_pages = max(1, math.ceil(total / per_page))
    page = min(page, total_pages)

    posts = list(
        db.posts.find({}).sort(sort_spec).skip((page - 1) * per_page).limit(per_page)
    )
    for p in posts:
        _enrich_post(p)

    user_id = session.get("user_id")
    return render_template(
        "community/index.html",
        posts=posts,
        sort=sort,
        page=page,
        total_pages=total_pages,
        total=total,
        user_id=user_id,
    )


# ── Create a post ────────────────────────────────────────────────────────────
@community_bp.route("/new", methods=["GET", "POST"])
@login_required
def new():
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        body = request.form.get("body", "").strip()
        if not title:
            flash("Please add a title for your post.", "error")
            return render_template("community/new.html", form={"title": title, "body": body})
        if len(title) > 160:
            flash("Title is too long (max 160 characters).", "error")
            return render_template("community/new.html", form={"title": title, "body": body})
        if len(body) > 5000:
            flash("Post is too long (max 5000 characters).", "error")
            return render_template("community/new.html", form={"title": title, "body": body})

        result = db.posts.insert_one(
            {
                "title": title,
                "body": body,
                "author_id": session["user_id"],
                "author_name": session.get("name", "User"),
                "created_at": utcnow(),
                "upvotes_count": 0,
                "upvoted_by": [],
                "comments_count": 0,
            }
        )
        flash("Your post is live!", "success")
        return redirect(url_for("community.view", post_id=str(result.inserted_id)))

    return render_template("community/new.html", form={})


# ── View a post ──────────────────────────────────────────────────────────────
@community_bp.route("/post/<post_id>")
def view(post_id):
    oid = to_object_id(post_id)
    if oid is None:
        return redirect(url_for("community.index"))
    post = db.posts.find_one({"_id": oid})
    if not post:
        return redirect(url_for("community.index"))
    _enrich_post(post)

    comments = list(db.post_comments.find({"post_id": post_id}).sort("created_at", 1))
    for c in comments:
        stringify_id(c)

    user_id = session.get("user_id")
    has_upvoted = user_id in post["upvoted_by"] if user_id else False
    can_delete = user_id and (user_id == post.get("author_id") or session.get("role") == "admin")
    return render_template(
        "community/post.html",
        post=post,
        comments=comments,
        has_upvoted=has_upvoted,
        can_delete=can_delete,
    )


# ── Upvote (AJAX) ────────────────────────────────────────────────────────────
@community_bp.route("/post/<post_id>/upvote", methods=["POST"])
def upvote(post_id):
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"error": "Unauthorized"}), 401
    oid = to_object_id(post_id)
    if oid is None:
        return jsonify({"error": "Not found"}), 404
    post = db.posts.find_one({"_id": oid}, {"upvoted_by": 1})
    if not post:
        return jsonify({"error": "Not found"}), 404

    if user_id in post.get("upvoted_by", []):
        db.posts.update_one({"_id": oid}, {"$pull": {"upvoted_by": user_id}, "$inc": {"upvotes_count": -1}})
        upvoted = False
    else:
        db.posts.update_one({"_id": oid}, {"$addToSet": {"upvoted_by": user_id}, "$inc": {"upvotes_count": 1}})
        upvoted = True
    count = max(int((db.posts.find_one({"_id": oid}) or {}).get("upvotes_count", 0)), 0)
    return jsonify({"upvoted": upvoted, "upvotes_count": count})


# ── Comment ──────────────────────────────────────────────────────────────────
@community_bp.route("/post/<post_id>/comment", methods=["POST"])
@login_required
def comment(post_id):
    oid = to_object_id(post_id)
    if oid is None or not db.posts.find_one({"_id": oid}, {"_id": 1}):
        abort(404)
    text = request.form.get("text", "").strip()
    if not text:
        flash("Comment cannot be empty.", "error")
    elif len(text) > 2000:
        flash("Comment is too long (max 2000 characters).", "error")
    else:
        db.post_comments.insert_one(
            {
                "post_id": post_id,
                "user_id": session["user_id"],
                "user_name": session.get("name", "User"),
                "text": text,
                "created_at": utcnow(),
            }
        )
        db.posts.update_one({"_id": oid}, {"$inc": {"comments_count": 1}})
        flash("Comment posted.", "success")
    return redirect(url_for("community.view", post_id=post_id))


# ── Delete a post (author or admin) ──────────────────────────────────────────
@community_bp.route("/post/<post_id>/delete", methods=["POST"])
@login_required
def delete(post_id):
    oid = to_object_id(post_id)
    if oid is None:
        abort(404)
    post = db.posts.find_one({"_id": oid})
    if not post:
        abort(404)
    if session.get("user_id") != post.get("author_id") and session.get("role") != "admin":
        abort(403)
    db.posts.delete_one({"_id": oid})
    db.post_comments.delete_many({"post_id": post_id})
    flash("Post deleted.", "success")
    return redirect(url_for("community.index"))
