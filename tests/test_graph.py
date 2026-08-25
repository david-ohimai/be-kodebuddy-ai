"""
Unit tests for the agent graph, using fakes for every external dependency
(Dev B's tools, the LLM client). No database, no network, no real LLM call.

Run with: pytest tests/test_graph.py -v
"""

from __future__ import annotations

import json

from app.agent.graph.build import build_agent_graph
from app.agent.graph.nodes import AgentDependencies
from app.agent.graph.state import EscalationReason, QueryType


class FakeLLM:
    """Stands in for Dev D's real LLMClient — returns a canned completion."""

    def __init__(self, response: str):
        self._response = response

    def complete(self, *, system: str, user: str) -> str:
        return self._response


class ExplodingLLM:
    """Used to prove a code path never calls the LLM at all (the
    no_context short-circuit)."""

    def complete(self, *, system: str, user: str) -> str:
        raise AssertionError("LLM should not have been called on this path")


def json_response(answer: str, uncertain: bool) -> str:
    return json.dumps({"answer": answer, "uncertain": uncertain})


def make_deps(
    llm=None,
    llm_response: str | None = None,
    curriculum_hits: list[dict] | None = None,
    faq_hits: list[dict] | None = None,
    assignment_brief: dict | None = None,
    max_history_turns: int = 6,
):
    """Builds an AgentDependencies wired to fakes, and a mutable dict that
    records the last escalate_to_trainer call, for assertions."""
    escalated: dict = {}

    def fake_search_curriculum(*, query, course_id, module_id=None):
        return curriculum_hits or []

    def fake_search_faqs(*, query, course_id):
        return faq_hits or []

    def fake_get_assignment_brief(assignment_id):
        return assignment_brief

    def fake_escalate(
        *, learner_id, course_id, trainer_id, question, reason, detail=None
    ):
        escalated["called"] = True
        escalated["trainer_id"] = trainer_id
        escalated["reason"] = reason
        escalated["detail"] = detail
        return 999

    if llm is None:
        llm = FakeLLM(
            llm_response
            if llm_response is not None
            else json_response("Grounded answer.", False)
        )

    deps = AgentDependencies(
        llm=llm,
        search_curriculum=fake_search_curriculum,
        search_faqs=fake_search_faqs,
        get_assignment_brief=fake_get_assignment_brief,
        escalate_to_trainer=fake_escalate,
        max_history_turns=max_history_turns,
    )
    return deps, escalated


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
# Confident path
# --------------------------------------------------------------------------
def test_confident_answer_is_returned_without_escalation():
    deps, escalated = make_deps(curriculum_hits=[good_chunk()])
    graph = build_agent_graph(deps)
    result = graph.invoke(base_state())

    assert result["escalated"] is False
    assert result["final_response"] == "Grounded answer."
    assert "called" not in escalated


# --------------------------------------------------------------------------
# no_context short-circuit (new: skips the LLM call entirely)
# --------------------------------------------------------------------------
def test_no_retrieval_and_no_brief_skips_llm_and_escalates():
    deps, escalated = make_deps(
        llm=ExplodingLLM(), curriculum_hits=[], faq_hits=[]
    )
    graph = build_agent_graph(deps)
    result = graph.invoke(base_state())

    assert result["escalated"] is True
    assert escalated["reason"] == EscalationReason.NO_RELEVANT_CONTEXT
    assert escalated["trainer_id"] == 55
    assert result["escalation_id"] == 999
    assert "trainer" in result["final_response"].lower()


def test_assignment_guidance_with_brief_but_no_chunks_still_reasons():
    """Assignment guidance with a brief (but zero retrieved chunks) should
    still go through `reason`, not the no_context short-circuit — the brief
    alone can be enough to give guidance."""
    deps, escalated = make_deps(
        curriculum_hits=[],
        faq_hits=[],
        assignment_brief={
            "title": "Reverse a string",
            "description": "Build a function that reverses a string.",
            "due_date": None,
            "maximum_score": None,
        },
    )
    graph = build_agent_graph(deps)
    graph.invoke(
        base_state(query_type=QueryType.ASSIGNMENT_GUIDANCE, assignment_id=42)
    )

    # Reached `reason` (LLM was called, didn't raise) and then confidence_gate
    # legitimately escalates on NO_RELEVANT_CONTEXT since there's still no
    # curriculum context — this proves it went through the full path, not
    # the short-circuit.
    assert "called" in escalated
    assert escalated["reason"] == EscalationReason.NO_RELEVANT_CONTEXT


# --------------------------------------------------------------------------
# Confidence gate branches, now via structured EscalationReason
# --------------------------------------------------------------------------
def test_low_relevance_retrieval_triggers_escalation():
    deps, escalated = make_deps(curriculum_hits=[good_chunk(score=0.40)])
    graph = build_agent_graph(deps)
    result = graph.invoke(base_state())

    assert result["escalated"] is True
    assert escalated["reason"] == EscalationReason.LOW_RETRIEVAL_CONFIDENCE


def test_weak_chunks_excluded_from_prompt_but_still_drive_low_confidence(
):
    """Regression test for the min_score filtering fix (raised by Dev B):
    a sub-threshold chunk must not reach the LLM's context, but must still
    count toward the confidence gate's *unfiltered* top score. Filtering at
    retrieval instead would turn a weak-hits query into an empty list —
    indistinguishable from a genuinely empty result — and misfile it as
    NO_RELEVANT_CONTEXT instead of LOW_RETRIEVAL_CONFIDENCE."""
    captured = {}

    class CapturingLLM:
        def complete(self, *, system, user):
            captured["user"] = user
            return json_response("some answer", False)

    weak_chunk = good_chunk(text="Barely related junk content.", score=0.1)
    deps, escalated = make_deps(
        llm=CapturingLLM(),
        curriculum_hits=[weak_chunk],
    )
    graph = build_agent_graph(deps)
    result = graph.invoke(base_state())

    # Reached `reason` (not the no_context short-circuit) since the chunk
    # list itself was non-empty — but the junk text never made it in.
    assert "Barely related junk content." not in captured["user"]
    assert "(no relevant context retrieved)" in captured["user"]

    # The gate still saw the real (weak) top score, not an emptied list.
    assert result["escalated"] is True
    assert (
        result["escalation_reason"]
        == EscalationReason.LOW_RETRIEVAL_CONFIDENCE
    )
    assert escalated["reason"] == EscalationReason.LOW_RETRIEVAL_CONFIDENCE


def test_prompt_excludes_weak_chunks_but_keeps_relevant_ones_in_mixed_results(
):
    captured = {}

    class CapturingLLM:
        def complete(self, *, system, user):
            captured["user"] = user
            return json_response("Grounded answer.", False)

    strong_chunk = good_chunk(
        chunk_id="c1",
        text="A relevant, strong match.",
        score=0.95,
    )
    weak_chunk = good_chunk(
        chunk_id="c2",
        text="An irrelevant, weak match.",
        score=0.1,
    )
    deps, escalated = make_deps(
        llm=CapturingLLM(),
        curriculum_hits=[weak_chunk, strong_chunk],
    )
    graph = build_agent_graph(deps)
    result = graph.invoke(base_state())

    assert "A relevant, strong match." in captured["user"]
    assert "An irrelevant, weak match." not in captured["user"]
    assert result["escalated"] is False
    assert "called" not in escalated


def test_model_uncertainty_triggers_escalation_even_with_good_retrieval():
    deps, escalated = make_deps(
        llm_response=json_response("Not totally sure about this one.", True),
        curriculum_hits=[good_chunk(score=0.95)],
    )
    graph = build_agent_graph(deps)
    result = graph.invoke(base_state())

    assert result["escalated"] is True
    assert escalated["reason"] == EscalationReason.MODEL_UNCERTAINTY
    assert "Not totally sure" in result["final_response"]


def test_malformed_json_is_a_distinct_parser_failure_not_model_uncertainty():
    """The team-lead review's core ask: a model that drops the expected
    format should be tracked separately from one that genuinely reports
    uncertainty, since they need different follow-up."""
    deps, escalated = make_deps(
        llm_response="Sure, here's an answer with no JSON structure at all.",
        curriculum_hits=[good_chunk(score=0.95)],
    )
    graph = build_agent_graph(deps)
    result = graph.invoke(base_state())

    assert result["escalated"] is True
    assert escalated["reason"] == EscalationReason.PARSER_FAILURE
    assert result["escalation_reason"] == EscalationReason.PARSER_FAILURE


def test_json_wrapped_in_markdown_fence_still_parses():
    """Some models wrap JSON output in a ```json fence despite instructions
    not to — the parser should tolerate that rather than treating it as a
    parser failure."""
    fenced = "```json\n" + json_response("Fenced but valid.", False) + "\n```"
    deps, escalated = make_deps(
        llm_response=fenced, curriculum_hits=[good_chunk(score=0.95)]
    )
    graph = build_agent_graph(deps)
    result = graph.invoke(base_state())

    assert result["escalated"] is False
    assert result["final_response"] == "Fenced but valid."
    assert "called" not in escalated


# --------------------------------------------------------------------------
# Policy violation (leaked full solution)
# --------------------------------------------------------------------------
def test_full_solution_code_block_triggers_policy_violation_escalation():
    leaked_solution = (
        "Here you go:\n```python\n"
        "def reverse_string(s):\n"
        "    result = ''\n"
        "    for ch in s:\n"
        "        result = ch + result\n"
        "    return result\n"
        "```"
    )
    deps, escalated = make_deps(
        llm_response=json_response(leaked_solution, False),
        assignment_brief={
            "title": "Reverse a string",
            "description": "Build a function that reverses a string.",
            "due_date": None,
            "maximum_score": None,
        },
        curriculum_hits=[good_chunk()],
    )
    graph = build_agent_graph(deps)
    result = graph.invoke(
        base_state(
            query_type=QueryType.ASSIGNMENT_GUIDANCE,
            assignment_id=42,
            question="I don't know where to start.",
        )
    )

    assert result["policy_violation"] is True
    assert result["escalated"] is True
    assert escalated["reason"] == EscalationReason.POLICY_VIOLATION


def test_short_snippet_does_not_violate_policy():
    allowed = (
        "Think about swapping ends. On [1, 2, 3, 4]:"
        "```python"
        "a, b = arr[0], arr[-1]"
        "```Try applying that idea to your string."
    )
    deps, escalated = make_deps(
        llm_response=json_response(allowed, False),
        assignment_brief={
            "title": "Reverse a string",
            "description": "Build a function that reverses a string.",
            "due_date": None,
            "maximum_score": None,
        },
        curriculum_hits=[good_chunk()],
    )
    graph = build_agent_graph(deps)
    result = graph.invoke(
        base_state(query_type=QueryType.ASSIGNMENT_GUIDANCE, assignment_id=42)
    )

    assert result["policy_violation"] is False
    assert result["escalated"] is False
    assert "called" not in escalated


def test_policy_check_is_not_applied_to_plain_chat():
    """The guide-don't-solve policy is assignment-specific; a chat answer
    with a longer code example (e.g. showing how a for loop works) must not
    be flagged."""
    long_example = (
        "```python"
        "for i in range(10):"
        "    print(i)"
        "    if i % 2 == 0:"
        "        print('even')"
        "    else:\n"
        "        print('odd')"
        "```"
    )
    deps, escalated = make_deps(
        llm_response=json_response(long_example, False),
        curriculum_hits=[good_chunk()],
    )
    graph = build_agent_graph(deps)
    result = graph.invoke(base_state(query_type=QueryType.CHAT))

    assert result["policy_violation"] is False
    assert result["escalated"] is False
    assert "called" not in escalated


# --------------------------------------------------------------------------
# Assignment brief: structured, fully passed through (no truncation)
# --------------------------------------------------------------------------
def test_assignment_brief_is_passed_through_without_truncation():
    brief = {
        "title": "Sort a doubly linked list",
        "description": (
            "Build an algorithm to sort a doubly linked list in place."
        ),
        "due_date": "2026-09-01",
        "maximum_score": 100.0,
    }
    deps, _ = make_deps(assignment_brief=brief, curriculum_hits=[good_chunk()])
    graph = build_agent_graph(deps)
    result = graph.invoke(
        base_state(query_type=QueryType.ASSIGNMENT_GUIDANCE, assignment_id=42)
    )

    # The full brief reaches state untouched — no naive truncation stripping
    # "to sort a doubly linked list" down to just "Build an algorithm".
    assert result["assignment_brief"] == brief
    assert "doubly linked list" in result["assignment_brief"]["description"]


def test_assignment_brief_formatting_omits_missing_optional_fields():
    from app.agent.prompts.assignment_guidance import _format_assignment_brief

    minimal_brief = {
        "title": "Reverse a string",
        "description": "Build a function that reverses a string.",
        "due_date": None,
        "maximum_score": None,
    }
    formatted = _format_assignment_brief(minimal_brief)
    assert "Due:" not in formatted
    assert "Maximum score:" not in formatted
    assert "Reverse a string" in formatted


def test_assignment_brief_formatting_includes_present_optional_fields():
    from app.agent.prompts.assignment_guidance import _format_assignment_brief

    full_brief = {
        "title": "Reverse a string",
        "description": "Build a function that reverses a string.",
        "due_date": "2026-09-01",
        "maximum_score": 100.0,
    }
    formatted = _format_assignment_brief(full_brief)
    assert "Due: 2026-09-01" in formatted
    assert "Maximum score: 100.0" in formatted


# --------------------------------------------------------------------------
# Defensive accessors: chunk and chat-turn shape drift (utils.py)
# --------------------------------------------------------------------------
def test_retrieval_tolerates_differently_keyed_chunks():
    """Simulates Dev B's tool returning `content`/`similarity_score` instead
    of `text`/`score` — should not raise, and should still sort correctly."""
    odd_shaped_hit = {
        "chunk_id": "c1",
        "course_id": 101,
        "module_id": 1001,
        "content_type": "curriculum",
        "content": "Odd-shaped but usable content.",
        "similarity_score": 0.9,
    }
    deps, escalated = make_deps(curriculum_hits=[odd_shaped_hit])
    graph = build_agent_graph(deps)
    result = graph.invoke(base_state())

    assert result["escalated"] is False
    assert "called" not in escalated


def test_history_tolerates_content_keyed_turns_instead_of_message():
    """Simulates Dev E passing turns shaped like {"role": ..., "content": ...}
    instead of {"role": ..., "message": ...} — must not raise a KeyError."""
    odd_shaped_history = [
        {"role": "user", "content": "What's a variable?"},
        {"role": "assistant", "content": "A named storage location."},
    ]
    deps, _ = make_deps(curriculum_hits=[good_chunk()])
    graph = build_agent_graph(deps)
    result = graph.invoke(base_state(chat_history=odd_shaped_history))

    assert result["escalated"] is False  # didn't raise, reached a real answer


def test_history_tolerates_object_shaped_turns():
    """Simulates a LangChain-style message object instead of a dict."""

    class FakeMessage:
        def __init__(self, role, content):
            self.role = role
            self.content = content

    odd_shaped_history = [FakeMessage("user", "What's a variable?")]
    deps, _ = make_deps(curriculum_hits=[good_chunk()])
    graph = build_agent_graph(deps)
    result = graph.invoke(base_state(chat_history=odd_shaped_history))

    assert result["escalated"] is False


# --------------------------------------------------------------------------
# Windowed history, now configurable via AgentDependencies
# --------------------------------------------------------------------------
def test_history_window_respects_deps_max_history_turns():
    from app.agent.prompts.chat import build_user_turn

    long_history = [
        {"role": "user" if i % 2 == 0 else "assistant", "message": f"turn {i}"}
        for i in range(20)
    ]
    windowed = build_user_turn("q", [], long_history, max_history_turns=3)
    assert windowed.count("turn ") == 3


def test_reason_node_uses_deps_max_history_turns_not_a_hardcoded_constant():
    captured = {}

    class CapturingLLM:
        def complete(self, *, system, user):
            captured["user"] = user
            return json_response("ok", False)

    long_history = [
        {"role": "user", "message": f"turn {i}"} for i in range(20)
    ]
    deps, _ = make_deps(
        llm=CapturingLLM(), curriculum_hits=[good_chunk()], max_history_turns=2
    )
    graph = build_agent_graph(deps)
    graph.invoke(base_state(chat_history=long_history))

    assert captured["user"].count("turn ") == 2


# --------------------------------------------------------------------------
# Trainer routing on escalation
# --------------------------------------------------------------------------
def test_escalation_carries_trainer_id_through():
    deps, escalated = make_deps(curriculum_hits=[])
    graph = build_agent_graph(deps)
    graph.invoke(base_state(trainer_id=77))

    assert escalated["trainer_id"] == 77


def test_escalation_still_proceeds_when_trainer_id_is_missing():
    """Missing trainer assignment must not silently drop the learner's
    question — it should still escalate (with trainer_id=None) so Dev B's
    fallback queue can pick it up."""
    deps, escalated = make_deps(curriculum_hits=[])
    graph = build_agent_graph(deps)
    result = graph.invoke(base_state(trainer_id=None))

    assert result["escalated"] is True
    assert escalated["trainer_id"] is None


# --------------------------------------------------------------------------
# State reset on re-entry (no leakage across turns)
# --------------------------------------------------------------------------
def test_stale_computed_fields_do_not_leak_into_a_fresh_invoke():
    """Simulates a caller reusing/mutating the same state dict across two
    turns instead of building a fresh one — the second turn must not
    inherit the first turn's escalation."""
    deps, escalated = make_deps(curriculum_hits=[])
    graph = build_agent_graph(deps)

    stale_state = base_state()
    first_result = graph.invoke(stale_state)
    assert first_result["escalated"] is True  # no retrieval -> escalates

    # Second turn reuses the *returned* dict (which carries over
    # escalated=True, escalation_reason=..., etc. from turn one) plus good
    # retrieval this time.
    escalated.clear()
    deps2, escalated2 = make_deps(curriculum_hits=[good_chunk()])
    graph2 = build_agent_graph(deps2)
    second_result = graph2.invoke(
        {**first_result, "question": "a new question"}
    )

    assert second_result["escalated"] is False
    assert second_result["escalation_reason"] is None
    assert "called" not in escalated2


# --------------------------------------------------------------------------
# ID validation
# --------------------------------------------------------------------------
def test_string_course_id_is_rejected_loudly_instead_of_silently_escalating():
    deps, escalated = make_deps(curriculum_hits=[good_chunk()])
    graph = build_agent_graph(deps)

    raised = False
    try:
        graph.invoke(base_state(course_id="101"))  # str, not int
    except TypeError:
        raised = True

    assert raised is True
    assert "called" not in escalated


def test_string_trainer_id_is_rejected_loudly():
    deps, _ = make_deps(curriculum_hits=[good_chunk()])
    graph = build_agent_graph(deps)

    raised = False
    try:
        graph.invoke(base_state(trainer_id="55"))
    except TypeError:
        raised = True

    assert raised is True


def test_bool_id_is_rejected_despite_being_an_int_subclass():
    """isinstance(True, int) is True in Python — this must not accidentally
    pass validation."""
    deps, _ = make_deps(curriculum_hits=[good_chunk()])
    graph = build_agent_graph(deps)

    raised = False
    try:
        graph.invoke(base_state(module_id=True))
    except TypeError:
        raised = True

    assert raised is True

def test_policy_violation_escalation_does_not_leak_the_solution_to_the_learner():
    """
    The whole point of POLICY_VIOLATION is to stop a full solution reaching
    the learner. If route()'s "here's what I found, which may still help"
    fallback includes the draft on this path, the guardrail is bypassed by
    the escalation message itself.
    """
    leaked_solution = (
        "Here you go:\n```python\n"
        "def reverse_string(s):\n"
        "    result = ''\n"
        "    for ch in s:\n"
        "        result = ch + result\n"
        "    return result\n"
        "```"
    )
    deps, escalated = make_deps(
        llm_response=json_response(leaked_solution, False),
        assignment_brief={
            "title": "Reverse a string",
            "description": "Build a function that reverses a string.",
            "due_date": None,
            "maximum_score": None,
        },
        curriculum_hits=[good_chunk()],
    )
    graph = build_agent_graph(deps)
    result = graph.invoke(
        base_state(
            query_type=QueryType.ASSIGNMENT_GUIDANCE,
            assignment_id=42,
            question="I don't know where to start.",
        )
    )

    assert result["escalated"] is True
    assert result["escalation_reason"] == EscalationReason.POLICY_VIOLATION
    assert leaked_solution not in result["final_response"], (
        "Policy-violation escalation leaked the full solution back to the "
        "learner via the 'may still help' fallback text."
    )
