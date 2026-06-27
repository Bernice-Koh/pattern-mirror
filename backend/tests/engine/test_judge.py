"""The Judge agent: schema-parsed output, count validation, and the calibrated gate.

The Anthropic call is replaced by a deterministic fake implementing the one method the agent
uses, so these run offline and never touch the live API (CONVENTIONS).
"""

from typing import Any

import pytest

from pattern_mirror.core.config import Settings
from pattern_mirror.core.errors import JudgeVerdictCountError
from pattern_mirror.engine.candidate_flag import CandidateFlag
from pattern_mirror.engine.judge import (
    JudgeResult,
    JudgeVerdict,
    run_judge,
    to_judge_scores,
)
from pattern_mirror.models.enums import BiasCategory, DocType, FlagSourceStage


class _FakeUsage:
    def __init__(self, input_tokens: int, output_tokens: int) -> None:
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens


class _FakeCompletion:
    def __init__(self, usage: _FakeUsage) -> None:
        self.usage = usage


class _FakeJudgeClient:
    """Returns a fixed result + usage and records the call kwargs for assertions."""

    def __init__(
        self, result: JudgeResult, *, input_tokens: int = 200, output_tokens: int = 30
    ) -> None:
        self._result = result
        self._completion = _FakeCompletion(_FakeUsage(input_tokens, output_tokens))
        self.calls: list[dict[str, Any]] = []

    def create_with_completion(self, **kwargs: Any) -> tuple[Any, Any]:
        self.calls.append(kwargs)
        return self._result, self._completion


def _flag(raw_span: str, category: BiasCategory = BiasCategory.gender) -> CandidateFlag:
    return CandidateFlag(
        source_stage=FlagSourceStage.contextual,
        category=category,
        raw_span=raw_span,
        explanation=f"why {raw_span}",
    )


def _result(*confidences: float) -> JudgeResult:
    return JudgeResult(verdicts=[JudgeVerdict(confidence=c, reasoning="r") for c in confidences])


def _settings(
    *, threshold: float = 0.7, overrides: dict[BiasCategory, float] | None = None
) -> Settings:
    return Settings(
        app_env="test",
        database_url="postgresql+psycopg://x:y@localhost/db",
        judge_confidence_threshold=threshold,
        judge_confidence_threshold_overrides=overrides or {},
    )


def test_run_judge_returns_parsed_result_and_usage() -> None:
    client = _FakeJudgeClient(_result(0.8), input_tokens=200, output_tokens=30)

    run = run_judge(client, flags=[_flag("a culture fit")], doc_type=DocType.jd, model="m")

    assert [v.confidence for v in run.result.verdicts] == [0.8]
    assert run.prompt_tokens == 200
    assert run.completion_tokens == 30
    assert run.latency_ms >= 0


def test_run_judge_requests_the_schema_with_each_flag() -> None:
    client = _FakeJudgeClient(_result(0.9, 0.4))

    run_judge(
        client,
        flags=[_flag("recent graduate", BiasCategory.age), _flag("culture fit")],
        doc_type=DocType.jd,
        model="model-x",
    )

    call = client.calls[0]
    assert call["model"] == "model-x"
    assert call["response_model"] is JudgeResult
    content = call["messages"][0]["content"]
    assert "recent graduate" in content
    assert "culture fit" in content
    assert "age" in content
    assert "job description" in content


def test_run_judge_raises_when_verdict_count_does_not_match() -> None:
    # The LLM is a boundary: a mismatched count is rejected, not silently truncated.
    client = _FakeJudgeClient(_result(0.9))

    with pytest.raises(JudgeVerdictCountError):
        run_judge(
            client,
            flags=[_flag("one"), _flag("two")],
            doc_type=DocType.jd,
            model="m",
        )


def test_to_judge_scores_suppresses_below_threshold_and_keeps_at_or_above() -> None:
    flags = [_flag("high"), _flag("boundary"), _flag("low")]
    result = _result(0.9, 0.7, 0.69)

    scores = to_judge_scores(flags, result, _settings(threshold=0.7))

    assert [s.confidence for s in scores] == [0.9, 0.7, 0.69]
    # >= is inclusive (ADR-0008): the boundary flag survives, only the lower one is suppressed.
    assert [s.suppressed for s in scores] == [False, False, True]


def test_to_judge_scores_applies_a_per_category_override() -> None:
    flags = [_flag("age claim", BiasCategory.age)]
    result = _result(0.55)

    surviving = to_judge_scores(flags, result, _settings(overrides={BiasCategory.age: 0.5}))
    suppressed = to_judge_scores(flags, result, _settings(threshold=0.7))

    assert surviving[0].suppressed is False
    assert suppressed[0].suppressed is True
