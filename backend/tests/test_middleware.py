import uuid

from fastapi.testclient import TestClient


def test_request_id_header_present(client: TestClient):
    response = client.get("/health")
    assert "x-request-id" in response.headers


def test_request_id_is_valid_uuid(client: TestClient):
    response = client.get("/health")
    request_id = response.headers["x-request-id"]
    parsed = uuid.UUID(request_id)
    assert parsed.version == 4


def test_request_id_unique_per_request(client: TestClient):
    r1 = client.get("/health")
    r2 = client.get("/health")
    assert r1.headers["x-request-id"] != r2.headers["x-request-id"]
