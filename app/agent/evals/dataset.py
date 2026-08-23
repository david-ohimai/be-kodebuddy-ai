"""
Regression eval set for the agent graph.

Owner: Dev E (History, Observability & Evals)

Each `EvalCase` pins a question to an expected *observable outcome*
(confident vs. escalated, and why) given a fixed, realistic retrieval/LLM
scenario. It does not test LLM answer quality — the LLM response is a
canned fixture, same as tests/test_graph.py's FakeLLM — it tests that the
graph's confidence/escalation *decision* for that scenario doesn't drift.

That's the point: when Dev C tunes a threshold in nodes.py (e.g.
MIN_RETRIEVAL_SCORE) or edits a prompt/policy check, running this set shows
exactly which previously-passing curriculum scenarios flipped, instead of
someone eyeballing a handful of manual chat transcripts.

To add a case: pick a real-ish learner question, decide what retrieval
should plausibly return for it, and decide by hand whether that scenario
*should* result in a confident answer or an escalation (and which reason).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.agent.graph.state import EscalationReason, QueryType


@dataclass
class EvalCase:
    id: str
    question: str
    query_type: QueryType = QueryType.CHAT
    course_id: int = 101
    module_id: int | None = 1001
    assignment_id: int | None = None

    curriculum_hits: list[dict] = field(default_factory=list)
    faq_hits: list[dict] = field(default_factory=list)
    assignment_brief: dict | None = None

    # Canned LLM output for this scenario — see module docstring.
    llm_answer: str = "Grounded answer."
    llm_uncertain: bool = False

    # Expected observable outcome.
    expect_confident: bool = True
    expect_escalation_reason: EscalationReason | None = None
    expect_final_response_contains: str | None = None


def _chunk(chunk_id: str, text: str, score: float, **overrides) -> dict:
    chunk = {
        "chunk_id": chunk_id,
        "course_id": 101,
        "module_id": 1001,
        "content_type": "curriculum",
        "text": text,
        "score": score,
    }
    chunk.update(overrides)
    return chunk


EVAL_CASES: list[EvalCase] = [
    EvalCase(
        id="for_loop_basics_confident",
        question="How does a for loop work in Python?",
        curriculum_hits=[
            _chunk(
                "c-for-loop",
                "A for loop repeats a block of code once for each item in "
                "a sequence, such as a list or range().",
                0.93,
            )
        ],
        llm_answer=(
            "A for loop iterates over a sequence, running its body once "
            "per item."
        ),
        expect_confident=True,
    ),
    EvalCase(
        id="recursion_base_case_confident",
        question="What is a base case in recursion?",
        curriculum_hits=[
            _chunk(
                "c-recursion",
                "A base case is the condition under which a recursive "
                "function stops calling itself.",
                0.88,
            )
        ],
        llm_answer=(
            "The base case is the stopping condition that prevents "
            "infinite recursion."
        ),
        expect_confident=True,
    ),
    EvalCase(
        id="off_topic_question_no_context_escalates",
        question="What's the best pizza topping?",
        curriculum_hits=[],
        faq_hits=[],
        expect_confident=False,
        expect_escalation_reason=EscalationReason.NO_RELEVANT_CONTEXT,
    ),
    EvalCase(
        id="weak_retrieval_escalates_low_confidence",
        question="How do I use decorators with class methods in a "
        "metaclass context?",
        curriculum_hits=[
            _chunk(
                "c-decorators-tangential",
                "Functions are first-class objects in Python.",
                0.45,
            )
        ],
        expect_confident=False,
        expect_escalation_reason=EscalationReason.LOW_RETRIEVAL_CONFIDENCE,
    ),
    EvalCase(
        id="model_uncertain_despite_good_retrieval_escalates",
        question="Why does my recursive function cause a stack overflow "
        "on this specific input?",
        curriculum_hits=[
            _chunk(
                "c-recursion-2",
                "Recursion without a reachable base case causes a stack "
                "overflow.",
                0.9,
            )
        ],
        llm_answer="I'm not fully sure why this specific case fails.",
        llm_uncertain=True,
        expect_confident=False,
        expect_escalation_reason=EscalationReason.MODEL_UNCERTAINTY,
    ),
    EvalCase(
        id="assignment_guidance_confident_no_full_solution",
        question="I'm stuck starting the sorting assignment, any hints?",
        query_type=QueryType.ASSIGNMENT_GUIDANCE,
        assignment_id=42,
        assignment_brief={
            "title": "Sort a list of integers",
            "description": "Implement a sorting algorithm from scratch.",
            "due_date": "2026-09-01",
            "maximum_score": 100.0,
        },
        curriculum_hits=[
            _chunk(
                "c-sorting",
                "Sorting algorithms rearrange elements into order, "
                "e.g. bubble sort compares adjacent pairs.",
                0.85,
            )
        ],
        llm_answer=(
            "Think about comparing adjacent elements and swapping them "
            "when out of order — that's the core idea behind a simple "
            "sort."
        ),
        expect_confident=True,
        expect_final_response_contains="comparing adjacent",
    ),
    EvalCase(
        id="assignment_guidance_full_solution_leak_escalates",
        question="Just give me the full working code for the assignment.",
        query_type=QueryType.ASSIGNMENT_GUIDANCE,
        assignment_id=42,
        assignment_brief={
            "title": "Sort a list of integers",
            "description": "Implement a sorting algorithm from scratch.",
            "due_date": "2026-09-01",
            "maximum_score": 100.0,
        },
        curriculum_hits=[
            _chunk("c-sorting", "Sorting rearranges elements into order.", 0.85)
        ],
        llm_answer=(
            "Here you go:\n```python\n"
            "def bubble_sort(arr):\n"
            "    n = len(arr)\n"
            "    for i in range(n):\n"
            "        for j in range(n - i - 1):\n"
            "            if arr[j] > arr[j + 1]:\n"
            "                arr[j], arr[j + 1] = arr[j + 1], arr[j]\n"
            "    return arr\n"
            "```"
        ),
        expect_confident=False,
        expect_escalation_reason=EscalationReason.POLICY_VIOLATION,
    ),
    EvalCase(
        id="parser_failure_on_unstructured_llm_output",
        question="What does the 'yield' keyword do?",
        curriculum_hits=[
            _chunk(
                "c-generators",
                "yield turns a function into a generator, pausing and "
                "resuming its state.",
                0.9,
            )
        ],
        llm_answer="__RAW_NON_JSON__",
        expect_confident=False,
        expect_escalation_reason=EscalationReason.PARSER_FAILURE,
    ),
]
