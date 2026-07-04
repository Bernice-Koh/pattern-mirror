"""The JD-criteria extractor: schema-parsed output over a fake Anthropic call.

The Anthropic call is replaced by a deterministic fake implementing the one method the agent
uses, so these run offline and never touch the live API (CONVENTIONS).
"""

from typing import Any

from pattern_mirror.engine.jd_criteria_extraction import (
    JdCriteriaDraftResult,
    JdCriterionDraft,
    run_jd_criteria_extraction,
)


class _FakeUsage:
    def __init__(self, input_tokens: int, output_tokens: int) -> None:
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens


class _FakeCompletion:
    def __init__(self, usage: _FakeUsage) -> None:
        self.usage = usage


class _FakeExtractionClient:
    """Returns a fixed result + usage and records the call kwargs for assertions."""

    def __init__(
        self,
        result: JdCriteriaDraftResult,
        *,
        input_tokens: int = 500,
        output_tokens: int = 90,
    ) -> None:
        self._result = result
        self._completion = _FakeCompletion(_FakeUsage(input_tokens, output_tokens))
        self.calls: list[dict[str, Any]] = []

    def create_with_completion(self, **kwargs: Any) -> tuple[Any, Any]:
        self.calls.append(kwargs)
        return self._result, self._completion


def _result(*texts: str) -> JdCriteriaDraftResult:
    return JdCriteriaDraftResult(criteria=[JdCriterionDraft(text=text) for text in texts])


def test_run_extraction_returns_parsed_result_and_usage() -> None:
    client = _FakeExtractionClient(
        _result("Five years of Python experience", "Stakeholder management"),
        input_tokens=500,
        output_tokens=90,
    )

    run = run_jd_criteria_extraction(client, jd_text="We are hiring a senior engineer.", model="m")

    assert [c.text for c in run.result.criteria] == [
        "Five years of Python experience",
        "Stakeholder management",
    ]
    assert run.prompt_tokens == 500
    assert run.completion_tokens == 90
    assert run.latency_ms >= 0


def test_run_extraction_requests_the_schema_with_the_jd_text() -> None:
    client = _FakeExtractionClient(_result())

    run_jd_criteria_extraction(client, jd_text="Must lead a platform team.", model="model-x")

    call = client.calls[0]
    assert call["model"] == "model-x"
    assert call["response_model"] is JdCriteriaDraftResult
    assert "Must lead a platform team." in call["messages"][0]["content"]
