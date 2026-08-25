"""
Compiles the graph nodes into a single runnable LangGraph StateGraph.

Owner: Dev C (Graph / Reasoning / Guardrails)

Graph shape:

    retrieve --[has usable context]--> reason -> confidence_gate ->
    route -> END
             -[no usable context]---> no_context -----------------^

"Usable context" means either at least one retrieved chunk, or — for
assignment guidance — an assignment brief. When neither is present, the
graph skips the LLM call entirely and routes straight to escalation via
`no_context`, rather than asking the model to answer from nothing.

Usage (by Dev D's service.py):

    from app.agent.graph.build import build_agent_graph
    from app.agent.graph.nodes import AgentDependencies

    deps = AgentDependencies(
        llm=real_llm_client,                              # Dev D
        search_curriculum=real_search_curriculum,           # Dev B
        search_faqs=real_search_faqs,                         # Dev B
        get_assignment_brief=real_get_assignment_brief,       # Dev B
        escalate_to_trainer=real_escalate_to_trainer,         # Dev B
    )
    graph = build_agent_graph(deps)
    result_state = graph.invoke(initial_state)  # initial_state: AgentState

Wiring tracing (Dev E):
    LangSmith/Langfuse tracing is added by wrapping the callables passed into
    AgentDependencies (e.g. an LLMClient whose .complete() is @traceable, or
    tool functions wrapped before being passed in) — this file and nodes.py
    don't need to change for that.
"""

from __future__ import annotations

from langgraph.graph import END, StateGraph

from app.agent.graph.nodes import (
    AgentDependencies,
    make_confidence_gate_node,
    make_no_context_node,
    make_reason_node,
    make_retrieval_error_node,
    make_retrieve_node,
    make_route_node,
)
from app.agent.graph.state import AgentState, QueryType

__all__ = ["AgentDependencies", "build_agent_graph"]


def _route_after_retrieve(state: AgentState) -> str:
    """Conditional-edge router: decides what `retrieve` found — a genuine
    infrastructure failure, nothing usable, or enough to reason over."""
    if state.get("retrieval_failed"):
        return "retrieval_error"

    has_chunks = bool(state.get("retrieved_chunks"))
    has_brief = (
        state.get("query_type") == QueryType.ASSIGNMENT_GUIDANCE
        and state.get("assignment_brief") is not None
    )
    return "reason" if (has_chunks or has_brief) else "no_context"


def build_agent_graph(deps: AgentDependencies):
    """
    Wires retrieve -> [reason -> confidence_gate | no_context] -> route into
    a compiled, invokable graph.

    `route` is a single node that internally branches on `is_confident`
    (rather than a further conditional edge to two separate terminal nodes)
    — both branches need the same inputs and produce the same output shape,
    so a plain if/else inside one node is simpler than a graph-level branch
    there, with no loss of clarity in the trace.
    """
    graph = StateGraph(AgentState)

    graph.add_node("retrieve", make_retrieve_node(deps))
    graph.add_node("reason", make_reason_node(deps))
    graph.add_node("confidence_gate", make_confidence_gate_node())
    graph.add_node("no_context", make_no_context_node())
    graph.add_node("retrieval_error", make_retrieval_error_node())
    graph.add_node("route", make_route_node(deps))

    graph.set_entry_point("retrieve")
    graph.add_conditional_edges(
        "retrieve",
        _route_after_retrieve,
        {
            "reason": "reason",
            "no_context": "no_context",
            "retrieval_error": "retrieval_error",
        },
    )
    graph.add_edge("reason", "confidence_gate")
    graph.add_edge("confidence_gate", "route")
    graph.add_edge("no_context", "route")
    graph.add_edge("retrieval_error", "route")
    graph.add_edge("route", END)

    return graph.compile()
