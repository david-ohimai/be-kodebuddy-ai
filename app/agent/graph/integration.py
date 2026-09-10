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
    mapping = agent_tools.as_mapping()
    return AgentDependencies(
        llm=llm,
        search_curriculum=mapping["search_curriculum"],
        search_faqs=mapping["search_faqs"],
        search_assignments=mapping["search_assignments"],
        get_assignment_brief=mapping["get_assignment_brief"],
        escalate_to_trainer=mapping["escalate_to_trainer"],
        max_history_turns=max_history_turns,
    )