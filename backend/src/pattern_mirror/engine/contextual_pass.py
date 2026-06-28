"""Stage 2 of the engine: the LLM Contextual Pass, an Agent (Claude Sonnet 4.6).

One schema-enforced Anthropic call (via Instructor) that reads a document in its role
context and does two things the deterministic dictionary cannot: it rules each keyword hit
against the TAFEP GDOR test, and it adds bias the keyword list missed — role-specific
phrasing, coded language, framing. The model's output is parsed into a Pydantic schema
before any flag is built: the LLM is a boundary, so raw model text never flows downstream
(CODE_STYLE).

The keyword checker is literal and context-blind, so the Contextual Pass is the layer that
decides whether a hit is genuine bias, a justified job requirement, or a false positive
(ADR 0010). New flags are tagged *general* (dictionary-eligible) vs *role-specific*
(LLM-only) — the trigger input for the Dictionary Growth loop (design spec §3). New spans
arrive without offsets; the Adjudicator resolves and verifies them, so a phrase the model
did not copy verbatim from the source is dropped before it can reach a manager.
"""

import time
import uuid
from collections.abc import Mapping
from dataclasses import dataclass

from pydantic import BaseModel, Field

from pattern_mirror.engine.candidate_flag import CandidateFlag
from pattern_mirror.engine.llm_agent import StructuredCompletionClient
from pattern_mirror.engine.state import DictionaryVerdict
from pattern_mirror.models.enums import (
    BiasCategory,
    DocType,
    FlagScope,
    FlagSourceStage,
    FlagVerdict,
)

_MAX_TOKENS = 4096

_DOC_TYPE_LABELS: dict[DocType, str] = {
    DocType.jd: "job description",
    DocType.feedback: "interview feedback",
    DocType.promotion: "promotion write-up",
}

_SYSTEM_PROMPT = (
    "You are a bias-detection reviewer for hiring and promotion writing under Singapore's "
    "TAFEP fair-employment rules. You judge phrasing against the protected characteristics: "
    "gender, age, race, nationality, religion, disability, and family status.\n\n"
    "Phrasing that references a protected characteristic is lawful ONLY as a Genuine and "
    "Determining Occupational Requirement (GDOR): the job cannot function without it, stated "
    'objectively as a capability or outcome ("must lift 15 kg"), never as an identity '
    "trait. Verdicts:\n"
    "- acceptable: no protected characteristic referenced (for a keyword hit, a false "
    "positive — the word is not biased here).\n"
    "- acceptable_with_justification: references a protected characteristic but is a genuine "
    "requirement stated objectively.\n"
    "- unacceptable: references a protected characteristic and is not a GDOR.\n\n"
    "You are given the document and the flags a fixed keyword checker already raised. Do two "
    "things:\n"
    "1. Rule on each keyword flag in context, returning its verdict and brief reasoning. The "
    "checker is literal and context-blind, so it raises false positives you must clear.\n"
    "2. Add flags for bias the checker missed — coded language, framing, role-specific "
    "phrasing. Do NOT re-flag or overlap a keyword span; speak to those through task 1. Copy "
    "each new span VERBATIM from the document; a span that is not an exact substring is "
    "discarded. When in doubt, do not add it — a false alarm costs the manager's trust."
)


class DictionaryFlagReview(BaseModel):
    """The model's in-context GDOR ruling on one keyword flag the checker raised."""

    flag_id: int = Field(
        description="The id of the keyword flag being ruled on, from the list given."
    )
    verdict: FlagVerdict = Field(description="The GDOR verdict for this keyword hit in context.")
    reasoning: str = Field(description="One or two sentences justifying the verdict in context.")


class ContextualFlag(BaseModel):
    """One bias flag the keyword checker missed, validated before any engine flag is built."""

    raw_span: str = Field(
        description=(
            "The biased phrase, copied verbatim from the document. Must be an exact "
            "substring of the source text or it is discarded."
        )
    )
    category: BiasCategory = Field(
        description="The protected characteristic the phrasing skews toward."
    )
    scope: FlagScope = Field(
        description=(
            "'general' if the phrasing is biased in any hiring context (a dictionary could "
            "catch it); 'role_specific' if it is biased only given this particular role."
        )
    )
    verdict: FlagVerdict = Field(
        description=(
            "'unacceptable' for clear bias; 'acceptable_with_justification' for a "
            "protected-characteristic reference that is a genuine, objectively-stated "
            "requirement."
        )
    )
    explanation: str = Field(
        description="One or two sentences: why this phrasing is biased in context."
    )


class ContextualPassResult(BaseModel):
    """The schema the model must fill: rulings on the keyword flags plus any it missed."""

    dictionary_reviews: list[DictionaryFlagReview] = Field(
        default_factory=list,
        description="A ruling for each keyword flag given; empty if none were given.",
    )
    new_flags: list[ContextualFlag] = Field(
        default_factory=list,
        description="Bias the keyword checker missed; an empty list if it caught everything.",
    )


@dataclass(frozen=True)
class ContextualPassRun:
    """A completed Contextual Pass: its parsed result plus what the audit log needs."""

    result: ContextualPassResult
    prompt_tokens: int | None
    completion_tokens: int | None
    latency_ms: int


def _format_keyword_flags(dictionary_flags: list[CandidateFlag]) -> str:
    if not dictionary_flags:
        return "None — the keyword checker raised nothing."
    return "\n".join(
        f'[{index}] "{flag.raw_span}" ({flag.category.value})'
        for index, flag in enumerate(dictionary_flags)
    )


def _user_prompt(
    document_text: str, doc_type: DocType, dictionary_flags: list[CandidateFlag]
) -> str:
    label = _DOC_TYPE_LABELS[doc_type]
    return (
        f"Review the following {label}. Rule on each keyword flag and add any bias missed.\n\n"
        f"--- {label.upper()} ---\n{document_text}\n\n"
        f"--- KEYWORD FLAGS ---\n{_format_keyword_flags(dictionary_flags)}"
    )


def run_contextual_pass(
    client: StructuredCompletionClient,
    *,
    document_text: str,
    doc_type: DocType,
    dictionary_flags: list[CandidateFlag],
    model: str,
) -> ContextualPassRun:
    """Run the Contextual Pass over a document and return its validated rulings + usage.

    Args:
        client: An Instructor-wrapped Anthropic client (or a test fake).
        document_text: The document to review.
        doc_type: The document's type, which sets the role context in the prompt.
        dictionary_flags: The keyword flags the dictionary stage raised, for in-context review.
        model: The Anthropic model id (from config).

    Returns:
        The parsed result and the token/latency figures the audit log records.
    """
    started = time.monotonic()
    parsed, completion = client.create_with_completion(
        model=model,
        max_tokens=_MAX_TOKENS,
        system=_SYSTEM_PROMPT,
        messages=[
            {"role": "user", "content": _user_prompt(document_text, doc_type, dictionary_flags)}
        ],
        response_model=ContextualPassResult,
    )
    latency_ms = int((time.monotonic() - started) * 1000)
    result: ContextualPassResult = parsed
    usage = getattr(completion, "usage", None)
    return ContextualPassRun(
        result=result,
        prompt_tokens=getattr(usage, "input_tokens", None),
        completion_tokens=getattr(usage, "output_tokens", None),
        latency_ms=latency_ms,
    )


def to_candidate_flags(
    result: ContextualPassResult, category_citations: Mapping[BiasCategory, uuid.UUID]
) -> list[CandidateFlag]:
    """Map the model's new flags to candidate flags, attaching each one's floor citation.

    Per ADR 0006 every flag carries a citation by reference: a contextual flag takes the
    category-level TAFEP citation for its bias category. A flag whose category has no floor
    citation is dropped rather than surfaced uncited. Offsets and the lemma key are absent;
    the Adjudicator resolves and verifies the span downstream.

    Args:
        result: The validated Contextual Pass output.
        category_citations: The per-category floor citations (``load_category_citations``).

    Returns:
        One candidate flag per cited new flag, carrying its verdict, in input order.
    """
    candidates: list[CandidateFlag] = []
    for flag in result.new_flags:
        citation_id = category_citations.get(flag.category)
        if citation_id is None:
            continue
        candidates.append(
            CandidateFlag(
                source_stage=FlagSourceStage.contextual,
                category=flag.category,
                raw_span=flag.raw_span,
                scope=flag.scope,
                citation_id=citation_id,
                explanation=flag.explanation,
                verdict=flag.verdict,
            )
        )
    return candidates


def to_dictionary_verdicts(
    dictionary_flags: list[CandidateFlag], result: ContextualPassResult
) -> list[DictionaryVerdict]:
    """Resolve the model's keyword rulings against the flags they ruled on, keyed by span.

    A review whose ``flag_id`` is out of range is dropped — the boundary trusts the schema's
    types but not that the model indexed a flag that exists. Offsets are present because the
    dictionary stage resolves them at match time.

    Args:
        dictionary_flags: The keyword flags passed to the model, in the order it indexed them.
        result: The validated Contextual Pass output.

    Returns:
        One verdict per valid review, carrying the ruled flag's span offsets.
    """
    verdicts: list[DictionaryVerdict] = []
    for review in result.dictionary_reviews:
        if not 0 <= review.flag_id < len(dictionary_flags):
            continue
        flag = dictionary_flags[review.flag_id]
        assert flag.start_offset is not None and flag.end_offset is not None
        verdicts.append(
            DictionaryVerdict(
                start_offset=flag.start_offset,
                end_offset=flag.end_offset,
                verdict=review.verdict,
                reasoning=review.reasoning,
            )
        )
    return verdicts
