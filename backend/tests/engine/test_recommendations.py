"""The Recommendations agent: schema-parsed output, count validation, flag pairing.

The Anthropic call is replaced by a deterministic fake implementing the one method the agent
uses, so these run offline and never touch the live API (CONVENTIONS).
"""

import uuid
from typing import Any

import pytest

from pattern_mirror.core.errors import RecommendationCountError
from pattern_mirror.engine.candidate_flag import CandidateFlag
from pattern_mirror.engine.recommendations import (
    Recommendation,
    RecommendationsResult,
    run_recommendations,
    to_flag_recommendations,
)
from pattern_mirror.models.enums import BiasCategory, DocType, FlagSourceStage


class _FakeUsage:
    def __init__(self, input_tokens: int, output_tokens: int) -> None:
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens


class _FakeCompletion:
    def __init__(self, usage: _FakeUsage) -> None:
        self.usage = usage


class _FakeRecommendationsClient:
    """Returns a fixed result + usage and records the call kwargs for assertions."""

    def __init__(
        self, result: RecommendationsResult, *, input_tokens: int = 300, output_tokens: int = 90
    ) -> None:
        self._result = result
        self._completion = _FakeCompletion(_FakeUsage(input_tokens, output_tokens))
        self.calls: list[dict[str, Any]] = []

    def create_with_completion(self, **kwargs: Any) -> tuple[Any, Any]:
        self.calls.append(kwargs)
        return self._result, self._completion


def _flag(
    raw_span: str,
    category: BiasCategory = BiasCategory.gender,
    citation_id: uuid.UUID | None = None,
) -> CandidateFlag:
    return CandidateFlag(
        source_stage=FlagSourceStage.contextual,
        category=category,
        raw_span=raw_span,
        citation_id=citation_id,
        explanation=f"why {raw_span}",
    )


def _result(*alternatives: list[str]) -> RecommendationsResult:
    return RecommendationsResult(
        recommendations=[Recommendation(rationale="r", alternatives=a) for a in alternatives]
    )


def test_run_recommendations_returns_parsed_result_and_usage() -> None:
    client = _FakeRecommendationsClient(
        _result(["direct", "assertive", "decisive"]), input_tokens=300, output_tokens=90
    )

    run = run_recommendations(
        client, flags=[_flag("aggressive")], evidence={}, doc_type=DocType.jd, model="m"
    )

    assert run.result.recommendations[0].alternatives == ["direct", "assertive", "decisive"]
    assert run.prompt_tokens == 300
    assert run.completion_tokens == 90
    assert run.latency_ms >= 0


def test_run_recommendations_requests_the_schema_with_each_flag_and_its_evidence() -> None:
    citation_id = uuid.uuid4()
    client = _FakeRecommendationsClient(_result(["x", "y"], ["p", "q"]))

    run_recommendations(
        client,
        flags=[
            _flag("aggressive", citation_id=citation_id),
            _flag("recent graduate", BiasCategory.age),
        ],
        evidence={citation_id: "TAFEP: gendered traits"},
        doc_type=DocType.jd,
        model="model-x",
    )

    call = client.calls[0]
    assert call["model"] == "model-x"
    assert call["response_model"] is RecommendationsResult
    content = call["messages"][0]["content"]
    assert "aggressive" in content
    assert "recent graduate" in content
    assert "TAFEP: gendered traits" in content
    assert "job description" in content


def test_run_recommendations_raises_when_set_count_does_not_match() -> None:
    # The LLM is a boundary: a mismatched count is rejected, not silently truncated.
    client = _FakeRecommendationsClient(_result(["only", "one set"]))

    with pytest.raises(RecommendationCountError):
        run_recommendations(
            client,
            flags=[_flag("one"), _flag("two")],
            evidence={},
            doc_type=DocType.jd,
            model="m",
        )


def test_to_flag_recommendations_pairs_each_flag_with_its_rewrites_in_order() -> None:
    flags = [_flag("aggressive"), _flag("culture fit")]
    result = _result(["direct", "assertive"], ["values our mission", "shares our goals"])

    recommendations = to_flag_recommendations(flags, result)

    assert [r.flag.raw_span for r in recommendations] == ["aggressive", "culture fit"]
    assert recommendations[0].alternatives == ["direct", "assertive"]
    assert recommendations[1].alternatives == ["values our mission", "shares our goals"]
