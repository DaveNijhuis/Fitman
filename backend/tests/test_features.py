"""Optional features, and the smart scale being opt-in (#326).

The scale integration serves one specific scale most users won't own. It is
off unless SCALE_ENABLED is set; manual weight entry works either way. A fork
without it was rejected: every fix would have to land twice.
"""

from collections.abc import Iterator

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from config import settings
from features import require_scale_enabled


def _auth(client: TestClient) -> dict:
    token = client.post(
        "/api/auth/login", json={"username": "testuser", "password": "testpass"}
    ).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def scale_on(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setattr(settings, "scale_enabled", True)
    yield


# ── GET /api/features ─────────────────────────────────────────────────────────


def test_features_report_the_scale_off_by_default(client: TestClient):
    resp = client.get("/api/features", headers=_auth(client))
    assert resp.status_code == 200
    assert resp.json() == {"scale": False}


def test_features_report_the_scale_when_enabled(client: TestClient, scale_on):
    assert client.get("/api/features", headers=_auth(client)).json() == {"scale": True}


def test_features_require_auth(client: TestClient):
    from main import app

    assert TestClient(app).get("/api/features").status_code == 401


# ── require_scale_enabled: the switch #323's scale endpoints hang off ─────────


@pytest.fixture
def probe() -> TestClient:
    """A throwaway app: no real scale endpoint exists until #323."""
    app = FastAPI()

    @app.get("/scale-only", dependencies=[Depends(require_scale_enabled)])
    def scale_only() -> dict[str, bool]:
        return {"ok": True}

    return TestClient(app)


def test_scale_endpoints_do_not_exist_while_off(probe: TestClient):
    """404, not 403: with the feature off there is nothing there to be refused."""
    assert probe.get("/scale-only").status_code == 404


def test_scale_endpoints_respond_when_enabled(probe: TestClient, scale_on):
    assert probe.get("/scale-only").json() == {"ok": True}


def test_the_switch_is_read_per_request(
    probe: TestClient, monkeypatch: pytest.MonkeyPatch
):
    """Not frozen at import: a restart with a new .env is the only real toggle,
    but reading it per request keeps it testable and free of import order."""
    assert probe.get("/scale-only").status_code == 404
    monkeypatch.setattr(settings, "scale_enabled", True)
    assert probe.get("/scale-only").status_code == 200
