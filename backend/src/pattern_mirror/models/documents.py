"""Documents and their analysis runs.

One ``documents`` table for all three writing types (D2): JD, feedback, and
promotion share owner/content/status/lifecycle and run the same engine, differing
only in a couple of nullable references. ``analysis_runs`` groups the flags from
one engine invocation and records the ``content_hash`` it saw, so a run's flag
offsets stay interpretable.
"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import TIMESTAMP, ForeignKey, Index, String, Text, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from pattern_mirror.db.base import Base
from pattern_mirror.models.columns import uuid_pk
from pattern_mirror.models.enums import (
    AnalysisRunStatus,
    AnalysisTrigger,
    DocType,
    DocumentStatus,
    analysis_run_status_enum,
    analysis_trigger_enum,
    doc_type_enum,
    document_status_enum,
)
from pattern_mirror.models.mixins import TimestampMixin

if TYPE_CHECKING:
    from pattern_mirror.models.engine import Flag, FlagDismissal
    from pattern_mirror.models.identity import Subject, User


class Document(TimestampMixin, Base):
    """A manager-owned JD, feedback, or promotion writeup analysed by the engine."""

    __tablename__ = "documents"
    __table_args__ = (
        Index("ix_documents_owner_id_doc_type", "owner_id", "doc_type"),
        Index("ix_documents_owner_id_created_at", "owner_id", "created_at"),
    )

    id: Mapped[uuid_pk]
    owner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    doc_type: Mapped[DocType] = mapped_column(doc_type_enum)
    title: Mapped[str | None] = mapped_column(String)
    role_title: Mapped[str | None] = mapped_column(String)
    status: Mapped[DocumentStatus] = mapped_column(
        document_status_enum, server_default=text("'draft'")
    )
    content: Mapped[str] = mapped_column(Text, server_default=text("''"))
    submitted_content: Mapped[str | None] = mapped_column(Text)
    submitted_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    reference_jd_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("documents.id"))
    subject_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("subjects.id"))

    owner: Mapped["User"] = relationship(back_populates="documents")
    subject: Mapped["Subject | None"] = relationship(back_populates="documents")
    reference_jd: Mapped["Document | None"] = relationship(
        remote_side=lambda: [Document.id], back_populates="dependent_feedback"
    )
    dependent_feedback: Mapped[list["Document"]] = relationship(back_populates="reference_jd")
    analysis_runs: Mapped[list["AnalysisRun"]] = relationship(back_populates="document")
    flags: Mapped[list["Flag"]] = relationship(back_populates="document")
    dismissals: Mapped[list["FlagDismissal"]] = relationship(back_populates="document")


class AnalysisRun(Base):
    """One engine invocation over a document; groups the flags it produced."""

    __tablename__ = "analysis_runs"

    id: Mapped[uuid_pk]
    document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("documents.id"), index=True)
    trigger: Mapped[AnalysisTrigger] = mapped_column(analysis_trigger_enum)
    content_hash: Mapped[str] = mapped_column(String(64))
    status: Mapped[AnalysisRunStatus] = mapped_column(
        analysis_run_status_enum, server_default=text("'running'")
    )
    started_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now()
    )
    completed_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))

    document: Mapped["Document"] = relationship(back_populates="analysis_runs")
    flags: Mapped[list["Flag"]] = relationship(back_populates="analysis_run")
