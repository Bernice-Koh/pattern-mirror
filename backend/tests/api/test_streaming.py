"""The /analyze/stream endpoint: SSE transport, a terminal event, and ownership rejection.

These tests substitute the streaming service with fixed events so they pin the transport
(event names, media type, terminal frame) without a live engine run; the end-to-end engine
behaviour is covered in the service test and the SSE framing in ``test_sse``.
"""

import uuid
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from pattern_mirror.api import streaming
from pattern_mirror.api.deps import get_current_user
from pattern_mirror.db.session import get_session
from pattern_mirror.main import create_app
from pattern_mirror.models.documents import Document
from pattern_mirror.models.enums import AnalysisRunStatus, DocType
from pattern_mirror.models.identity import User
from pattern_mirror.services.streaming_analysis import RunCompleted, StageCompleted

pytestmark = pytest.mark.db


@pytest.fixture
def owner(db_session: Session) -> User:
    user = User(
        external_user_id="stream-api-manager",
        legal_name="Stream API Manager",
        email="stream.api@example.com",
    )
    db_session.add(user)
    db_session.flush()
    return user


@pytest.fixture
def stream_client(db_session: Session, owner: User) -> Iterator[TestClient]:
    app = create_app()
    app.dependency_overrides[get_session] = lambda: db_session
    app.dependency_overrides[get_current_user] = lambda: owner
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


def test_stream_emits_sse_frames_and_a_terminal_done(
    stream_client: TestClient, db_session: Session, owner: User, monkeypatch: pytest.MonkeyPatch
) -> None:
    document = Document(owner_id=owner.id, doc_type=DocType.jd, content="text")
    db_session.add(document)
    db_session.flush()

    run_id = uuid.uuid4()

    def fake_stream(*args: object, **kwargs: object) -> Iterator[object]:
        yield StageCompleted(stage="contextual")
        yield RunCompleted(analysis_run_id=run_id, status=AnalysisRunStatus.complete, flag_count=0)

    monkeypatch.setattr(streaming, "stream_analysis_events", fake_stream)

    response = stream_client.post(
        "/analyze/stream", json={"document_id": str(document.id), "content": "text"}
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert "event: stage" in response.text
    assert "event: done" in response.text
    assert str(run_id) in response.text


def test_unknown_document_is_rejected(stream_client: TestClient) -> None:
    response = stream_client.post(
        "/analyze/stream", json={"document_id": str(uuid.uuid4()), "content": "text"}
    )

    assert response.status_code == 404


def test_another_users_document_is_rejected(stream_client: TestClient, db_session: Session) -> None:
    other = User(
        external_user_id="other-manager",
        legal_name="Other Manager",
        email="other@example.com",
    )
    db_session.add(other)
    db_session.flush()
    foreign = Document(owner_id=other.id, doc_type=DocType.jd, content="text")
    db_session.add(foreign)
    db_session.flush()

    response = stream_client.post(
        "/analyze/stream", json={"document_id": str(foreign.id), "content": "text"}
    )

    assert response.status_code == 404
