"""Seed all branches and subjects for Vignan's Institute of Engineering for
Women (VIEW), Visakhapatnam.

VIEW (autonomous, est. 2008) follows the same JNTU-GV / AP autonomous B.Tech
curriculum as VIIT, so the subject data is reused from seed_viit.

Run with:
    flask --app run seed-view
    python -m papersnav.seed_view
Idempotent — running again won't create duplicates.
"""
import logging

from .seed_viit import seed_college

logger = logging.getLogger("papersnav")

COLLEGE = {"name": "Vignan's Institute of Engineering for Women", "code": "VIEW", "city": "Visakhapatnam"}

BRANCHES = [
    {"code": "CSE", "name": "Computer Science and Engineering"},
    {"code": "AIML", "name": "CSE (Artificial Intelligence and Machine Learning)"},
    {"code": "AIDS", "name": "CSE (Data Science)"},
    {"code": "ECE", "name": "Electronics and Communication Engineering"},
    {"code": "EEE", "name": "Electrical and Electronics Engineering"},
    {"code": "IT", "name": "Information Technology"},
    {"code": "MECH", "name": "Mechanical Engineering"},
]


def seed_view():
    """Insert VIEW's college, branches and subjects. Returns counts created."""
    return seed_college(COLLEGE, BRANCHES)


def main():
    from . import create_app

    app = create_app()
    with app.app_context():
        created = seed_view()
    print("Seeded VIEW:", created)


if __name__ == "__main__":
    main()
