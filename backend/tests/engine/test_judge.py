"""The Judge agent: context extraction, rubric samples, self-consistency, and the gate.

The Anthropic call is replaced by a deterministic fake implementing the one method the agent
uses, so these run offline and never touch the live API (CONVENTIONS).
"""

from typing import Any

from pattern_mirror.core.config import Settings
from pattern_mirror.engine.candidate_flag import CandidateFlag
from pattern_mirror.engine.judge import (
    JudgeRubric,
    JudgeSample,
    _sample_order,
    aggregation_fields,
    context_window,
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
    """Returns the next queued sample per call and records the call kwargs for assertions."""

    def __init__(
        self, samples: list[JudgeSample], *, input_tokens: int = 200, output_tokens: int = 30
    ) -> None:
        self._samples = samples
        self._completion = _FakeCompletion(_FakeUsage(input_tokens, output_tokens))
        self.calls: list[dict[str, Any]] = []

    def create_with_completion(self, **kwargs: Any) -> tuple[Any, Any]:
        sample = self._samples[len(self.calls)]
        self.calls.append(kwargs)
        return sample, self._completion


def _flag(
    raw_span: str,
    category: BiasCategory = BiasCategory.gender,
    *,
    start: int | None = None,
    end: int | None = None,
) -> CandidateFlag:
    return CandidateFlag(
        source_stage=FlagSourceStage.contextual,
        category=category,
        raw_span=raw_span,
        explanation=f"why {raw_span}",
        start_offset=start,
        end_offset=end,
    )


def _rubric(flag_id: int, *, biased: bool) -> JudgeRubric:
    """A rubric whose derived verdict is ``biased``: an unqualified characteristic reference."""
    return JudgeRubric(
        flag_id=flag_id,
        references_characteristic=biased,
        reference_style="coded" if biased else "none",
        gdor_plausible=False,
        stated_objectively=False,
        reasoning="r",
    )


def _sample(*rubrics: JudgeRubric) -> JudgeSample:
    return JudgeSample(rubrics=list(rubrics))


def _settings(
    *, threshold: float = 0.7, overrides: dict[BiasCategory, float] | None = None
) -> Settings:
    return Settings(
        app_env="test",
        database_url="postgresql+psycopg://x:y@localhost/db",
        judge_confidence_threshold=threshold,
        judge_confidence_threshold_overrides=overrides or {},
    )


def test_sample_order_is_a_reproducible_permutation_that_varies_by_seed() -> None:
    orders = [_sample_order(4, seed) for seed in range(3)]

    assert all(sorted(order) == [1, 2, 3, 4] for order in orders)  # each a full permutation
    assert _sample_order(4, 0) == _sample_order(4, 0)  # reproducible for a fixed seed
    assert len({tuple(order) for order in orders}) > 1  # order differs across seeds


def test_context_window_cuts_the_containing_sentence() -> None:
    text = "We work hard. We want a digital native here. Apply now."
    start = text.index("digital native")
    end = start + len("digital native")

    assert context_window(text, start, end) == "We want a digital native here."


def test_run_judge_draws_one_sample_per_requested_count() -> None:
    client = _FakeJudgeClient([_sample(_rubric(1, biased=True)) for _ in range(3)])

    run = run_judge(
        client,
        flags=[_flag("a culture fit")],
        document_text="We want a culture fit.",
        doc_type=DocType.jd,
        model="m",
        samples=3,
    )

    assert len(run.samples) == 3
    assert len(client.calls) == 3
    # Usage is summed across samples.
    assert run.prompt_tokens == 600
    assert run.completion_tokens == 90
    assert run.latency_ms >= 0


def test_run_judge_prompt_carries_context_and_withholds_the_explanation() -> None:
    text = "The team needs a recent graduate for this role."
    start = text.index("recent graduate")
    client = _FakeJudgeClient([_sample(_rubric(1, biased=True))])

    run_judge(
        client,
        flags=[_flag("recent graduate", BiasCategory.age, start=start, end=start + 15)],
        document_text=text,
        doc_type=DocType.jd,
        model="model-x",
        samples=1,
    )

    content = client.calls[0]["messages"][0]["content"]
    assert client.calls[0]["model"] == "model-x"
    assert client.calls[0]["response_model"] is JudgeSample
    assert "recent graduate" in content
    assert "The team needs a recent graduate for this role." in content
    assert "job description" in content
    # The generator's explanation must not leak into the Judge's evidence (ADR-0013).
    assert "why recent graduate" not in content


def test_shuffled_order_still_matches_verdicts_by_flag_id() -> None:
    flags = [_flag("high"), _flag("low")]
    # The sample answers flag 2 before flag 1; flag_id, not order, decides the mapping.
    sample = _sample(_rubric(2, biased=False), _rubric(1, biased=True))

    scores = to_judge_scores(flags, [sample], _settings())

    assert scores[0].confidence == 1.0 and scores[0].suppressed is False
    assert scores[1].confidence == 0.0 and scores[1].suppressed is True


def test_confidence_is_the_fraction_of_samples_deriving_bias() -> None:
    flags = [_flag("culture fit")]
    samples = [
        _sample(_rubric(1, biased=True)),
        _sample(_rubric(1, biased=True)),
        _sample(_rubric(1, biased=False)),
    ]

    scores = to_judge_scores(flags, samples, _settings(threshold=0.7))

    # 2 of 3 samples judged it biased.
    assert scores[0].confidence == 0.667
    assert scores[0].suppressed is True  # 0.667 < 0.7


def test_gate_boundary_is_inclusive_on_the_agreement_lattice() -> None:
    flags = [_flag("boundary")]
    samples = [_sample(_rubric(1, biased=b)) for b in (True, True, False)]

    # 2/3 == 0.667; a threshold at that value passes (>= is inclusive, ADR-0008).
    scores = to_judge_scores(flags, samples, _settings(threshold=0.667))

    assert scores[0].suppressed is False


def test_a_flag_no_sample_answered_passes_ungated() -> None:
    flags = [_flag("answered"), _flag("skipped")]
    samples = [_sample(_rubric(1, biased=True)), _sample(_rubric(1, biased=True))]

    scores = to_judge_scores(flags, samples, _settings())

    assert scores[0].confidence == 1.0 and scores[0].suppressed is False
    assert scores[1].confidence is None and scores[1].suppressed is False


def test_duplicate_flag_id_within_a_sample_counts_once() -> None:
    flags = [_flag("culture fit")]
    # One sample double-answers flag 1; only the first counts, so this is a single biased vote.
    samples = [_sample(_rubric(1, biased=True), _rubric(1, biased=False))]

    scores = to_judge_scores(flags, samples, _settings())

    assert scores[0].confidence == 1.0


def test_to_judge_scores_applies_a_per_category_override() -> None:
    flags = [_flag("age claim", BiasCategory.age)]
    # 1 of 3 biased => 0.333; below the default 0.7 but at/above a 0.3 age override.
    samples = [_sample(_rubric(1, biased=b)) for b in (True, False, False)]

    surviving = to_judge_scores(flags, samples, _settings(overrides={BiasCategory.age: 0.3}))
    suppressed = to_judge_scores(flags, samples, _settings(threshold=0.7))

    assert surviving[0].suppressed is False
    assert suppressed[0].suppressed is True


def test_aggregation_fields_report_votes_and_per_criterion_fractions() -> None:
    flags = [_flag("culture fit")]
    samples = [
        _sample(_rubric(1, biased=True)),
        _sample(_rubric(1, biased=True)),
        _sample(_rubric(1, biased=False)),
    ]

    fields = aggregation_fields(flags, samples)

    assert fields["samples"] == 3
    entry = fields["flags"][0]
    assert entry["flag_id"] == 1
    assert entry["votes"] == 3
    assert entry["confidence"] == 0.667
    # references_characteristic is True in the two biased rubrics, False in the third.
    assert entry["criteria"]["references_characteristic"] == 0.667
    assert entry["criteria"]["gdor_plausible"] == 0.0
