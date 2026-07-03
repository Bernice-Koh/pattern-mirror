"""The drift check's output and the manager's responses to it.

``drift_findings`` — one reference criterion per row, whether the document addresses it, with a
verbatim evidence span when it does — and the ``drift_dismissals`` that suppress them, plus
``drift_interactions``, the append-only dismiss/undo log.

Mirrors the flag model (``models/engine.py``): every finding is stored, including suppressed ones
("log everything, suppress only in UI"). A criterion is atomic, so its dismissal signature is the
one-part ``(document_id, reference_kind, normalised_criterion)`` — no sentence fingerprint. A
dismissal suppresses matching findings on future runs by that signature and has its own lifecycle.
"""

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Index, Integer, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from pattern_mirror.db.base import Base
from pattern_mirror.models.columns import uuid_pk
from pattern_mirror.models.enums import (
    DriftFindingInteractionKind,
    ReferenceKind,
    drift_finding_interaction_kind_enum,
    reference_kind_enum,
)
from pattern_mirror.models.mixins import CreatedAtMixin

if TYPE_CHECKING:
    from pattern_mirror.models.documents import AnalysisRun, Document


class DriftFinding(CreatedAtMixin, Base):
    """One reference criterion and whether a document addresses it, including suppressed ones."""

    __tablename__ = "drift_findings"
    __table_args__ = (
        Index(
            "ix_drift_findings_document_reference_criterion",
            "document_id",
            "reference_kind",
            "normalised_criterion",
        ),
        Index("ix_drift_findings_document_suppressed", "document_id", "suppressed"),
    )

    id: Mapped[uuid_pk]
    document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("documents.id"))
    analysis_run_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("analysis_runs.id"), index=True
    )
    reference_kind: Mapped[ReferenceKind] = mapped_column(reference_kind_enum)
    criterion: Mapped[str] = mapped_column(Text)
    normalised_criterion: Mapped[str] = mapped_column(String)
    addressed: Mapped[bool] = mapped_column()
    evidence: Mapped[str | None] = mapped_column(Text)
    evidence_start: Mapped[int | None] = mapped_column(Integer)
    evidence_end: Mapped[int | None] = mapped_column(Integer)
    suppressed: Mapped[bool] = mapped_column(server_default=text("false"))
    suppressed_by_dismissal_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("drift_dismissals.id")
    )

    document: Mapped["Document"] = relationship(back_populates="drift_findings")
    analysis_run: Mapped["AnalysisRun | None"] = relationship(back_populates="drift_findings")
    suppressed_by_dismissal: Mapped["DriftFindingDismissal | None"] = relationship(
        back_populates="suppressed_findings"
    )
    interactions: Mapped[list["DriftFindingInteraction"]] = relationship(
        back_populates="drift_finding"
    )


class DriftFindingDismissal(CreatedAtMixin, Base):
    """A manager's dismissal that suppresses matching drift findings on future runs by signature."""

    __tablename__ = "drift_dismissals"
    __table_args__ = (
        Index(
            "ix_drift_dismissals_document_reference_criterion",
            "document_id",
            "reference_kind",
            "normalised_criterion",
        ),
    )

    id: Mapped[uuid_pk]
    document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("documents.id"))
    reference_kind: Mapped[ReferenceKind] = mapped_column(reference_kind_enum)
    normalised_criterion: Mapped[str] = mapped_column(String)
    active: Mapped[bool] = mapped_column(server_default=text("true"))

    document: Mapped["Document"] = relationship(back_populates="drift_finding_dismissals")
    suppressed_findings: Mapped[list["DriftFinding"]] = relationship(
        back_populates="suppressed_by_dismissal"
    )


class DriftFindingInteraction(CreatedAtMixin, Base):
    """A manager's dismiss or undo on a drift finding; append-only, so every dismissal is logged."""

    __tablename__ = "drift_interactions"
    __table_args__ = (Index("ix_drift_interactions_drift_finding_id", "drift_finding_id"),)

    id: Mapped[uuid_pk]
    drift_finding_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("drift_findings.id"))
    kind: Mapped[DriftFindingInteractionKind] = mapped_column(drift_finding_interaction_kind_enum)

    drift_finding: Mapped["DriftFinding"] = relationship(back_populates="interactions")
