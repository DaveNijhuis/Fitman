"""One command launches Fitman: plain `docker compose up -d` (#339).

docker-compose.yml was the Vite development stack and production lived in
docker-compose.prod.yml, so the obvious command started the wrong thing: a dev
server, and a database nothing outside the stack could query. Every production
command needed `-f docker-compose.prod.yml`, and forgetting it once replaced the
running app with the dev stack, since both shared a project name.

docker-compose.yml is now production. Development moved to
docker-compose.dev.yml under its own project name, so it can no longer touch
production's containers or data.
"""

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
PROD = ROOT / "docker-compose.yml"
DEV = ROOT / "docker-compose.dev.yml"
README = (ROOT / "README.md").read_text()
ARCHITECTURE = (ROOT / "ARCHITECTURE.md").read_text()
CI = (ROOT / ".github" / "workflows" / "ci.yml").read_text()

needs_docker = pytest.mark.skipif(
    shutil.which("docker") is None, reason="needs Docker Compose"
)


def _yaml(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text())


# ── Compose files ─────────────────────────────────────────────────────────────


@needs_docker
def test_plain_docker_compose_launches_production(tmp_path: Path):
    """No -f: Compose picks docker-compose.yml, which must be the prod stack."""
    for f in (PROD, DEV):
        shutil.copy(f, tmp_path / f.name)
    (tmp_path / ".env").write_text("SECRET_KEY=x\nPOSTGRES_PASSWORD=0123abcd\n")
    result = subprocess.run(  # noqa: S603, S607 — fixed arguments
        ["docker", "compose", "config", "--format", "json"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    services = json.loads(result.stdout)["services"]
    assert set(services) == {"db-guard", "postgres", "backend", "frontend"}
    assert services["frontend"]["build"]["dockerfile"] == "Dockerfile.prod"
    assert [p["published"] for p in services["frontend"]["ports"]] == ["80"]
    assert services["postgres"]["ports"][0]["published"] == "5433"


def test_no_compose_file_takes_precedence_over_docker_compose_yml():
    """Compose prefers compose.yaml/compose.yml; one would silently win."""
    for name in ("compose.yaml", "compose.yml"):
        assert not (ROOT / name).exists(), name


def test_there_is_one_production_definition():
    assert not (ROOT / "docker-compose.prod.yml").exists()


def test_production_keeps_the_directory_project_name():
    """The volume is <project>_db_data. Pinning a name would switch an instance
    cloned into another directory onto a new, empty volume, starting healthy on
    a blank database."""
    assert "name" not in _yaml(PROD)


def test_dev_stack_runs_the_vite_dev_server():
    frontend = _yaml(DEV)["services"]["frontend"]
    assert frontend["build"] == "./frontend"  # Dockerfile runs `npm run dev`
    assert "VITE_API_PROXY_TARGET" in frontend["environment"]


def test_dev_stack_never_touches_production():
    """Its own project, so its own containers and its own db_data volume."""
    assert _yaml(DEV)["name"] == "fitman-dev"


# ── Documentation ─────────────────────────────────────────────────────────────


def test_readme_deploys_with_plain_docker_compose_up():
    deploy = README[README.index("### 4. Deploy Fitman") : README.index("### 5.")]
    assert "docker compose up -d\n" in deploy


@pytest.mark.parametrize(
    "text", [README, ARCHITECTURE, CI], ids=["README", "ARCHITECTURE", "ci.yml"]
)
def test_nothing_runs_the_old_production_file(text: str):
    assert "-f docker-compose.prod.yml" not in text


def test_readme_tells_existing_deployments_how_to_switch():
    """Old habits and scripts still say -f docker-compose.prod.yml."""
    note = README[README.index("### Upgrading from docker-compose.prod.yml") :]
    assert "docker compose up -d --build" in note[:1500]


def test_readme_documents_the_dev_stack():
    assert "docker compose -f docker-compose.dev.yml up" in README


def test_readme_backups_use_the_compose_service():
    """`docker exec fitman-postgres` names the dev container from `docker run`,
    not production's (fitman-postgres-1): the cron line dumped the wrong
    database, or nothing."""
    assert "docker exec fitman-postgres" not in README
    assert "docker exec -i fitman-postgres" not in README
    assert "exec -T postgres pg_dump" in README
