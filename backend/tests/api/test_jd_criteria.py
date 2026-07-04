"""The JD-criteria endpoints on the /documents router: draft (agent), confirm (write), read.

The extraction agent's Anthropic client is substituted with a fake so these run offline; the
draft endpoint persists only an audit row, so the confirm/read round-trip is what proves a
criterion reaches ``jd_criteria``.
"""

import uuid
from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from pattern_mirror.api import documents
from pattern_mirror.api.deps import get_current_user
from pattern_mirror.db.session import get_session
from pattern_mirror.engine.jd_criteria_extraction import (
    JdCriteriaDraftResult,
    JdCriterionDraft,
)
from pattern_mirror.main import create_app
from pattern_mirror.models.documents import Document
from pattern_mirror.models.enums import DocType
from pattern_mirror.models.identity import User

pytestmark = pytest.mark.db


class _FakeUsage:
    def __init__(self, input_tokens: int, output_tokens: int) -> None:
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens


class _FakeCompletion:
    def __init__(self, usage: _FakeUsage) -> None:
        self.usage = usage


class _FakeExtractionClient:
    def __init__(self, *texts: str) -> None:
        self._result = JdCriteriaDraftResult(
            criteria=[JdCriterionDraft(text=text) for text in texts]
        )
        self._completion = _FakeCompletion(_FakeUsage(300, 60))

    def create_with_completion(self, **kwargs: Any) -> tuple[Any, Any]:
        return self._result, self._completion


@pytest.fixture
def owner(db_session: Session) -> User:
    user = User(
        external_user_id="jd-criteria-api-manager",
        legal_name="JD Criteria API Manager",
        email="jd.criteria.api@example.com",
    )
    db_session.add(user)
    db_session.flush()
    return user


@pytest.fixture
def api_client(db_session: Session, owner: User) -> Iterator[TestClient]:
    app = create_app()
    app.dependency_overrides[get_session] = lambda: db_session
    app.dependency_overrides[get_current_user] = lambda: owner
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


def _jd(db_session: Session, owner: User) -> uuid.UUID:
    jd = Document(owner_id=owner.id, doc_type=DocType.jd, content="jd text")
    db_session.add(jd)
    db_session.flush()
    return jd.id


def test_draft_returns_criteria_from_the_agent(
    api_client: TestClient, db_session: Session, owner: User, monkeypatch: pytest.MonkeyPatch
) -> None:
    jd_id = _jd(db_session, owner)
    monkeypatch.setattr(
        documents,
        "build_instructor_client",
        lambda settings: _FakeExtractionClient("Python proficiency", "Leadership"),
    )

    response = api_client.post(
        f"/documents/{jd_id}/jd-criteria/draft", json={"content": "Senior engineer role."}
    )

    assert response.status_code == 200
    assert response.json()["criteria"] == ["Python proficiency", "Leadership"]


def test_draft_without_a_configured_client_returns_503(
    api_client: TestClient, db_session: Session, owner: User, monkeypatch: pytest.MonkeyPatch
) -> None:
    jd_id = _jd(db_session, owner)
    monkeypatch.setattr(documents, "build_instructor_client", lambda settings: None)

    response = api_client.post(f"/documents/{jd_id}/jd-criteria/draft", json={"content": "x"})

    assert response.status_code == 503


def test_draft_on_a_non_jd_returns_409(
    api_client: TestClient, db_session: Session, owner: User, monkeypatch: pytest.MonkeyPatch
) -> None:
    feedback = Document(owner_id=owner.id, doc_type=DocType.feedback, content="fb")
    db_session.add(feedback)
    db_session.flush()
    monkeypatch.setattr(
        documents, "build_instructor_client", lambda settings: _FakeExtractionClient("a")
    )

    response = api_client.post(f"/documents/{feedback.id}/jd-criteria/draft", json={"content": "x"})

    assert response.status_code == 409


def test_confirm_then_read_round_trips_the_criteria(
    api_client: TestClient, db_session: Session, owner: User
) -> None:
    jd_id = _jd(db_session, owner)

    confirmed = api_client.put(
        f"/documents/{jd_id}/jd-criteria",
        json={"criteria": ["First", "  ", "first", "Second"]},
    )
    assert confirmed.status_code == 200
    assert confirmed.json()["criteria"] == ["First", "Second"]

    read = api_client.get(f"/documents/{jd_id}/jd-criteria")
    assert read.status_code == 200
    assert read.json()["criteria"] == ["First", "Second"]


def test_read_of_another_users_jd_is_rejected(api_client: TestClient, db_session: Session) -> None:
    other = User(
        external_user_id="jd-criteria-api-other",
        legal_name="JD Criteria API Other",
        email="jd.criteria.api.other@example.com",
    )
    db_session.add(other)
    db_session.flush()
    foreign = Document(owner_id=other.id, doc_type=DocType.jd, content="jd")
    db_session.add(foreign)
    db_session.flush()

    response = api_client.get(f"/documents/{foreign.id}/jd-criteria")

    assert response.status_code == 404
