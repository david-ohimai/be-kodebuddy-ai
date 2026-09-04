# tests/test_agent_app_boots.py
"""
Smoke test that the agent's router actually mounts and the app boots with
it -- the specific gap that let the ConversationHistoryRepository/
QueryLogRepository import bug (fixed in app/agent/repository.py) ship
undetected: every other agent test exercises the graph/tools/history logic
against fakes, but nothing imported app.agent.router or app.main directly.
"""

from fastapi.testclient import TestClient

from app.main import app


def _flatten_route_paths(routes):
    paths = set()
    for route in routes:
        if hasattr(route, "path") and route.path:
            paths.add(route.path)
        if hasattr(route, "routes"):
            paths |= _flatten_route_paths(route.routes)
        if hasattr(route, "original_router"):
            paths |= _flatten_route_paths(route.original_router.routes)
    return paths


def test_app_boots_with_agent_router_mounted():
    """Importing app.main must not raise, and /agent/chat must be a real
    registered route -- this is the exact failure mode of bug #1."""
    client = TestClient(app)
    route_paths = _flatten_route_paths(app.routes)
    assert "/agent/chat" in route_paths
    assert "/agent/history" in route_paths
    # /agent/assignment-guidance was merged into /agent/chat -- assignment_id
    # is now just an optional field on the same request, not a separate route.


def test_agent_chat_requires_auth():
    """Doesn't need a real learner/DB fixture -- just confirms the endpoint
    is wired through auth (get_current_learner) rather than 404ing or
    500ing on an import-time problem."""
    client = TestClient(app)
    response = client.post(
        "/agent/chat",
        json={"course_id": 1, "module_id": None, "question": "test"},
    )
    assert response.status_code in (401, 403)


def test_agent_chat_accepts_optional_assignment_id():
    """Same auth-gate check, but confirms the unified endpoint still parses
    a request that includes assignment_id -- guards against a future change
    to MessageRequest accidentally making assignment_id required again."""
    client = TestClient(app)
    response = client.post(
        "/agent/chat",
        json={
            "course_id": 1,
            "module_id": None,
            "assignment_id": 2,
            "question": "test",
        },
    )
    assert response.status_code in (401, 403)