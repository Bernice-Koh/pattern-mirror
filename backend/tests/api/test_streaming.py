"""The /analyze/stream endpoint: SSE framing, a terminal event, and ownership rejection.

The framing test substitutes the streaming service with fixed events so the test pins the
transport (event names, ``data:`` JSON, media type) without a live engine run; the
end-to-end engine behaviour is covered in the service test. ``_format_sse`` is unit-tested
per event type, with a real persisted flag for the flag frame.
"""

import uuid
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from pattern_mirror.api import streaming
from pattern_mirror.api.deps import get_current_user
from pattern_mirror.api.streaming import _format_sse
from pattern_mirror.db.session import get_session
from pattern_mirror.main import create_app
from pattern_mirror.models.documents import Document
from pattern_mirror.models.enums import AnalysisRunStatus, DocType
from pattern_mirror.models.identity import User
from pattern_mirror.services.analysis import analyze_document
from pattern_mirror.services.streaming_analysis import (
    FlagSurfaced,
    RunCompleted,
    StageCompleted,
)

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


def test_format_sse_renders_stage_and_done_frames() -> None:
    stage_frame = _format_sse(StageCompleted(stage="judge")).decode()
    assert stage_frame == 'event: stage\ndata: {"stage":"judge"}\n\n'

    run_id = uuid.uuid4()
    done_frame = _format_sse(
        RunCompleted(analysis_run_id=run_id, status=AnalysisRunStatus.complete, flag_count=2)
    ).decode()
    assert done_frame.startswith("event: done\ndata: ")
    assert f'"analysis_run_id":"{run_id}"' in done_frame
    assert '"status":"complete"' in done_frame
    assert '"flag_count":2' in done_frame


def test_format_sse_renders_a_flag_frame_from_a_persisted_flag(db_session: Session) -> None:
    user = User(
        external_user_id="flag-frame-manager",
        legal_name="Flag Frame Manager",
        email="flag.frame@example.com",
    )
    db_session.add(user)
    db_session.flush()
    result = analyze_document(
        db_session,
        owner_id=user.id,
        doc_type=DocType.jd,
        content="We want a digital native.",
    )

    frame = _format_sse(FlagSurfaced(flag=result.flags[0])).decode()

    assert frame.startswith("event: flag\ndata: ")
    assert '"raw_span":"digital native"' in frame
    assert '"citation":' in frame
    # A dictionary flag the Recommendations Agent never runs on serialises with a null field.
    assert '"recommendations":null' in frame


def test_format_sse_renders_recommendations_when_a_flag_has_them(db_session: Session) -> None:
    user = User(
        external_user_id="rec-frame-manager",
        legal_name="Rec Frame Manager",
        email="rec.frame@example.com",
    )
    db_session.add(user)
    db_session.flush()
    result = analyze_document(
        db_session,
        owner_id=user.id,
        doc_type=DocType.jd,
        content="We want a digital native.",
    )
    flag = result.flags[0]
    flag.recommendations = {
        "rationale": "Coded age bias.",
        "alternatives": ["adaptable", "tech-savvy"],
    }
    db_session.flush()

    frame = _format_sse(FlagSurfaced(flag=flag)).decode()

    assert '"rationale":"Coded age bias."' in frame
    assert '"adaptable"' in frame
