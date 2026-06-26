"""Seed the database with starter content so the app is usable immediately:
colleges, branches, subjects (per branch + semester) and a few sample papers.

Run it with either:
    flask --app run seed
    python -m papersnav.seed_data
Both are idempotent — running again won't create duplicates.
"""
import logging

from .db import db
from .utils import utcnow

logger = logging.getLogger("papersnav")

COLLEGES = [
    {"name": "Anna University", "code": "AU", "city": "Chennai"},
    {"name": "VIT University", "code": "VIT", "city": "Vellore"},
    {"name": "SRM Institute of Science and Technology", "code": "SRM", "city": "Chennai"},
    {"name": "PSG College of Technology", "code": "PSG", "city": "Coimbatore"},
    {"name": "Vignan's Institute of Information Technology", "code": "VIIT", "city": "Visakhapatnam"},
]

BRANCHES = [
    {"name": "Computer Science and Engineering", "code": "CSE"},
    {"name": "Electronics and Communication Engineering", "code": "ECE"},
    {"name": "Electrical and Electronics Engineering", "code": "EEE"},
    {"name": "Mechanical Engineering", "code": "MECH"},
    {"name": "Civil Engineering", "code": "CIVIL"},
    {"name": "Information Technology", "code": "IT"},
]

# branch_code -> { semester -> [subject names] }
SUBJECTS = {
    "CSE": {
        1: ["Engineering Mathematics I", "Programming in C", "Engineering Physics", "Engineering Chemistry"],
        2: ["Engineering Mathematics II", "Object Oriented Programming", "Data Structures", "Digital Logic Design"],
        3: ["Discrete Mathematics", "Computer Organization", "Operating Systems", "Database Management Systems", "Design and Analysis of Algorithms"],
        4: ["Theory of Computation", "Microprocessors and Microcontrollers", "Java Programming", "Computer Networks", "Software Engineering"],
        5: ["Compiler Design", "Web Technologies", "Artificial Intelligence", "Computer Graphics"],
        6: ["Machine Learning", "Cloud Computing", "Cryptography and Network Security", "Internet of Things"],
        7: ["Big Data Analytics", "Deep Learning", "Distributed Systems", "Information Security"],
        8: ["Block Chain Technology", "Quantum Computing", "Professional Ethics"],
    },
    "ECE": {
        3: ["Signals and Systems", "Electronic Devices", "Network Theory", "Digital Electronics"],
        4: ["Analog Communication", "Linear Integrated Circuits", "Control Systems", "Electromagnetic Fields"],
    },
    "EEE": {
        3: ["Electrical Machines I", "Circuit Theory", "Electromagnetic Theory", "Measurements and Instrumentation"],
        4: ["Electrical Machines II", "Power Systems I", "Analog Electronics", "Control Systems"],
    },
    "MECH": {
        3: ["Engineering Thermodynamics", "Fluid Mechanics and Machinery", "Manufacturing Technology", "Strength of Materials"],
        4: ["Kinematics of Machinery", "Heat and Mass Transfer", "Engineering Metallurgy", "Hydraulics"],
    },
    "CIVIL": {
        3: ["Mechanics of Solids", "Surveying", "Fluid Mechanics", "Building Materials"],
        4: ["Structural Analysis", "Concrete Technology", "Soil Mechanics", "Highway Engineering"],
    },
    "IT": {
        3: ["Data Structures", "Operating Systems", "Database Management Systems", "Object Oriented Programming"],
        4: ["Computer Networks", "Web Technologies", "Software Engineering", "Java Programming"],
    },
}

SAMPLE_PAPERS = [
    {"subject": "Database Management Systems", "branch": "CSE", "semester": 3, "year": 2024, "college": "Anna University"},
    {"subject": "Operating Systems", "branch": "CSE", "semester": 3, "year": 2023, "college": "VIT University"},
    {"subject": "Computer Networks", "branch": "CSE", "semester": 4, "year": 2024, "college": "SRM Institute of Science and Technology"},
    {"subject": "Signals and Systems", "branch": "ECE", "semester": 3, "year": 2023, "college": "Anna University"},
    {"subject": "Engineering Thermodynamics", "branch": "MECH", "semester": 3, "year": 2024, "college": "PSG College of Technology"},
]


def seed_database(with_samples=True, admin_email="seed@papersnav.local"):
    """Insert starter content. Returns a dict of how many docs were created."""
    created = {"colleges": 0, "branches": 0, "subjects": 0, "papers": 0}

    for college in COLLEGES:
        if not db.colleges.find_one({"code": college["code"]}):
            db.colleges.insert_one(dict(college))
            created["colleges"] += 1

    for college in COLLEGES:
        for branch in BRANCHES:
            key = {"code": branch["code"], "college_code": college["code"]}
            if not db.branches.find_one(key):
                db.branches.insert_one({**branch, "college_code": college["code"]})
                created["branches"] += 1

    for college in COLLEGES:
        for branch_code, by_sem in SUBJECTS.items():
            for semester, names in by_sem.items():
                for name in names:
                    key = {
                        "name": name,
                        "college_code": college["code"],
                        "branch_code": branch_code,
                        "semester": semester,
                    }
                    if not db.subjects.find_one(key):
                        db.subjects.insert_one(dict(key))
                        created["subjects"] += 1

    if with_samples and db.papers.count_documents({}) == 0:
        for sp in SAMPLE_PAPERS:
            db.papers.insert_one(
                {
                    **sp,
                    "filename": None,
                    "status": "approved",
                    "uploaded_by": admin_email,
                    "uploaded_at": utcnow(),
                    "downloads": 0,
                    "upvotes_count": 0,
                    "upvoted_by": [],
                    "ratings": [],
                }
            )
            created["papers"] += 1

    logger.info("Seed complete: %s", created)
    return created


def main():
    from . import create_app

    app = create_app()
    with app.app_context():
        created = seed_database()
    print("Seeded:", created)


if __name__ == "__main__":
    main()
