"""Document-scoped dismissal suppression, a deterministic Module (design spec §12).

A manager's dismissal is a ``flag_dismissals`` row keyed by signature ``(document_id,
rule_id, normalised_span, sentence_fingerprint)``. Every run regenerates flags; this module
decides which an active dismissal already covers, so the same concern in the same context is
logged but not re-surfaced. Scoping is the loader's query, so dismissals never cross documents.
"""

import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from pattern_mirror.engine.candidate_flag import CandidateFlag
from pattern_mirror.engine.fingerprint import compute_sentence_fingerprint
from pattern_mirror.engine.lemmatiser import lemma_key
from pattern_mirror.engine.state import SuppressedFlag
from pattern_mirror.models.engine import FlagDismissal


def load_active_dismissals(session: Session, document_id: uuid.UUID) -> list[FlagDismissal]:
    """Load one document's active dismissals; the document filter is the scoping guarantee.

    Args:
        session: An open database session.
        document_id: The document whose dismissals apply.

    Returns:
        The document's active dismissals; empty when none are recorded.
    """
    return list(
        session.scalars(
            select(FlagDismissal).where(
                FlagDismissal.document_id == document_id,
                FlagDismissal.active.is_(True),
            )
        ).all()
    )


def normalised_span_of(candidate: CandidateFlag) -> str:
    """Return the lemma-normalised span used in a flag's dismissal signature.

    Dictionary flags carry a ``lemma_key`` already; contextual flags derive one from the raw
    span. Shared by suppression matching and flag persistence so the two cannot drift.
    """
    return candidate.lemma_key if candidate.lemma_key is not None else lemma_key(candidate.raw_span)


@dataclass(frozen=True)
class DismissalIndex:
    """Active dismissals indexed for the §12 signature lookup, built once per run.

    Keyed by ``(rule_id, normalised_span)`` — the text-independent part of the signature —
    each entry maps a ``sentence_fingerprint`` to the dismissal that recorded it.
    """

    _by_key: dict[tuple[uuid.UUID | None, str], dict[str, uuid.UUID]]

    @classmethod
    def from_dismissals(cls, dismissals: list[FlagDismissal]) -> "DismissalIndex":
        """Build the index from a document's active dismissals."""
        by_key: dict[tuple[uuid.UUID | None, str], dict[str, uuid.UUID]] = {}
        for dismissal in dismissals:
            key = (dismissal.rule_id, dismissal.normalised_span)
            by_key.setdefault(key, {})[dismissal.sentence_fingerprint] = dismissal.id
        return cls(_by_key=by_key)

    def resolve(
        self, *, rule_id: uuid.UUID | None, normalised_span: str, sentence_fingerprint: str
    ) -> uuid.UUID | None:
        """Return the dismissal suppressing this signature, or ``None`` to surface the flag.

        A different fingerprint under a matched key means the context shifted, so the manager
        re-judges and the flag surfaces.

        Args:
            rule_id: The flag's dictionary rule, or ``None`` for a contextual flag.
            normalised_span: The flag's lemma-normalised span.
            sentence_fingerprint: The lemma-bag hash of the flag's containing sentence.

        Returns:
            The matching active dismissal's id, or ``None`` when nothing matches exactly.
        """
        fingerprints = self._by_key.get((rule_id, normalised_span))
        if fingerprints is None:
            return None
        return fingerprints.get(sentence_fingerprint)


def partition_by_dismissal(
    flags: list[CandidateFlag], *, content: str, index: DismissalIndex
) -> tuple[list[CandidateFlag], list[SuppressedFlag]]:
    """Split verified flags into those to score and those an active dismissal suppresses.

    Suppressed flags ride out paired with their dismissal id for persistence; they are logged
    but never scored, rewritten, or surfaced. Offsets are resolved here (the Adjudicator ran),
    so every fingerprint is computable.

    Args:
        flags: The Adjudicator's verified flags.
        content: The exact document text the offsets index into.
        index: The document's active dismissals, indexed for lookup.

    Returns:
        The survivors to pass on, and the dismissal-suppressed flags to persist.
    """
    survivors: list[CandidateFlag] = []
    suppressed: list[SuppressedFlag] = []
    for flag in flags:
        assert flag.start_offset is not None and flag.end_offset is not None
        dismissal_id = index.resolve(
            rule_id=flag.dictionary_entry_id,
            normalised_span=normalised_span_of(flag),
            sentence_fingerprint=compute_sentence_fingerprint(
                content, flag.start_offset, flag.end_offset
            ),
        )
        if dismissal_id is None:
            survivors.append(flag)
        else:
            suppressed.append(SuppressedFlag(flag=flag, dismissal_id=dismissal_id))
    return survivors, suppressed
