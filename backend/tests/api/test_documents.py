"""The /documents endpoints: the draft lifecycle (create, restore, autosave, submit) and
the re-check stream.

The lifecycle tests round-trip through the real CRUD path. The re-check test substitutes the
streaming service with fixed events to pin the transport and the recheck trigger without a live
engine run; the re-surfacing behaviour over the real engine is covered in the service test, and
the dismissal-clearing side effect is asserted directly since the handler commits it before the
stream opens.
"""

import uuid
from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from pattern_mirror.api import documents
from pattern_mirror.api.deps import get_current_user
from pattern_mirror.db.session import get_session
from pattern_mirror.main import create_app
from pattern_mirror.models.documents import AnalysisRun, Document
from pattern_mirror.models.engine import FlagDismissal
from pattern_mirror.models.enums import AnalysisRunStatus, AnalysisTrigger, DocType
from pattern_mirror.models.identity import User
from pattern_mirror.models.jd_criteria import JdCriterion
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
def documents_client(db_session: Session, owner: User) -> Iterator[TestClient]:
    app = create_app()
    app.dependency_overrides[get_session] = lambda: db_session
    app.dependency_overrides[get_current_user] = lambda: owner
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


def test_create_returns_an_empty_draft(documents_client: TestClient) -> None:
    response = documents_client.post("/documents", json={"doc_type": "jd"})

    assert response.status_code == 200
    body = response.json()
    assert body["id"]
    assert body["doc_type"] == "jd"
    assert body["status"] == "draft"
    assert body["content"] == ""
    assert body["title"] is None


def test_list_returns_the_owners_documents_without_content(
    documents_client: TestClient, db_session: Session, owner: User
) -> None:
    mine = Document(
        owner_id=owner.id,
        doc_type=DocType.jd,
        title="Senior Engineer",
        role_title="Engineering",
        content="draft text",
    )
    other = User(
        external_user_id="documents-list-other",
        legal_name="Documents List Other",
        email="documents.list.other@example.com",
    )
    db_session.add_all([mine, other])
    db_session.flush()
    db_session.add(Document(owner_id=other.id, doc_type=DocType.jd, content="hidden"))
    db_session.flush()

    response = documents_client.get("/documents")

    assert response.status_code == 200
    body = response.json()
    assert [item["id"] for item in body] == [str(mine.id)]
    summary = body[0]
    assert summary["title"] == "Senior Engineer"
    assert summary["role_title"] == "Engineering"
    assert summary["status"] == "draft"
    assert summary["created_at"]
    assert "content" not in summary


def test_autosave_round_trips_through_get(documents_client: TestClient) -> None:
    doc_id = documents_client.post("/documents", json={"doc_type": "jd"}).json()["id"]

    patched = documents_client.patch(
        f"/documents/{doc_id}",
        json={"title": "Senior Engineer", "content": "We want a digital native."},
    )
    assert patched.status_code == 200

    restored = documents_client.get(f"/documents/{doc_id}").json()
    assert restored["title"] == "Senior Engineer"
    assert restored["content"] == "We want a digital native."
    assert restored["status"] == "draft"


def test_autosave_persists_no_analysis_run(
    documents_client: TestClient, db_session: Session
) -> None:
    doc_id = documents_client.post("/documents", json={"doc_type": "jd"}).json()["id"]

    documents_client.patch(f"/documents/{doc_id}", json={"content": "We want a digital native."})

    runs = db_session.scalar(
        select(func.count())
        .select_from(AnalysisRun)
        .where(AnalysisRun.document_id == uuid.UUID(doc_id))
    )
    assert runs == 0


def test_submit_transitions_and_captures_final_text(
    documents_client: TestClient, db_session: Session
) -> None:
    doc_id = documents_client.post("/documents", json={"doc_type": "jd"}).json()["id"]
    documents_client.patch(f"/documents/{doc_id}", json={"content": "draft text"})

    response = documents_client.post(f"/documents/{doc_id}/submit", json={"content": "final text"})

    assert response.status_code == 200
    assert response.json()["status"] == "submitted"

    document = db_session.get(Document, uuid.UUID(doc_id))
    assert document is not None
    assert document.submitted_content == "final text"
    assert document.submitted_at is not None


def test_fetching_an_unknown_document_is_rejected(documents_client: TestClient) -> None:
    response = documents_client.get(f"/documents/{uuid.uuid4()}")

    assert response.status_code == 404


def test_autosave_of_another_users_document_is_rejected(
    documents_client: TestClient, db_session: Session
) -> None:
    other = User(
        external_user_id="documents-other-manager",
        legal_name="Documents Other Manager",
        email="documents.other@example.com",
    )
    db_session.add(other)
    db_session.flush()
    foreign = Document(owner_id=other.id, doc_type=DocType.jd, content="text")
    db_session.add(foreign)
    db_session.flush()

    response = documents_client.patch(f"/documents/{foreign.id}", json={"content": "x"})

    assert response.status_code == 404


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
    documents_client: TestClient, db_session: Session, owner: User, monkeypatch: pytest.MonkeyPatch
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

    response = documents_client.post(f"/documents/{document.id}/recheck", json={"content": "text"})

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert "event: stage" in response.text
    assert "event: done" in response.text
    assert captured["trigger"] is AnalysisTrigger.recheck

    db_session.refresh(dismissal)
    assert dismissal.active is False


def test_recheck_of_feedback_attaches_the_drift_check(
    documents_client: TestClient, db_session: Session, owner: User, monkeypatch: pytest.MonkeyPatch
) -> None:
    jd = Document(owner_id=owner.id, doc_type=DocType.jd, role_title="Analyst", content="jd")
    db_session.add(jd)
    db_session.flush()
    db_session.add(JdCriterion(jd_document_id=jd.id, text="Python proficiency", position=0))
    feedback = Document(
        owner_id=owner.id, doc_type=DocType.feedback, reference_jd_id=jd.id, content="fb"
    )
    db_session.add(feedback)
    db_session.flush()

    captured: dict[str, Any] = {}

    def fake_stream(*args: object, **kwargs: object) -> Iterator[object]:
        captured.update(kwargs)
        yield RunCompleted(
            analysis_run_id=uuid.uuid4(), status=AnalysisRunStatus.complete, flag_count=0
        )

    monkeypatch.setattr(documents, "stream_analysis_events", fake_stream)

    response = documents_client.post(f"/documents/{feedback.id}/recheck", json={"content": "fb"})

    assert response.status_code == 200
    reference = captured["drift_reference"]
    assert reference is not None
    assert reference.reference_text == "Python proficiency"
    assert captured["drift_client"] is captured["contextual_client"]


def test_recheck_of_an_unknown_document_is_rejected(documents_client: TestClient) -> None:
    response = documents_client.post(f"/documents/{uuid.uuid4()}/recheck", json={"content": "text"})

    assert response.status_code == 404


def test_recheck_of_another_users_document_is_rejected(
    documents_client: TestClient, db_session: Session
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

    response = documents_client.post(f"/documents/{foreign.id}/recheck", json={"content": "text"})

    assert response.status_code == 404
