import pytest
from app.agent.graph.state import AgentState, QueryType, EscalationReason
from app.agent.graph.nodes import (
    AgentDependencies,
    make_retrieve_node,
    _violates_guide_dont_solve_policy,
)
from app.agent.graph.build import build_agent_graph

# ==========================================
# MOCK DEPENDENCIES SETUP
# ==========================================

class ValidMockLLMClient:
    def complete(self, *, system: str, user: str) -> str:
        return '{"answer": "Here is a conceptual guide.", "uncertain": false}'

class BrokenJSONLLMClient:
    def complete(self, *, system: str, user: str) -> str:
        return "Not valid JSON output {"

def mock_search_curriculum_high_score(query: str, course_id: int, module_id: int | None = None):
    return [
        {
            "chunk_id": "c1",
            "course_id": course_id,
            "module_id": module_id,
            "content_type": "curriculum",
            "text": "Python basics concept text.",
            "score": 0.85,
        }
    ]

def mock_search_curriculum_low_score(query: str, course_id: int, module_id: int | None = None):
    return [
        {
            "chunk_id": "c2",
            "course_id": course_id,
            "module_id": module_id,
            "content_type": "curriculum",
            "text": "Unrelated topic text.",
            "score": 0.30,
        }
    ]

def mock_search_faqs(query: str, course_id: int):
    return []

def mock_get_assignment_brief(assignment_id: int):
    return {
        "assignment_id": assignment_id,
        "course_id": 1,
        "module_id": 1,
        "title": "Sample Assignment",
        "description": "Write a python script.",
        "due_date": "2026-09-01",
        "maximum_score": 100,
    }

def mock_escalate_to_trainer(*, learner_id, course_id, trainer_id, question, reason, detail=None):
    return 999  # Escalation Record ID

@pytest.fixture
def default_deps():
    return AgentDependencies(
        llm=ValidMockLLMClient(),
        search_curriculum=mock_search_curriculum_high_score,
        search_faqs=mock_search_faqs,
        get_assignment_brief=mock_get_assignment_brief,
        escalate_to_trainer=mock_escalate_to_trainer,
    )

# ==========================================
# 1. ID VALIDATION TESTS
# ==========================================

def test_id_validation_raises_type_error(default_deps):
    """Confirm TypeError is raised when passing non-integer IDs."""
    retrieve_fn = make_retrieve_node(default_deps)
    
    invalid_state: AgentState = {
        "learner_id": "1",  # String instead of int
        "course_id": 10,
        "question": "How do loops work?",
        "query_type": QueryType.CHAT,
    }
    
    with pytest.raises(TypeError):
        retrieve_fn(invalid_state)

# ==========================================
# 2. GUIDE-DON'T-SOLVE GUARDRAIL TESTS
# ==========================================

def test_violates_guide_dont_solve_policy_true():
    """Triggers true when response contains code block with >4 non-empty lines."""
    violating_response = """Here is the solution:
```python
def solve():
    a = 1
    b = 2
    c = 3
    return a + b + c
```"""
    assert _violates_guide_dont_solve_policy(violating_response) is True

def test_violates_guide_dont_solve_policy_false():
    """Returns false for conceptual hints with short code snippets (<=4 lines)."""
    compliant_response = """Try using this syntax:
```python
# A simple hint
x = 10
```"""
    assert _violates_guide_dont_solve_policy(compliant_response) is False

# ==========================================
# 3. UNCERTAINTY & LOW SCORE ESCALATION TESTS
# ==========================================

def test_low_confidence_score_triggers_escalation():
    """Tests low similarity score (<0.55/0.62) sets escalated=True and triggers escalation."""
    escalate_called = False

    def tracking_escalate(*args, **kwargs):
        nonlocal escalate_called
        escalate_called = True
        return 999

    low_score_deps = AgentDependencies(
        llm=ValidMockLLMClient(),
        search_curriculum=mock_search_curriculum_low_score,
        search_faqs=mock_search_faqs,
        get_assignment_brief=mock_get_assignment_brief,
        escalate_to_trainer=tracking_escalate,
    )

    graph = build_agent_graph(low_score_deps)
    output = graph.invoke({
        "learner_id": 1,
        "course_id": 10,
        "question": "Obscure topic",
        "query_type": QueryType.CHAT,
        "trainer_id": 5,
    })

    assert output["escalated"] is True
    assert output.get("escalation_reason") is not None  # Ensures an escalation reason was provided
    assert escalate_called is True
    
# ==========================================
# 4. PARSER FAILURES & FALLBACK TESTS
# ==========================================

def test_parser_failure_triggers_safe_escalation():
    """Ensures broken JSON response sets parser_failed=True and escalates safely."""
    broken_deps = AgentDependencies(
        llm=BrokenJSONLLMClient(),
        search_curriculum=mock_search_curriculum_high_score,
        search_faqs=mock_search_faqs,
        get_assignment_brief=mock_get_assignment_brief,
        escalate_to_trainer=mock_escalate_to_trainer,
    )

    graph = build_agent_graph(broken_deps)
    output = graph.invoke({
        "learner_id": 1,
        "course_id": 10,
        "question": "What is recursion?",
        "query_type": QueryType.CHAT,
        "trainer_id": 5,
    })

    assert output.get("parser_failed") is True
    assert output["escalated"] is True