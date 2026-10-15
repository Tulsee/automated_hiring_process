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

from app.routes import interviews


def _matches(document: dict, query: dict) -> bool:
    return all(document.get(key) == value for key, value in query.items())


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

    async def count_documents(self, query: dict) -> int:
        return sum(1 for document in self.documents if _matches(document, query))

    def find(self, query: dict, projection: dict | None = None):
        """Returns an async iterator, like a Motor cursor."""
        matches = [
            document for document in self.documents if _matches(document, query)
        ]

        async def cursor():
            for document in matches:
                yield document

        return cursor()

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


@pytest.fixture
def fakes(monkeypatch, tmp_path):
    """Replace the route module's collections and upload directory."""
    fakes = Fakes(FakeCollection(), FakeCollection(), FakeCollection())

    monkeypatch.setattr(interviews, "candidates_collection", fakes.candidates)
    monkeypatch.setattr(
        interviews, "interview_sessions_collection", fakes.sessions
    )
    monkeypatch.setattr(
        interviews, "interview_answers_collections", fakes.answers
    )
    monkeypatch.setattr(interviews, "ANSWER_UPLOAD_DIR", tmp_path)

    return fakes


@pytest_asyncio.fixture
async def client(fakes):
    app = FastAPI()
    app.include_router(interviews.router)

    transport = ASGITransport(app=app)
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
