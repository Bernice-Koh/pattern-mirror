"""The Contextual Pass agent: schema-parsed output, GDOR rulings, provenance mapping, wiring.

The Anthropic call is replaced by a deterministic fake implementing the one method the agent
uses, so these run offline and never touch the live API (CONVENTIONS).
"""

import uuid
from typing import Any

from pattern_mirror.engine.candidate_flag import CandidateFlag
from pattern_mirror.engine.contextual_pass import (
    ContextualFlag,
    ContextualPassResult,
    DictionaryFlagReview,
    run_contextual_pass,
    to_candidate_flags,
    to_dictionary_verdicts,
)
from pattern_mirror.models.enums import (
    BiasCategory,
    DocType,
    FlagScope,
    FlagSourceStage,
    FlagVerdict,
)


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


def _dictionary_flag(raw_span: str, category: BiasCategory, start: int) -> CandidateFlag:
    return CandidateFlag(
        source_stage=FlagSourceStage.dictionary,
        category=category,
        raw_span=raw_span,
        start_offset=start,
        end_offset=start + len(raw_span),
        dictionary_entry_id=uuid.uuid4(),
        lemma_key=raw_span.lower(),
    )


def test_run_contextual_pass_returns_parsed_result_and_usage() -> None:
    client = _FakeContextualClient(ContextualPassResult(), input_tokens=120, output_tokens=40)

    run = run_contextual_pass(
        client,
        document_text="We value a culture fit.",
        doc_type=DocType.jd,
        dictionary_flags=[],
        model="m",
    )

    assert run.result.new_flags == []
    assert run.prompt_tokens == 120
    assert run.completion_tokens == 40
    assert run.latency_ms >= 0


def test_run_contextual_pass_requests_the_schema_with_document_and_keyword_flags() -> None:
    client = _FakeContextualClient(ContextualPassResult())

    run_contextual_pass(
        client,
        document_text="We want a digital native.",
        doc_type=DocType.jd,
        dictionary_flags=[_dictionary_flag("digital native", BiasCategory.age, 10)],
        model="model-x",
    )

    call = client.calls[0]
    content = call["messages"][0]["content"]
    assert call["model"] == "model-x"
    assert call["response_model"] is ContextualPassResult
    assert "digital native" in content
    assert "job description" in content
    assert "[0]" in content  # the keyword flag is listed for in-context review


def test_to_candidate_flags_carries_provenance_verdict_and_the_floor_citation() -> None:
    floor = uuid.uuid4()
    result = ContextualPassResult(
        new_flags=[
            ContextualFlag(
                raw_span="recent graduate",
                category=BiasCategory.age,
                scope=FlagScope.role_specific,
                verdict=FlagVerdict.unacceptable,
                explanation="Screens on career stage, a proxy for age.",
            )
        ]
    )

    candidates = to_candidate_flags(result, {BiasCategory.age: floor})

    assert len(candidates) == 1
    candidate = candidates[0]
    assert candidate.source_stage is FlagSourceStage.contextual
    assert candidate.raw_span == "recent graduate"
    assert candidate.scope is FlagScope.role_specific
    assert candidate.verdict is FlagVerdict.unacceptable
    assert candidate.citation_id == floor  # the category-level TAFEP citation (ADR 0006)
    # Offsets and the lemma key are absent — the Adjudicator resolves the span later.
    assert candidate.start_offset is None
    assert candidate.lemma_key is None


def test_to_candidate_flags_drops_a_flag_with_no_floor_citation() -> None:
    # ADR 0006: a flag whose category has no citation floor is suppressed, not surfaced.
    result = ContextualPassResult(
        new_flags=[
            ContextualFlag(
                raw_span="recent graduate",
                category=BiasCategory.age,
                scope=FlagScope.role_specific,
                verdict=FlagVerdict.unacceptable,
                explanation="Screens on career stage.",
            )
        ]
    )

    assert to_candidate_flags(result, {BiasCategory.gender: uuid.uuid4()}) == []


def test_to_candidate_flags_on_clean_result_is_empty() -> None:
    assert to_candidate_flags(ContextualPassResult(), {}) == []


def test_to_dictionary_verdicts_maps_each_review_to_its_flag_span() -> None:
    flags = [
        _dictionary_flag("young", BiasCategory.age, 10),
        _dictionary_flag("mature", BiasCategory.age, 40),
    ]
    result = ContextualPassResult(
        dictionary_reviews=[
            DictionaryFlagReview(
                flag_id=0, verdict=FlagVerdict.unacceptable, reasoning="age proxy"
            ),
            DictionaryFlagReview(
                flag_id=1, verdict=FlagVerdict.acceptable, reasoning="describes the cheese"
            ),
        ]
    )

    verdicts = to_dictionary_verdicts(flags, result)

    assert [(v.start_offset, v.end_offset, v.verdict) for v in verdicts] == [
        (10, 15, FlagVerdict.unacceptable),
        (40, 46, FlagVerdict.acceptable),
    ]


def test_to_dictionary_verdicts_drops_an_out_of_range_flag_id() -> None:
    flags = [_dictionary_flag("young", BiasCategory.age, 10)]
    result = ContextualPassResult(
        dictionary_reviews=[
            DictionaryFlagReview(flag_id=5, verdict=FlagVerdict.unacceptable, reasoning="x")
        ]
    )

    assert to_dictionary_verdicts(flags, result) == []
