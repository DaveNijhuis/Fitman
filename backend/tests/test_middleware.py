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


# ── Structured JSON logging (#234) ───────────────────────────────────────────


def test_json_formatter_produces_valid_json():
    """JSONFormatter.format() must return a parseable single-line JSON string."""
    import json

    from main import JSONFormatter

    record = logging.makeLogRecord(
        {"name": "test", "levelname": "INFO", "msg": "hello"}
    )
    record.request_id = "req-123"  # type: ignore[attr-defined]
    output = JSONFormatter().format(record)
    parsed = json.loads(output)
    assert "message" in parsed


def test_json_formatter_fields():
    """JSON log lines must carry time, level, logger, request_id, and message."""
    import json

    from main import JSONFormatter

    record = logging.makeLogRecord(
        {"name": "mylogger", "levelname": "WARNING", "msg": "something happened"}
    )
    record.request_id = "test-req-456"  # type: ignore[attr-defined]
    data = json.loads(JSONFormatter().format(record))
    assert data["level"] == "WARNING"
    assert data["logger"] == "mylogger"
    assert data["message"] == "something happened"
    assert data["request_id"] == "test-req-456"
    assert "time" in data


def test_log_output_is_json_by_default(client: TestClient, caplog):
    """JSONFormatter must produce parseable JSON for every record emitted in a request."""
    import json

    from main import JSONFormatter

    with caplog.at_level(logging.INFO):
        client.get("/health")

    assert caplog.records, "No log records captured during request"
    fmt = JSONFormatter()
    for record in caplog.records:
        data = json.loads(fmt.format(record))
        assert "message" in data
