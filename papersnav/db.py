"""MongoDB access layer.

A thin wrapper around a single MongoClient that exposes the collections used by
the app as attributes (``db.users``, ``db.papers`` ...). Blueprints import the
shared ``db`` instance and never touch pymongo directly.
"""
import logging

from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError

logger = logging.getLogger("papersnav")


class Database:
    """Lazily-initialised holder for the Mongo connection and collections."""

    def __init__(self):
        self._client = None
        self._db = None

    def init_app(self, app):
        uri = app.config.get("MONGO_URI")
        if not uri:
            raise ValueError("MONGO_URI is required but not set")

        try:
            self._client = MongoClient(
                uri, serverSelectionTimeoutMS=5000, connectTimeoutMS=5000
            )
            self._client.admin.command("ping")
        except (ServerSelectionTimeoutError, ConnectionFailure) as exc:
            logger.error("Failed to connect to MongoDB: %s", exc)
            raise

        self._db = self._client[app.config["MONGO_DB_NAME"]]
        logger.info("Connected to MongoDB (%s)", app.config["MONGO_DB_NAME"])
        self._ensure_indexes()
        # expose on the app for convenience / testing
        app.extensions["database"] = self
        return self

    # ── Collections ───────────────────────────────────────────────────────
    @property
    def handle(self):
        if self._db is None:
            raise RuntimeError("Database not initialised; call init_app() first")
        return self._db

    @property
    def users(self):
        return self.handle["users"]

    @property
    def papers(self):
        return self.handle["papers"]

    @property
    def colleges(self):
        return self.handle["colleges"]

    @property
    def branches(self):
        return self.handle["branches"]

    @property
    def subjects(self):
        return self.handle["subjects"]

    @property
    def comments(self):
        return self.handle["comments"]

    @property
    def otp_requests(self):
        return self.handle["otp_requests"]

    @property
    def posts(self):
        return self.handle["posts"]

    @property
    def post_comments(self):
        return self.handle["post_comments"]

    @property
    def messages(self):
        return self.handle["messages"]

    @property
    def fs(self):
        """GridFS handle for storing uploaded PDFs in MongoDB (persistent)."""
        import gridfs

        return gridfs.GridFS(self.handle)

    # ── Indexes ───────────────────────────────────────────────────────────
    def _ensure_indexes(self):
        try:
            self.users.create_index("email", unique=True)
            self.papers.create_index("status")
            self.papers.create_index(
                [("college", 1), ("branch", 1), ("semester", 1), ("subject", 1)]
            )
            self.branches.create_index("college_code")
            self.subjects.create_index([("branch_code", 1), ("semester", 1)])
            self.comments.create_index([("paper_id", 1), ("created_at", -1)])
            self.posts.create_index([("created_at", -1)])
            self.post_comments.create_index([("post_id", 1), ("created_at", 1)])
            self.messages.create_index([("created_at", -1)])
            logger.info("Database indexes ensured")
        except Exception as exc:  # non-fatal
            logger.warning("Index creation warning: %s", exc)


# Shared singleton imported across the codebase.
db = Database()
