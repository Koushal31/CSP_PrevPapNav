"""Repository-style helpers that sit between the blueprints and the raw
collections. They centralise the document shapes and the little bits of logic
(rating averages, uploader names, bookmark membership) that would otherwise be
duplicated across views.
"""
from .db import db
from .utils import stringify_id, to_object_id, utcnow


# ── Users ─────────────────────────────────────────────────────────────────
def get_user_by_email(email):
    if not email:
        return None
    return db.users.find_one({"email": email.strip().lower()})


def get_user_by_id(user_id):
    oid = to_object_id(user_id)
    return db.users.find_one({"_id": oid}) if oid else None


def uploader_name(email):
    """Resolve a friendly display name for an uploader email."""
    if not email:
        return None
    user = db.users.find_one({"email": email}, {"_id": 0, "name": 1})
    return user.get("name") if user else email


# ── Bookmarks ───────────────────────────────────────────────────────────────
def get_bookmarks(user_id):
    user = get_user_by_id(user_id)
    return list(user.get("bookmarks", [])) if user else []


def toggle_bookmark(user_id, paper_id):
    """Add/remove a paper from the user's bookmarks. Returns True if now saved."""
    oid = to_object_id(user_id)
    if not oid:
        return False
    user = db.users.find_one({"_id": oid}, {"bookmarks": 1})
    bookmarks = (user or {}).get("bookmarks", [])
    if paper_id in bookmarks:
        db.users.update_one({"_id": oid}, {"$pull": {"bookmarks": paper_id}})
        return False
    db.users.update_one({"_id": oid}, {"$addToSet": {"bookmarks": paper_id}})
    return True


# ── Papers ─────────────────────────────────────────────────────────────────
def enrich_paper(paper):
    """Add UI-friendly derived fields to a paper document (in place)."""
    if not paper:
        return paper
    paper["upvotes_count"] = paper.get("upvotes_count", 0)
    paper["upvoted_by"] = paper.get("upvoted_by", [])
    ratings = paper.get("ratings", [])
    paper["rating_count"] = len(ratings)
    paper["rating_avg"] = round(sum(r["value"] for r in ratings) / len(ratings), 1) if ratings else 0
    paper["uploaded_by_name"] = uploader_name(paper.get("uploaded_by"))
    stringify_id(paper)
    return paper


def user_rating(paper, user_id):
    for r in paper.get("ratings", []):
        if r.get("user_id") == user_id:
            return r.get("value")
    return None


def set_rating(paper_object_id, user_id, value):
    """Upsert a user's rating on a paper (1-5)."""
    # remove any existing rating from this user, then add the new one
    db.papers.update_one(
        {"_id": paper_object_id}, {"$pull": {"ratings": {"user_id": user_id}}}
    )
    db.papers.update_one(
        {"_id": paper_object_id},
        {"$push": {"ratings": {"user_id": user_id, "value": int(value), "at": utcnow()}}},
    )


# ── Comments ─────────────────────────────────────────────────────────────────
def list_comments(paper_id):
    items = list(db.comments.find({"paper_id": paper_id}).sort("created_at", -1))
    for c in items:
        stringify_id(c)
    return items


def add_comment(paper_id, user_id, user_name, text):
    db.comments.insert_one(
        {
            "paper_id": paper_id,
            "user_id": user_id,
            "user_name": user_name,
            "text": text.strip(),
            "created_at": utcnow(),
        }
    )
