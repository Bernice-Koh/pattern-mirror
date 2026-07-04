"""The JD-criteria extractor: an Agent (Claude Sonnet 4.6) that drafts a role's criteria.

One schema-enforced Anthropic call (via Instructor) that reads a job description and proposes
the distinct criteria a candidate would be assessed against — the reference a feedback note's
drift check is later measured against (#116). The draft is never authoritative on its own: the
manager confirms or edits it before any row is persisted (#122), so this agent only proposes.

The LLM is a boundary: the response is parsed into a Pydantic schema before any criterion is
read. Criteria are distilled paraphrases, not quotes from the JD, so there is no verbatim gate
here (unlike the drift and bias stages) — the manager-confirm step is the correctness guard.
"""

import time
from dataclasses import dataclass

from pydantic import BaseModel, Field

from pattern_mirror.engine.llm_agent import StructuredCompletionClient

_MAX_TOKENS = 2048

_SYSTEM_PROMPT = (
    "You extract the assessment criteria stated in a job description: the distinct requirements "
    "a candidate would be evaluated against — skills, experience, competencies, and "
    "responsibilities the role calls for.\n\n"
    "Return each criterion as one concise, self-contained statement a reviewer could check "
    "feedback against, in the order the job description presents them. Merge duplicates and keep "
    "each criterion to a single requirement. Base every criterion on what the job description "
    "actually states — do not invent requirements it does not support, and do not include "
    "boilerplate that is not a criterion (company blurb, benefits, how to apply)."
)


class JdCriterionDraft(BaseModel):
    """One drafted criterion, validated at the boundary before the manager reviews it."""

    text: str = Field(description="One concise, self-contained assessment criterion.")


class JdCriteriaDraftResult(BaseModel):
    """The schema the model must fill: the drafted criteria in stated order."""

    criteria: list[JdCriterionDraft] = Field(default_factory=list)


@dataclass(frozen=True)
class JdCriteriaExtractionRun:
    """A completed extraction call: its parsed result plus what the audit log needs."""

    result: JdCriteriaDraftResult
    prompt_tokens: int | None
    completion_tokens: int | None
    latency_ms: int


def _user_prompt(jd_text: str) -> str:
    return f"Extract the assessment criteria from the following job description.\n\n{jd_text}"


def run_jd_criteria_extraction(
    client: StructuredCompletionClient, *, jd_text: str, model: str
) -> JdCriteriaExtractionRun:
    """Draft a JD's assessment criteria; return them plus the call's token/latency figures.

    Args:
        client: An Instructor-wrapped Anthropic client (or a test fake).
        jd_text: The job description text to draft criteria from.
        model: The Anthropic model id (from config).

    Returns:
        The parsed criteria and the token/latency figures the audit log records.
    """
    started = time.monotonic()
    parsed, completion = client.create_with_completion(
        model=model,
        max_tokens=_MAX_TOKENS,
        system=_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": _user_prompt(jd_text)}],
        response_model=JdCriteriaDraftResult,
    )
    latency_ms = int((time.monotonic() - started) * 1000)
    result: JdCriteriaDraftResult = parsed
    usage = getattr(completion, "usage", None)
    return JdCriteriaExtractionRun(
        result=result,
        prompt_tokens=getattr(usage, "input_tokens", None),
        completion_tokens=getattr(usage, "output_tokens", None),
        latency_ms=latency_ms,
    )
