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

from pattern_mirror.engine.adjudicator import adjudicate_flags
from pattern_mirror.engine.dictionary import load_active_rules, match_dictionary
from pattern_mirror.engine.state import EngineState, StateUpdate, log_transition

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


def build_default_graph(session: Session) -> CompiledStateGraph[EngineState]:
    """The production graph: a real dictionary node, passthrough stubs for the LLM stages."""

    def dictionary_node(state: EngineState) -> StateUpdate:
        return _dictionary_node(state, session)

    return build_engine_graph(
        dictionary_node=dictionary_node,
        contextual_node=_passthrough_node("contextual"),
        judge_node=_passthrough_node("judge"),
        recommendations_node=_passthrough_node("recommendations"),
    )
