"""Tier-2 audit backbone: ``agent_runs``.

One generic table logs every agent invocation's structured I/O, beating seven
agent-specific tables. Nullable FKs attach a run to whatever it concerned: a
document/flag for the engine agents, a ``dictionary_proposals`` row for the four
growth agents. Cost and latency live here too, doubling as input to the model eval.
"""

import uuid
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from sqlalchemy import ForeignKey, Integer, Numeric, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from pattern_mirror.db.base import Base
from pattern_mirror.models.columns import uuid_pk
from pattern_mirror.models.enums import AgentName, agent_name_enum
from pattern_mirror.models.mixins import CreatedAtMixin

if TYPE_CHECKING:
    from pattern_mirror.models.documents import AnalysisRun, Document
    from pattern_mirror.models.engine import Flag
    from pattern_mirror.models.growth import DictionaryProposal


class AgentRun(CreatedAtMixin, Base):
    """A logged LLM agent invocation with its structured I/O, cost, and latency."""

    __tablename__ = "agent_runs"

    id: Mapped[uuid_pk]
    agent_name: Mapped[AgentName] = mapped_column(agent_name_enum, index=True)
    model: Mapped[str] = mapped_column(String)
    document_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("documents.id"), index=True)
    flag_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("flags.id"), index=True)
    analysis_run_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("analysis_runs.id"))
    proposal_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("dictionary_proposals.id"), index=True
    )
    input: Mapped[dict[str, Any]] = mapped_column(JSONB)
    output: Mapped[dict[str, Any]] = mapped_column(JSONB)
    prompt_tokens: Mapped[int | None] = mapped_column(Integer)
    completion_tokens: Mapped[int | None] = mapped_column(Integer)
    cost_usd: Mapped[Decimal | None] = mapped_column(Numeric(10, 6))
    latency_ms: Mapped[int | None] = mapped_column(Integer)

    document: Mapped["Document | None"] = relationship()
    flag: Mapped["Flag | None"] = relationship()
    analysis_run: Mapped["AnalysisRun | None"] = relationship()
    proposal: Mapped["DictionaryProposal | None"] = relationship()
