"""Engine orchestration: stage order, channel merges, the Adjudicator gate, audit logs.

The pure tests inject fake stage nodes so the graph runs offline; the ``db``-marked test
drives the real default graph (dictionary node included) against the seeded SG lexicon.
"""

import uuid
from types import SimpleNamespace
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session
from structlog.testing import capture_logs

from pattern_mirror.core.config import Settings
from pattern_mirror.engine.adjudicator import RejectionReason
from pattern_mirror.engine.candidate_flag import CandidateFlag
from pattern_mirror.engine.judge import JudgeResult, JudgeVerdict
from pattern_mirror.engine.orchestrator import (
    EngineNode,
    _adjudicator_node,
    _build_judge_node,
    build_default_graph,
    build_engine_graph,
)
from pattern_mirror.engine.state import (
    EngineState,
    JudgeScore,
    StateUpdate,
    initial_state,
    log_transition,
)
from pattern_mirror.models.audit import AgentRun
from pattern_mirror.models.documents import AnalysisRun, Document
from pattern_mirror.models.enums import (
    AgentName,
    AnalysisTrigger,
    BiasCategory,
    DocType,
    FlagSourceStage,
)
from pattern_mirror.models.identity import User


def _flag(raw_span: str, *, stage: FlagSourceStage = FlagSourceStage.contextual) -> CandidateFlag:
    return CandidateFlag(
        source_stage=stage,
        category=BiasCategory.gender,
        raw_span=raw_span,
    )


def _fake_stage(stage: str, update: StateUpdate) -> EngineNode:
    """A node that logs its transition and returns a fixed update, like the real stages do."""

    def node(state: EngineState) -> StateUpdate:
        log_transition(stage, state["document_id"], update)
        return update

    return node


def _passthrough(stage: str) -> EngineNode:
    return _fake_stage(stage, {})


def _state(document_text: str) -> EngineState:
    return initial_state(
        analysis_run_id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        document_text=document_text,
        doc_type=DocType.jd,
        region_code="SG",
    )


def test_adjudicator_node_keeps_verbatim_flags_and_logs_rejections() -> None:
    state = _state("We want someone aggressive.")
    state["candidate_flags"] = [_flag("aggressive"), _flag("a culture fit")]

    with capture_logs() as logs:
        update = _adjudicator_node(state)

    assert [flag.raw_span for flag in update["verified_flags"]] == ["aggressive"]
    rejections = [log for log in logs if log["event"] == "engine.flag_rejected"]
    assert len(rejections) == 1
    assert rejections[0]["reason"] is RejectionReason.span_not_in_source
    assert rejections[0]["document_id"] == str(state["document_id"])


def test_graph_runs_every_stage_in_order() -> None:
    graph = build_engine_graph(
        dictionary_node=_passthrough("dictionary"),
        contextual_node=_passthrough("contextual"),
        judge_node=_passthrough("judge"),
        recommendations_node=_passthrough("recommendations"),
    )

    with capture_logs() as logs:
        graph.invoke(_state("Clean text."))

    stages = [log["stage"] for log in logs if log["event"] == "engine.transition"]
    assert stages == ["dictionary", "contextual", "adjudicator", "judge", "recommendations"]


def test_candidate_flags_accumulate_across_producing_stages() -> None:
    text = "We want someone aggressive with culture fit."
    graph = build_engine_graph(
        dictionary_node=_fake_stage(
            "dictionary",
            {"candidate_flags": [_flag("aggressive", stage=FlagSourceStage.dictionary)]},
        ),
        contextual_node=_fake_stage("contextual", {"candidate_flags": [_flag("culture fit")]}),
        judge_node=_passthrough("judge"),
        recommendations_node=_passthrough("recommendations"),
    )

    final = graph.invoke(_state(text))

    assert [flag.raw_span for flag in final["candidate_flags"]] == ["aggressive", "culture fit"]
    assert {flag.source_stage for flag in final["candidate_flags"]} == {
        FlagSourceStage.dictionary,
        FlagSourceStage.contextual,
    }


def test_judge_scores_flow_through_the_overwrite_channel() -> None:
    score = JudgeScore(flag=_flag("aggressive"), confidence=0.9)
    graph = build_engine_graph(
        dictionary_node=_fake_stage("dictionary", {"candidate_flags": [_flag("aggressive")]}),
        contextual_node=_passthrough("contextual"),
        judge_node=_fake_stage("judge", {"judge_scores": [score]}),
        recommendations_node=_passthrough("recommendations"),
    )

    final = graph.invoke(_state("We want someone aggressive."))

    assert final["judge_scores"] == [score]


def test_hallucinated_flag_is_dropped_before_the_judge() -> None:
    graph = build_engine_graph(
        dictionary_node=_passthrough("dictionary"),
        contextual_node=_fake_stage("contextual", {"candidate_flags": [_flag("a culture fit")]}),
        judge_node=_passthrough("judge"),
        recommendations_node=_passthrough("recommendations"),
    )

    with capture_logs() as logs:
        final = graph.invoke(_state("We value collaboration."))

    assert final["verified_flags"] == []
    rejections = [log for log in logs if log["event"] == "engine.flag_rejected"]
    assert rejections[0]["reason"] is RejectionReason.span_not_in_source


@pytest.mark.db
def test_default_graph_verifies_a_seeded_flag_end_to_end(db_session: Session) -> None:
    graph = build_default_graph(db_session)

    final = graph.invoke(_state("We want a digital native for this role."))

    assert "digital native" in [flag.raw_span for flag in final["verified_flags"]]
    # With no judge client the Judge passes every flag through ungated (confidence None).
    scores = final["judge_scores"]
    assert [score.flag.raw_span for score in scores] == ["digital native"]
    assert scores[0].confidence is None
    assert scores[0].suppressed is False


class _FakeJudgeClient:
    """Returns fixed verdicts and fixed usage; the Anthropic call is never made."""

    def __init__(self, result: JudgeResult) -> None:
        self._result = result
        self._completion = SimpleNamespace(usage=SimpleNamespace(input_tokens=80, output_tokens=20))

    def create_with_completion(self, **kwargs: Any) -> tuple[Any, Any]:
        return self._result, self._completion


def _settings(threshold: float = 0.7) -> Settings:
    return Settings(
        app_env="test",
        database_url="postgresql+psycopg://x:y@localhost/db",
        judge_confidence_threshold=threshold,
    )


@pytest.mark.db
def test_judge_node_scores_contextual_gates_below_threshold_and_passes_dictionary(
    db_session: Session,
) -> None:
    user = User(
        external_user_id=f"judge-{uuid.uuid4()}",
        legal_name="Judge Manager",
        email=f"{uuid.uuid4()}@example.test",
    )
    db_session.add(user)
    db_session.flush()
    document = Document(owner_id=user.id, doc_type=DocType.jd, content="text")
    db_session.add(document)
    db_session.flush()
    run = AnalysisRun(
        document_id=document.id, trigger=AnalysisTrigger.typing_pause, content_hash="0" * 64
    )
    db_session.add(run)
    db_session.flush()

    state = _state("text")
    state["document_id"] = document.id
    state["analysis_run_id"] = run.id
    state["verified_flags"] = [
        _flag("digital native", stage=FlagSourceStage.dictionary),
        _flag("culture fit"),
        _flag("recent graduate"),
    ]
    client = _FakeJudgeClient(
        JudgeResult(
            verdicts=[
                JudgeVerdict(confidence=0.9, reasoning="strong"),
                JudgeVerdict(confidence=0.4, reasoning="weak"),
            ]
        )
    )
    node = _build_judge_node(db_session, client, "claude-haiku-4-5", _settings(threshold=0.7))

    scores = node(state)["judge_scores"]

    assert [s.flag.raw_span for s in scores] == ["digital native", "culture fit", "recent graduate"]
    assert scores[0].confidence is None and scores[0].suppressed is False  # dictionary, ungated
    assert scores[1].confidence == 0.9 and scores[1].suppressed is False  # contextual, kept
    assert scores[2].confidence == 0.4 and scores[2].suppressed is True  # contextual, dropped

    agent_run = db_session.scalars(
        select(AgentRun).where(AgentRun.document_id == document.id)
    ).one()
    assert agent_run.agent_name is AgentName.judge
    assert agent_run.analysis_run_id == run.id
