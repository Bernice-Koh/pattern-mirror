"""The drift agent: schema-parsed output, swappable corpus, verbatim evidence gate.

The Anthropic call is replaced by a deterministic fake implementing the one method the agent
uses, so these run offline and never touch the live API (CONVENTIONS).
"""

from typing import Any

from pattern_mirror.engine.drift import (
    DriftCriterionFinding,
    DriftResult,
    run_drift,
    to_drift_findings,
)
from pattern_mirror.models.enums import DocType


class _FakeUsage:
    def __init__(self, input_tokens: int, output_tokens: int) -> None:
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens


class _FakeCompletion:
    def __init__(self, usage: _FakeUsage) -> None:
        self.usage = usage


class _FakeDriftClient:
    """Returns a fixed result + usage and records the call kwargs for assertions."""

    def __init__(
        self, result: DriftResult, *, input_tokens: int = 400, output_tokens: int = 120
    ) -> None:
        self._result = result
        self._completion = _FakeCompletion(_FakeUsage(input_tokens, output_tokens))
        self.calls: list[dict[str, Any]] = []

    def create_with_completion(self, **kwargs: Any) -> tuple[Any, Any]:
        self.calls.append(kwargs)
        return self._result, self._completion


def _result(*findings: DriftCriterionFinding) -> DriftResult:
    return DriftResult(findings=list(findings))


def test_run_drift_returns_parsed_result_and_usage() -> None:
    client = _FakeDriftClient(
        _result(DriftCriterionFinding(criterion="stakeholder management", addressed=False)),
        input_tokens=400,
        output_tokens=120,
    )

    run = run_drift(
        client,
        document_text="The candidate writes clean code.",
        doc_type=DocType.feedback,
        reference_text="Must show stakeholder management.",
        model="m",
    )

    assert run.result.findings[0].criterion == "stakeholder management"
    assert run.prompt_tokens == 400
    assert run.completion_tokens == 120
    assert run.latency_ms >= 0


def test_run_drift_requests_the_schema_with_document_and_reference() -> None:
    client = _FakeDriftClient(_result())

    run_drift(
        client,
        document_text="Strong Python skills throughout.",
        doc_type=DocType.feedback,
        reference_text="Requires Python proficiency.",
        model="model-x",
    )

    call = client.calls[0]
    assert call["model"] == "model-x"
    assert call["response_model"] is DriftResult
    content = call["messages"][0]["content"]
    assert "Strong Python skills throughout." in content
    assert "Requires Python proficiency." in content
    assert "interview feedback" in content


def test_same_agent_serves_a_swapped_reference_corpus() -> None:
    # One implementation, two corpora: only the reference text changes (design spec §8).
    jd_client = _FakeDriftClient(_result())
    peer_client = _FakeDriftClient(_result())
    document = "Consistently delivered under pressure."

    run_drift(
        jd_client,
        document_text=document,
        doc_type=DocType.feedback,
        reference_text="JD: must handle pressure.",
        model="m",
    )
    run_drift(
        peer_client,
        document_text=document,
        doc_type=DocType.promotion,
        reference_text="Peer feedback: calm under pressure.",
        model="m",
    )

    assert jd_client.calls[0]["response_model"] is DriftResult
    assert peer_client.calls[0]["response_model"] is DriftResult
    assert "JD: must handle pressure." in jd_client.calls[0]["messages"][0]["content"]
    assert "Peer feedback: calm under pressure." in peer_client.calls[0]["messages"][0]["content"]


def test_to_drift_findings_carries_verbatim_evidence_with_offsets() -> None:
    document = "The candidate demonstrated strong leadership on the migration."
    result = _result(
        DriftCriterionFinding(
            criterion="leadership",
            addressed=True,
            evidence="demonstrated strong leadership",
        )
    )

    findings = to_drift_findings(result, document)

    assert findings[0].addressed is True
    assert findings[0].evidence == "demonstrated strong leadership"
    start, end = findings[0].evidence_start, findings[0].evidence_end
    assert start is not None and end is not None
    assert document[start:end] == "demonstrated strong leadership"


def test_to_drift_findings_blanks_a_non_verbatim_quote_but_keeps_the_verdict() -> None:
    # A fabricated quote never surfaces; the addressed verdict stands (blank-quote-keep-verdict).
    document = "The candidate led the migration."
    result = _result(
        DriftCriterionFinding(
            criterion="leadership",
            addressed=True,
            evidence="showed exceptional leadership",
        )
    )

    findings = to_drift_findings(result, document)

    assert findings[0].addressed is True
    assert findings[0].evidence is None
    assert findings[0].evidence_start is None
    assert findings[0].evidence_end is None


def test_to_drift_findings_leaves_an_unaddressed_criterion_without_evidence() -> None:
    result = _result(DriftCriterionFinding(criterion="mentoring", addressed=False))

    findings = to_drift_findings(result, "Unrelated document text.")

    assert findings[0].addressed is False
    assert findings[0].evidence is None
    assert findings[0].evidence_start is None
