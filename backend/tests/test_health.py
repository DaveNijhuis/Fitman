from unittest.mock import MagicMock

from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from database import get_db
from main import app


def test_health_ok(client: TestClient):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_health_db_down():
    def mock_db_fail():
        mock = MagicMock()
        mock.execute.side_effect = OperationalError("DB down", None, None)
        yield mock

    app.dependency_overrides[get_db] = mock_db_fail
    try:
        with TestClient(app) as c:
            response = c.get("/health")
        assert response.status_code == 503
        assert response.json()["status"] == "error"
    finally:
        app.dependency_overrides.pop(get_db, None)
