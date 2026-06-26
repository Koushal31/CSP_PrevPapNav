# PapersNav — Previous Year Papers Navigator

A Flask + MongoDB web app where engineering students search, browse, upload and
download previous-year question papers organised by college, branch, semester
and subject. Uploads are reviewed by an admin before going live, and access is
restricted to college email addresses.

Modular build: an application factory with separated blueprints, a thin
database/repository layer, CSRF-protected forms, and configuration driven
entirely by environment variables.

## Features

- **Search & browse** — filter by college, branch, semester, subject and year, plus free-text keyword search, with pagination.
- **Accounts** — email/password registration and login, **Google sign-in / sign-up** (OAuth), and a self-service **password reset** flow.
- **College-email restriction** — registration and Google sign-in can be limited to one or more email domains (`ALLOWED_EMAIL_DOMAINS`).
- **Account settings** — change password, set a password for Google accounts, and edit name/college.
- **Profiles** — each user sees their uploads (with approval status), can delete their own uploads, and keeps **bookmarked** papers.
- **Uploads & moderation** — authenticated users upload PDFs; an admin approves, rejects or deletes them, and uploaders are emailed on approve/reject.
- **Engagement** — upvotes, 1–5 star **ratings**, **bookmarks** and a **comment** thread on each paper.
- **Admin panel** — dashboard, review queue, and management of colleges, branches, subjects and users.
- **Security & ops** — CSRF protection on every form, role-based access control, password hashing, and a `/healthz` health check.

## Project structure

```
csp/
├── run.py                  # local dev entry point (python run.py)
├── wsgi.py                 # production entry point (gunicorn wsgi:app)
├── requirements.txt        # runtime deps
├── requirements-dev.txt    # + pytest, mongomock
├── Procfile / render.yaml  # deployment
├── .env.example
├── papersnav/              # application package
│   ├── __init__.py         # create_app() factory + CLI + error handlers
│   ├── config.py           # env-driven configuration
│   ├── extensions.py       # OAuth, Mail, CSRF instances
│   ├── db.py               # MongoDB connection + collections + indexes
│   ├── models.py           # repository helpers
│   ├── utils.py            # helpers: email/domain checks, email sender
│   ├── decorators.py       # login_required / admin_required
│   ├── seed.py             # default admin bootstrap
│   ├── seed_data.py        # colleges/branches/subjects/sample papers + `flask seed`
│   └── blueprints/         # main, auth, papers, admin
├── templates/              # Jinja templates (+ admin/)
├── static/                 # css/, js/, uploads/
└── tests/                  # pytest suite (in-memory Mongo via mongomock)
```

## Setup

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows  (use: source .venv/bin/activate on macOS/Linux)
pip install -r requirements.txt
cp .env.example .env            # then edit values
python run.py                   # http://localhost:5000
```

At minimum set `SECRET_KEY` and `MONGO_URI`. Google OAuth and email are
optional — leave their variables blank to disable those features.

## Seed starter content

The colleges/branches/subjects dropdowns are empty on a fresh database. Populate
them (and a few sample papers) with:

```bash
flask --app run seed
# or
python -m papersnav.seed_data
```

It's idempotent — safe to run more than once.

## Configuration reference

| Variable | Required | Purpose |
|----------|----------|---------|
| `SECRET_KEY` | yes | Flask session signing key |
| `MONGO_URI` | yes | MongoDB connection string |
| `MONGO_DB_NAME` | no | Database name (default `previous_papers_navigator`) |
| `ADMIN_EMAIL` / `ADMIN_PASSWORD` | no | Default admin account created on first run |
| `PAPERS_PER_PAGE` | no | Results per page when browsing (default 9) |
| `ALLOWED_EMAIL_DOMAINS` | no | Comma-separated domains allowed to register / use Google (blank = any) |
| `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` / `GOOGLE_REDIRECT_URI` | no | Enable Google OAuth |
| `MAIL_SERVER` / `MAIL_PORT` / `MAIL_USERNAME` / `MAIL_PASSWORD` / `MAIL_DEFAULT_SENDER` | no | Enable email |
| `RESET_TOKEN_TTL` | no | Password-reset link lifetime in seconds (default 3600) |

### Restrict to college emails

Set the domain(s) and only those may register or sign in with Google
(subdomains included):

```
ALLOWED_EMAIL_DOMAINS=vit.ac.in,annauniv.edu
```

### Google sign-in

The app sends exactly the `GOOGLE_REDIRECT_URI` you configure, so register that
identical URL in Google Cloud Console → Credentials → **Authorized redirect
URIs**, e.g. `http://localhost:5000/auth/google/callback`.

## Running the tests

```bash
pip install -r requirements-dev.txt
pytest
```

The suite spins up the app against an in-memory MongoDB (mongomock) and covers
registration (domain-restricted), login, upload + admin approval,
browse/search/pagination, view/comment/rate/bookmark, account password change,
and that CSRF protection is active — no real database required.

## Deployment (Render)

Build: `pip install -r requirements.txt` · Start: `gunicorn wsgi:app`. Set the
environment variables from the table above with `FLASK_ENV=production`. A
`render.yaml` and `Procfile` are included.

## Default admin

`admin@gmail.com` / `1234` — **change these in production** via
`ADMIN_EMAIL` / `ADMIN_PASSWORD`.

## Data model (MongoDB collections)

`users`, `papers`, `colleges`, `branches`, `subjects`, `comments`. Indexes are
created automatically on startup.

## Tech stack

Flask · MongoDB · Authlib (Google OAuth) · Flask-Mail · Flask-WTF (CSRF) ·
vanilla HTML/CSS/JS.
