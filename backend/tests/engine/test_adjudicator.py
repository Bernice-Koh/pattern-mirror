"""Stage-3 adjudication: verbatim span verification, offset resolution, rejection.

The fixture flags are built in-memory so the tests run offline, exactly as the
Sprint 2 Contextual Pass will hand them over: contextual flags arrive without offsets,
dictionary flags arrive with them.
"""

import uuid

from pattern_mirror.engine.adjudicator import (
    RejectionReason,
    adjudicate_flags,
)
from pattern_mirror.engine.candidate_flag import CandidateFlag
from pattern_mirror.models.enums import BiasCategory, FlagSourceStage, Severity


def _contextual_flag(
    raw_span: str,
    *,
    start_offset: int | None = None,
    end_offset: int | None = None,
) -> CandidateFlag:
    """A contextual flag as the LLM stage emits it: a quote, offsets optional."""
    return CandidateFlag(
        source_stage=FlagSourceStage.contextual,
        category=BiasCategory.gender,
        severity=Severity.medium,
        raw_span=raw_span,
        start_offset=start_offset,
        end_offset=end_offset,
        explanation="Synthetic contextual flag.",
    )


def test_hallucinated_span_is_dropped_with_its_reason() -> None:
    flag = _contextual_flag("a strong cultural fit")

    result = adjudicate_flags([flag], "We seek a collaborative team player.")

    assert result.verified == []
    assert len(result.rejected) == 1
    assert result.rejected[0].flag is flag
    assert result.rejected[0].reason is RejectionReason.span_not_in_source


def test_verbatim_span_passes_unchanged() -> None:
    text = "We want someone aggressive."
    flag = _contextual_flag("aggressive", start_offset=16, end_offset=26)
    assert text[16:26] == "aggressive"

    result = adjudicate_flags([flag], text)

    assert result.rejected == []
    assert result.verified == [flag]


def test_offsetless_span_gains_its_first_occurrence_offsets() -> None:
    text = "We want someone aggressive."
    flag = _contextual_flag("aggressive")

    verified = adjudicate_flags([flag], text).verified[0]

    assert verified.start_offset == 16
    assert verified.end_offset == 26
    assert text[verified.start_offset : verified.end_offset] == "aggressive"


def test_repeated_span_is_verified_at_its_claimed_offsets() -> None:
    text = "A bachelor seeks a bachelor."
    second = text.rfind("bachelor")
    flag = _contextual_flag("bachelor", start_offset=second, end_offset=second + len("bachelor"))

    result = adjudicate_flags([flag], text)

    assert result.verified == [flag]
    assert result.verified[0].start_offset == second


def test_claimed_offsets_not_bearing_the_span_are_rejected() -> None:
    text = "A bachelor seeks a bachelor."
    flag = _contextual_flag("bachelor", start_offset=0, end_offset=4)

    result = adjudicate_flags([flag], text)

    assert result.verified == []
    assert result.rejected[0].reason is RejectionReason.offset_mismatch


def test_verification_is_case_sensitive() -> None:
    flag = _contextual_flag("Aggressive")

    result = adjudicate_flags([flag], "We want someone aggressive.")

    assert result.verified == []
    assert result.rejected[0].reason is RejectionReason.span_not_in_source


def test_trailing_whitespace_difference_is_not_verbatim() -> None:
    flag = _contextual_flag("aggressive ")

    result = adjudicate_flags([flag], "He is aggressive.")

    assert result.verified == []
    assert result.rejected[0].reason is RejectionReason.span_not_in_source


def test_empty_span_cannot_be_verified() -> None:
    flag = _contextual_flag("")

    result = adjudicate_flags([flag], "Any text at all.")

    assert result.verified == []
    assert result.rejected[0].reason is RejectionReason.span_not_in_source


def test_survivors_and_rejections_are_partitioned() -> None:
    text = "We want someone aggressive and collaborative."
    real = _contextual_flag("aggressive")
    hallucinated = _contextual_flag("a culture fit")

    result = adjudicate_flags([real, hallucinated], text)

    assert [flag.raw_span for flag in result.verified] == ["aggressive"]
    assert [rejected.flag.raw_span for rejected in result.rejected] == ["a culture fit"]


def test_dictionary_flag_with_correct_offsets_survives_untouched() -> None:
    text = "We seek a digital native."
    flag = CandidateFlag(
        source_stage=FlagSourceStage.dictionary,
        category=BiasCategory.age,
        severity=Severity.medium,
        raw_span="digital native",
        start_offset=10,
        end_offset=24,
        citation_id=uuid.uuid4(),
        dictionary_entry_id=uuid.uuid4(),
        explanation="Synthetic dictionary flag.",
        lemma_key="digital native",
    )
    assert text[10:24] == "digital native"

    result = adjudicate_flags([flag], text)

    assert result.verified == [flag]


def test_no_flags_yields_empty_result() -> None:
    result = adjudicate_flags([], "Any text at all.")

    assert result.verified == []
    assert result.rejected == []
