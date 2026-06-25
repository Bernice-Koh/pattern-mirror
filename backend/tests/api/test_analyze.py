"""End-to-end /analyze: persisted cited flags out; an unknown doc_type rejected.

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
from pattern_mirror.models.identity import User

pytestmark = pytest.mark.db


@pytest.fixture
def analyze_client(db_session: Session) -> Iterator[TestClient]:
    user = User(
        external_user_id="api-test-manager",
        legal_name="API Manager",
        email="api.manager@example.com",
    )
    db_session.add(user)
    db_session.flush()

    app = create_app()
    app.dependency_overrides[get_session] = lambda: db_session
    app.dependency_overrides[get_current_user] = lambda: user
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


def test_biased_document_returns_persisted_cited_flags(
    analyze_client: TestClient, db_session: Session
) -> None:
    response = analyze_client.post(
        "/analyze", json={"doc_type": "jd", "content": "We want a digital native."}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["analysis_run_id"]
    assert len(body["content_hash"]) == 64
    assert len(body["flags"]) == 1
    flag = body["flags"][0]
    assert flag["category"] == "age"
    assert flag["raw_span"] == "digital native"
    assert flag["citation"]["source_type"] == "tafep"

    document_id = uuid.UUID(body["document_id"])
    assert db_session.get(Document, document_id) is not None
    persisted = db_session.scalars(select(Flag).where(Flag.document_id == document_id)).all()
    assert len(persisted) == 1


def test_unknown_doc_type_is_rejected(analyze_client: TestClient) -> None:
    response = analyze_client.post("/analyze", json={"doc_type": "memo", "content": "anything"})

    assert response.status_code == 422


def test_response_carries_only_typed_fields(analyze_client: TestClient) -> None:
    response = analyze_client.post(
        "/analyze", json={"doc_type": "jd", "content": "We want a digital native."}
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
    }
