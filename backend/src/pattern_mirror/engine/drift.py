"""The drift check: an Agent (Claude Sonnet 4.6) that runs alongside the five-stage pipeline.

One schema-enforced Anthropic call (via Instructor) comparing the document under analysis
against a swappable reference corpus — JD criteria for interview feedback, historical peer
feedback for promotions. Architecturally one implementation, two corpora: only the reference
text is swapped. The agent names which reference criteria the writing did
and did not address, each addressed one backed by a verbatim quote from the document.

The LLM is a boundary: the response is parsed into a Pydantic schema before any finding is
built. Evidence a criterion is addressed must be copied verbatim from the source;
``to_drift_findings`` verifies it and blanks a quote that is not, so a fabricated quote never
reaches a manager — the same guarantee the Adjudicator gives bias spans.
"""

import time
from dataclasses import dataclass

from pydantic import BaseModel, Field

from pattern_mirror.engine.llm_agent import StructuredCompletionClient
from pattern_mirror.engine.state import DriftFinding
from pattern_mirror.models.enums import DocType

_MAX_TOKENS = 4096

_DOC_TYPE_LABELS: dict[DocType, str] = {
    DocType.jd: "job description",
    DocType.feedback: "interview feedback",
    DocType.promotion: "promotion write-up",
}

_SYSTEM_PROMPT = (
    "You check whether a piece of hiring or promotion writing addresses the criteria set out "
    "in a reference document. The reference is the source of truth for what the writing should "
    "cover — the criteria in a job description, or the themes in an employee's prior peer "
    "feedback.\n\n"
    "From the reference, identify each distinct criterion the writing is expected to address. "
    "For each one, decide whether the document addresses it and return:\n"
    "- criterion: the reference point, stated in a few words.\n"
    "- addressed: true if the document speaks to it, false if it is missing.\n"
    "- evidence: when addressed, the phrase from the DOCUMENT that addresses it, copied "
    "VERBATIM as an exact substring; empty when not addressed. Never quote the reference, and "
    "never paraphrase — a quote that is not an exact substring of the document is discarded.\n\n"
    "Judge only coverage against the reference; do not flag bias or rewrite anything. Do not "
    "invent criteria the reference does not contain."
)


class DriftCriterionFinding(BaseModel):
    """One reference criterion and whether the document addresses it, validated at the boundary."""

    criterion: str = Field(description="The reference criterion, stated in a few words.")
    addressed: bool = Field(
        description="True if the document addresses this criterion, false if it is missing."
    )
    evidence: str = Field(
        default="",
        description=(
            "When addressed, the phrase from the document that addresses it, copied verbatim; "
            "empty otherwise. Must be an exact substring of the document or it is discarded."
        ),
    )


class DriftResult(BaseModel):
    """The schema the model must fill: one finding per reference criterion."""

    findings: list[DriftCriterionFinding] = Field(default_factory=list)


@dataclass(frozen=True)
class DriftRun:
    """A completed drift call: its parsed result plus what the audit log needs."""

    result: DriftResult
    prompt_tokens: int | None
    completion_tokens: int | None
    latency_ms: int


def _user_prompt(document_text: str, doc_type: DocType, reference_text: str) -> str:
    label = _DOC_TYPE_LABELS[doc_type]
    return (
        f"Check whether the following {label} addresses the criteria in the reference.\n\n"
        f"--- REFERENCE ---\n{reference_text}\n\n"
        f"--- {label.upper()} ---\n{document_text}"
    )


def run_drift(
    client: StructuredCompletionClient,
    *,
    document_text: str,
    doc_type: DocType,
    reference_text: str,
    model: str,
) -> DriftRun:
    """Run the drift check over a document and reference corpus; return its findings + usage.

    Args:
        client: An Instructor-wrapped Anthropic client (or a test fake).
        document_text: The document under analysis.
        doc_type: The document's type, which sets the role context in the prompt.
        reference_text: The swappable reference corpus (JD criteria or peer feedback).
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
            {"role": "user", "content": _user_prompt(document_text, doc_type, reference_text)}
        ],
        response_model=DriftResult,
    )
    latency_ms = int((time.monotonic() - started) * 1000)
    result: DriftResult = parsed
    usage = getattr(completion, "usage", None)
    return DriftRun(
        result=result,
        prompt_tokens=getattr(usage, "input_tokens", None),
        completion_tokens=getattr(usage, "output_tokens", None),
        latency_ms=latency_ms,
    )


def to_drift_findings(result: DriftResult, document_text: str) -> list[DriftFinding]:
    """Map the model's findings to engine findings, verifying each addressed one's evidence.

    An addressed finding keeps its verdict; its evidence is carried with resolved offsets only
    when the quote is a verbatim substring of the document, and blanked otherwise so a
    fabricated quote never surfaces. Unaddressed findings carry no evidence.

    Args:
        result: The validated drift output.
        document_text: The exact document the evidence must be verbatim in.

    Returns:
        One ``DriftFinding`` per model finding, in order.
    """
    findings: list[DriftFinding] = []
    for finding in result.findings:
        evidence: str | None = None
        start: int | None = None
        end: int | None = None
        if finding.addressed and finding.evidence:
            position = document_text.find(finding.evidence)
            if position != -1:
                evidence = finding.evidence
                start = position
                end = position + len(finding.evidence)
        findings.append(
            DriftFinding(
                criterion=finding.criterion,
                addressed=finding.addressed,
                evidence=evidence,
                evidence_start=start,
                evidence_end=end,
            )
        )
    return findings
