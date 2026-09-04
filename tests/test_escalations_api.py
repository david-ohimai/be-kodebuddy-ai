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


def test_escalation_and_notification_routes_are_registered():
    client = TestClient(app)
    route_paths = _flatten_route_paths(app.routes)

    assert "/agent/escalate" in route_paths
    assert "/escalations/trainer" in route_paths
    assert "/escalations/{escalation_id}" in route_paths
    assert "/notifications" in route_paths
    assert "/notifications/trainer" in route_paths
    assert "/notifications/learner" in route_paths

    response = client.get("/escalations/trainer")
    assert response.status_code in (401, 403)

    response = client.get("/notifications")
    assert response.status_code in (401, 403)


def test_learner_escalation_endpoint_is_protected():
    client = TestClient(app)
    response = client.post(
        "/agent/escalate",
        json={
            "course_id": 1,
            "question": "Why is this failing?",
            "reason": "low_retrieval_confidence",
            "detail": "Need help",
        },
    )
    assert response.status_code in (401, 403)
