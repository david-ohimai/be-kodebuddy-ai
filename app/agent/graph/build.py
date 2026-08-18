"""
Compiles the four graph nodes into a single runnable LangGraph StateGraph.

Owner: Dev C (Graph / Reasoning / Guardrails)

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
    make_reason_node,
    make_retrieve_node,
    make_route_node,
)
from app.agent.graph.state import AgentState

__all__ = ["AgentDependencies", "build_agent_graph"]


def build_agent_graph(deps: AgentDependencies):
    """
    Wires retrieve -> reason -> confidence_gate -> route into a compiled,
    invokable graph.

    `route` is a single node that internally branches on `is_confident`
    (rather than a LangGraph conditional edge to two separate terminal
    nodes) — both branches need the same inputs and produce the same output
    shape, so a plain if/else inside one node is simpler than a graph-level
    branch, with no loss of clarity in the trace.
    """
    graph = StateGraph(AgentState)

    graph.add_node("retrieve", make_retrieve_node(deps))
    graph.add_node("reason", make_reason_node(deps))
    graph.add_node("confidence_gate", make_confidence_gate_node())
    graph.add_node("route", make_route_node(deps))

    graph.set_entry_point("retrieve")
    graph.add_edge("retrieve", "reason")
    graph.add_edge("reason", "confidence_gate")
    graph.add_edge("confidence_gate", "route")
    graph.add_edge("route", END)

    return graph.compile()
