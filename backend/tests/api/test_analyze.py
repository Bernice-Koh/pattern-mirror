"""End-to-end /analyze: persisted cited flags out for an existing document.

The client's session and current-user dependencies are overridden onto the test's
rolled-back transaction, so the endpoint's writes and the test's assertions share one
transaction and the round trip can be verified down to the persisted rows.
"""

import uuid
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from pattern_mirror.api.deps import get_current_user
from pattern_mirror.db.session import get_session
from pattern_mirror.main import create_app
from pattern_mirror.models.documents import Document
from pattern_mirror.models.engine import Flag
from pattern_mirror.models.enums import DocType
from pattern_mirror.models.identity import User

pytestmark = pytest.mark.db


@pytest.fixture
def owner(db_session: Session) -> User:
    user = User(
        external_user_id="api-test-manager",
        legal_name="API Manager",
        email="api.manager@example.com",
    )
    db_session.add(user)
    db_session.flush()
    return user


@pytest.fixture
def draft(db_session: Session, owner: User) -> Document:
    document = Document(owner_id=owner.id, doc_type=DocType.jd)
    db_session.add(document)
    db_session.flush()
    return document


@pytest.fixture
def analyze_client(db_session: Session, owner: User) -> Iterator[TestClient]:
    app = create_app()
    app.dependency_overrides[get_session] = lambda: db_session
    app.dependency_overrides[get_current_user] = lambda: owner
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


def test_biased_document_returns_persisted_cited_flags(
    analyze_client: TestClient, db_session: Session, draft: Document
) -> None:
    response = analyze_client.post(
        "/analyze", json={"document_id": str(draft.id), "content": "We want a digital native."}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["document_id"] == str(draft.id)
    assert body["analysis_run_id"]
    assert len(body["content_hash"]) == 64
    assert len(body["flags"]) == 1
    flag = body["flags"][0]
    assert flag["category"] == "age"
    assert flag["raw_span"] == "digital native"
    assert flag["citation"]["source_type"] == "tafep"

    persisted = db_session.scalars(select(Flag).where(Flag.document_id == draft.id)).all()
    assert len(persisted) == 1


def test_unknown_document_is_rejected(analyze_client: TestClient) -> None:
    response = analyze_client.post(
        "/analyze", json={"document_id": str(uuid.uuid4()), "content": "anything"}
    )

    assert response.status_code == 404


def test_response_carries_only_typed_fields(analyze_client: TestClient, draft: Document) -> None:
    response = analyze_client.post(
        "/analyze", json={"document_id": str(draft.id), "content": "We want a digital native."}
    )

    flag = response.json()["flags"][0]
    assert set(flag) == {
        "id",
        "source_stage",
        "category",
        "raw_span",
        "start_offset",
        "end_offset",
        "explanation",
        "citation",
        "recommendations",
    }
