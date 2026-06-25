"""The five-stage engine wired as a LangGraph StateGraph over ``EngineState``.

The linear pipeline Dictionary -> Contextual -> Adjudicator -> Judge -> Recommendations:
the deterministic Modules are real nodes, the LLM Agents are injected and stubbed with
passthroughs until their own stages land. Each node returns a partial ``StateUpdate`` the
graph merges by channel and logs; the Adjudicator drops unverifiable flags and records why.
"""

from collections.abc import Callable

import structlog
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from sqlalchemy.orm import Session

from pattern_mirror.core.config import get_settings
from pattern_mirror.engine.adjudicator import adjudicate_flags
from pattern_mirror.engine.contextual_pass import (
    StructuredCompletionClient,
    estimate_cost_usd,
    run_contextual_pass,
    to_candidate_flags,
)
from pattern_mirror.engine.dictionary import (
    load_active_rules,
    load_category_citations,
    match_dictionary,
)
from pattern_mirror.engine.state import EngineState, StateUpdate, log_transition
from pattern_mirror.models.enums import AgentName
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

    The node calls the Agent, records the run (input/output/cost/latency), and appends the
    proposed flags to the candidate channel with contextual provenance. Spans are offset-less
    here; the Adjudicator resolves and verifies them downstream.
    """

    def node(state: EngineState) -> StateUpdate:
        run = run_contextual_pass(
            client,
            document_text=state["document_text"],
            doc_type=state["doc_type"],
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
        dropped = len(run.result.flags) - len(candidates)
        if dropped:
            # ADR 0006: a flag with no citation floor for its category is suppressed.
            _log.info(
                "engine.contextual_uncited_dropped",
                document_id=str(state["document_id"]),
                dropped=dropped,
            )
        update: StateUpdate = {"candidate_flags": candidates}
        log_transition("contextual", state["document_id"], update)
        return update

    return node


def build_engine_graph(
    *,
    dictionary_node: EngineNode,
    contextual_node: EngineNode,
    judge_node: EngineNode,
    recommendations_node: EngineNode,
) -> CompiledStateGraph[EngineState]:
    """Compile the five-stage graph from injected nodes; the Adjudicator is fixed.

    Every node is injectable except the Adjudicator, which is deterministic and owns the
    verbatim gate, so it is wired in directly. Tests pass fakes; production passes the real
    dictionary node and the stubbed LLM stages via ``build_default_graph``.
    """
    graph: StateGraph[EngineState] = StateGraph(EngineState)
    nodes: list[tuple[str, EngineNode]] = [
        ("dictionary", dictionary_node),
        ("contextual", contextual_node),
        ("adjudicator", _adjudicator_node),
        ("judge", judge_node),
        ("recommendations", recommendations_node),
    ]
    for name, node in nodes:
        # langgraph's overloaded add_node does not infer our EngineNode signature under --strict.
        graph.add_node(name, node)  # type: ignore[call-overload]
    graph.add_edge(START, "dictionary")
    graph.add_edge("dictionary", "contextual")
    graph.add_edge("contextual", "adjudicator")
    graph.add_edge("adjudicator", "judge")
    graph.add_edge("judge", "recommendations")
    graph.add_edge("recommendations", END)
    return graph.compile()


def build_default_graph(
    session: Session, *, contextual_client: StructuredCompletionClient | None = None
) -> CompiledStateGraph[EngineState]:
    """The production graph: real dictionary + adjudicator, the Contextual Pass when wired.

    ``contextual_client`` is injected rather than read from settings so the engine layer
    stays pure and tests stay deterministic: a caller passes the production client (built by
    ``contextual_pass.build_contextual_client``), a test passes a fake, and ``None`` degrades
    the contextual stage to a passthrough (dictionary-only). The Judge and Recommendations
    stages remain stubbed until #49/#50.
    """

    def dictionary_node(state: EngineState) -> StateUpdate:
        return _dictionary_node(state, session)

    if contextual_client is not None:
        contextual_node = _build_contextual_node(
            session, contextual_client, get_settings().analysis_model
        )
    else:
        contextual_node = _passthrough_node("contextual")

    return build_engine_graph(
        dictionary_node=dictionary_node,
        contextual_node=contextual_node,
        judge_node=_passthrough_node("judge"),
        recommendations_node=_passthrough_node("recommendations"),
    )
