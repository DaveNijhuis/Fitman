"""The production database password is the operator's, not the repo's (#335).

docker-compose.prod.yml hard-coded POSTGRES_PASSWORD: fitman, and .env.example
the matching DATABASE_URL, so every deployment ran on a password published in
this public repository. The prod database now publishes a port on 127.0.0.1
(queryable from the server, or through an SSH tunnel), so its password is what
actually protects it.

The compose file is exercised with Docker Compose itself, from a temporary
copy with its own .env: a developer's real .env never enters into it.
"""

import json
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
PROD = ROOT / "docker-compose.yml"  # production (#339)
README = (ROOT / "README.md").read_text()
ENV_EXAMPLE = (ROOT / ".env.example").read_text()

needs_docker = pytest.mark.skipif(
    shutil.which("docker") is None, reason="needs Docker Compose"
)


def _config(tmp_path: Path, env: str) -> subprocess.CompletedProcess[str]:
    shutil.copy(PROD, tmp_path / "docker-compose.yml")
    (tmp_path / ".env").write_text(env)
    return subprocess.run(  # noqa: S603, S607 — fixed arguments
        ["docker", "compose", "config", "--format", "json"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )


# ── Compose file ──────────────────────────────────────────────────────────────


def test_prod_compose_contains_no_literal_password():
    postgres = yaml.safe_load(PROD.read_text())["services"]["postgres"]
    assert postgres["environment"]["POSTGRES_PASSWORD"].startswith(
        "${POSTGRES_PASSWORD:?"
    )


@needs_docker
def test_starting_without_a_password_is_refused_with_a_pointer(tmp_path: Path):
    result = _config(tmp_path, "SECRET_KEY=x\n")
    assert result.returncode != 0
    assert "POSTGRES_PASSWORD" in result.stderr
    assert "README" in result.stderr


@needs_docker
def test_the_backend_connects_with_the_same_password(tmp_path: Path):
    """Built from POSTGRES_PASSWORD, so the two can't drift apart."""
    result = _config(tmp_path, "SECRET_KEY=x\nPOSTGRES_PASSWORD=0123abcd\n")
    assert result.returncode == 0, result.stderr
    services = json.loads(result.stdout)["services"]
    assert services["postgres"]["environment"]["POSTGRES_PASSWORD"] == "0123abcd"
    url = services["backend"]["environment"]["DATABASE_URL"]
    assert url == "postgresql://fitman:0123abcd@postgres:5432/fitman"


@needs_docker
def test_the_database_is_queryable_from_the_server_only(tmp_path: Path):
    result = _config(tmp_path, "SECRET_KEY=x\nPOSTGRES_PASSWORD=0123abcd\n")
    [port] = json.loads(result.stdout)["services"]["postgres"]["ports"]
    assert port["host_ip"] == "127.0.0.1"  # never the network
    assert (port["published"], port["target"]) == ("5433", 5432)


def test_throwaway_stacks_keep_their_fixed_password():
    """Dev and E2E databases are disposable; only production takes a secret."""
    for name in ("docker-compose.dev.yml", "docker-compose.e2e.yml"):
        env = yaml.safe_load((ROOT / name).read_text())["services"]["postgres"][
            "environment"
        ]
        assert env["POSTGRES_PASSWORD"] == "fitman", name


def test_ci_production_build_provides_a_password():
    """The prod build job writes a stub .env; without the variable, compose refuses."""
    ci = (ROOT / ".github" / "workflows" / "ci.yml").read_text()
    assert 'echo "POSTGRES_PASSWORD=' in ci


# ── Documentation ─────────────────────────────────────────────────────────────


def test_env_example_asks_for_a_generated_password():
    lines = [
        line
        for line in ENV_EXAMPLE.splitlines()
        if line.startswith("POSTGRES_PASSWORD=")
    ]
    assert lines == ["POSTGRES_PASSWORD="], (
        "must be set by the operator, with no usable default"
    )
    assert "token_hex" in ENV_EXAMPLE


def test_readme_deploy_step_generates_the_password():
    deploy = README[README.index("### 4. Deploy Fitman") : README.index("### 5.")]
    assert "POSTGRES_PASSWORD" in deploy
    assert "token_hex" in deploy


def test_readme_explains_changing_the_password_on_an_existing_database():
    """Postgres applies POSTGRES_PASSWORD only when it first creates the database."""
    assert "ALTER USER fitman WITH PASSWORD" in README


def test_readme_explains_querying_the_database():
    assert "localhost:5433" in README
    assert "SSH" in README
