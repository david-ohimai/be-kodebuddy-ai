from __future__ import annotations

from dataclasses import replace
from typing import Callable, TypeVar

try:
    from langsmith import traceable as _traceable
except ImportError:
    def _traceable(*_args, **_kwargs):
        def decorator(fn):
            return fn
        return decorator

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

F = TypeVar("F", bound=Callable)


def _traced(name: str, run_type: str) -> Callable[[F], F]:
    return _traceable(name=name, run_type=run_type)


def traced_dependencies(deps: AgentDependencies) -> AgentDependencies:
    llm = deps.llm
    traced_llm_complete = _traced("agent.llm.complete", "llm")(llm.complete)

    class _TracedLLMClient:
        def complete(self, *, system: str, user: str) -> str:
            return traced_llm_complete(system=system, user=user)

    return replace(
        deps,
        llm=_TracedLLMClient(),
        search_curriculum=_traced(
            "agent.tool.search_curriculum", "retriever"
        )(deps.search_curriculum),
        search_faqs=_traced(
            "agent.tool.search_faqs", "retriever"
        )(deps.search_faqs),
        search_assignments=_traced(
            "agent.tool.search_assignments", "retriever"
        )(deps.search_assignments),
        get_assignment_brief=_traced(
            "agent.tool.get_assignment_brief", "tool"
        )(deps.get_assignment_brief),
        escalate_to_trainer=_traced(
            "agent.tool.escalate_to_trainer", "tool"
        )(deps.escalate_to_trainer),
    )


def _route_after_retrieve(state: AgentState) -> str:
    if state.get("retrieval_failed"):
        return "retrieval_error"

    has_chunks = bool(state.get("retrieved_chunks"))
    has_brief = (
        state.get("query_type") == QueryType.ASSIGNMENT_GUIDANCE
        and state.get("assignment_brief") is not None
    )
    return "reason" if (has_chunks or has_brief) else "no_context"


def build_traced_agent_graph(deps: AgentDependencies):
    traced_deps = traced_dependencies(deps)

    graph = StateGraph(AgentState)

    graph.add_node(
        "retrieve",
        _traced("agent.graph.retrieve", "chain")(
            make_retrieve_node(traced_deps)
        ),
    )
    graph.add_node(
        "reason",
        _traced("agent.graph.reason", "chain")(make_reason_node(traced_deps)),
    )
    graph.add_node(
        "confidence_gate",
        _traced("agent.graph.confidence_gate", "chain")(
            make_confidence_gate_node()
        ),
    )
    graph.add_node(
        "no_context",
        _traced("agent.graph.no_context", "chain")(make_no_context_node()),
    )
    graph.add_node(
        "retrieval_error",
        _traced("agent.graph.retrieval_error", "chain")(
            make_retrieval_error_node()
        ),
    )
    graph.add_node(
        "route",
        _traced("agent.graph.route", "chain")(make_route_node(traced_deps)),
    )

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


__all__ = ["traced_dependencies", "build_traced_agent_graph"]