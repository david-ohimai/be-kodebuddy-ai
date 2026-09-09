from __future__ import annotations

import json
from dataclasses import dataclass

from app.agent.graph.build import build_agent_graph
from app.agent.graph.nodes import AgentDependencies

from .dataset import EVAL_CASES, EvalCase

_RAW_NON_JSON_SENTINEL = "__RAW_NON_JSON__"


@dataclass
class EvalResult:
    case_id: str
    passed: bool
    failures: list[str]
    final_response: str | None
    is_confident: bool
    escalation_reason: object


def _make_llm(case: EvalCase):
    if case.llm_answer == _RAW_NON_JSON_SENTINEL:
        raw = "Sure, here's an answer with no JSON structure at all."
    else:
        raw = json.dumps(
            {"answer": case.llm_answer, "uncertain": case.llm_uncertain}
        )

    class _FixedLLM:
        def complete(self, *, system: str, user: str) -> str:
            return raw

    return _FixedLLM()


def _make_deps(case: EvalCase) -> AgentDependencies:
    def search_curriculum(*, query, course_id, module_id=None):
        return case.curriculum_hits

    def search_faqs(*, query, course_id):
        return case.faq_hits

    def get_assignment_brief(assignment_id):
        return case.assignment_brief

    def escalate_to_trainer(
        *, learner_id, course_id, trainer_id, question, reason, detail=None
    ):
        return 1

    return AgentDependencies(
        llm=_make_llm(case),
        search_curriculum=search_curriculum,
        search_faqs=search_faqs,
        get_assignment_brief=get_assignment_brief,
        escalate_to_trainer=escalate_to_trainer,
    )


def run_case(case: EvalCase) -> EvalResult:
    deps = _make_deps(case)
    graph = build_agent_graph(deps)

    result = graph.invoke(
        {
            "learner_id": 1,
            "course_id": case.course_id,
            "module_id": case.module_id,
            "assignment_id": case.assignment_id,
            "trainer_id": 55,
            "question": case.question,
            "query_type": case.query_type,
            "chat_history": [],
        }
    )

    failures: list[str] = []

    is_confident = bool(result.get("is_confident"))
    if is_confident != case.expect_confident:
        failures.append(
            f"expected is_confident={case.expect_confident}, "
            f"got {is_confident}"
        )

    escalation_reason = result.get("escalation_reason")
    if case.expect_escalation_reason is not None:
        if escalation_reason != case.expect_escalation_reason:
            failures.append(
                f"expected escalation_reason="
                f"{case.expect_escalation_reason}, got {escalation_reason}"
            )
    elif case.expect_confident and escalation_reason is not None:
        failures.append(
            f"expected no escalation reason, got {escalation_reason}"
        )

    final_response = result.get("final_response")
    if (
        case.expect_final_response_contains is not None
        and case.expect_final_response_contains not in (final_response or "")
    ):
        failures.append(
            f"expected final_response to contain "
            f"{case.expect_final_response_contains!r}, got {final_response!r}"
        )

    return EvalResult(
        case_id=case.id,
        passed=not failures,
        failures=failures,
        final_response=final_response,
        is_confident=is_confident,
        escalation_reason=escalation_reason,
    )


def run_all(cases: list[EvalCase] | None = None) -> list[EvalResult]:
    return [run_case(case) for case in (cases if cases is not None else EVAL_CASES)]


if __name__ == "__main__":
    results = run_all()
    failed = [r for r in results if not r.passed]

    if failed:
        raise SystemExit(1)