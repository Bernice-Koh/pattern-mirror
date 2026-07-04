"""Prime the demo: run the real engine over the seeded submitted documents and persist their
flags and drift findings, so reopening a published demo document re-hydrates real analysis (#130).

Run on demand (``python -m pattern_mirror.jobs.seed_demo_analysis``) after ``seed_demo``. With an
Anthropic key configured it makes real calls — the full pipeline, so the contextual flags that
carry the demo's gendered pattern ("polished", "collaborative") surface alongside the dictionary
hits, plus drift coverage. With no key it persists the deterministic dictionary pass only. Never
part of CI (it can make real calls, like ``calibrate``).

Idempotent by construction: it analyses only documents that have no analysis run yet. A document a
manager submitted live already has runs (they fire while editing), so it is skipped; the seeded
demo documents have none, so they are the ones primed. A re-run is a no-op.
"""

import structlog
from sqlalchemy import select
from sqlalchemy.orm import Session

from pattern_mirror.core.config import get_settings
from pattern_mirror.db.session import get_sessionmaker
from pattern_mirror.engine.llm_agent import StructuredCompletionClient, build_instructor_client
from pattern_mirror.models.documents import AnalysisRun, Document
from pattern_mirror.models.enums import DocumentStatus
from pattern_mirror.services.drift_reference import resolve_drift_reference
from pattern_mirror.services.run_registry import get_run_registry
from pattern_mirror.services.streaming_analysis import stream_analysis_events

_log = structlog.get_logger("pattern_mirror.jobs.seed_demo_analysis")


def _unanalysed_submitted_documents(session: Session) -> list[Document]:
    """Submitted documents with no analysis run yet — the seeded demo docs, not live submissions."""
    has_run = select(AnalysisRun.id).where(AnalysisRun.document_id == Document.id).exists()
    return list(
        session.scalars(
            select(Document)
            .where(Document.status == DocumentStatus.submitted, ~has_run)
            .order_by(Document.created_at)
        )
    )


def seed_demo_analysis(
    session: Session, *, client: StructuredCompletionClient | None = None
) -> int:
    """Analyse each un-analysed submitted document, persisting its flags and drift findings.

    Reuses the exact streaming-submission path (``stream_analysis_events``), so a primed document is
    indistinguishable from one submitted live: the same runs, flags, suppression, and drift rows.
    ``client`` drives the LLM stages; None runs the deterministic dictionary-only path.

    Returns the number of documents analysed.
    """
    registry = get_run_registry()
    documents = _unanalysed_submitted_documents(session)
    for document in documents:
        content = document.submitted_content or document.content
        drift_reference = resolve_drift_reference(session, document)
        # Drain the generator: each stage persists and commits internally.
        for _ in stream_analysis_events(
            session,
            document_id=document.id,
            content=content,
            doc_type=document.doc_type,
            registry=registry,
            contextual_client=client,
            judge_client=client,
            recommendations_client=client,
            drift_client=client if drift_reference is not None else None,
            drift_reference=drift_reference,
        ):
            pass
        _log.info(
            "demo.document_analysed",
            document_id=str(document.id),
            title=document.title,
        )
    return len(documents)


def main() -> None:
    settings = get_settings()
    # Network-free to build; None when no key is configured, which runs dictionary-only.
    client = build_instructor_client(settings)
    if client is None:
        _log.warning("demo.no_api_key_dictionary_only")
    with get_sessionmaker()() as session:
        count = seed_demo_analysis(session, client=client)
        session.commit()
    _log.info("demo.analysis_seeded", documents=count)


if __name__ == "__main__":
    main()
