"""Persist the drift agent's findings and read them back for the surfaces (#65).

The drift stage produces engine-state ``DriftFinding`` objects; this module makes them durable
and readable. Every finding is written, including ones an active dismissal suppresses ("log
everything, suppress only in UI") — a criterion the manager already dismissed on a prior run is
persisted ``suppressed=True`` with its dismissal reference, but not returned for surfacing.

A criterion is atomic, so its dismissal signature is the one-part ``(reference_kind,
normalised_criterion)`` scoped to the document, where ``normalised_criterion`` reuses the flag
normaliser (``lemma_key``) so drift and flag matching cannot drift apart.
"""

import uuid
from dataclasses import dataclass

import structlog
from sqlalchemy import select
from sqlalchemy.orm import Session

from pattern_mirror.core.errors import DocumentNotFoundError
from pattern_mirror.engine.lemmatiser import lemma_key
from pattern_mirror.engine.state import DriftFinding as DriftFindingState
from pattern_mirror.models.documents import AnalysisRun, Document
from pattern_mirror.models.drift import DriftFinding, DriftFindingDismissal
from pattern_mirror.models.enums import DocType, ReferenceKind

_log = structlog.get_logger("pattern_mirror.services.drift_findings")

_REFERENCE_KIND_BY_DOC_TYPE: dict[DocType, ReferenceKind] = {
    DocType.feedback: ReferenceKind.jd_criteria,
    DocType.promotion: ReferenceKind.peer_feedback,
}


def reference_kind_for(doc_type: DocType) -> ReferenceKind:
    """Map a document type to the reference corpus its drift check runs against.

    Feedback drifts against JD criteria, a promotion against peer feedback (design spec §3). A JD
    has no reference of its own, so it never reaches the drift stage.
    """
    kind = _REFERENCE_KIND_BY_DOC_TYPE.get(doc_type)
    if kind is None:
        raise ValueError(f"No drift reference corpus for doc_type {doc_type}")
    return kind


@dataclass(frozen=True)
class DriftDismissalIndex:
    """A document's active drift dismissals indexed by signature for the per-run lookup."""

    _by_signature: dict[tuple[ReferenceKind, str], uuid.UUID]

    @classmethod
    def from_dismissals(cls, dismissals: list[DriftFindingDismissal]) -> "DriftDismissalIndex":
        """Build the index from a document's active drift dismissals."""
        return cls(
            _by_signature={
                (dismissal.reference_kind, dismissal.normalised_criterion): dismissal.id
                for dismissal in dismissals
            }
        )

    def resolve(
        self, *, reference_kind: ReferenceKind, normalised_criterion: str
    ) -> uuid.UUID | None:
        """Return the dismissal suppressing this criterion, or ``None`` to surface it."""
        return self._by_signature.get((reference_kind, normalised_criterion))


def load_active_drift_dismissals(
    session: Session, document_id: uuid.UUID
) -> list[DriftFindingDismissal]:
    """Load one document's active drift dismissals; the document filter is the scoping guarantee."""
    return list(
        session.scalars(
            select(DriftFindingDismissal).where(
                DriftFindingDismissal.document_id == document_id,
                DriftFindingDismissal.active.is_(True),
            )
        ).all()
    )


def build_drift_finding(
    *,
    document_id: uuid.UUID,
    analysis_run_id: uuid.UUID,
    reference_kind: ReferenceKind,
    finding: DriftFindingState,
    suppressed: bool = False,
    suppressed_by_dismissal_id: uuid.UUID | None = None,
) -> DriftFinding:
    """Build a persistable ``DriftFinding`` row from an engine-state finding.

    The evidence span rides along verbatim with its resolved offsets (the drift agent already
    verified it against the source); ``normalised_criterion`` is the lemma key that dismissals
    match on.
    """
    return DriftFinding(
        document_id=document_id,
        analysis_run_id=analysis_run_id,
        reference_kind=reference_kind,
        criterion=finding.criterion,
        normalised_criterion=lemma_key(finding.criterion),
        addressed=finding.addressed,
        evidence=finding.evidence,
        evidence_start=finding.evidence_start,
        evidence_end=finding.evidence_end,
        suppressed=suppressed,
        suppressed_by_dismissal_id=suppressed_by_dismissal_id,
    )


def persist_drift_findings(
    session: Session,
    *,
    run: AnalysisRun,
    document_id: uuid.UUID,
    reference_kind: ReferenceKind,
    findings: list[DriftFindingState],
) -> list[DriftFinding]:
    """Persist every drift finding, suppressing ones an active dismissal covers, and flush.

    A finding whose ``(reference_kind, normalised_criterion)`` signature matches an active
    dismissal is written ``suppressed=True`` with its dismissal reference and left out of the
    returned surfaced findings; the rest are returned in the order produced.

    Args:
        session: The active session (committed by the caller).
        run: The analysis run these findings belong to.
        document_id: The document under analysis.
        reference_kind: The corpus the findings were checked against.
        findings: The engine-state findings from the drift stage.

    Returns:
        The persisted, un-suppressed findings, in order.
    """
    index = DriftDismissalIndex.from_dismissals(load_active_drift_dismissals(session, document_id))
    surfaced: list[DriftFinding] = []
    for finding in findings:
        dismissal_id = index.resolve(
            reference_kind=reference_kind,
            normalised_criterion=lemma_key(finding.criterion),
        )
        row = build_drift_finding(
            document_id=document_id,
            analysis_run_id=run.id,
            reference_kind=reference_kind,
            finding=finding,
            suppressed=dismissal_id is not None,
            suppressed_by_dismissal_id=dismissal_id,
        )
        session.add(row)
        if dismissal_id is None:
            surfaced.append(row)
    session.flush()
    _log.info(
        "drift.findings_persisted",
        document_id=str(document_id),
        analysis_run_id=str(run.id),
        total=len(findings),
        surfaced=len(surfaced),
    )
    return surfaced


def list_drift_findings(
    session: Session, *, document_id: uuid.UUID, owner_id: uuid.UUID
) -> list[DriftFinding]:
    """Return a document's latest-run, un-suppressed drift findings for the owner.

    The surfaces render the current run only, so this returns the findings of the most recent run
    that produced any, suppressed ones excluded. A document owned by another user is treated as
    absent.

    Args:
        session: An open session.
        document_id: The document whose findings are read.
        owner_id: The current manager; a foreign document raises rather than leaks.

    Returns:
        The latest run's surfaced findings, oldest first; empty when the document has none.

    Raises:
        DocumentNotFoundError: if the document is absent or owned by another user.
    """
    document = session.get(Document, document_id)
    if document is None or document.owner_id != owner_id:
        raise DocumentNotFoundError(document_id)

    latest_run_id = session.scalars(
        select(DriftFinding.analysis_run_id)
        .join(AnalysisRun, AnalysisRun.id == DriftFinding.analysis_run_id)
        .where(DriftFinding.document_id == document_id)
        .order_by(AnalysisRun.started_at.desc())
        .limit(1)
    ).first()
    if latest_run_id is None:
        return []

    return list(
        session.scalars(
            select(DriftFinding)
            .where(
                DriftFinding.analysis_run_id == latest_run_id,
                DriftFinding.suppressed.is_(False),
            )
            .order_by(DriftFinding.created_at, DriftFinding.id)
        ).all()
    )
