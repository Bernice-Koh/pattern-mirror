"""The Verdict Module: attach Contextual Pass rulings and split survivors from the suppressed.

Pure functions over plain value objects, so these run offline with no graph and no DB.
"""

from pattern_mirror.engine.candidate_flag import CandidateFlag
from pattern_mirror.engine.state import DictionaryVerdict
from pattern_mirror.engine.verdict import apply_verdicts
from pattern_mirror.models.enums import BiasCategory, FlagSourceStage, FlagVerdict


def _dictionary_flag(raw_span: str, start: int) -> CandidateFlag:
    return CandidateFlag(
        source_stage=FlagSourceStage.dictionary,
        category=BiasCategory.age,
        raw_span=raw_span,
        start_offset=start,
        end_offset=start + len(raw_span),
        explanation="dictionary rationale",
    )


def _contextual_flag(raw_span: str, start: int, verdict: FlagVerdict) -> CandidateFlag:
    return CandidateFlag(
        source_stage=FlagSourceStage.contextual,
        category=BiasCategory.race,
        raw_span=raw_span,
        start_offset=start,
        end_offset=start + len(raw_span),
        verdict=verdict,
        explanation="contextual rationale",
    )


def _verdict(flag: CandidateFlag, verdict: FlagVerdict, reasoning: str) -> DictionaryVerdict:
    assert flag.start_offset is not None and flag.end_offset is not None
    return DictionaryVerdict(
        start_offset=flag.start_offset,
        end_offset=flag.end_offset,
        verdict=verdict,
        reasoning=reasoning,
    )


def test_unacceptable_dictionary_flag_survives_with_its_verdict_attached() -> None:
    flag = _dictionary_flag("young", 10)
    verdicts = [_verdict(flag, FlagVerdict.unacceptable, "age proxy")]

    survivors, suppressed = apply_verdicts([flag], verdicts)

    assert suppressed == []
    assert survivors[0].verdict is FlagVerdict.unacceptable
    assert survivors[0].explanation == "dictionary rationale"  # survivor keeps its TAFEP rationale


def test_acceptable_dictionary_flag_is_suppressed_carrying_the_reasoning() -> None:
    flag = _dictionary_flag("mature", 10)
    verdicts = [_verdict(flag, FlagVerdict.acceptable, "describes the cheese, not a person")]

    survivors, suppressed = apply_verdicts([flag], verdicts)

    assert survivors == []
    assert suppressed[0].verdict is FlagVerdict.acceptable
    assert suppressed[0].explanation == "describes the cheese, not a person"


def test_acceptable_with_justification_dictionary_flag_is_suppressed() -> None:
    flag = _dictionary_flag("seasoned", 10)
    verdicts = [_verdict(flag, FlagVerdict.acceptable_with_justification, "tied to outcomes")]

    survivors, suppressed = apply_verdicts([flag], verdicts)

    assert survivors == []
    assert suppressed[0].verdict is FlagVerdict.acceptable_with_justification


def test_unreviewed_dictionary_flag_surfaces_with_no_verdict() -> None:
    flag = _dictionary_flag("young", 10)

    survivors, suppressed = apply_verdicts([flag], [])

    assert suppressed == []
    assert survivors == [flag]
    assert survivors[0].verdict is None


def test_contextual_flag_keeps_its_own_verdict_and_is_partitioned_by_it() -> None:
    surfaced = _contextual_flag("culture fit", 10, FlagVerdict.unacceptable)
    cleared = _contextual_flag("steady judgment", 40, FlagVerdict.acceptable_with_justification)

    survivors, suppressed = apply_verdicts([surfaced, cleared], [])

    assert survivors == [surfaced]
    assert suppressed == [cleared]


def test_verdict_matches_by_span_so_an_unrelated_flag_is_untouched() -> None:
    flagged = _dictionary_flag("young", 10)
    other = _dictionary_flag("digital native", 40)
    verdicts = [_verdict(flagged, FlagVerdict.acceptable, "false positive")]

    survivors, suppressed = apply_verdicts([flagged, other], verdicts)

    assert [flag.raw_span for flag in survivors] == ["digital native"]
    assert [flag.raw_span for flag in suppressed] == ["young"]
