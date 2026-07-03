"""record_drift_interaction logs the event and toggles the finding's dismissal on dismiss/undo."""

import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from pattern_mirror.core.errors import DriftFindingNotFoundError
from pattern_mirror.engine.state import DriftFinding as DriftFindingState
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
    DriftFindingInteractionKind,
    ReferenceKind,
)
from pattern_mirror.models.identity import User
from pattern_mirror.services.drift_findings import persist_drift_findings
from pattern_mirror.services.drift_interactions import record_drift_interaction

pytestmark = pytest.mark.db

_DISMISS = DriftFindingInteractionKind.dismiss
_UNDO = DriftFindingInteractionKind.undo


def _manager(db_session: Session, suffix: str) -> User:
    user = User(
        external_user_id=f"drift-interactions-{suffix}",
        legal_name="Drift Manager",
        email=f"{suffix}@example.test",
    )
    db_session.add(user)
    db_session.flush()
    return user


def _finding_on_a_document(db_session: Session, owner: User) -> DriftFinding:
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
    surfaced = persist_drift_findings(
        db_session,
        run=run,
        document_id=document.id,
        reference_kind=ReferenceKind.jd_criteria,
        findings=[
            DriftFindingState(
                criterion="stakeholder management",
                addressed=False,
                evidence=None,
                evidence_start=None,
                evidence_end=None,
            )
        ],
    )
    return surfaced[0]


def _dismissals_for(db_session: Session, finding: DriftFinding) -> list[DriftFindingDismissal]:
    return list(
        db_session.scalars(
            select(DriftFindingDismissal).where(
                DriftFindingDismissal.document_id == finding.document_id
            )
        ).all()
    )


def test_dismiss_logs_an_event_and_writes_a_matching_dismissal(db_session: Session) -> None:
    owner = _manager(db_session, "dismiss")
    finding = _finding_on_a_document(db_session, owner)

    result = record_drift_interaction(
        db_session, finding_id=finding.id, owner_id=owner.id, kind=_DISMISS
    )

    assert result.dismissal is not None
    dismissal = result.dismissal
    assert dismissal.active is True
    # The signature is copied straight off the finding the manager saw.
    assert dismissal.document_id == finding.document_id
    assert dismissal.reference_kind is finding.reference_kind
    assert dismissal.normalised_criterion == finding.normalised_criterion
    events = list(
        db_session.scalars(
            select(DriftFindingInteraction).where(
                DriftFindingInteraction.drift_finding_id == finding.id
            )
        ).all()
    )
    assert [e.kind for e in events] == [_DISMISS]


def test_undo_deactivates_the_dismissal(db_session: Session) -> None:
    owner = _manager(db_session, "undo")
    finding = _finding_on_a_document(db_session, owner)

    record_drift_interaction(db_session, finding_id=finding.id, owner_id=owner.id, kind=_DISMISS)
    result = record_drift_interaction(
        db_session, finding_id=finding.id, owner_id=owner.id, kind=_UNDO
    )

    assert result.dismissal is not None
    assert result.dismissal.active is False
    events = list(
        db_session.scalars(
            select(DriftFindingInteraction).where(
                DriftFindingInteraction.drift_finding_id == finding.id
            )
        ).all()
    )
    assert [e.kind for e in events] == [_DISMISS, _UNDO]


def test_undo_without_a_prior_dismissal_is_a_noop(db_session: Session) -> None:
    owner = _manager(db_session, "undo-noop")
    finding = _finding_on_a_document(db_session, owner)

    result = record_drift_interaction(
        db_session, finding_id=finding.id, owner_id=owner.id, kind=_UNDO
    )

    assert result.dismissal is None
    assert _dismissals_for(db_session, finding) == []


def test_redismiss_reuses_one_dismissal_row(db_session: Session) -> None:
    owner = _manager(db_session, "redismiss")
    finding = _finding_on_a_document(db_session, owner)

    record_drift_interaction(db_session, finding_id=finding.id, owner_id=owner.id, kind=_DISMISS)
    record_drift_interaction(db_session, finding_id=finding.id, owner_id=owner.id, kind=_UNDO)
    record_drift_interaction(db_session, finding_id=finding.id, owner_id=owner.id, kind=_DISMISS)

    dismissals = _dismissals_for(db_session, finding)
    assert len(dismissals) == 1
    assert dismissals[0].active is True


def test_a_finding_on_another_users_document_is_not_found(db_session: Session) -> None:
    owner = _manager(db_session, "owner")
    intruder = _manager(db_session, "intruder")
    finding = _finding_on_a_document(db_session, owner)

    with pytest.raises(DriftFindingNotFoundError):
        record_drift_interaction(
            db_session, finding_id=finding.id, owner_id=intruder.id, kind=_DISMISS
        )


def test_a_missing_finding_is_not_found(db_session: Session) -> None:
    owner = _manager(db_session, "missing")

    with pytest.raises(DriftFindingNotFoundError):
        record_drift_interaction(
            db_session, finding_id=uuid.uuid4(), owner_id=owner.id, kind=_DISMISS
        )
