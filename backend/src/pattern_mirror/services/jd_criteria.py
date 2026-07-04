"""JD-criteria authoring: draft a JD's criteria with an agent, then confirm the manager's set.

The write path #116 left as a TODO. ``draft_jd_criteria`` runs the extraction agent over a JD's
text and logs the invocation to ``agent_runs`` — but persists nothing: the draft is unconfirmed
model output, and the design keeps that out of ``jd_criteria`` (#122). ``replace_jd_criteria``
writes the manager's confirmed set, the only rows the drift check ever reads. Every function is
owner-scoped and JD-scoped; the caller owns the transaction (flush, never commit).
"""

import uuid

import structlog
from sqlalchemy import delete
from sqlalchemy.orm import Session

from pattern_mirror.core.errors import (
    DocumentNotFoundError,
    DocumentTypeMismatchError,
    LlmClientUnavailableError,
)
from pattern_mirror.engine.jd_criteria_extraction import run_jd_criteria_extraction
from pattern_mirror.engine.llm_agent import StructuredCompletionClient, estimate_cost_usd
from pattern_mirror.models.documents import Document
from pattern_mirror.models.enums import AgentName, DocType
from pattern_mirror.models.jd_criteria import JdCriterion
from pattern_mirror.services.agent_runs import record_agent_run
from pattern_mirror.services.drift_reference import resolve_jd_criteria

_log = structlog.get_logger("pattern_mirror.services.jd_criteria")


def _owned_jd(session: Session, document_id: uuid.UUID, owner_id: uuid.UUID) -> Document:
    """Return the owner's JD, or raise if it is missing, foreign, or not a job description."""
    document = session.get(Document, document_id)
    if document is None or document.owner_id != owner_id:
        raise DocumentNotFoundError(document_id)
    if document.doc_type is not DocType.jd:
        raise DocumentTypeMismatchError(document_id, DocType.jd.value, document.doc_type.value)
    return document


def _clean_texts(texts: list[str]) -> list[str]:
    """Strip whitespace, drop blanks, and de-duplicate case-insensitively, keeping stated order."""
    cleaned: list[str] = []
    seen: set[str] = set()
    for text in texts:
        stripped = text.strip()
        key = stripped.casefold()
        if stripped and key not in seen:
            seen.add(key)
            cleaned.append(stripped)
    return cleaned


def draft_jd_criteria(
    session: Session,
    *,
    document_id: uuid.UUID,
    owner_id: uuid.UUID,
    jd_text: str,
    client: StructuredCompletionClient | None,
    model: str,
) -> list[str]:
    """Draft a JD's criteria with the extraction agent and log the run; persist nothing.

    The draft is unconfirmed model output, so it never touches ``jd_criteria`` — only the
    ``agent_runs`` audit row is written. The manager reviews and edits the returned list, then
    confirms it through ``replace_jd_criteria``.

    Raises:
        DocumentNotFoundError: if the document is absent or owned by another user.
        DocumentTypeMismatchError: if the document is not a job description.
        LlmClientUnavailableError: if no Anthropic client is configured.
    """
    _owned_jd(session, document_id, owner_id)
    if client is None:
        raise LlmClientUnavailableError()

    run = run_jd_criteria_extraction(client, jd_text=jd_text, model=model)
    record_agent_run(
        session,
        agent_name=AgentName.jd_criteria_drafter,
        model=model,
        input={"jd_text": jd_text},
        output=run.result.model_dump(mode="json"),
        document_id=document_id,
        prompt_tokens=run.prompt_tokens,
        completion_tokens=run.completion_tokens,
        cost_usd=estimate_cost_usd(model, run.prompt_tokens, run.completion_tokens),
        latency_ms=run.latency_ms,
    )
    return _clean_texts([criterion.text for criterion in run.result.criteria])


def replace_jd_criteria(
    session: Session,
    *,
    document_id: uuid.UUID,
    owner_id: uuid.UUID,
    texts: list[str],
) -> list[str]:
    """Replace the JD's confirmed criteria with ``texts``, in order; return the persisted set.

    Idempotent: the JD's existing criteria are cleared and the confirmed set re-written, so the
    manager can re-confirm an edited set without accumulating stale rows.

    Raises:
        DocumentNotFoundError: if the document is absent or owned by another user.
        DocumentTypeMismatchError: if the document is not a job description.
    """
    _owned_jd(session, document_id, owner_id)
    session.execute(delete(JdCriterion).where(JdCriterion.jd_document_id == document_id))
    cleaned = _clean_texts(texts)
    for position, text in enumerate(cleaned):
        session.add(JdCriterion(jd_document_id=document_id, text=text, position=position))
    session.flush()
    _log.info("jd_criteria.confirmed", document_id=str(document_id), count=len(cleaned))
    return cleaned


def list_jd_criteria(session: Session, *, document_id: uuid.UUID, owner_id: uuid.UUID) -> list[str]:
    """Return a JD's confirmed criteria in stated order, so the confirm step can pre-fill them.

    Raises:
        DocumentNotFoundError: if the document is absent or owned by another user.
        DocumentTypeMismatchError: if the document is not a job description.
    """
    _owned_jd(session, document_id, owner_id)
    return resolve_jd_criteria(session, jd_document_id=document_id)
