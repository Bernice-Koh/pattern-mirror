"""The bias engine's output: ``flags`` and the ``flag_dismissals`` that suppress them.

Every flag the engine produces is stored, including suppressed ones
("log everything, suppress only in UI"). Judge scores are nullable because a
flag only reaches the Judge if it survives the Adjudicator. Dismissals are a
separate entity (D6): flags are regenerated every run, so a dismissal suppresses
many future flag rows by signature ``(document_id, rule_id, normalised_span,
sentence_fingerprint)`` and has its own lifecycle (recheck flips ``active``; it
outlives a deleted span; it feeds the adoption metric).
"""

import uuid
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from sqlalchemy import ForeignKey, Index, Integer, Numeric, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from pattern_mirror.db.base import Base
from pattern_mirror.models.columns import uuid_pk
from pattern_mirror.models.enums import (
    BiasCategory,
    FlagScope,
    FlagSourceStage,
    FlagVerdict,
    bias_category_enum,
    flag_scope_enum,
    flag_source_stage_enum,
    flag_verdict_enum,
)
from pattern_mirror.models.mixins import CreatedAtMixin

if TYPE_CHECKING:
    from pattern_mirror.models.dictionary import Dictionary
    from pattern_mirror.models.documents import AnalysisRun, Document
    from pattern_mirror.models.reference import Citation


class Flag(CreatedAtMixin, Base):
    """One bias detection over a document, including suppressed ones."""

    __tablename__ = "flags"
    __table_args__ = (
        Index(
            "ix_flags_document_id_normalised_span_sentence_fingerprint",
            "document_id",
            "normalised_span",
            "sentence_fingerprint",
        ),
        Index("ix_flags_document_id_suppressed", "document_id", "suppressed"),
        Index("ix_flags_category", "category"),
        Index("ix_flags_verdict", "verdict"),
        Index("ix_flags_created_at", "created_at"),
    )

    id: Mapped[uuid_pk]
    document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("documents.id"))
    analysis_run_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("analysis_runs.id"), index=True
    )
    source_stage: Mapped[FlagSourceStage] = mapped_column(flag_source_stage_enum)
    dictionary_entry_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("dictionaries.id"))
    citation_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("citations.id"))
    category: Mapped[BiasCategory] = mapped_column(bias_category_enum)
    scope: Mapped[FlagScope] = mapped_column(flag_scope_enum)
    verdict: Mapped[FlagVerdict | None] = mapped_column(flag_verdict_enum)
    raw_span: Mapped[str] = mapped_column(Text)
    normalised_span: Mapped[str] = mapped_column(String)
    sentence_fingerprint: Mapped[str] = mapped_column(String(64))
    start_offset: Mapped[int | None] = mapped_column(Integer)
    end_offset: Mapped[int | None] = mapped_column(Integer)
    rationale: Mapped[dict[str, Any]] = mapped_column(JSONB)
    judge_confidence: Mapped[Decimal | None] = mapped_column(Numeric(4, 3))
    suppressed: Mapped[bool] = mapped_column(server_default=text("false"))
    suppressed_by_dismissal_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("flag_dismissals.id")
    )

    document: Mapped["Document"] = relationship(back_populates="flags")
    analysis_run: Mapped["AnalysisRun | None"] = relationship(back_populates="flags")
    dictionary_entry: Mapped["Dictionary | None"] = relationship(back_populates="flags")
    citation: Mapped["Citation | None"] = relationship(back_populates="flags")
    suppressed_by_dismissal: Mapped["FlagDismissal | None"] = relationship(
        back_populates="suppressed_flags"
    )


class FlagDismissal(CreatedAtMixin, Base):
    """A manager's dismissal that suppresses matching flags on future runs by signature."""

    __tablename__ = "flag_dismissals"
    __table_args__ = (
        Index(
            "ix_flag_dismissals_document_id_rule_id_normalised_span",
            "document_id",
            "rule_id",
            "normalised_span",
        ),
    )

    id: Mapped[uuid_pk]
    document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("documents.id"))
    rule_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("dictionaries.id"))
    normalised_span: Mapped[str] = mapped_column(String)
    sentence_fingerprint: Mapped[str] = mapped_column(String(64))
    active: Mapped[bool] = mapped_column(server_default=text("true"))

    document: Mapped["Document"] = relationship(back_populates="dismissals")
    rule: Mapped["Dictionary | None"] = relationship(back_populates="dismissals")
    suppressed_flags: Mapped[list["Flag"]] = relationship(back_populates="suppressed_by_dismissal")
