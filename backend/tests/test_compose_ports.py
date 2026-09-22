"""The production stack's published ports come from .env (#347).

They were hard-coded: the web app on 80 and PostgreSQL on 127.0.0.1:5433. On a
server where something else already holds 80, such as a reverse proxy,
`docker compose up -d` failed with "port is already allocated", and the only
way round it was editing a tracked file that then conflicts on every pull.

The compose file is exercised with Docker Compose itself, from a temporary
copy with its own .env, as in test_prod_db_credentials.py.
"""

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]
PROD = ROOT / "docker-compose.yml"
README = (ROOT / "README.md").read_text()
ENV_EXAMPLE = (ROOT / ".env.example").read_text()

needs_docker = pytest.mark.skipif(
    shutil.which("docker") is None, reason="needs Docker Compose"
)

BASE_ENV = "SECRET_KEY=x\nPOSTGRES_PASSWORD=0123abcd\n"


def _config(tmp_path: Path, extra: str = "") -> subprocess.CompletedProcess[str]:
    shutil.copy(PROD, tmp_path / "docker-compose.yml")
    (tmp_path / ".env").write_text(BASE_ENV + extra)
    return subprocess.run(  # noqa: S603, S607 — fixed arguments
        ["docker", "compose", "config", "--format", "json"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )


def _port(tmp_path: Path, service: str, extra: str = "") -> dict[str, Any]:
    result = _config(tmp_path, extra)
    assert result.returncode == 0, result.stderr
    [port] = json.loads(result.stdout)["services"][service]["ports"]
    return port


# ── Defaults: existing deployments change nothing ─────────────────────────────


@needs_docker
def test_web_app_defaults_to_port_80_on_every_interface(tmp_path: Path):
    port = _port(tmp_path, "frontend")
    assert (port["published"], port["target"]) == ("80", 80)
    assert not port.get("host_ip")  # IPv4 and IPv6, as "80:80" always did


@needs_docker
def test_database_defaults_to_5433_on_localhost(tmp_path: Path):
    port = _port(tmp_path, "postgres")
    assert (port["host_ip"], port["published"], port["target"]) == (
        "127.0.0.1",
        "5433",
        5432,
    )


# ── Overrides ─────────────────────────────────────────────────────────────────


@needs_docker
def test_web_app_port_can_move(tmp_path: Path):
    port = _port(tmp_path, "frontend", "FITMAN_HTTP_PORT=8081\n")
    assert (port["published"], port["target"]) == ("8081", 80)


@needs_docker
def test_web_app_can_listen_on_localhost_only(tmp_path: Path):
    """For a reverse proxy on the same host: nothing else can reach it."""
    port = _port(tmp_path, "frontend", "FITMAN_HTTP_PORT=127.0.0.1:8081\n")
    assert (port["host_ip"], port["published"]) == ("127.0.0.1", "8081")


@needs_docker
def test_database_port_can_move_and_stays_on_localhost(tmp_path: Path):
    port = _port(tmp_path, "postgres", "FITMAN_DB_PORT=5499\n")
    assert (port["host_ip"], port["published"]) == ("127.0.0.1", "5499")


@needs_docker
def test_database_cannot_be_opened_to_the_network(tmp_path: Path):
    """An address in FITMAN_DB_PORT would widen the binding; it is refused."""
    result = _config(tmp_path, "FITMAN_DB_PORT=0.0.0.0:5499\n")
    assert result.returncode != 0


# ── Documentation ─────────────────────────────────────────────────────────────


@pytest.mark.parametrize("name", ["FITMAN_HTTP_PORT", "FITMAN_DB_PORT"])
def test_env_example_documents_the_port_settings(name: str):
    assert name in ENV_EXAMPLE


def test_readme_lists_the_ports_of_every_stack():
    ports = README[README.index("### Ports") :][:3000]
    for port in ("80", "5433", "3000", "8000", "8080"):
        assert port in ports, port
    assert "FITMAN_HTTP_PORT" in ports and "FITMAN_DB_PORT" in ports


def test_readme_explains_running_behind_an_existing_reverse_proxy():
    section = README[README.index("### Behind an existing reverse proxy") :][:3000]
    assert "reverse_proxy" in section  # a working Caddy example
    assert "127.0.0.1" in section


def test_readme_offers_tailscale_serve_on_another_https_port():
    """When a proxy already holds 443, tailscale serve can use another port."""
    assert "--https=8443" in README
