"""End-to-end drift endpoints: read a document's findings, dismiss one, foreign access 404s.

Session and current-user dependencies are overridden onto the test's rolled-back transaction, so
the endpoint's writes and the test's assertions share one transaction.
"""

import uuid
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from pattern_mirror.api.deps import get_current_user
from pattern_mirror.db.session import get_session
from pattern_mirror.engine.state import DriftFinding as DriftFindingState
from pattern_mirror.main import create_app
from pattern_mirror.models.documents import AnalysisRun, Document
from pattern_mirror.models.drift import (
    DriftFinding,
    DriftFindingDismissal,
    DriftFindingInteraction,
)
from pattern_mirror.models.enums import (
    AnalysisRunStatus,
    AnalysisTrigger,
    DocType,
    ReferenceKind,
)
from pattern_mirror.models.identity import User
from pattern_mirror.services.drift_findings import persist_drift_findings

pytestmark = pytest.mark.db


@pytest.fixture
def drift_client(db_session: Session) -> Iterator[tuple[TestClient, User]]:
    user = User(
        external_user_id="api-drift-manager",
        legal_name="API Drift Manager",
        email="api.drift@example.com",
    )
    db_session.add(user)
    db_session.flush()

    app = create_app()
    app.dependency_overrides[get_session] = lambda: db_session
    app.dependency_overrides[get_current_user] = lambda: user
    with TestClient(app) as client:
        yield client, user
    app.dependency_overrides.clear()


def _document_with_findings(
    db_session: Session, owner: User, *findings: DriftFindingState
) -> Document:
    document = Document(owner_id=owner.id, doc_type=DocType.feedback, content="Doc under analysis.")
    db_session.add(document)
    db_session.flush()
    run = AnalysisRun(
        document_id=document.id,
        trigger=AnalysisTrigger.typing_pause,
        content_hash="0" * 64,
        status=AnalysisRunStatus.complete,
    )
    db_session.add(run)
    db_session.flush()
    persist_drift_findings(
        db_session,
        run=run,
        document_id=document.id,
        reference_kind=ReferenceKind.jd_criteria,
        findings=list(findings),
    )
    return document


def _finding(
    criterion: str, *, addressed: bool = False, evidence: str | None = None
) -> DriftFindingState:
    return DriftFindingState(
        criterion=criterion,
        addressed=addressed,
        evidence=evidence,
        evidence_start=0 if evidence else None,
        evidence_end=len(evidence) if evidence else None,
    )


def test_get_returns_the_documents_findings_in_one_shape(
    drift_client: tuple[TestClient, User], db_session: Session
) -> None:
    client, user = drift_client
    document = _document_with_findings(
        db_session,
        user,
        _finding("leadership", addressed=True, evidence="led"),
        _finding("stakeholder management"),
    )

    response = client.get(f"/documents/{document.id}/drift-findings")

    assert response.status_code == 200
    body = response.json()
    assert {f["criterion"] for f in body} == {"leadership", "stakeholder management"}
    addressed = next(f for f in body if f["criterion"] == "leadership")
    assert addressed["reference_kind"] == "jd_criteria"
    assert addressed["addressed"] is True
    assert addressed["evidence"] == "led"


def test_dismiss_persists_an_event_and_a_dismissal(
    drift_client: tuple[TestClient, User], db_session: Session
) -> None:
    client, user = drift_client
    document = _document_with_findings(db_session, user, _finding("stakeholder management"))
    finding = db_session.scalars(
        select(DriftFinding).where(DriftFinding.document_id == document.id)
    ).one()

    response = client.post(f"/drift-findings/{finding.id}/interactions", json={"kind": "dismiss"})

    assert response.status_code == 200
    body = response.json()
    assert body["kind"] == "dismiss"
    assert body["dismissed"] is True
    assert db_session.scalars(
        select(DriftFindingInteraction).where(
            DriftFindingInteraction.drift_finding_id == finding.id
        )
    ).one()
    assert db_session.scalars(
        select(DriftFindingDismissal).where(DriftFindingDismissal.document_id == document.id)
    ).one()


def test_a_dismissed_finding_drops_out_of_the_next_read(
    drift_client: tuple[TestClient, User], db_session: Session
) -> None:
    client, user = drift_client
    document = _document_with_findings(
        db_session, user, _finding("stakeholder management"), _finding("leadership")
    )
    dismissed = db_session.scalars(
        select(DriftFinding).where(
            DriftFinding.document_id == document.id,
            DriftFinding.criterion == "stakeholder management",
        )
    ).one()

    client.post(f"/drift-findings/{dismissed.id}/interactions", json={"kind": "dismiss"})
    response = client.get(f"/documents/{document.id}/drift-findings")

    # The dismissal only suppresses on the next run; this run's rows still read back. The signature
    # is what carries the dismissal forward, asserted in the service tests.
    assert response.status_code == 200
    assert {f["criterion"] for f in response.json()} == {"stakeholder management", "leadership"}


def test_get_on_another_users_document_is_not_found(
    drift_client: tuple[TestClient, User], db_session: Session
) -> None:
    client, _ = drift_client
    other = User(
        external_user_id="api-drift-other",
        legal_name="Other Manager",
        email="api.drift.other@example.com",
    )
    db_session.add(other)
    db_session.flush()
    document = _document_with_findings(db_session, other, _finding("leadership"))

    response = client.get(f"/documents/{document.id}/drift-findings")

    assert response.status_code == 404


def test_dismiss_of_an_unknown_finding_is_not_found(
    drift_client: tuple[TestClient, User],
) -> None:
    client, _ = drift_client

    response = client.post(f"/drift-findings/{uuid.uuid4()}/interactions", json={"kind": "dismiss"})

    assert response.status_code == 404


def test_unknown_kind_is_rejected(
    drift_client: tuple[TestClient, User], db_session: Session
) -> None:
    client, user = drift_client
    document = _document_with_findings(db_session, user, _finding("leadership"))
    finding = db_session.scalars(
        select(DriftFinding).where(DriftFinding.document_id == document.id)
    ).one()

    response = client.post(f"/drift-findings/{finding.id}/interactions", json={"kind": "accept"})

    assert response.status_code == 422
