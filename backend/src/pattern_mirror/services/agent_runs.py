"""Tier-2 audit write helper: persist one ``agent_runs`` row.

The single place the engine's Agent nodes record an invocation. The table and ORM
model already exist (migration 0001, ``models/audit.py``); this is the helper half
of #57.
"""

import uuid
from decimal import Decimal
from typing import Any

import structlog
from sqlalchemy.orm import Session

from pattern_mirror.models.audit import AgentRun
from pattern_mirror.models.enums import AgentName

_log = structlog.get_logger("pattern_mirror.services.agent_runs")


def record_agent_run(
    session: Session,
    *,
    agent_name: AgentName,
    model: str,
    input: dict[str, Any],
    output: dict[str, Any],
    document_id: uuid.UUID | None = None,
    flag_id: uuid.UUID | None = None,
    analysis_run_id: uuid.UUID | None = None,
    prompt_tokens: int | None = None,
    completion_tokens: int | None = None,
    cost_usd: Decimal | None = None,
    latency_ms: int | None = None,
) -> AgentRun:
    """Persist one agent invocation to ``agent_runs`` and return the flushed row.

    ``input`` and ``output`` are already JSON-safe dicts (the caller's Pydantic
    context and parsed result via ``model_dump(mode="json")``). Flushes but does
    not commit — the caller owns the transaction, so the run joins the same unit
    of work as the flags it concerns.
    """
    run = AgentRun(
        agent_name=agent_name,
        model=model,
        input=input,
        output=output,
        document_id=document_id,
        flag_id=flag_id,
        analysis_run_id=analysis_run_id,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        cost_usd=cost_usd,
        latency_ms=latency_ms,
    )
    session.add(run)
    session.flush()
    _log.info(
        "agent_run.recorded",
        agent_run_id=str(run.id),
        agent_name=agent_name,
        model=model,
        document_id=str(document_id) if document_id else None,
        flag_id=str(flag_id) if flag_id else None,
        analysis_run_id=str(analysis_run_id) if analysis_run_id else None,
    )
    return run
