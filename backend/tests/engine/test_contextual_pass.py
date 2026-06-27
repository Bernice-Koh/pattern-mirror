"""The Contextual Pass agent: schema-parsed output, provenance mapping, cost, client wiring.

The Anthropic call is replaced by a deterministic fake implementing the one method the agent
uses, so these run offline and never touch the live API (CONVENTIONS).
"""

import uuid
from typing import Any

from pattern_mirror.engine.contextual_pass import (
    ContextualFlag,
    ContextualPassResult,
    run_contextual_pass,
    to_candidate_flags,
)
from pattern_mirror.models.enums import BiasCategory, DocType, FlagScope, FlagSourceStage


class _FakeUsage:
    def __init__(self, input_tokens: int, output_tokens: int) -> None:
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens


class _FakeCompletion:
    def __init__(self, usage: _FakeUsage) -> None:
        self.usage = usage


class _FakeContextualClient:
    """Returns a fixed result + usage and records the call kwargs for assertions."""

    def __init__(
        self, result: ContextualPassResult, *, input_tokens: int = 120, output_tokens: int = 40
    ) -> None:
        self._result = result
        self._completion = _FakeCompletion(_FakeUsage(input_tokens, output_tokens))
        self.calls: list[dict[str, Any]] = []

    def create_with_completion(self, **kwargs: Any) -> tuple[Any, Any]:
        self.calls.append(kwargs)
        return self._result, self._completion


def _result(*flags: ContextualFlag) -> ContextualPassResult:
    return ContextualPassResult(flags=list(flags))


def test_run_contextual_pass_returns_parsed_result_and_usage() -> None:
    client = _FakeContextualClient(_result(), input_tokens=120, output_tokens=40)

    run = run_contextual_pass(
        client, document_text="We value a culture fit.", doc_type=DocType.jd, model="m"
    )

    assert run.result.flags == []
    assert run.prompt_tokens == 120
    assert run.completion_tokens == 40
    assert run.latency_ms >= 0


def test_run_contextual_pass_requests_the_schema_with_the_document() -> None:
    client = _FakeContextualClient(_result())

    run_contextual_pass(
        client, document_text="seeking a recent graduate", doc_type=DocType.jd, model="model-x"
    )

    call = client.calls[0]
    assert call["model"] == "model-x"
    assert call["response_model"] is ContextualPassResult
    assert "recent graduate" in call["messages"][0]["content"]
    assert "job description" in call["messages"][0]["content"]


def test_to_candidate_flags_carries_provenance_and_the_floor_citation() -> None:
    floor = uuid.uuid4()
    result = _result(
        ContextualFlag(
            raw_span="recent graduate",
            category=BiasCategory.age,
            scope=FlagScope.role_specific,
            explanation="Screens on career stage, a proxy for age.",
        )
    )

    candidates = to_candidate_flags(result, {BiasCategory.age: floor})

    assert len(candidates) == 1
    candidate = candidates[0]
    assert candidate.source_stage is FlagSourceStage.contextual
    assert candidate.raw_span == "recent graduate"
    assert candidate.scope is FlagScope.role_specific
    assert candidate.citation_id == floor  # the category-level TAFEP citation (ADR 0006)
    # Offsets and the lemma key are absent — the Adjudicator resolves the span later.
    assert candidate.start_offset is None
    assert candidate.lemma_key is None


def test_to_candidate_flags_drops_a_flag_with_no_floor_citation() -> None:
    # ADR 0006: a flag whose category has no citation floor is suppressed, not surfaced.
    result = _result(
        ContextualFlag(
            raw_span="recent graduate",
            category=BiasCategory.age,
            scope=FlagScope.role_specific,
            explanation="Screens on career stage.",
        )
    )

    assert to_candidate_flags(result, {BiasCategory.gender: uuid.uuid4()}) == []


def test_to_candidate_flags_on_clean_result_is_empty() -> None:
    assert to_candidate_flags(_result(), {}) == []
