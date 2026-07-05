"""Stage 4 of the engine: the LLM Judge, an Agent (Claude Haiku 4.5).

N schema-enforced Anthropic calls (via Instructor), each answering a GDOR rubric for every
verified contextual flag (ADR-0013). The Judge sees each flag's span with its surrounding
document context; the Contextual Pass's explanation is withheld so the verdict is independent
evidence. The model emits no confidence number: each sample's bias verdict is derived from its
rubric answers, and a flag's confidence is the fraction of samples deriving bias
(self-consistency). Gating against the threshold runs on the calibrated score in
``to_judge_scores``; below-threshold flags are marked suppressed and terminate here.
"""

import random
import time
from dataclasses import dataclass
from typing import Any, Literal

import structlog
from pydantic import BaseModel, Field

from pattern_mirror.core.config import Settings
from pattern_mirror.engine.calibration import (
    agreement_fraction,
    calibrate_confidence,
    derive_bias_verdict,
    passes_threshold,
    threshold_for,
)
from pattern_mirror.engine.candidate_flag import CandidateFlag
from pattern_mirror.engine.llm_agent import StructuredCompletionClient
from pattern_mirror.engine.state import JudgeScore
from pattern_mirror.models.enums import DocType

_log = structlog.get_logger("pattern_mirror.engine.judge")

_MAX_TOKENS = 4096
_CONFIDENCE_DECIMALS = 3  # matches the flags.judge_confidence column, Numeric(4, 3)
_SENTENCE_BREAKS = ".!?\n"

_DOC_TYPE_LABELS: dict[DocType, str] = {
    DocType.jd: "job description",
    DocType.feedback: "interview feedback",
    DocType.promotion: "promotion write-up",
}

_SYSTEM_PROMPT = (
    "You are an independent reviewer of hiring and promotion bias flags under Singapore's "
    "TAFEP fair-employment rules. Each flag is a phrase already confirmed to appear verbatim "
    "in the document; you are given the phrase and its surrounding context, and you answer a "
    "fixed rubric per flag. You never emit a score. Judge from the context alone, and never "
    "question whether the phrase exists.\n\n"
    "The rubric per flag:\n"
    "- references_characteristic: does the phrase, in context, reference a protected "
    "characteristic (gender, age, race, nationality, religion, disability, family status)?\n"
    "- reference_style: 'explicit' if the characteristic is named outright, 'coded' if it is "
    "implied through proxy language, 'none' if no characteristic is referenced.\n"
    "- gdor_plausible: could the reference be a Genuine and Determining Occupational "
    "Requirement, meaning the job cannot function without it?\n"
    "- stated_objectively: is it stated as a measurable capability or outcome "
    '("must lift 15 kg"), rather than as an identity trait?\n\n'
    "Answer each question on its own merits rather than working back from an overall "
    "impression. Return one rubric per flag, matched by flag_id."
)


class JudgeRubric(BaseModel):
    """One sample's rubric answers for one flag, matched back to it by ``flag_id``."""

    flag_id: int = Field(description="The id of the flag being judged, from the list given.")
    references_characteristic: bool = Field(
        description="Whether the phrase references a protected characteristic in context."
    )
    reference_style: Literal["explicit", "coded", "none"] = Field(
        description="How the characteristic is referenced; 'none' if it is not."
    )
    gdor_plausible: bool = Field(
        description="Whether a genuine and determining occupational requirement is plausible."
    )
    stated_objectively: bool = Field(
        description="Whether it is stated as a measurable capability or outcome."
    )
    reasoning: str = Field(description="One sentence: the deciding observation.")


class JudgeSample(BaseModel):
    """The schema one Judge call must fill: one rubric per flag given, in any order."""

    rubrics: list[JudgeRubric] = Field(default_factory=list)


@dataclass(frozen=True)
class JudgeRun:
    """A completed Judge stage: its N samples plus the audit figures, summed across samples."""

    samples: list[JudgeSample]
    prompt_tokens: int | None
    completion_tokens: int | None
    latency_ms: int


def context_window(text: str, start: int, end: int) -> str:
    """The sentence containing ``[start, end)``, bounded by sentence punctuation or a newline."""
    left = start
    while left > 0 and text[left - 1] not in _SENTENCE_BREAKS:
        left -= 1
    right = end
    while right < len(text) and text[right] not in _SENTENCE_BREAKS:
        right += 1
    if right < len(text) and text[right] != "\n":
        right += 1  # keep the closing punctuation, drop a trailing newline
    return text[left:right].strip()


def _flag_context(document_text: str, flag: CandidateFlag) -> str:
    start, end = flag.start_offset, flag.end_offset
    if start is None or end is None:
        found = document_text.find(flag.raw_span)
        if found < 0:
            return flag.raw_span
        start, end = found, found + len(flag.raw_span)
    return context_window(document_text, start, end)


def _user_prompt(
    flags: list[CandidateFlag], document_text: str, doc_type: DocType, seed: int
) -> str:
    # Flag order is shuffled per sample (seeded, so a run is reproducible) to neutralise
    # position bias; flag_id keys each rubric back regardless of order. The Contextual Pass's
    # explanation is omitted so the Judge's evidence is the document, not the generator (ADR-0013).
    numbered = list(enumerate(flags, start=1))
    random.Random(seed).shuffle(numbered)
    label = _DOC_TYPE_LABELS[doc_type]
    listing = "\n".join(
        f'[flag_id {flag_id}] "{flag.raw_span}" (claimed category: {flag.category.value})\n'
        f'  context: "{_flag_context(document_text, flag)}"'
        for flag_id, flag in numbered
    )
    return (
        f"Judge each flagged phrase from this {label}. "
        f"Return one rubric per flag, matched by flag_id.\n\n{listing}"
    )


def _accumulate_usage(totals: tuple[int, int] | None, usage: Any) -> tuple[int, int] | None:
    prompt = getattr(usage, "input_tokens", None)
    completion = getattr(usage, "output_tokens", None)
    if prompt is None or completion is None:
        return totals
    running_prompt, running_completion = totals or (0, 0)
    return running_prompt + prompt, running_completion + completion


def run_judge(
    client: StructuredCompletionClient,
    *,
    flags: list[CandidateFlag],
    document_text: str,
    doc_type: DocType,
    model: str,
    samples: int,
) -> JudgeRun:
    """Judge the given flags over N self-consistency samples and return them with summed usage.

    Args:
        client: An Instructor-wrapped Anthropic client (or a test fake).
        flags: The verified contextual flags to judge; their 1-based position is the flag_id.
        document_text: The source document, from which each flag's context window is cut.
        doc_type: The document's type, which sets the role context in the prompt.
        model: The Anthropic model id (from config).
        samples: How many samples to draw, each with an independently shuffled flag order.

    Returns:
        The parsed samples and the summed token/latency figures the audit log records.
    """
    started = time.monotonic()
    collected: list[JudgeSample] = []
    totals: tuple[int, int] | None = None
    for seed in range(samples):
        parsed, completion = client.create_with_completion(
            model=model,
            max_tokens=_MAX_TOKENS,
            system=_SYSTEM_PROMPT,
            messages=[
                {"role": "user", "content": _user_prompt(flags, document_text, doc_type, seed)}
            ],
            response_model=JudgeSample,
        )
        collected.append(parsed)
        totals = _accumulate_usage(totals, getattr(completion, "usage", None))
    latency_ms = int((time.monotonic() - started) * 1000)
    prompt_tokens, completion_tokens = totals if totals is not None else (None, None)
    return JudgeRun(
        samples=collected,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        latency_ms=latency_ms,
    )


def _rubrics_by_flag(flag_count: int, samples: list[JudgeSample]) -> dict[int, list[JudgeRubric]]:
    """Group each flag's rubrics across samples; unknown or duplicate ids within a sample drop.

    A sample that skips a flag contributes no vote for it, degrading to fewer votes rather than
    failing the run (ADR-0013): flag_id matching replaces the old positional count check.
    """
    collected: dict[int, list[JudgeRubric]] = {flag_id: [] for flag_id in range(1, flag_count + 1)}
    for sample in samples:
        seen: set[int] = set()
        for rubric in sample.rubrics:
            if rubric.flag_id in collected and rubric.flag_id not in seen:
                collected[rubric.flag_id].append(rubric)
                seen.add(rubric.flag_id)
    return collected


def _votes(rubrics: list[JudgeRubric]) -> list[bool]:
    return [
        derive_bias_verdict(
            references_characteristic=rubric.references_characteristic,
            gdor_plausible=rubric.gdor_plausible,
            stated_objectively=rubric.stated_objectively,
        )
        for rubric in rubrics
    ]


def to_judge_scores(
    flags: list[CandidateFlag], samples: list[JudgeSample], settings: Settings
) -> list[JudgeScore]:
    """Pair each flag with its gate verdict: agreement confidence against its category threshold.

    Args:
        flags: The flags passed to ``run_judge``, whose 1-based positions are the flag ids.
        samples: The validated Judge samples.
        settings: Source of the per-category thresholds.

    Returns:
        One ``JudgeScore`` per flag; ``suppressed`` is True when the calibrated confidence falls
        below the flag's threshold. A flag no sample answered passes ungated (``confidence=None``)
        with a warning, mirroring the no-client degrade.
    """
    collected = _rubrics_by_flag(len(flags), samples)
    scores: list[JudgeScore] = []
    for flag_id, flag in enumerate(flags, start=1):
        votes = _votes(collected[flag_id])
        if not votes:
            _log.warning(
                "engine.judge_flag_unscored",
                raw_span=flag.raw_span,
                category=flag.category.value,
            )
            scores.append(JudgeScore(flag=flag, confidence=None, suppressed=False))
            continue
        confidence = round(agreement_fraction(votes), _CONFIDENCE_DECIMALS)
        calibrated = calibrate_confidence(confidence)
        suppressed = not passes_threshold(calibrated, threshold_for(flag.category, settings))
        scores.append(JudgeScore(flag=flag, confidence=confidence, suppressed=suppressed))
    return scores


def _criterion_fraction(rubrics: list[JudgeRubric], attribute: str) -> float | None:
    if not rubrics:
        return None
    return round(
        agreement_fraction([getattr(rubric, attribute) for rubric in rubrics]),
        _CONFIDENCE_DECIMALS,
    )


def aggregation_fields(flags: list[CandidateFlag], samples: list[JudgeSample]) -> dict[str, Any]:
    """Flatten the per-flag aggregation for the ``agent_runs`` output (ADR-0013).

    Per flag: how many samples voted, the agreement confidence, and each rubric criterion's
    fraction-true across samples, which the calibration dashboard reads.
    """
    collected = _rubrics_by_flag(len(flags), samples)
    per_flag: list[dict[str, Any]] = []
    for flag_id, flag in enumerate(flags, start=1):
        rubrics = collected[flag_id]
        votes = _votes(rubrics)
        per_flag.append(
            {
                "flag_id": flag_id,
                "category": flag.category.value,
                "raw_span": flag.raw_span,
                "votes": len(votes),
                "confidence": (
                    round(agreement_fraction(votes), _CONFIDENCE_DECIMALS) if votes else None
                ),
                "criteria": {
                    "references_characteristic": _criterion_fraction(
                        rubrics, "references_characteristic"
                    ),
                    "gdor_plausible": _criterion_fraction(rubrics, "gdor_plausible"),
                    "stated_objectively": _criterion_fraction(rubrics, "stated_objectively"),
                },
            }
        )
    return {"samples": len(samples), "flags": per_flag}
