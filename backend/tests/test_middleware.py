import logging
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


# ── Request-ID in log records (#229) ─────────────────────────────────────────


def test_request_id_filter_unit():
    """RequestIDFilter must stamp record.request_id from the context var."""
    from main import RequestIDFilter, _request_id_ctx

    tok = _request_id_ctx.set("unit-test-id-xyz")
    try:
        record = logging.makeLogRecord({"msg": "hello"})
        RequestIDFilter().filter(record)
        assert record.request_id == "unit-test-id-xyz"  # type: ignore[attr-defined]
    finally:
        _request_id_ctx.reset(tok)


def test_request_id_in_log_records(client: TestClient, caplog):
    """Every log record emitted during a request must carry the X-Request-ID."""
    with caplog.at_level(logging.INFO):
        resp = client.get("/health")
    req_id = resp.headers["x-request-id"]
    matched = [r for r in caplog.records if getattr(r, "request_id", None) == req_id]
    assert matched, f"No log records found with request_id={req_id!r}"
