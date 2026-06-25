"""Stage 2 of the engine: the LLM Contextual Pass, an Agent (Claude Sonnet 4.6).

One schema-enforced Anthropic call (via Instructor) that reads a document in its role
context and proposes bias flags the deterministic dictionary cannot catch — role-specific
phrasing, coded language, framing. The model's output is parsed into a Pydantic schema
before any flag is built: the LLM is a boundary, so raw model text never flows downstream
(CODE_STYLE). Each candidate is tagged *general* (dictionary-eligible) vs *role-specific*
(LLM-only) — the trigger input for the Dictionary Growth loop (design spec §3).

Spans arrive without offsets; the Adjudicator resolves and verifies them, so a phrase the
model did not copy verbatim from the source is dropped before it can reach a manager.
"""

import time
import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Protocol, TypeVar, cast

import instructor
from anthropic import Anthropic
from pydantic import BaseModel, Field

from pattern_mirror.core.config import Settings
from pattern_mirror.engine.candidate_flag import CandidateFlag
from pattern_mirror.models.enums import BiasCategory, DocType, FlagScope, FlagSourceStage

T = TypeVar("T")

_MAX_TOKENS = 4096

# USD per million tokens (input, output) per model, for the agent_runs cost audit. Static
# table kept in code deliberately — update when Anthropic pricing changes; an unknown model
# logs a null cost rather than a wrong one.
_PRICES_USD_PER_MTOK: dict[str, tuple[str, str]] = {
    "claude-sonnet-4-6": ("3", "15"),
}

_DOC_TYPE_LABELS: dict[DocType, str] = {
    DocType.jd: "job description",
    DocType.feedback: "interview feedback",
    DocType.promotion: "promotion write-up",
}

_SYSTEM_PROMPT = (
    "You are a bias-detection reviewer for hiring and promotion writing. You read a "
    "document in its role context and flag phrasing that signals bias toward a protected "
    "characteristic: gender, age, race, nationality, religion, disability, or family "
    "status.\n\n"
    "You catch what a fixed keyword list cannot: phrasing that is only biased given the "
    "role, coded language, and framing. Only flag text that is actually present. Do not "
    "flag neutral, job-relevant requirements (a real skill, qualification, or duty is not "
    "bias). When in doubt, do not flag — a false alarm costs the manager's trust.\n\n"
    "Copy each flagged span VERBATIM from the document — character for character, "
    "including original casing and punctuation. A span that is not an exact substring of "
    "the document is discarded, so paraphrasing wastes the flag."
)


class ContextualFlag(BaseModel):
    """One bias flag proposed by the model, validated before any engine flag is built."""

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
    explanation: str = Field(
        description="One or two sentences: why this phrasing is biased in context."
    )


class ContextualPassResult(BaseModel):
    """The schema the model must fill: the bias flags found in the document."""

    flags: list[ContextualFlag] = Field(
        default_factory=list,
        description="Every biased phrase found; an empty list if the document is clean.",
    )


@dataclass(frozen=True)
class ContextualPassRun:
    """A completed Contextual Pass: its parsed result plus what the audit log needs."""

    result: ContextualPassResult
    prompt_tokens: int | None
    completion_tokens: int | None
    latency_ms: int


class StructuredCompletionClient(Protocol):
    """The one Instructor method the pass uses: schema-validated output plus the completion.

    Typed as a Protocol so the agent is exercised in tests with a deterministic fake and is
    not coupled to Instructor's class hierarchy.
    """

    def create_with_completion(self, **kwargs: Any) -> tuple[Any, Any]: ...


def _user_prompt(document_text: str, doc_type: DocType) -> str:
    label = _DOC_TYPE_LABELS[doc_type]
    return (
        f"Review the following {label} for biased phrasing and return the flags.\n\n"
        f"--- {label.upper()} ---\n{document_text}"
    )


def run_contextual_pass(
    client: StructuredCompletionClient,
    *,
    document_text: str,
    doc_type: DocType,
    model: str,
) -> ContextualPassRun:
    """Run the Contextual Pass over a document and return its validated flags + usage.

    Args:
        client: An Instructor-wrapped Anthropic client (or a test fake).
        document_text: The document to review.
        doc_type: The document's type, which sets the role context in the prompt.
        model: The Anthropic model id (from config).

    Returns:
        The parsed result and the token/latency figures the audit log records.
    """
    started = time.monotonic()
    parsed, completion = client.create_with_completion(
        model=model,
        max_tokens=_MAX_TOKENS,
        system=_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": _user_prompt(document_text, doc_type)}],
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
    """Map validated model output to candidate flags, attaching each one's floor citation.

    Per ADR 0006 every flag carries a citation by reference: a contextual flag takes the
    category-level TAFEP citation for its bias category. A flag whose category has no floor
    citation is dropped rather than surfaced uncited. Offsets and the lemma key are absent;
    the Adjudicator resolves and verifies the span downstream.

    Args:
        result: The validated Contextual Pass output.
        category_citations: The per-category floor citations (``load_category_citations``).

    Returns:
        One candidate flag per cited model flag, in input order.
    """
    candidates: list[CandidateFlag] = []
    for flag in result.flags:
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
            )
        )
    return candidates


def estimate_cost_usd(
    model: str, prompt_tokens: int | None, completion_tokens: int | None
) -> Decimal | None:
    """Estimate the call cost from token usage, or None if pricing/usage is unavailable."""
    price = _PRICES_USD_PER_MTOK.get(model)
    if price is None or prompt_tokens is None or completion_tokens is None:
        return None
    input_price, output_price = price
    per_million = Decimal(1_000_000)
    return (
        Decimal(prompt_tokens) * Decimal(input_price)
        + Decimal(completion_tokens) * Decimal(output_price)
    ) / per_million


def build_contextual_client(settings: Settings) -> StructuredCompletionClient | None:
    """Build the production Instructor-wrapped Anthropic client, or None without a key.

    Construction is network-free — no request is made until ``create_with_completion`` is
    called — so this is safe to call on a path that may not run the agent. Returns None when
    no API key is configured, which the orchestrator wires as a passthrough (the engine
    degrades to dictionary-only rather than failing).
    """
    if settings.anthropic_api_key is None:
        return None
    # Instructor's overloaded create_with_completion doesn't structurally unify with the
    # minimal Protocol, but the runtime contract is exactly what the agent calls.
    client = instructor.from_anthropic(Anthropic(api_key=settings.anthropic_api_key))
    return cast(StructuredCompletionClient, client)
