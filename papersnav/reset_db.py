"""Reset the academic data only — colleges, branches and subjects.

Users, papers, comments and bookmarks are left untouched. Handy after changing
seed data (e.g. the VIGNAN -> VIIT college-code change) so you can re-seed
cleanly.

Run with:
    flask --app run reset-academic
    python -m papersnav.reset_db
"""
import logging

from .db import db

logger = logging.getLogger("papersnav")


def reset_academic():
    """Delete all colleges, branches and subjects. Returns deleted counts."""
    result = {
        "colleges": db.colleges.delete_many({}).deleted_count,
        "branches": db.branches.delete_many({}).deleted_count,
        "subjects": db.subjects.delete_many({}).deleted_count,
    }
    logger.info("Academic data reset: %s", result)
    return result


def main():
    from . import create_app

    app = create_app()
    with app.app_context():
        result = reset_academic()
    print("Reset academic data (deleted):", result)


if __name__ == "__main__":
    main()
