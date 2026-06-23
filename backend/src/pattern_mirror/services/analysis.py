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

import structlog
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from pattern_mirror.engine.dictionary import load_active_rules, match_dictionary
from pattern_mirror.engine.fingerprint import compute_sentence_fingerprint
from pattern_mirror.models.documents import AnalysisRun, Document
from pattern_mirror.models.engine import Flag
from pattern_mirror.models.enums import AnalysisRunStatus, AnalysisTrigger, DocType, FlagScope

_REGION_CODE = "SG"
_log = structlog.get_logger("pattern_mirror.services.analysis")


@dataclass(frozen=True)
class AnalysisResult:
    """The persisted outcome of one analysis run, ready for serialisation."""

    document: Document
    run: AnalysisRun
    flags: list[Flag]


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
        # Dictionary candidates always carry offsets and a lemma key; narrow for mypy.
        assert (
            candidate.start_offset is not None
            and candidate.end_offset is not None
            and candidate.lemma_key is not None
        )
        session.add(
            Flag(
                document_id=document.id,
                analysis_run_id=run.id,
                source_stage=candidate.source_stage,
                dictionary_entry_id=candidate.dictionary_entry_id,
                citation_id=candidate.citation_id,
                category=candidate.category,
                scope=FlagScope.general,
                raw_span=candidate.raw_span,
                normalised_span=candidate.lemma_key,
                sentence_fingerprint=compute_sentence_fingerprint(
                    content, candidate.start_offset, candidate.end_offset
                ),
                start_offset=candidate.start_offset,
                end_offset=candidate.end_offset,
                rationale={"explanation": candidate.explanation},
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
