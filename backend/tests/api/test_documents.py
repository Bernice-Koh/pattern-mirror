"""The /documents/{doc_id}/recheck endpoint: clears dismissals, then streams a fresh run.

Like the streaming endpoint test, these substitute the streaming service with fixed events
to pin the transport and the recheck trigger without a live engine run; the re-surfacing
behaviour over the real engine is covered in the service test. The dismissal-clearing side
effect is asserted directly, since the handler commits it before the stream opens.
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
from pattern_mirror.main import create_app
from pattern_mirror.models.documents import Document
from pattern_mirror.models.engine import FlagDismissal
from pattern_mirror.models.enums import AnalysisRunStatus, AnalysisTrigger, DocType
from pattern_mirror.models.identity import User
from pattern_mirror.services.streaming_analysis import RunCompleted, StageCompleted

pytestmark = pytest.mark.db


@pytest.fixture
def owner(db_session: Session) -> User:
    user = User(
        external_user_id="recheck-api-manager",
        legal_name="Recheck API Manager",
        email="recheck.api@example.com",
    )
    db_session.add(user)
    db_session.flush()
    return user


@pytest.fixture
def recheck_client(db_session: Session, owner: User) -> Iterator[TestClient]:
    app = create_app()
    app.dependency_overrides[get_session] = lambda: db_session
    app.dependency_overrides[get_current_user] = lambda: owner
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


def _dismissal_on(db_session: Session, document: Document) -> FlagDismissal:
    dismissal = FlagDismissal(
        document_id=document.id,
        rule_id=None,
        normalised_span="digital native",
        sentence_fingerprint="f" * 64,
        active=True,
    )
    db_session.add(dismissal)
    db_session.flush()
    return dismissal


def test_recheck_clears_dismissals_and_streams_a_terminal_done(
    recheck_client: TestClient, db_session: Session, owner: User, monkeypatch: pytest.MonkeyPatch
) -> None:
    document = Document(owner_id=owner.id, doc_type=DocType.jd, content="text")
    db_session.add(document)
    db_session.flush()
    dismissal = _dismissal_on(db_session, document)

    captured: dict[str, Any] = {}

    def fake_stream(*args: object, **kwargs: object) -> Iterator[object]:
        captured.update(kwargs)
        yield StageCompleted(stage="dictionary")
        yield RunCompleted(
            analysis_run_id=uuid.uuid4(), status=AnalysisRunStatus.complete, flag_count=0
        )

    monkeypatch.setattr(documents, "stream_analysis_events", fake_stream)

    response = recheck_client.post(f"/documents/{document.id}/recheck", json={"content": "text"})

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert "event: stage" in response.text
    assert "event: done" in response.text
    assert captured["trigger"] is AnalysisTrigger.recheck

    db_session.refresh(dismissal)
    assert dismissal.active is False


def test_recheck_of_an_unknown_document_is_rejected(recheck_client: TestClient) -> None:
    response = recheck_client.post(f"/documents/{uuid.uuid4()}/recheck", json={"content": "text"})

    assert response.status_code == 404


def test_recheck_of_another_users_document_is_rejected(
    recheck_client: TestClient, db_session: Session
) -> None:
    other = User(
        external_user_id="recheck-other-manager",
        legal_name="Recheck Other Manager",
        email="recheck.other@example.com",
    )
    db_session.add(other)
    db_session.flush()
    foreign = Document(owner_id=other.id, doc_type=DocType.jd, content="text")
    db_session.add(foreign)
    db_session.flush()

    response = recheck_client.post(f"/documents/{foreign.id}/recheck", json={"content": "text"})

    assert response.status_code == 404
