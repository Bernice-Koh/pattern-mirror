"""Stage 3 of the engine: the Adjudicator, a deterministic Module (no LLM).

Verifies that each candidate flag's claimed span exists verbatim in the source and drops
any that does not, so a hallucinated quote can never reach the Judge or the manager. A
pure function over plain value objects; persisting its result (#21) stays at the boundary.
"""

from dataclasses import dataclass, replace
from enum import StrEnum, auto

from pattern_mirror.engine.candidate_flag import CandidateFlag


class RejectionReason(StrEnum):
    """Why a candidate flag failed verbatim verification and was dropped."""

    span_not_in_source = auto()
    offset_mismatch = auto()


@dataclass(frozen=True)
class RejectedFlag:
    """A dropped flag paired with the reason it failed, for the audit trail."""

    flag: CandidateFlag
    reason: RejectionReason


@dataclass(frozen=True)
class AdjudicationResult:
    """The outcome of one adjudication: survivors to score, rejections to record."""

    verified: list[CandidateFlag]
    rejected: list[RejectedFlag]


def adjudicate_flags(flags: list[CandidateFlag], source_text: str) -> AdjudicationResult:
    """Drop any flag whose claimed span is not verbatim in the source; keep the rest.

    A flag with offsets is verified at exactly those offsets, so one of two identical
    spans is never relocated to the other; a flag without offsets gains those of its
    first occurrence.

    Args:
        flags: Candidate flags from the dictionary and contextual stages.
        source_text: The exact document text the manager submitted.

    Returns:
        The verified survivors (each with resolved offsets) and the rejected flags,
        each carrying the reason it failed.
    """
    verified: list[CandidateFlag] = []
    rejected: list[RejectedFlag] = []
    for flag in flags:
        outcome = _verify(flag, source_text)
        if isinstance(outcome, RejectionReason):
            rejected.append(RejectedFlag(flag=flag, reason=outcome))
        else:
            verified.append(outcome)
    return AdjudicationResult(verified=verified, rejected=rejected)


def _verify(flag: CandidateFlag, source_text: str) -> CandidateFlag | RejectionReason:
    if not flag.raw_span:
        return RejectionReason.span_not_in_source

    if flag.start_offset is not None and flag.end_offset is not None:
        if source_text[flag.start_offset : flag.end_offset] == flag.raw_span:
            return flag
        return RejectionReason.offset_mismatch

    start = source_text.find(flag.raw_span)
    if start == -1:
        return RejectionReason.span_not_in_source
    return replace(flag, start_offset=start, end_offset=start + len(flag.raw_span))
