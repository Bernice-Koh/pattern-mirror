"""The engine wired as a LangGraph StateGraph over ``EngineState``.

The linear pipeline is Dictionary -> Contextual -> Adjudicator -> Verdict -> Suppression ->
Judge -> Recommendations. The deterministic Modules (Dictionary, Adjudicator, Verdict,
Suppression) and the injected Agents (Contextual Pass, Judge, Recommendations) are real
nodes; an absent Agent client degrades its stage to a passthrough. Each node returns a
partial ``StateUpdate`` the graph merges by channel and logs; the Adjudicator drops
unverifiable flags, the Verdict node suppresses flags the Contextual Pass cleared, and the
Suppression Module drops flags an active dismissal already covers.
"""

from collections.abc import Callable

import structlog
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from sqlalchemy.orm import Session

from pattern_mirror.core.config import Settings, get_settings
from pattern_mirror.engine.adjudicator import adjudicate_flags
from pattern_mirror.engine.candidate_flag import CandidateFlag
from pattern_mirror.engine.citations import load_citation_evidence
from pattern_mirror.engine.contextual_pass import (
    run_contextual_pass,
    to_candidate_flags,
    to_dictionary_verdicts,
)
from pattern_mirror.engine.dictionary import (
    load_active_rules,
    load_category_citations,
    match_dictionary,
)
from pattern_mirror.engine.drift import run_drift, to_drift_findings
from pattern_mirror.engine.judge import aggregation_fields, run_judge, to_judge_scores
from pattern_mirror.engine.llm_agent import StructuredCompletionClient, estimate_cost_usd
from pattern_mirror.engine.recommendations import (
    run_recommendations,
    to_flag_recommendations,
)
from pattern_mirror.engine.state import EngineState, JudgeScore, StateUpdate, log_transition
from pattern_mirror.engine.suppression import (
    DismissalIndex,
    load_active_dismissals,
    partition_by_dismissal,
)
from pattern_mirror.engine.verdict import apply_verdicts
from pattern_mirror.models.enums import AgentName, FlagSourceStage
from pattern_mirror.services.agent_runs import record_agent_run

_log = structlog.get_logger("pattern_mirror.engine.orchestrator")

EngineNode = Callable[[EngineState], StateUpdate]


def _dictionary_node(state: EngineState, session: Session) -> StateUpdate:
    rules = load_active_rules(session, state["region_code"])
    flags = match_dictionary(state["document_text"], rules)
    update: StateUpdate = {"candidate_flags": flags}
    log_transition("dictionary", state["document_id"], update)
    return update


def _adjudicator_node(state: EngineState) -> StateUpdate:
    result = adjudicate_flags(state["candidate_flags"], state["document_text"])
    for rejected in result.rejected:
        _log.info(
            "engine.flag_rejected",
            document_id=str(state["document_id"]),
            reason=rejected.reason,
            raw_span=rejected.flag.raw_span,
            source_stage=rejected.flag.source_stage,
        )
    update: StateUpdate = {"verified_flags": result.verified}
    log_transition("adjudicator", state["document_id"], update)
    return update


def _verdict_node(state: EngineState) -> StateUpdate:
    """Apply the Contextual Pass's GDOR verdicts; suppress all but the unacceptable flags.

    Runs after the Adjudicator, so every span has resolved offsets to match a verdict against,
    and before the Judge, so cleared flags spend no scoring tokens. Survivors stay on
    ``verified_flags``; the suppressed flags route to their own channel to be persisted but not
    surfaced.
    """
    survivors, suppressed = apply_verdicts(state["verified_flags"], state["dictionary_verdicts"])
    for flag in suppressed:
        _log.info(
            "engine.flag_verdict_suppressed",
            document_id=str(state["document_id"]),
            raw_span=flag.raw_span,
            source_stage=flag.source_stage,
            verdict=flag.verdict,
        )
    update: StateUpdate = {
        "verified_flags": survivors,
        "verdict_suppressed_flags": suppressed,
    }
    log_transition("verdict", state["document_id"], update)
    return update


def _build_suppression_node(session: Session) -> EngineNode:
    """Build the suppression Module: drop dismissal-matched flags before the LLM stages.

    Runs after the Adjudicator, so every flag has resolved offsets, and before the Judge, so
    the Judge and Recommendations spend no tokens on a flag the manager already dismissed
    . Overwrites ``verified_flags`` with the survivors and routes the
    suppressed flags onto their own channel, to be persisted but not surfaced.
    """

    def node(state: EngineState) -> StateUpdate:
        index = DismissalIndex.from_dismissals(
            load_active_dismissals(session, state["document_id"])
        )
        survivors, suppressed = partition_by_dismissal(
            state["verified_flags"], content=state["document_text"], index=index
        )
        update: StateUpdate = {
            "verified_flags": survivors,
            "dismissal_suppressed_flags": suppressed,
        }
        log_transition("suppression", state["document_id"], update)
        return update

    return node


def _passthrough_node(stage: str) -> EngineNode:
    """A stub for an LLM stage not yet built: logs its transition, changes nothing."""

    def node(state: EngineState) -> StateUpdate:
        update: StateUpdate = {}
        log_transition(stage, state["document_id"], update)
        return update

    return node


def _build_contextual_node(
    session: Session, client: StructuredCompletionClient, model: str
) -> EngineNode:
    """Build the real Contextual Pass node: a Sonnet 4.6 Agent logged to ``agent_runs``.

    The node hands the Agent the dictionary flags raised so far, records the run
    (input/output/cost/latency), appends the Agent's new flags to the candidate channel with
    contextual provenance, and emits its rulings on the dictionary flags for the Verdict node.
    New spans are offset-less here; the Adjudicator resolves and verifies them downstream.
    """

    def node(state: EngineState) -> StateUpdate:
        dictionary_flags = [
            flag
            for flag in state["candidate_flags"]
            if flag.source_stage is FlagSourceStage.dictionary
        ]
        run = run_contextual_pass(
            client,
            document_text=state["document_text"],
            doc_type=state["doc_type"],
            dictionary_flags=dictionary_flags,
            model=model,
        )
        record_agent_run(
            session,
            agent_name=AgentName.contextual_pass,
            model=model,
            input={"doc_type": state["doc_type"].value, "document_text": state["document_text"]},
            output=run.result.model_dump(mode="json"),
            document_id=state["document_id"],
            analysis_run_id=state["analysis_run_id"],
            prompt_tokens=run.prompt_tokens,
            completion_tokens=run.completion_tokens,
            cost_usd=estimate_cost_usd(model, run.prompt_tokens, run.completion_tokens),
            latency_ms=run.latency_ms,
        )
        category_citations = load_category_citations(session, state["region_code"])
        candidates = to_candidate_flags(run.result, category_citations)
        dropped = len(run.result.new_flags) - len(candidates)
        if dropped:
            # ADR 0006: a flag with no citation floor for its category is suppressed.
            _log.info(
                "engine.contextual_uncited_dropped",
                document_id=str(state["document_id"]),
                dropped=dropped,
            )
        update: StateUpdate = {
            "candidate_flags": candidates,
            "dictionary_verdicts": to_dictionary_verdicts(dictionary_flags, run.result),
        }
        log_transition("contextual", state["document_id"], update)
        return update

    return node


def _ungated_judge_score(flag: CandidateFlag) -> JudgeScore:
    """A flag that bypasses the Judge — surfaced, unscored (deterministic, or no Agent wired)."""
    return JudgeScore(flag=flag, confidence=None, suppressed=False)


def _build_judge_node(
    session: Session,
    client: StructuredCompletionClient | None,
    model: str,
    settings: Settings,
) -> EngineNode:
    """Build the Judge node: a Haiku 4.5 Agent that confidence-scores the contextual flags.

    Dictionary flags are deterministic and pass ungated; contextual flags are scored and
    gated on the calibrated threshold, with below-threshold flags marked suppressed (logged,
    not surfaced, no recommendation — ADR-0007/0008). With no client the stage degrades to
    passing every flag ungated. Emits one ``JudgeScore`` per verified flag, in order, and
    logs the run.
    """

    def node(state: EngineState) -> StateUpdate:
        verified = state["verified_flags"]
        contextual = [f for f in verified if f.source_stage is FlagSourceStage.contextual]

        if client is not None and contextual:
            run = run_judge(
                client,
                flags=contextual,
                document_text=state["document_text"],
                doc_type=state["doc_type"],
                model=model,
                samples=settings.judge_samples,
            )
            record_agent_run(
                session,
                agent_name=AgentName.judge,
                model=model,
                input={
                    "doc_type": state["doc_type"].value,
                    "flags": [
                        {"category": f.category.value, "raw_span": f.raw_span} for f in contextual
                    ],
                },
                output=aggregation_fields(contextual, run.samples),
                document_id=state["document_id"],
                analysis_run_id=state["analysis_run_id"],
                prompt_tokens=run.prompt_tokens,
                completion_tokens=run.completion_tokens,
                cost_usd=estimate_cost_usd(model, run.prompt_tokens, run.completion_tokens),
                latency_ms=run.latency_ms,
            )
            contextual_scores = to_judge_scores(contextual, run.samples, settings)
        else:
            contextual_scores = [_ungated_judge_score(f) for f in contextual]

        # Re-thread the per-contextual scores back into verified order; dictionary flags ungated.
        contextual_iter = iter(contextual_scores)
        scores = [
            next(contextual_iter)
            if flag.source_stage is FlagSourceStage.contextual
            else _ungated_judge_score(flag)
            for flag in verified
        ]
        update: StateUpdate = {"judge_scores": scores}
        log_transition("judge", state["document_id"], update)
        return update

    return node


def _build_recommendations_node(
    session: Session, client: StructuredCompletionClient, model: str
) -> EngineNode:
    """Build the Recommendations node: a Sonnet 4.6 Agent that rewrites surfaced flags.

    It runs on the un-suppressed *contextual* flags only — the ones the Judge passed above
    threshold (design spec §7); dictionary flags bypass it (their stable rewrites are a curated
    concern, not the non-deterministic Agent). Each rationale is anchored to the flag's cited
    evidence, loaded here and passed by value. Recommendations are non-blocking: the flags are
    already persisted and surfaced, so a failed call degrades to no rewrites rather than failing
    the run (CONVENTIONS). Emits one ``FlagRecommendation`` per rewritten flag and logs the run.
    """

    def node(state: EngineState) -> StateUpdate:
        flags = [
            score.flag
            for score in state["judge_scores"]
            if score.flag.source_stage is FlagSourceStage.contextual and not score.suppressed
        ]
        if not flags:
            update: StateUpdate = {"recommendations": []}
            log_transition("recommendations", state["document_id"], update)
            return update

        evidence = load_citation_evidence(
            session, [flag.citation_id for flag in flags if flag.citation_id is not None]
        )
        try:
            run = run_recommendations(
                client,
                flags=flags,
                evidence=evidence,
                doc_type=state["doc_type"],
                model=model,
            )
        except Exception as exc:
            # Non-blocking: the flags already stand, so a rewrite failure must not fail the run.
            _log.warning(
                "engine.recommendations_failed",
                document_id=str(state["document_id"]),
                error=str(exc),
            )
            update = {"recommendations": []}
            log_transition("recommendations", state["document_id"], update)
            return update

        record_agent_run(
            session,
            agent_name=AgentName.recommendations,
            model=model,
            input={
                "doc_type": state["doc_type"].value,
                "flags": [
                    {"category": flag.category.value, "raw_span": flag.raw_span} for flag in flags
                ],
            },
            output=run.result.model_dump(mode="json"),
            document_id=state["document_id"],
            analysis_run_id=state["analysis_run_id"],
            prompt_tokens=run.prompt_tokens,
            completion_tokens=run.completion_tokens,
            cost_usd=estimate_cost_usd(model, run.prompt_tokens, run.completion_tokens),
            latency_ms=run.latency_ms,
        )
        update = {"recommendations": to_flag_recommendations(flags, run.result)}
        log_transition("recommendations", state["document_id"], update)
        return update

    return node


def _build_drift_node(
    session: Session, client: StructuredCompletionClient, model: str
) -> EngineNode:
    """Build the drift node: a Sonnet 4.6 Agent that checks the document against a reference.

    It compares the document against the run's ``drift_reference`` and emits which reference
    criteria the writing did and did not address. No-ops when no reference is present (the
    common JD path carries none). Non-blocking: the drift check is advisory and independent of
    the bias flags, so a failed call degrades to no findings rather than failing the run
    (CONVENTIONS). Emits ``drift_findings`` and logs the run.
    """

    def node(state: EngineState) -> StateUpdate:
        reference = state["drift_reference"]
        if reference is None:
            update: StateUpdate = {}
            log_transition("drift", state["document_id"], update)
            return update

        try:
            run = run_drift(
                client,
                document_text=state["document_text"],
                doc_type=state["doc_type"],
                reference_text=reference.reference_text,
                model=model,
            )
        except Exception as exc:
            # Non-blocking: drift is advisory, so a failure must not fail the bias run.
            _log.warning(
                "engine.drift_failed",
                document_id=str(state["document_id"]),
                error=str(exc),
            )
            update = {"drift_findings": []}
            log_transition("drift", state["document_id"], update)
            return update

        record_agent_run(
            session,
            agent_name=AgentName.drift,
            model=model,
            input={
                "doc_type": state["doc_type"].value,
                "document_text": state["document_text"],
                "reference_text": reference.reference_text,
            },
            output=run.result.model_dump(mode="json"),
            document_id=state["document_id"],
            analysis_run_id=state["analysis_run_id"],
            prompt_tokens=run.prompt_tokens,
            completion_tokens=run.completion_tokens,
            cost_usd=estimate_cost_usd(model, run.prompt_tokens, run.completion_tokens),
            latency_ms=run.latency_ms,
        )
        update = {"drift_findings": to_drift_findings(run.result, state["document_text"])}
        log_transition("drift", state["document_id"], update)
        return update

    return node


def build_engine_graph(
    *,
    dictionary_node: EngineNode,
    contextual_node: EngineNode,
    suppression_node: EngineNode,
    judge_node: EngineNode,
    recommendations_node: EngineNode,
    drift_node: EngineNode | None = None,
) -> CompiledStateGraph[EngineState]:
    """Compile the engine graph from injected nodes; the Adjudicator is fixed.

    Every node is injectable except the Adjudicator, which is deterministic and owns the
    verbatim gate, so it is wired in directly. Tests pass fakes; production passes the real
    dictionary and suppression nodes and the LLM stages via ``build_default_graph``. The drift
    node is optional: when given, it runs as an independent stage after the linear pipeline.
    """
    graph: StateGraph[EngineState] = StateGraph(EngineState)
    nodes: list[tuple[str, EngineNode]] = [
        ("dictionary", dictionary_node),
        ("contextual", contextual_node),
        ("adjudicator", _adjudicator_node),
        ("verdict", _verdict_node),
        ("suppression", suppression_node),
        ("judge", judge_node),
        ("recommendations", recommendations_node),
    ]
    for name, node in nodes:
        # langgraph's overloaded add_node does not infer our EngineNode signature under --strict.
        graph.add_node(name, node)  # type: ignore[call-overload]
    graph.add_edge(START, "dictionary")
    graph.add_edge("dictionary", "contextual")
    graph.add_edge("contextual", "adjudicator")
    graph.add_edge("adjudicator", "verdict")
    graph.add_edge("verdict", "suppression")
    graph.add_edge("suppression", "judge")
    graph.add_edge("judge", "recommendations")
    if drift_node is not None:
        # Drift is independent of the bias flags, but it shares the run's Session, which is not
        # safe for LangGraph's concurrent branch execution. So it runs as its own stage after the
        # pipeline rather than a parallel branch — still non-blocking, writing only
        # ``drift_findings``.
        graph.add_node("drift", drift_node)  # type: ignore[call-overload]
        graph.add_edge("recommendations", "drift")
        graph.add_edge("drift", END)
    else:
        graph.add_edge("recommendations", END)
    return graph.compile()


def build_default_graph(
    session: Session,
    *,
    contextual_client: StructuredCompletionClient | None = None,
    judge_client: StructuredCompletionClient | None = None,
    recommendations_client: StructuredCompletionClient | None = None,
    drift_client: StructuredCompletionClient | None = None,
) -> CompiledStateGraph[EngineState]:
    """The production graph: real dictionary + adjudicator, plus the Agent stages when wired.

    The Agent clients are injected rather than read from settings so the engine layer stays
    pure and tests stay deterministic: a caller passes the production client (built by
    ``llm_agent.build_instructor_client``), a test passes a fake, and ``None`` degrades that
    stage — the Contextual Pass to a passthrough (dictionary-only), the Judge to scoring
    nothing (every flag ungated), Recommendations to producing no rewrites. The Judge always
    runs because it is the persistence point for the streaming path. ``drift_client`` appends the
    independent drift stage; without it the graph is the linear bias pipeline, unchanged.
    """
    settings = get_settings()

    def dictionary_node(state: EngineState) -> StateUpdate:
        return _dictionary_node(state, session)

    if contextual_client is not None:
        contextual_node = _build_contextual_node(
            session, contextual_client, settings.analysis_model
        )
    else:
        contextual_node = _passthrough_node("contextual")

    suppression_node = _build_suppression_node(session)

    judge_node = _build_judge_node(session, judge_client, settings.judge_model, settings)

    if recommendations_client is not None:
        recommendations_node = _build_recommendations_node(
            session, recommendations_client, settings.analysis_model
        )
    else:
        recommendations_node = _passthrough_node("recommendations")

    drift_node = (
        _build_drift_node(session, drift_client, settings.analysis_model)
        if drift_client is not None
        else None
    )

    return build_engine_graph(
        dictionary_node=dictionary_node,
        contextual_node=contextual_node,
        suppression_node=suppression_node,
        judge_node=judge_node,
        recommendations_node=recommendations_node,
        drift_node=drift_node,
    )
