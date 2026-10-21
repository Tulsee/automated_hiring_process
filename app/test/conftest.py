"""Shared fixtures for the test suite.

The routes import their Mongo collections into the module namespace, so the
tests swap those names for in-memory fakes. That keeps the suite free of a
running MongoDB while still exercising the real route code.
"""

from dataclasses import dataclass, field

import pytest
import pytest_asyncio
from bson import ObjectId
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.routes import applications, auth, interviews, jobs
from app.core import auth as auth_core
from app.services import auth_service
from app.services import interview_service


def _matches_condition(value, condition) -> bool:
    """Support the handful of Mongo operators the routes use."""
    if not isinstance(condition, dict):
        return value == condition

    for operator, operand in condition.items():
        if operator == "$gte":
            if value is None or value < operand:
                return False
        elif operator == "$lte":
            if value is None or value > operand:
                return False
        elif operator == "$ne":
            if value == operand:
                return False
        elif operator == "$in":
            if value not in operand:
                return False
        else:  # pragma: no cover - a new operator needs adding here
            raise NotImplementedError(f"FakeCollection: {operator}")

    return True


def _matches(document: dict, query: dict) -> bool:
    for key, value in query.items():
        if key == "$or":
            if not any(_matches(document, clause) for clause in value):
                return False
        elif not _matches_condition(document.get(key), value):
            return False
    return True


def _sort_key(field_and_direction):
    """Mongo orders null before any value, which decides where it lands."""
    field, direction = field_and_direction

    def key(document):
        value = document.get(field)

        return (value is not None, value if value is not None else 0)

    return key, direction


class FakeCursor:
    """Chainable like a Motor cursor: .sort().skip().limit(), then iterate."""

    def __init__(self, documents):
        self._documents = list(documents)

    def sort(self, key_or_list, direction=None):
        if isinstance(key_or_list, str):
            pairs = [(key_or_list, direction or 1)]
        else:
            pairs = list(key_or_list)

        # Apply least-significant key first, as a stable multi-key sort.
        for field, field_direction in reversed(pairs):
            key, _ = _sort_key((field, field_direction))

            self._documents.sort(key=key, reverse=field_direction < 0)

        return self

    def skip(self, count):
        self._documents = self._documents[count:]

        return self

    def limit(self, count):
        self._documents = self._documents[:count]

        return self

    def __aiter__(self):
        async def iterator():
            for document in self._documents:
                yield document

        return iterator()


@dataclass
class FakeCollection:
    """Minimal stand-in for the handful of Motor calls the routes make."""

    documents: list[dict] = field(default_factory=list)

    async def find_one(self, query: dict):
        for document in self.documents:
            if _matches(document, query):
                return document
        return None

    async def insert_one(self, document: dict):
        document.setdefault("_id", ObjectId())
        self.documents.append(document)
        return type("InsertResult", (), {"inserted_id": document["_id"]})()

    async def delete_one(self, query: dict):
        for index, document in enumerate(self.documents):
            if _matches(document, query):
                del self.documents[index]

                return type("DeleteResult", (), {"deleted_count": 1})()

        return type("DeleteResult", (), {"deleted_count": 0})()

    async def count_documents(self, query: dict) -> int:
        return sum(1 for document in self.documents if _matches(document, query))

    def find(self, query: dict | None = None, projection: dict | None = None):
        """Returns a chainable cursor, like Motor."""
        return FakeCursor(
            document
            for document in self.documents
            if _matches(document, query or {})
        )

    async def update_one(self, query: dict, update: dict):
        for document in self.documents:
            if _matches(document, query):
                document.update(update["$set"])
                return type("UpdateResult", (), {"modified_count": 1})()
        return type("UpdateResult", (), {"modified_count": 0})()


@dataclass
class Fakes:
    candidates: FakeCollection
    sessions: FakeCollection
    answers: FakeCollection
    jobs: FakeCollection
    users: FakeCollection
    roles: FakeCollection
    #: candidate ids handed to the background processor
    processed: list[str] = field(default_factory=list)


@pytest.fixture
def fakes(monkeypatch, tmp_path):
    """Replace the route module's collections and upload directory."""
    fakes = Fakes(
        FakeCollection(),
        FakeCollection(),
        FakeCollection(),
        FakeCollection(),
        FakeCollection(),
        FakeCollection(),
    )

    monkeypatch.setattr(interviews, "candidates_collection", fakes.candidates)
    monkeypatch.setattr(
        interviews, "interview_sessions_collection", fakes.sessions
    )
    monkeypatch.setattr(
        interviews, "interview_answers_collections", fakes.answers
    )
    monkeypatch.setattr(interviews, "jobs_collection", fakes.jobs)
    monkeypatch.setattr(interviews, "ANSWER_UPLOAD_DIR", tmp_path)

    # The service holds its own references, and creates sessions for both the
    # route and the screening graph.
    monkeypatch.setattr(
        interview_service, "interview_sessions_collection", fakes.sessions
    )
    monkeypatch.setattr(interview_service, "jobs_collection", fakes.jobs)
    monkeypatch.setattr(
        interview_service, "candidates_collection", fakes.candidates
    )

    # Browsing candidates reads the same collections from its own module.
    monkeypatch.setattr(applications, "candidates_collection", fakes.candidates)
    monkeypatch.setattr(applications, "jobs_collection", fakes.jobs)
    monkeypatch.setattr(
        applications, "interview_sessions_collection", fakes.sessions
    )
    monkeypatch.setattr(
        applications, "interview_answers_collections", fakes.answers
    )

    # Jobs carry the application window, so their routes read the same fake.
    monkeypatch.setattr(jobs, "jobs_collection", fakes.jobs)

    # Uploading a resume schedules this as a background task, and it talks to
    # Mongo, Qdrant and Ollama directly. Replaced with a recorder so a test
    # can assert it was scheduled without running the pipeline.
    async def fake_process(candidate_id: str):
        fakes.processed.append(candidate_id)

    monkeypatch.setattr(applications, "process_candidate", fake_process)

    # Auth reads users and roles from its own module-level handles.
    monkeypatch.setattr(auth_service, "users_collection", fakes.users)
    monkeypatch.setattr(auth_service, "roles_collection", fakes.roles)
    monkeypatch.setattr(auth, "users_collection", fakes.users)
    monkeypatch.setattr(auth, "roles_collection", fakes.roles)

    return fakes


# Every route the app gates now sits behind get_current_user. Tests that are
# not about authorisation run as the superadmin, so the guards pass while the
# endpoint logic under test is reached exactly as before. Auth itself is tested
# with the override cleared (see test_auth.py).
SUPERADMIN_PRINCIPAL = {
    "_id": ObjectId(),
    "email": "superadmin@example.com",
    "name": "Super Admin",
    "kind": "administration",
    "role": None,
    "is_superadmin": True,
    "active": True,
}


@pytest.fixture
def principal():
    """The user the default `client` is signed in as. Tests that need their
    own data to belong to the caller align it to this object (rather than
    importing SUPERADMIN_PRINCIPAL, which pytest's conftest loading would make
    a different instance)."""
    return SUPERADMIN_PRINCIPAL


@pytest.fixture
def app_under_test(fakes):
    app = FastAPI()
    app.include_router(auth.router)
    app.include_router(interviews.router)
    app.include_router(applications.router)
    app.include_router(jobs.router)

    async def _as_superadmin():
        return SUPERADMIN_PRINCIPAL

    # Signed in as the superadmin by default; test_auth.py clears this to run
    # the real guards (see the `real_auth` fixture there). optional_user is
    # overridden too, so the default client counts as a signed-in superadmin
    # for endpoints that personalise (e.g. seeing draft jobs), not as anonymous.
    app.dependency_overrides[auth_core.get_current_user] = _as_superadmin
    app.dependency_overrides[auth_core.optional_user] = _as_superadmin

    return app


@pytest_asyncio.fixture
async def client(app_under_test):
    transport = ASGITransport(app=app_under_test)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
def candidate(fakes):
    """An interview-eligible candidate."""
    document = {
        "_id": ObjectId(),
        "job_id": str(ObjectId()),
        "decision": "invited_to_interview",
    }
    fakes.candidates.documents.append(document)
    return document
