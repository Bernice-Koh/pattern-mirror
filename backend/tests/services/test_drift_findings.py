"""persist_drift_findings logs every finding (suppressing dismissed ones) and list_ reads them back.

``db``-marked: findings, dismissals, and the run they belong to are persisted against the
migration-built schema.
"""

import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from pattern_mirror.core.errors import DocumentNotFoundError
from pattern_mirror.engine.lemmatiser import lemma_key
from pattern_mirror.engine.state import DriftFinding as DriftFindingState
from pattern_mirror.models.documents import AnalysisRun, Document
from pattern_mirror.models.drift import DriftFinding, DriftFindingDismissal
from pattern_mirror.models.enums import (
    AnalysisRunStatus,
    AnalysisTrigger,
    DocType,
    ReferenceKind,
)
from pattern_mirror.models.identity import User
from pattern_mirror.services.drift_findings import (
    list_drift_findings,
    persist_drift_findings,
    reference_kind_for,
)

pytestmark = pytest.mark.db

_JD = ReferenceKind.jd_criteria


def _owner_and_document(db_session: Session, suffix: str) -> tuple[User, Document]:
    user = User(
        external_user_id=f"drift-findings-{suffix}",
        legal_name="Drift Manager",
        email=f"{suffix}@example.test",
    )
    db_session.add(user)
    db_session.flush()
    document = Document(owner_id=user.id, doc_type=DocType.feedback, content="Doc under analysis.")
    db_session.add(document)
    db_session.flush()
    return user, document


def _run(
    db_session: Session, document: Document, *, started_at: datetime | None = None
) -> AnalysisRun:
    run = AnalysisRun(
        document_id=document.id,
        trigger=AnalysisTrigger.typing_pause,
        content_hash="0" * 64,
        status=AnalysisRunStatus.complete,
    )
    if started_at is not None:
        # now() is constant within a test transaction, so distinguish run recency explicitly.
        run.started_at = started_at
    db_session.add(run)
    db_session.flush()
    return run


def _finding(
    criterion: str,
    *,
    addressed: bool = False,
    evidence: str | None = None,
    start: int | None = None,
    end: int | None = None,
) -> DriftFindingState:
    return DriftFindingState(
        criterion=criterion,
        addressed=addressed,
        evidence=evidence,
        evidence_start=start,
        evidence_end=end,
    )


def test_reference_kind_maps_by_doc_type() -> None:
    assert reference_kind_for(DocType.feedback) is ReferenceKind.jd_criteria
    assert reference_kind_for(DocType.promotion) is ReferenceKind.peer_feedback


def test_a_jd_has_no_reference_corpus() -> None:
    with pytest.raises(ValueError):
        reference_kind_for(DocType.jd)


def test_persist_writes_every_finding_and_returns_the_surfaced_ones(db_session: Session) -> None:
    _, document = _owner_and_document(db_session, "persist")
    run = _run(db_session, document)

    surfaced = persist_drift_findings(
        db_session,
        run=run,
        document_id=document.id,
        reference_kind=_JD,
        findings=[
            _finding("leadership", addressed=True, evidence="led the team", start=0, end=11),
            _finding("stakeholder management", addressed=False),
        ],
    )

    assert {f.criterion for f in surfaced} == {"leadership", "stakeholder management"}
    persisted = db_session.scalars(
        select(DriftFinding).where(DriftFinding.document_id == document.id)
    ).all()
    assert len(persisted) == 2
    addressed = next(f for f in persisted if f.criterion == "leadership")
    assert addressed.reference_kind is _JD
    assert addressed.addressed is True
    assert addressed.evidence == "led the team"
    assert addressed.normalised_criterion == lemma_key("leadership")
    assert addressed.suppressed is False


def test_persist_suppresses_a_finding_a_dismissal_covers(db_session: Session) -> None:
    _, document = _owner_and_document(db_session, "suppress")
    run = _run(db_session, document)
    db_session.add(
        DriftFindingDismissal(
            document_id=document.id,
            reference_kind=_JD,
            normalised_criterion=lemma_key("stakeholder management"),
            active=True,
        )
    )
    db_session.flush()

    surfaced = persist_drift_findings(
        db_session,
        run=run,
        document_id=document.id,
        reference_kind=_JD,
        findings=[_finding("stakeholder management"), _finding("leadership", addressed=True)],
    )

    # Suppress in UI: the dismissed criterion is not returned for surfacing.
    assert [f.criterion for f in surfaced] == ["leadership"]
    # Log everything: it is still persisted, marked suppressed and pointing at the dismissal.
    dismissed = db_session.scalars(
        select(DriftFinding).where(
            DriftFinding.document_id == document.id,
            DriftFinding.criterion == "stakeholder management",
        )
    ).one()
    assert dismissed.suppressed is True
    assert dismissed.suppressed_by_dismissal_id is not None


def test_suppression_matches_across_case_and_inflection(db_session: Session) -> None:
    # The dismissal signature is the lemma key, so a re-phrased criterion still matches.
    _, document = _owner_and_document(db_session, "normalise")
    run = _run(db_session, document)
    db_session.add(
        DriftFindingDismissal(
            document_id=document.id,
            reference_kind=_JD,
            normalised_criterion=lemma_key("Stakeholder Management"),
            active=True,
        )
    )
    db_session.flush()

    surfaced = persist_drift_findings(
        db_session,
        run=run,
        document_id=document.id,
        reference_kind=_JD,
        findings=[_finding("stakeholder management")],
    )

    assert surfaced == []


def test_an_inactive_dismissal_does_not_suppress(db_session: Session) -> None:
    _, document = _owner_and_document(db_session, "inactive")
    run = _run(db_session, document)
    db_session.add(
        DriftFindingDismissal(
            document_id=document.id,
            reference_kind=_JD,
            normalised_criterion=lemma_key("leadership"),
            active=False,
        )
    )
    db_session.flush()

    surfaced = persist_drift_findings(
        db_session,
        run=run,
        document_id=document.id,
        reference_kind=_JD,
        findings=[_finding("leadership")],
    )

    assert [f.criterion for f in surfaced] == ["leadership"]


def test_list_returns_the_latest_runs_unsuppressed_findings(db_session: Session) -> None:
    owner, document = _owner_and_document(db_session, "list-latest")
    first_run = _run(db_session, document, started_at=datetime(2026, 7, 1, tzinfo=UTC))
    persist_drift_findings(
        db_session,
        run=first_run,
        document_id=document.id,
        reference_kind=_JD,
        findings=[_finding("old criterion")],
    )
    second_run = _run(db_session, document, started_at=datetime(2026, 7, 2, tzinfo=UTC))
    persist_drift_findings(
        db_session,
        run=second_run,
        document_id=document.id,
        reference_kind=_JD,
        findings=[_finding("new criterion"), _finding("also new", addressed=True)],
    )

    findings = list_drift_findings(db_session, document_id=document.id, owner_id=owner.id)

    assert {f.criterion for f in findings} == {"new criterion", "also new"}


def test_list_excludes_suppressed_findings(db_session: Session) -> None:
    owner, document = _owner_and_document(db_session, "list-suppressed")
    run = _run(db_session, document)
    db_session.add(
        DriftFindingDismissal(
            document_id=document.id,
            reference_kind=_JD,
            normalised_criterion=lemma_key("dismissed criterion"),
            active=True,
        )
    )
    db_session.flush()
    persist_drift_findings(
        db_session,
        run=run,
        document_id=document.id,
        reference_kind=_JD,
        findings=[_finding("dismissed criterion"), _finding("kept criterion")],
    )

    findings = list_drift_findings(db_session, document_id=document.id, owner_id=owner.id)

    assert [f.criterion for f in findings] == ["kept criterion"]


def test_list_is_empty_when_a_document_has_no_findings(db_session: Session) -> None:
    owner, document = _owner_and_document(db_session, "list-empty")

    assert list_drift_findings(db_session, document_id=document.id, owner_id=owner.id) == []


def test_list_on_another_users_document_is_not_found(db_session: Session) -> None:
    owner, document = _owner_and_document(db_session, "list-owner")
    intruder = User(
        external_user_id="drift-findings-intruder",
        legal_name="Intruder",
        email="intruder@example.test",
    )
    db_session.add(intruder)
    db_session.flush()

    with pytest.raises(DocumentNotFoundError):
        list_drift_findings(db_session, document_id=document.id, owner_id=intruder.id)


def test_list_on_a_missing_document_is_not_found(db_session: Session) -> None:
    owner, _ = _owner_and_document(db_session, "list-missing")

    with pytest.raises(DocumentNotFoundError):
        list_drift_findings(db_session, document_id=uuid.uuid4(), owner_id=owner.id)
