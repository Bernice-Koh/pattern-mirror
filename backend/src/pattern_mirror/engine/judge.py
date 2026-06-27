"""Stage 4 of the engine: the LLM Judge, an Agent (Claude Haiku 4.5).

One schema-enforced Anthropic call (via Instructor) that scores each verified contextual flag
on confidence only. The Adjudicator already guarantees the span exists verbatim, so there is
no hallucination check (ADR-0007). The score is an uncalibrated verbalized confidence in
[0, 1] (ADR-0008); gating against the threshold runs on the calibrated score in
``to_judge_scores``. Below-threshold flags are marked suppressed and terminate here.
"""

import time
from dataclasses import dataclass

from pydantic import BaseModel, Field

from pattern_mirror.core.config import Settings
from pattern_mirror.core.errors import JudgeVerdictCountError
from pattern_mirror.engine.calibration import (
    calibrate_confidence,
    passes_threshold,
    threshold_for,
)
from pattern_mirror.engine.candidate_flag import CandidateFlag
from pattern_mirror.engine.llm_agent import StructuredCompletionClient
from pattern_mirror.engine.state import JudgeScore
from pattern_mirror.models.enums import DocType

_MAX_TOKENS = 4096

_DOC_TYPE_LABELS: dict[DocType, str] = {
    DocType.jd: "job description",
    DocType.feedback: "interview feedback",
    DocType.promotion: "promotion write-up",
}

_SYSTEM_PROMPT = (
    "You are a calibration reviewer for hiring and promotion bias flags. Each flag is a phrase "
    "already confirmed to appear verbatim in the document; your only job is to judge how "
    "strongly it reflects bias toward the stated protected characteristic, in context.\n\n"
    "Return a confidence in [0, 1] for each flag, in the order given: 1 means the phrasing is "
    "unambiguously biased, 0 means it is benign or genuinely job-relevant. Be calibrated, not "
    "generous — a borderline or context-dependent case belongs near the middle, not near 1. "
    "Judge only the bias claim; never question whether the phrase exists."
)


class JudgeVerdict(BaseModel):
    """The Judge's confidence that one flagged phrase reflects the claimed bias."""

    confidence: float = Field(
        ge=0,
        le=1,
        description="0 = benign/job-relevant, 1 = unambiguous bias, for THIS flag.",
    )
    reasoning: str = Field(description="One sentence: why this confidence.")


class JudgeResult(BaseModel):
    """The schema the model must fill: one verdict per flag, in the order the flags were given."""

    verdicts: list[JudgeVerdict] = Field(default_factory=list)


@dataclass(frozen=True)
class JudgeRun:
    """A completed Judge call: its parsed result plus what the audit log needs."""

    result: JudgeResult
    prompt_tokens: int | None
    completion_tokens: int | None
    latency_ms: int


def _user_prompt(flags: list[CandidateFlag], doc_type: DocType) -> str:
    label = _DOC_TYPE_LABELS[doc_type]
    listing = "\n".join(
        f"{index}. category={flag.category.value} | span={flag.raw_span!r} | "
        f"why={flag.explanation or ''}"
        for index, flag in enumerate(flags, start=1)
    )
    return (
        f"Score each flagged phrase from this {label}. Return one verdict per flag, in order.\n\n"
        f"{listing}"
    )


def run_judge(
    client: StructuredCompletionClient,
    *,
    flags: list[CandidateFlag],
    doc_type: DocType,
    model: str,
) -> JudgeRun:
    """Score the given flags on confidence and return the validated verdicts + usage.

    Args:
        client: An Instructor-wrapped Anthropic client (or a test fake).
        flags: The verified flags to score, in the order verdicts must come back.
        doc_type: The document's type, which sets the role context in the prompt.
        model: The Anthropic model id (from config).

    Returns:
        The parsed result and the token/latency figures the audit log records.

    Raises:
        JudgeVerdictCountError: if the model returns a different number of verdicts than flags.
    """
    started = time.monotonic()
    parsed, completion = client.create_with_completion(
        model=model,
        max_tokens=_MAX_TOKENS,
        system=_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": _user_prompt(flags, doc_type)}],
        response_model=JudgeResult,
    )
    latency_ms = int((time.monotonic() - started) * 1000)
    result: JudgeResult = parsed
    if len(result.verdicts) != len(flags):
        raise JudgeVerdictCountError(len(flags), len(result.verdicts))
    usage = getattr(completion, "usage", None)
    return JudgeRun(
        result=result,
        prompt_tokens=getattr(usage, "input_tokens", None),
        completion_tokens=getattr(usage, "output_tokens", None),
        latency_ms=latency_ms,
    )


def to_judge_scores(
    flags: list[CandidateFlag], result: JudgeResult, settings: Settings
) -> list[JudgeScore]:
    """Pair each scored flag with its gate verdict: calibrated score against its threshold.

    Args:
        flags: The flags passed to ``run_judge``, in the same order as ``result.verdicts``.
        result: The validated Judge output.
        settings: Source of the per-category thresholds.

    Returns:
        One ``JudgeScore`` per flag; ``suppressed`` is True when the calibrated confidence
        falls below the flag's category threshold.
    """
    scores: list[JudgeScore] = []
    for flag, verdict in zip(flags, result.verdicts, strict=True):
        calibrated = calibrate_confidence(verdict.confidence)
        suppressed = not passes_threshold(calibrated, threshold_for(flag.category, settings))
        scores.append(JudgeScore(flag=flag, confidence=verdict.confidence, suppressed=suppressed))
    return scores
