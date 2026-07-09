from fastapi.testclient import TestClient


def test_login_rate_limit_triggers_on_sixth_attempt(client: TestClient):
    payload = {"username": "nobody", "password": "wrongpass"}
    for _ in range(5):
        client.post("/api/auth/login", json=payload)
    response = client.post("/api/auth/login", json=payload)
    assert response.status_code == 429


def test_rate_limit_does_not_affect_health_endpoint(client: TestClient):
    for _ in range(10):
        r = client.get("/health")
        assert r.status_code == 200
