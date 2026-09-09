"""
Integration glue between Dev B's shipped `app.agent.tools.AgentTools` and
Dev C's `AgentDependencies`.

Owner: Dev C (Graph / Reasoning / Guardrails)

`AgentTools.as_mapping()` returns tools keyed exactly as `AgentDependencies`
expects (search_curriculum, search_faqs, get_assignment_brief,
escalate_to_trainer), including the `trainer_id` keyword on
escalate_to_trainer — Dev C's AgentState/contracts.py use that same name,
so this is a direct splat with no per-keyword adapting required.

This module exists anyway, rather than having Dev D call
`AgentDependencies(llm=..., **tools.as_mapping())` inline, so there's one
place documenting the per-request construction requirement below, and one
place to add translation logic again if either side's naming ever drifts.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.agent.graph.nodes import AgentDependencies

if TYPE_CHECKING:
    from app.agent.tools import AgentTools


def build_dependencies_from_agent_tools(
    llm,
    agent_tools: AgentTools,
    *,
    max_history_turns: int = 6,
) -> AgentDependencies:
    """
    Builds `AgentDependencies` directly from Dev B's
    `AgentTools.for_learner(...)`.

    Usage (Dev D's service.py) — build both fresh per request, scoped to
    the *authenticated* user, matching Dev B's own guidance in
    `AgentTools.for_learner`'s docstring ("never share one graph across
    learners"):

        from app.agent.tools import AgentTools
        from app.agent.graph.build import build_agent_graph
        from app.agent.graph.integration import
        build_dependencies_from_agent_tools

        tools = AgentTools.for_learner(session, current_user.id)
        deps = build_dependencies_from_agent_tools(llm_client, tools)
        graph = build_agent_graph(deps)
        result = graph.invoke(initial_state)

    IMPORTANT — `initial_state["learner_id"]` must be the same id used to
    build `tools` above (i.e. the authenticated user's id, never a
    client-supplied value). Dev B's `escalate_to_trainer` validates this
    itself and raises `EscalationWriteError` on a mismatch (see their
    docstring) — that's a defence-in-depth check, not the primary one; the
    primary guarantee is Dev D's service layer never populating either
    value from anything other than the authenticated session.
    """
    mapping = agent_tools.as_mapping()
    return AgentDependencies(
        llm=llm,
        search_curriculum=mapping["search_curriculum"],
        search_faqs=mapping["search_faqs"],
        get_assignment_brief=mapping["get_assignment_brief"],
        escalate_to_trainer=mapping["escalate_to_trainer"],
        max_history_turns=max_history_turns,
    )
