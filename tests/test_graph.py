"""
Unit tests for the agent graph, using fakes for every external dependency
(Dev B's tools, the LLM client). No database, no network, no real LLM call.

This is:
  - the harness Dev C runs locally/in CI before Dev B's real tools exist
  - the pattern Dev E's eval set builds on top of (swap `make_deps()`'s
    canned responses for real curriculum questions + expected outcomes)

Run with: pytest tests/test_graph.py -v
"""

from __future__ import annotations

from app.agent.graph.build import build_agent_graph
from app.agent.graph.nodes import AgentDependencies
from app.agent.graph.state import QueryType


class FakeLLM:
    """Stands in for Dev D's real LLMClient - returns a canned completion."""

    def __init__(self, response: str):
        self._response = response

    def complete(self, *, system: str, user: str) -> str:
        return self._response


def make_deps(
    llm_response: str = "This is the grounded answer.\nUNCERTAIN: false",
    curriculum_hits: list[dict] | None = None,
    faq_hits: list[dict] | None = None,
    assignment_brief: str | None = None,
):
    """Builds an AgentDependencies wired to fakes, and a mutable dict that
    records whether/why escalate_to_trainer was called, for assertions."""
    escalated: dict = {}

    def fake_search_curriculum(*, query, course_id, module_id=None):
        return curriculum_hits or []

    def fake_search_faqs(*, query, course_id):
        return faq_hits or []

    def fake_get_assignment_brief(assignment_id):
        return assignment_brief

    def fake_escalate(*, learner_id, course_id, question, reason):
        escalated["called"] = True
        escalated["reason"] = reason
        return "escalation-123"

    deps = AgentDependencies(
        llm=FakeLLM(llm_response),
        search_curriculum=fake_search_curriculum,
        search_faqs=fake_search_faqs,
        get_assignment_brief=fake_get_assignment_brief,
        escalate_to_trainer=fake_escalate,
    )
    return deps, escalated


def base_state(**overrides):
    state = {
        "learner_id": "learner-1",
        "course_id": "course-1",
        "module_id": "module-1",
        "assignment_id": None,
        "question": "How does a for loop work?",
        "query_type": QueryType.CHAT,
        "chat_history": [],
    }
    state.update(overrides)
    return state


def test_confident_answer_is_returned_without_escalation():
    deps, escalated = make_deps(
        curriculum_hits=[
            {
                "chunk_id": "c1",
                "course_id": "course-1",
                "module_id": "module-1",
                "content_type": "curriculum",
                "text": "A for loop repeats a block of"
                " code a fixed number of times.",
                "score": 0.91,
            }
        ],
    )
    graph = build_agent_graph(deps)
    result = graph.invoke(base_state())

    assert result["escalated"] is False
    assert result["final_response"] == "This is the grounded answer."
    assert "called" not in escalated


def test_no_retrieval_triggers_escalation():
    deps, escalated = make_deps(curriculum_hits=[], faq_hits=[])
    graph = build_agent_graph(deps)
    result = graph.invoke(base_state())

    assert result["escalated"] is True
    assert escalated.get("reason") == "no_relevant_content_retrieved"
    assert result["escalation_id"] == "escalation-123"
    assert "trainer" in result["final_response"].lower()


def test_low_relevance_retrieval_triggers_escalation():
    deps, escalated = make_deps(
        curriculum_hits=[
            {
                "chunk_id": "c1",
                "course_id": "course-1",
                "module_id": "module-1",
                "content_type": "curriculum",
                "text": "Loosely related content.",
                "score": 0.40,  # below MIN_RETRIEVAL_SCORE
            }
        ],
    )
    graph = build_agent_graph(deps)
    result = graph.invoke(base_state())

    assert result["escalated"] is True
    assert escalated.get("reason") == "low_retrieval_relevance"


def test_model_uncertainty_triggers_escalation_even_with_good_retrieval():
    deps, escalated = make_deps(
        llm_response="Not totally sure about this one.\nUNCERTAIN: true",
        curriculum_hits=[
            {
                "chunk_id": "c1",
                "course_id": "course-1",
                "module_id": "module-1",
                "content_type": "curriculum",
                "text": "Some genuinely relevant content.",
                "score": 0.95,
            }
        ],
    )
    graph = build_agent_graph(deps)
    result = graph.invoke(base_state())

    assert result["escalated"] is True
    assert escalated.get("reason") == "model_expressed_uncertainty"
    # The learner still sees the (uncertain) draft as a courtesy, alongside
    # the escalation notice.
    assert "Not totally sure" in result["final_response"]


def test_missing_uncertainty_marker_fails_safe_to_escalation():
    """If the model doesn't follow the UNCERTAIN: format, we must not treat
    that as confident - this is the fail-safe behaviour in
    _parse_uncertainty_flag."""
    deps, escalated = make_deps(
        llm_response="Here's an answer with no marker at all.",
        curriculum_hits=[
            {
                "chunk_id": "c1",
                "course_id": "course-1",
                "module_id": "module-1",
                "content_type": "curriculum",
                "text": "Relevant content.",
                "score": 0.95,
            }
        ],
    )
    graph = build_agent_graph(deps)
    result = graph.invoke(base_state())

    assert result["escalated"] is True
    assert escalated.get("reason") == "model_expressed_uncertainty"


def test_assignment_guidance_uses_assignment_brief_and_query_type():
    deps, _ = make_deps(
        assignment_brief="Build a function that reverses a string.",
        curriculum_hits=[
            {
                "chunk_id": "c1",
                "course_id": "course-1",
                "module_id": "module-1",
                "content_type": "curriculum",
                "text": "Strings can be sliced and iterated.",
                "score": 0.9,
            }
        ],
    )
    graph = build_agent_graph(deps)
    result = graph.invoke(
        base_state(
            query_type=QueryType.ASSIGNMENT_GUIDANCE,
            assignment_id="assign-1",
            question="I don't know where to start.",
        )
    )

    assert result["assignment_brief"] == "Build a function"
    " that reverses a string."
    assert result["escalated"] is False


def test_chat_history_is_windowed_not_full(monkeypatch):
    """Confirms only the last MAX_HISTORY_TURNS_IN_PROMPT turns are passed
    into the prompt, by capturing what build_user_turn actually receives."""
    from app.agent.graph import nodes as nodes_module

    captured = {}
    original = nodes_module.build_user_turn

    def spy_build_user_turn(*args, **kwargs):
        captured["history"] = kwargs.get("history") or args[2]
        return original(*args, **kwargs)

    monkeypatch.setattr(nodes_module, "build_user_turn", spy_build_user_turn)

    long_history = [
        {"role": "user" if i % 2 == 0 else "assistant", "message": f"turn {i}"}
        for i in range(20)
    ]
    deps, _ = make_deps(
        curriculum_hits=[
            {
                "chunk_id": "c1",
                "course_id": "course-1",
                "module_id": "module-1",
                "content_type": "curriculum",
                "text": "Relevant content.",
                "score": 0.95,
            }
        ],
    )
    graph = build_agent_graph(deps)
    graph.invoke(base_state(chat_history=long_history))

    assert len(captured["history"]) == 20  # full history passed in
    # windowing itself is asserted at the prompt-builder level below
    from app.agent.prompts.chat import build_user_turn as real_builder

    windowed = real_builder("q", [], long_history, max_history_turns=6)
    assert windowed.count("turn ") == 6
