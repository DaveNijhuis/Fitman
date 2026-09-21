"""The dev compose frontend must be able to reach the backend (#274).

docker-compose.dev.yml (docker-compose.yml before #339) runs the Vite dev server in the frontend container. Vite
proxies /api to the target in vite.config.ts, which was hardcoded to
localhost:8000 — correct on the host, but inside the container that resolves
to the frontend itself, where nothing listens. Every API call returned 502
while the stack reported healthy.

The prod and E2E stacks build with Dockerfile.prod, whose nginx proxies to
http://backend:8000 by service name, and are unaffected.
"""

from pathlib import Path
from typing import Any

import yaml

_ROOT = Path(__file__).resolve().parents[2]
_DEV_COMPOSE = _ROOT / "docker-compose.dev.yml"
_VITE_CONFIG = _ROOT / "frontend" / "vite.config.ts"

_PROXY_ENV_VAR = "VITE_API_PROXY_TARGET"


def _frontend_service() -> dict[str, Any]:
    compose = yaml.safe_load(_DEV_COMPOSE.read_text())
    return compose["services"]["frontend"]


def _frontend_environment() -> dict[str, str]:
    """Compose accepts environment as a mapping or a list of KEY=value strings."""
    env = _frontend_service().get("environment", {})
    if isinstance(env, list):
        pairs = (item.split("=", 1) for item in env)
        return {k: v for k, v in pairs}
    return {k: str(v) for k, v in env.items()}


def test_dev_compose_sets_the_proxy_target() -> None:
    """Without this the frontend container proxies /api to itself."""
    assert _PROXY_ENV_VAR in _frontend_environment()


def test_proxy_target_names_the_backend_service() -> None:
    """Inside the compose network the backend is reachable by service name."""
    target = _frontend_environment()[_PROXY_ENV_VAR]
    assert "backend" in target, (
        f"{_PROXY_ENV_VAR} is {target!r}, which is not the backend service"
    )
    assert "localhost" not in target


def test_proxy_target_points_at_a_service_compose_defines() -> None:
    """A typo'd service name would fail exactly like the original bug."""
    compose = yaml.safe_load(_DEV_COMPOSE.read_text())
    host = _frontend_environment()[_PROXY_ENV_VAR].split("//")[-1].split(":")[0]
    assert host in compose["services"], (
        f"proxy target host {host!r} is not a service in docker-compose.dev.yml"
    )


def test_vite_config_reads_the_target_from_the_environment() -> None:
    """A hardcoded target cannot be right both on the host and in a container."""
    source = _VITE_CONFIG.read_text()
    assert _PROXY_ENV_VAR in source


def test_vite_config_keeps_a_localhost_default() -> None:
    """`npm run dev` on the host must keep working with no env var set."""
    source = _VITE_CONFIG.read_text()
    assert "http://localhost:8000" in source
