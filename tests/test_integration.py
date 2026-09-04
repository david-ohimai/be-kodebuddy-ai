"""
Tests for the Dev B <-> Dev C integration seam (graph/integration.py) and
for how the graph handles Dev B's AgentRetrievalError contract.

Uses fakes shaped like Dev B's *real* shipped code (real AgentRetrievalError
subclasses, an as_mapping() shaped exactly like their factory's output)
rather than reusing test_graph.py's own fakes, so this file actually proves
the two sides fit together instead of just re-testing our own protocol.
"""

from __future__ import annotations

import json

from app.agent.graph.build import build_agent_graph
from app.agent.graph.integration import build_dependencies_from_agent_tools
from app.agent.graph.state import EscalationReason, QueryType
from app.agent.types import (
    ContentStoreUnavailableError,
    EmbeddingUnavailableError,
)


def json_response(answer: str, uncertain: bool) -> str:
    return json.dumps({"answer": answer, "uncertain": uncertain})


class FakeLLM:
    def __init__(self, response: str):
        self._response = response

    def complete(self, *, system: str, user: str) -> str:
        return self._response


class ExplodingLLM:
    def complete(self, *, system: str, user: str) -> str:
        raise AssertionError("LLM should not have been called on this path")


def base_state(**overrides):
    state = {
        "learner_id": 1,
        "course_id": 101,
        "module_id": 1001,
        "assignment_id": None,
        "trainer_id": 55,
        "question": "How does a for loop work?",
        "query_type": QueryType.CHAT,
        "chat_history": [],
    }
    state.update(overrides)
    return state


def good_chunk(**overrides):
    chunk = {
        "chunk_id": "c1",
        "course_id": 101,
        "module_id": 1001,
        "content_type": "curriculum",
        "text": "A for loop repeats a block of code once for each item.",
        "score": 0.91,
    }
    chunk.update(overrides)
    return chunk


# --------------------------------------------------------------------------
# build_dependencies_from_agent_tools: full wiring, using a fake AgentTools
# whose as_mapping() mirrors Dev B's real factory output exactly (including
# the escalate_to_trainer keyword being `trainer_id`, matching both sides).
# --------------------------------------------------------------------------
class FakeAgentTools:
    """Stands in for Dev B's real AgentTools — same as_mapping() shape."""

    def __init__(
        self,
        curriculum_hits=None,
        faq_hits=None,
        assignment_brief=None,
    ):
        self._curriculum_hits = curriculum_hits or []
        self._faq_hits = faq_hits or []
        self._assignment_brief = assignment_brief
        self.escalated = {}

    def _search_curriculum(self, *, query, course_id, module_id=None):
        return self._curriculum_hits

    def _search_faqs(self, *, query, course_id=None):
        return self._faq_hits

    def _get_assignment_brief(self, assignment_id):
        return self._assignment_brief

    def _escalate_to_trainer(
        self,
        *,
        learner_id,
        course_id,
        trainer_id,
        question,
        reason,
        detail=None,
    ):
        self.escalated["called"] = True
        self.escalated["trainer_id"] = trainer_id
        self.escalated["reason"] = reason
        return 777

    def as_mapping(self):
        return {
            "search_curriculum": self._search_curriculum,
            "search_faqs": self._search_faqs,
            "get_assignment_brief": self._get_assignment_brief,
            "escalate_to_trainer": self._escalate_to_trainer,
        }


def test_build_dependencies_from_agent_tools_is_a_direct_splat():
    """No adapter needed since both sides agree on `trainer_id` — this just
    confirms as_mapping()'s four keys line up with AgentDependencies without
    any translation layer in between.

    Compares `__func__` rather than the bound methods themselves:
    `as_mapping()` returns a fresh bound-method object on every call, so two
    separate calls to it are never `is`-identical even when they wrap the
    exact same underlying tool — comparing the underlying function avoids
    that false negative."""
    tools = FakeAgentTools()
    mapping = tools.as_mapping()
    deps = build_dependencies_from_agent_tools(FakeLLM(""), tools)

    assert (
        deps.search_curriculum.__func__
        is mapping["search_curriculum"].__func__
    )
    assert (
        deps.search_faqs.__func__
        is mapping["search_faqs"].__func__
    )
    assert (
        deps.get_assignment_brief.__func__
        is mapping["get_assignment_brief"].__func__
    )
    assert (
        deps.escalate_to_trainer.__func__
        is mapping["escalate_to_trainer"].__func__
    )


def test_build_dependencies_from_agent_tools_runs_the_full_graph():
    tools = FakeAgentTools(curriculum_hits=[good_chunk()])
    deps = build_dependencies_from_agent_tools(
        FakeLLM(json_response("Grounded answer.", False)), tools
    )
    graph = build_agent_graph(deps)
    result = graph.invoke(base_state())

    assert result["escalated"] is False
    assert result["final_response"] == "Grounded answer."


def test_escalation_reaches_dev_b_shaped_tool():
    tools = FakeAgentTools(curriculum_hits=[])
    deps = build_dependencies_from_agent_tools(ExplodingLLM(), tools)
    graph = build_agent_graph(deps)
    result = graph.invoke(base_state(trainer_id=77))

    assert result["escalated"] is True
    assert (
        tools.escalated["trainer_id"] == 77
    )  # arrived correctly on Dev B's side
    assert result["escalation_id"] == 777


# --------------------------------------------------------------------------
# Retrieval-failure handling (AgentRetrievalError), using the real exception
# classes from app.agent.types.
# --------------------------------------------------------------------------
def test_embedding_unavailable_routes_to_retrieval_error_and_skips_llm():
    def raising_search_curriculum(*, query, course_id, module_id=None):
        raise EmbeddingUnavailableError("embedding provider timed out")

    tools = FakeAgentTools()
    tools._search_curriculum = raising_search_curriculum

    deps = build_dependencies_from_agent_tools(ExplodingLLM(), tools)
    graph = build_agent_graph(deps)
    result = graph.invoke(base_state())

    assert result["escalated"] is True
    assert (
        result["escalation_reason"] == EscalationReason.RETRIEVAL_UNAVAILABLE
    )
    assert tools.escalated["reason"] == EscalationReason.RETRIEVAL_UNAVAILABLE


def test_content_store_unavailable_also_routes_to_retrieval_error():
    def raising_search_faqs(*, query, course_id=None):
        raise ContentStoreUnavailableError("content_embeddings table missing")

    tools = FakeAgentTools(curriculum_hits=[good_chunk()])
    tools._search_faqs = raising_search_faqs

    deps = build_dependencies_from_agent_tools(ExplodingLLM(), tools)
    graph = build_agent_graph(deps)
    result = graph.invoke(base_state())

    assert result["escalated"] is True
    assert (
        result["escalation_reason"] == EscalationReason.RETRIEVAL_UNAVAILABLE
    )


def test_retrieval_failure_takes_priority_over_a_usable_assignment_brief():
    """A brief alone would normally be enough to reach `reason` (see
    test_graph.py's brief-but-no-chunks test) — but if retrieval itself
    failed, that must still short-circuit to retrieval_error, not silently
    reason from the brief as if nothing were wrong."""

    def raising_search_curriculum(*, query, course_id, module_id=None):
        raise EmbeddingUnavailableError("down")

    tools = FakeAgentTools(
        assignment_brief={
            "title": "Reverse a string",
            "description": "Build a function that reverses a string.",
            "due_date": None,
            "maximum_score": None,
        }
    )
    tools._search_curriculum = raising_search_curriculum

    deps = build_dependencies_from_agent_tools(ExplodingLLM(), tools)
    graph = build_agent_graph(deps)
    result = graph.invoke(
        base_state(query_type=QueryType.ASSIGNMENT_GUIDANCE, assignment_id=42)
    )

    assert result["escalated"] is True
    assert (
        result["escalation_reason"] == EscalationReason.RETRIEVAL_UNAVAILABLE
    )
    # The brief must not have been carried through as if retrieval succeeded.
    assert result.get("assignment_brief") is None


def test_no_retrieval_failure_is_distinguishable_from_no_relevant_content():
    """Confirms the two failure modes produce different, queryable
    escalation reasons rather than being conflated."""
    empty_tools = FakeAgentTools(curriculum_hits=[], faq_hits=[])
    deps = build_dependencies_from_agent_tools(ExplodingLLM(), empty_tools)
    graph = build_agent_graph(deps)
    empty_result = graph.invoke(base_state())

    def raising_search_curriculum(*, query, course_id, module_id=None):
        raise EmbeddingUnavailableError("down")

    broken_tools = FakeAgentTools()
    broken_tools._search_curriculum = raising_search_curriculum
    deps2 = build_dependencies_from_agent_tools(ExplodingLLM(), broken_tools)
    graph2 = build_agent_graph(deps2)
    broken_result = graph2.invoke(base_state())

    assert (
        empty_result["escalation_reason"]
        == EscalationReason.NO_RELEVANT_CONTEXT
    )
    assert (
        broken_result["escalation_reason"]
        == EscalationReason.RETRIEVAL_UNAVAILABLE
    )
    assert (
        empty_result["escalation_reason"] != broken_result["escalation_reason"]
    )
