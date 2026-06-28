"""Engine state channels: candidate flags accumulate, scores overwrite, transitions log.

Built in-memory and offline: the schema is a plain TypedDict the LangGraph runtime later
consumes via its Annotated channel reducers, so it is unit-testable without the graph.
"""

import uuid
from typing import get_type_hints

from structlog.testing import capture_logs

from pattern_mirror.engine.candidate_flag import CandidateFlag
from pattern_mirror.engine.state import (
    EngineState,
    StateUpdate,
    accumulate_candidate_flags,
    log_transition,
)
from pattern_mirror.models.enums import BiasCategory, FlagSourceStage


def _flag(raw_span: str, *, stage: FlagSourceStage = FlagSourceStage.dictionary) -> CandidateFlag:
    """A minimal candidate flag tagged with the stage that produced it."""
    return CandidateFlag(
        source_stage=stage,
        category=BiasCategory.gender,
        raw_span=raw_span,
    )


def test_accumulate_appends_preserving_order_and_provenance() -> None:
    dictionary = [_flag("aggressive", stage=FlagSourceStage.dictionary)]
    contextual = [_flag("culture fit", stage=FlagSourceStage.contextual)]

    merged = accumulate_candidate_flags(dictionary, contextual)

    assert [flag.raw_span for flag in merged] == ["aggressive", "culture fit"]
    assert [flag.source_stage for flag in merged] == [
        FlagSourceStage.dictionary,
        FlagSourceStage.contextual,
    ]


def test_accumulate_from_empty_is_the_new_flags() -> None:
    contextual = [_flag("culture fit", stage=FlagSourceStage.contextual)]

    assert accumulate_candidate_flags([], contextual) == contextual


def test_accumulate_does_not_mutate_its_inputs() -> None:
    existing = [_flag("aggressive")]

    accumulate_candidate_flags(existing, [_flag("culture fit")])

    assert [flag.raw_span for flag in existing] == ["aggressive"]


def test_candidate_flags_channel_accumulates_scores_channel_overwrites() -> None:
    hints = get_type_hints(EngineState, include_extras=True)

    assert accumulate_candidate_flags in hints["candidate_flags"].__metadata__
    assert not hasattr(hints["judge_scores"], "__metadata__")
    assert not hasattr(hints["dismissal_suppressed_flags"], "__metadata__")


def test_log_transition_records_document_id_and_the_delta() -> None:
    document_id = uuid.uuid4()
    update: StateUpdate = {"candidate_flags": [_flag("aggressive"), _flag("culture fit")]}

    with capture_logs() as logs:
        log_transition("dictionary", document_id, update)

    (entry,) = logs
    assert entry["event"] == "engine.transition"
    assert entry["stage"] == "dictionary"
    assert entry["document_id"] == str(document_id)
    assert entry["channels"] == ["candidate_flags"]
    assert entry["delta_sizes"] == {"candidate_flags": 2}


def test_log_transition_reports_each_changed_channel_size() -> None:
    update: StateUpdate = {"judge_scores": []}

    with capture_logs() as logs:
        log_transition("judge", uuid.uuid4(), update)

    (entry,) = logs
    assert entry["channels"] == ["judge_scores"]
    assert entry["delta_sizes"] == {"judge_scores": 0}
