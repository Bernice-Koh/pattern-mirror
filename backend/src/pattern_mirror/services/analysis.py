"""Stage-1 analysis service: persist a document, run the Dictionary Service, persist flags.

The end-to-end seam (#21) that the later engine stages plug into without changing the
endpoint contract. Region is fixed to SG for the MVP, document content is stored inline as
text (schema decision D2), and flags are written with full provenance — stage, rule,
citation, normalised span, sentence fingerprint, offsets — so the run is reconstructable
and dismissals can later match by signature.
"""

import hashlib
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

import structlog
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from pattern_mirror.engine.candidate_flag import CandidateFlag
from pattern_mirror.engine.dictionary import load_active_rules, match_dictionary
from pattern_mirror.engine.fingerprint import compute_sentence_fingerprint
from pattern_mirror.engine.lemmatiser import lemma_key
from pattern_mirror.models.documents import AnalysisRun, Document
from pattern_mirror.models.engine import Flag
from pattern_mirror.models.enums import AnalysisRunStatus, AnalysisTrigger, DocType

_REGION_CODE = "SG"
_log = structlog.get_logger("pattern_mirror.services.analysis")


@dataclass(frozen=True)
class AnalysisResult:
    """The persisted outcome of one analysis run, ready for serialisation."""

    document: Document
    run: AnalysisRun
    flags: list[Flag]


def build_flag(
    *,
    document_id: uuid.UUID,
    analysis_run_id: uuid.UUID,
    candidate: CandidateFlag,
    content: str,
    judge_confidence: float | None = None,
    suppressed: bool = False,
) -> Flag:
    """Build a persistable ``Flag`` row from a candidate, with its full provenance.

    Shared by the synchronous analyze path and the streaming pipeline so both write
    flags the same way. The sentence fingerprint is recomputed from ``content`` and the
    span offsets so dismissals can later match this flag by signature (#56).

    Args:
        document_id: The document the flag belongs to.
        analysis_run_id: The run that produced the flag.
        candidate: A verified candidate flag from the engine. Offsets are present (the
            Adjudicator resolves them for every survivor); ``lemma_key`` is present only
            on dictionary flags, so for contextual flags the normalised span is derived
            from ``raw_span``.
        content: The exact document text the offsets index into.
        judge_confidence: The Judge's raw confidence, or None for a flag it did not score.
        suppressed: True when the Judge's gate dropped the flag (logged, not surfaced).

    Returns:
        An unpersisted ``Flag`` carrying the candidate's span, provenance, and fingerprint.
    """
    assert candidate.start_offset is not None and candidate.end_offset is not None
    normalised_span = (
        candidate.lemma_key if candidate.lemma_key is not None else lemma_key(candidate.raw_span)
    )
    return Flag(
        document_id=document_id,
        analysis_run_id=analysis_run_id,
        source_stage=candidate.source_stage,
        dictionary_entry_id=candidate.dictionary_entry_id,
        citation_id=candidate.citation_id,
        category=candidate.category,
        scope=candidate.scope,
        raw_span=candidate.raw_span,
        normalised_span=normalised_span,
        sentence_fingerprint=compute_sentence_fingerprint(
            content, candidate.start_offset, candidate.end_offset
        ),
        start_offset=candidate.start_offset,
        end_offset=candidate.end_offset,
        rationale={"explanation": candidate.explanation},
        judge_confidence=Decimal(str(judge_confidence)) if judge_confidence is not None else None,
        suppressed=suppressed,
    )


def analyze_document(
    session: Session,
    *,
    owner_id: uuid.UUID,
    doc_type: DocType,
    content: str,
) -> AnalysisResult:
    """Persist ``content`` as a document, run Stage 1, and persist its flags.

    Args:
        session: The active database session (committed by the caller).
        owner_id: The manager the document belongs to.
        doc_type: The document's type, already validated at the API boundary.
        content: The raw document text.

    Returns:
        The persisted document, its run, and the flags produced, each with its citation
        and dictionary entry eager-loaded for serialisation.
    """
    document = Document(owner_id=owner_id, doc_type=doc_type, content=content)
    session.add(document)
    session.flush()

    run = AnalysisRun(
        document_id=document.id,
        trigger=AnalysisTrigger.submit,
        content_hash=hashlib.sha256(content.encode("utf-8")).hexdigest(),
    )
    session.add(run)
    session.flush()

    rules = load_active_rules(session, _REGION_CODE)
    for candidate in match_dictionary(content, rules):
        session.add(
            build_flag(
                document_id=document.id,
                analysis_run_id=run.id,
                candidate=candidate,
                content=content,
            )
        )

    run.status = AnalysisRunStatus.complete
    run.completed_at = datetime.now(UTC)
    session.flush()

    flags = list(
        session.scalars(
            select(Flag)
            .where(Flag.analysis_run_id == run.id)
            .options(selectinload(Flag.citation), selectinload(Flag.dictionary_entry))
            .order_by(Flag.start_offset)
        ).all()
    )
    _log.info(
        "analysis.complete",
        document_id=str(document.id),
        analysis_run_id=str(run.id),
        flag_count=len(flags),
    )
    return AnalysisResult(document=document, run=run, flags=flags)
