"""Shared test fixtures for Lodge API tests.

Uses Starlette's TestClient so no running server is needed and sync step defs
work without async boilerplate.
The stub database overrides get_db so no real PostgreSQL is required.
"""

from __future__ import annotations

import uuid
from typing import Any, Generator

import pytest
from starlette.testclient import TestClient

from lodge.adapters.outbound.db import get_db
from lodge.adapters.inbound.api import app


# ---------------------------------------------------------------------------
# Stub database session
# ---------------------------------------------------------------------------


class _ScalarResult:
    def __init__(self, value: Any = 0) -> None:
        self._value = value

    def scalar_one(self) -> Any:
        return self._value

    def scalars(self) -> "_ScalarResult":
        return self

    def all(self) -> list:
        return []


class _StubSession:
    """In-memory stub satisfying router db.add / commit / refresh / execute patterns."""

    def add(self, obj: Any) -> None:
        if not getattr(obj, "id", None):
            obj.id = uuid.uuid4()

    async def commit(self) -> None:
        pass

    async def refresh(self, obj: Any) -> None:
        pass

    async def execute(self, *args: Any, **kwargs: Any) -> _ScalarResult:
        return _ScalarResult(0)


# ---------------------------------------------------------------------------
# Dependency override
# ---------------------------------------------------------------------------


async def _override_get_db():
    yield _StubSession()


app.dependency_overrides[get_db] = _override_get_db


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    """Sync test client wired to the FastAPI app; no running server needed."""
    with TestClient(app, raise_server_exceptions=True) as c:
        yield c
