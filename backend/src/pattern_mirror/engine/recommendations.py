"""Stage 5 of the engine: the Recommendations Agent (Claude Sonnet 4.6).

One schema-enforced Anthropic call (via Instructor) that, for each surfaced flag, proposes
2-3 evidence-anchored alternative phrasings — never a single "correct" answer (design spec
§7). It runs only on flags the Judge passed above threshold, so low-confidence noise never
reaches a manager. Each recommendation's rationale is grounded in the flag's citation, which
is supplied to the prompt by reference; the model is told not to invent research.
"""

import time
import uuid
from collections.abc import Mapping
from dataclasses import dataclass

from pydantic import BaseModel, Field

from pattern_mirror.core.errors import RecommendationCountError
from pattern_mirror.engine.candidate_flag import CandidateFlag
from pattern_mirror.engine.llm_agent import StructuredCompletionClient
from pattern_mirror.engine.state import FlagRecommendation
from pattern_mirror.models.enums import DocType

_MAX_TOKENS = 4096

_DOC_TYPE_LABELS: dict[DocType, str] = {
    DocType.jd: "job description",
    DocType.feedback: "interview feedback",
    DocType.promotion: "promotion write-up",
}

_SYSTEM_PROMPT = (
    "You help managers rewrite biased phrasing in hiring and promotion documents. Each phrase "
    "you are given is already confirmed to reflect bias toward a protected characteristic and "
    "is already backed by a cited source.\n\n"
    "For each flag, propose 2 or 3 alternative phrasings that preserve the author's intent but "
    "remove the bias, plus a one-sentence rationale. Offer alternatives, never a single "
    "'correct' answer — the manager chooses. Keep each alternative a concrete drop-in "
    "replacement for the flagged span, not a rewrite of the whole sentence. Ground the "
    "rationale in the supplied evidence; never invent research or cite a source not given."
)


class Recommendation(BaseModel):
    """Evidence-anchored rewrites for one flagged phrase."""

    rationale: str = Field(
        description="One sentence, grounded in the supplied evidence, on why the bias arises."
    )
    alternatives: list[str] = Field(
        min_length=2,
        max_length=3,
        description="2-3 drop-in replacements for the flagged span; never a single answer.",
    )


class RecommendationsResult(BaseModel):
    """The schema the model must fill: one recommendation per flag, in the order given."""

    recommendations: list[Recommendation] = Field(default_factory=list)


@dataclass(frozen=True)
class RecommendationRun:
    """A completed Recommendations call: its parsed result plus what the audit log needs."""

    result: RecommendationsResult
    prompt_tokens: int | None
    completion_tokens: int | None
    latency_ms: int


def _user_prompt(
    flags: list[CandidateFlag], evidence: Mapping[uuid.UUID, str], doc_type: DocType
) -> str:
    label = _DOC_TYPE_LABELS[doc_type]
    listing = "\n".join(
        f"{index}. category={flag.category.value} | span={flag.raw_span!r} | "
        f"why={flag.explanation or ''} | "
        f"evidence={evidence.get(flag.citation_id, '') if flag.citation_id else ''}"
        for index, flag in enumerate(flags, start=1)
    )
    return (
        f"Suggest rewrites for each flagged phrase from this {label}. Return one "
        f"recommendation per flag, in order.\n\n{listing}"
    )


def run_recommendations(
    client: StructuredCompletionClient,
    *,
    flags: list[CandidateFlag],
    evidence: Mapping[uuid.UUID, str],
    doc_type: DocType,
    model: str,
) -> RecommendationRun:
    """Generate rewrites for the given flags and return the validated result + usage.

    Args:
        client: An Instructor-wrapped Anthropic client (or a test fake).
        flags: The above-threshold flags to rewrite, in the order results must come back.
        evidence: Per-citation evidence text keyed by citation id, anchoring the rationale.
        doc_type: The document's type, which sets the role context in the prompt.
        model: The Anthropic model id (from config).

    Returns:
        The parsed result and the token/latency figures the audit log records.

    Raises:
        RecommendationCountError: if the model returns a different number of sets than flags.
    """
    started = time.monotonic()
    parsed, completion = client.create_with_completion(
        model=model,
        max_tokens=_MAX_TOKENS,
        system=_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": _user_prompt(flags, evidence, doc_type)}],
        response_model=RecommendationsResult,
    )
    latency_ms = int((time.monotonic() - started) * 1000)
    result: RecommendationsResult = parsed
    if len(result.recommendations) != len(flags):
        raise RecommendationCountError(len(flags), len(result.recommendations))
    usage = getattr(completion, "usage", None)
    return RecommendationRun(
        result=result,
        prompt_tokens=getattr(usage, "input_tokens", None),
        completion_tokens=getattr(usage, "output_tokens", None),
        latency_ms=latency_ms,
    )


def to_flag_recommendations(
    flags: list[CandidateFlag], result: RecommendationsResult
) -> list[FlagRecommendation]:
    """Pair each flag with its rewrites, in the order the flags were given.

    Args:
        flags: The flags passed to ``run_recommendations``, in result order.
        result: The validated Recommendations output.

    Returns:
        One ``FlagRecommendation`` per flag, carrying the flag so persistence can match it.
    """
    return [
        FlagRecommendation(flag=flag, rationale=rec.rationale, alternatives=list(rec.alternatives))
        for flag, rec in zip(flags, result.recommendations, strict=True)
    ]
