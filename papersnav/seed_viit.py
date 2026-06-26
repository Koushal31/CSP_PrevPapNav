"""Seed all branches and subjects for Vignan's Institute of Information
Technology (VIIT), Duvvada, Visakhapatnam.

Branches reflect VIIT's B.Tech programs; subjects follow the standard
JNTU-GV / AP autonomous B.Tech curriculum (core subjects per semester).

Run with:
    flask --app run seed-viit
    python -m papersnav.seed_viit
Idempotent — running again won't create duplicates.
"""
import logging

from .db import db

logger = logging.getLogger("papersnav")

COLLEGE = {"name": "Vignan's Institute of Information Technology", "code": "VIIT", "city": "Visakhapatnam"}

BRANCHES = [
    {"code": "CSE", "name": "Computer Science and Engineering"},
    {"code": "AIML", "name": "CSE (Artificial Intelligence and Machine Learning)"},
    {"code": "AIDS", "name": "CSE (Artificial Intelligence and Data Science)"},
    {"code": "CSEIOT", "name": "CSE (IoT, Cyber Security and Block Chain)"},
    {"code": "ECE", "name": "Electronics and Communication Engineering"},
    {"code": "EEE", "name": "Electrical and Electronics Engineering"},
    {"code": "IT", "name": "Information Technology"},
    {"code": "MECH", "name": "Mechanical Engineering"},
    {"code": "CIVIL", "name": "Civil Engineering"},
]

# Common first year (semesters 1 & 2) shared across all branches.
COMMON = {
    1: [
        "Linear Algebra and Calculus",
        "Engineering Physics",
        "Programming for Problem Solving",
        "Engineering Chemistry",
        "Communicative English",
        "Engineering Graphics",
    ],
    2: [
        "Differential Equations and Vector Calculus",
        "Applied Physics",
        "Data Structures",
        "Basic Electrical and Electronics Engineering",
        "Python Programming",
        "Engineering Workshop",
    ],
}

# Branch-specific subjects, semesters 3–8.
BRANCH_SUBJECTS = {
    "CSE": {
        3: ["Discrete Mathematics", "Digital Logic Design", "Data Structures and Algorithms", "Computer Organization and Architecture", "Object Oriented Programming through Java", "Mathematical Foundations of Computer Science"],
        4: ["Operating Systems", "Database Management Systems", "Design and Analysis of Algorithms", "Probability and Statistics", "Formal Languages and Automata Theory", "Software Engineering"],
        5: ["Computer Networks", "Web Technologies", "Compiler Design", "Machine Learning", "Object Oriented Analysis and Design"],
        6: ["Artificial Intelligence", "Cryptography and Network Security", "Data Warehousing and Data Mining", "Cloud Computing", "Computer Graphics"],
        7: ["Big Data Analytics", "Internet of Things", "Deep Learning", "Distributed Systems", "Natural Language Processing"],
        8: ["Block Chain Technology", "Cyber Security", "Project Work", "Professional Elective", "Open Elective"],
    },
    "AIML": {
        3: ["Discrete Mathematics", "Data Structures", "Digital Logic Design", "Object Oriented Programming through Java", "Computer Organization", "Mathematical Foundations for AI"],
        4: ["Operating Systems", "Database Management Systems", "Design and Analysis of Algorithms", "Probability and Statistics", "Introduction to Artificial Intelligence", "Software Engineering"],
        5: ["Machine Learning", "Computer Networks", "Data Warehousing and Mining", "Automata Theory and Compiler Design", "Python for Machine Learning"],
        6: ["Deep Learning", "Natural Language Processing", "Computer Vision", "Cloud Computing", "Reinforcement Learning"],
        7: ["Big Data Analytics", "Neural Networks", "AI for Robotics", "Pattern Recognition", "Generative AI"],
        8: ["Explainable AI", "MLOps", "Project Work", "Professional Elective", "Open Elective"],
    },
    "AIDS": {
        3: ["Discrete Mathematics", "Data Structures", "Digital Logic Design", "Object Oriented Programming through Java", "Computer Organization", "Statistical Foundations for Data Science"],
        4: ["Operating Systems", "Database Management Systems", "Design and Analysis of Algorithms", "Probability and Statistics", "Introduction to Data Science", "Software Engineering"],
        5: ["Machine Learning", "Data Visualization", "Computer Networks", "Data Warehousing and Mining", "Exploratory Data Analysis"],
        6: ["Deep Learning", "Big Data Analytics", "Natural Language Processing", "Cloud Computing", "Business Intelligence"],
        7: ["Data Engineering", "Predictive Analytics", "Time Series Analysis", "Reinforcement Learning", "Data Ethics and Privacy"],
        8: ["Generative AI", "MLOps", "Project Work", "Professional Elective", "Open Elective"],
    },
    "CSEIOT": {
        3: ["Discrete Mathematics", "Data Structures", "Digital Logic Design", "Object Oriented Programming through Java", "Computer Organization", "Sensors and Actuators"],
        4: ["Operating Systems", "Database Management Systems", "Design and Analysis of Algorithms", "Computer Networks", "Introduction to IoT", "Software Engineering"],
        5: ["Embedded Systems", "Cryptography and Network Security", "Wireless Sensor Networks", "Machine Learning", "Cloud Computing"],
        6: ["IoT Protocols and Architecture", "Cyber Security", "Block Chain Technology", "Edge Computing", "Web Technologies"],
        7: ["Ethical Hacking", "Digital Forensics", "Industrial IoT", "Smart Systems Design", "Big Data Analytics"],
        8: ["IoT Security", "Cryptocurrency and Smart Contracts", "Project Work", "Professional Elective", "Open Elective"],
    },
    "ECE": {
        3: ["Electronic Devices and Circuits", "Network Analysis", "Signals and Systems", "Switching Theory and Logic Design", "Random Variables and Stochastic Processes", "Electromagnetic Waves and Transmission Lines"],
        4: ["Analog Communications", "Linear IC Applications", "Control Systems", "Electronic Circuit Analysis", "Probability Theory and Stochastic Processes", "Pulse and Digital Circuits"],
        5: ["Digital Communications", "Microprocessors and Microcontrollers", "Antennas and Wave Propagation", "Digital Signal Processing", "VLSI Design"],
        6: ["Microwave Engineering", "Optical Communications", "Embedded Systems", "Computer Networks", "Digital IC Applications"],
        7: ["Radar Systems", "Satellite Communications", "Wireless Communications", "Digital Image Processing", "CMOS Analog IC Design"],
        8: ["Cellular and Mobile Communications", "Internet of Things", "Project Work", "Professional Elective", "Open Elective"],
    },
    "EEE": {
        3: ["Electrical Circuit Analysis", "Electromagnetic Fields", "Electrical Machines-I", "Network Theory", "Complex Variables and Transforms", "Electronic Devices and Circuits"],
        4: ["Electrical Machines-II", "Power Systems-I", "Control Systems", "Analog Electronics", "Electrical Measurements and Instrumentation", "Signals and Systems"],
        5: ["Power Systems-II", "Power Electronics", "Microprocessors and Microcontrollers", "Digital Signal Processing", "Linear and Digital IC Applications"],
        6: ["Power System Analysis", "Electrical Machine Design", "Switchgear and Protection", "Advanced Control Systems", "Renewable Energy Sources"],
        7: ["Power System Operation and Control", "Electric Drives", "HVDC Transmission", "Power Quality", "Electric Vehicles"],
        8: ["Smart Grid Technologies", "FACTS Devices", "Project Work", "Professional Elective", "Open Elective"],
    },
    "IT": {
        3: ["Discrete Mathematics", "Data Structures", "Digital Logic Design", "Object Oriented Programming through Java", "Computer Organization and Architecture", "Probability and Statistics"],
        4: ["Operating Systems", "Database Management Systems", "Design and Analysis of Algorithms", "Formal Languages and Automata Theory", "Software Engineering", "Java Programming"],
        5: ["Computer Networks", "Web Technologies", "Information Security", "Machine Learning", "Data Warehousing and Data Mining"],
        6: ["Cloud Computing", "Mobile Application Development", "Artificial Intelligence", "Big Data Technologies", "Software Testing Methodologies"],
        7: ["Internet of Things", "Cyber Security", "Full Stack Development", "Data Science", "Distributed Systems"],
        8: ["Block Chain Technology", "DevOps", "Project Work", "Professional Elective", "Open Elective"],
    },
    "MECH": {
        3: ["Engineering Mechanics", "Thermodynamics", "Mechanics of Solids", "Material Science and Metallurgy", "Transforms and Numerical Methods", "Manufacturing Processes"],
        4: ["Fluid Mechanics and Hydraulic Machinery", "Kinematics of Machinery", "Production Technology", "Thermal Engineering-I", "Metrology and Surface Engineering", "Instrumentation and Control Systems"],
        5: ["Dynamics of Machinery", "Design of Machine Elements", "Thermal Engineering-II", "Heat Transfer", "Machine Tools and Metal Cutting"],
        6: ["Design of Transmission Systems", "CAD/CAM", "Refrigeration and Air Conditioning", "Operations Research", "Finite Element Methods"],
        7: ["Automobile Engineering", "Power Plant Engineering", "Mechatronics", "Robotics", "Computational Fluid Dynamics"],
        8: ["Industrial Engineering and Management", "Additive Manufacturing", "Project Work", "Professional Elective", "Open Elective"],
    },
    "CIVIL": {
        3: ["Strength of Materials-I", "Surveying", "Fluid Mechanics", "Engineering Geology", "Transforms and Numerical Methods", "Building Materials and Construction"],
        4: ["Strength of Materials-II", "Structural Analysis-I", "Hydraulics and Hydraulic Machinery", "Concrete Technology", "Advanced Surveying", "Soil Mechanics"],
        5: ["Structural Analysis-II", "Design of Reinforced Concrete Structures", "Geotechnical Engineering", "Water Resources Engineering", "Transportation Engineering-I"],
        6: ["Design of Steel Structures", "Environmental Engineering-I", "Foundation Engineering", "Transportation Engineering-II", "Estimation and Costing"],
        7: ["Environmental Engineering-II", "Prestressed Concrete", "Construction Technology and Management", "Remote Sensing and GIS", "Engineering Hydrology"],
        8: ["Earthquake Resistant Design", "Ground Improvement Techniques", "Project Work", "Professional Elective", "Open Elective"],
    },
}


def seed_college(college, branches):
    """Insert a college with the given branches and the shared AP/JNTU-GV
    curriculum (common first year + branch-specific subjects). Idempotent.
    Returns counts created.
    """
    created = {"branches": 0, "subjects": 0}
    code = college["code"]

    if not db.colleges.find_one({"code": code}):
        db.colleges.insert_one(dict(college))

    for branch in branches:
        if not db.branches.find_one({"code": branch["code"], "college_code": code}):
            db.branches.insert_one({**branch, "college_code": code})
            created["branches"] += 1

        # Build the full semester map: common first year + branch-specific.
        sem_map = dict(COMMON)
        sem_map.update(BRANCH_SUBJECTS[branch["code"]])
        for semester, names in sem_map.items():
            for name in names:
                key = {
                    "name": name,
                    "college_code": code,
                    "branch_code": branch["code"],
                    "semester": semester,
                }
                if not db.subjects.find_one(key):
                    db.subjects.insert_one(dict(key))
                    created["subjects"] += 1

    logger.info("Seed complete for %s: %s", code, created)
    return created


def seed_viit():
    """Insert VIIT's college, branches and subjects. Returns counts created."""
    return seed_college(COLLEGE, BRANCHES)


def main():
    from . import create_app

    app = create_app()
    with app.app_context():
        created = seed_viit()
    print("Seeded VIIT:", created)


if __name__ == "__main__":
    main()
