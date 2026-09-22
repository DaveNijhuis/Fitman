"""update.sh: a safe update for a running deployment (#350).

A real git: a bare "origin" repository, a deployment cloned from it, and a
publisher clone that pushes new versions. Docker is a fake on a bare PATH that
logs its calls, steered through environment variables:

    FAKE_STOPPED     set: Fitman isn't running (nothing to back up)
    FAKE_EMPTY_DUMP  set: pg_dump produces nothing
    FAKE_UP_EXIT     exit code of `docker compose up`
    FAKE_MIGRATIONS  what the backend logged about migrations
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "update.sh"
README = (ROOT / "README.md").read_text()

TOOLS = (
    "bash sh env cat cp mv rm sed grep tr head tail basename dirname mkdir "
    "mktemp awk cut printf sort comm wc date git"
).split()

FAKE_DOCKER = r"""#!/bin/bash
echo "docker $*" >> "$FAKE_LOG"
case "$*" in
  "compose version"*|"info"*) ;;
  "compose ps"*) [ -n "$FAKE_STOPPED" ] || echo "abc123" ;;
  "compose exec -T postgres pg_dump"*)
    [ -n "$FAKE_EMPTY_DUMP" ] || echo "-- PostgreSQL database dump" ;;
  "compose up"*) exit "${FAKE_UP_EXIT:-0}" ;;
  "compose logs"*) printf '%s\n' "${FAKE_MIGRATIONS:-}" ;;
esac
exit 0
"""

GIT = ["git", "-c", "user.name=Test", "-c", "user.email=test@example.com"]


def _git(cwd: Path, *args: str) -> str:
    return subprocess.run(  # noqa: S603 — fixed arguments
        [*GIT, *args], cwd=cwd, check=True, capture_output=True, text=True
    ).stdout.strip()


class Deployment:
    def __init__(self, tmp_path: Path):
        origin = tmp_path / "origin.git"
        _git(tmp_path, "init", "--bare", "-b", "main", str(origin))
        self.publisher = tmp_path / "publisher"
        _git(tmp_path, "clone", str(origin), str(self.publisher))
        for name in ("update.sh", "docker-compose.yml", ".env.example"):
            shutil.copy(ROOT / name, self.publisher / name)
        (self.publisher / ".gitignore").write_text(".env\nbackups/\n")
        _git(self.publisher, "add", "-A")
        _git(self.publisher, "commit", "-m", "Fitman 1.0")
        _git(self.publisher, "push", "origin", "main")

        self.repo = tmp_path / "Fitman"
        _git(tmp_path, "clone", str(origin), str(self.repo))
        (self.repo / ".env").write_text("SECRET_KEY=aa11\nPOSTGRES_PASSWORD=bb22\n")

        self.bin = tmp_path / "bin"
        self.bin.mkdir()
        for tool in TOOLS:
            real = shutil.which(tool)
            if real:
                (self.bin / tool).symlink_to(real)
        docker = self.bin / "docker"
        docker.write_text(FAKE_DOCKER)
        docker.chmod(0o755)
        self.log = tmp_path / "calls.log"
        self.log.touch()

    def publish(self, message: str, files: dict[str, str] | None = None) -> str:
        """Push a new version to origin; returns its commit."""
        for name, content in (files or {}).items():
            (self.publisher / name).write_text(content)
        if not files:
            (self.publisher / "CHANGELOG").write_text(message)
        _git(self.publisher, "add", "-A")
        _git(self.publisher, "commit", "-m", message)
        _git(self.publisher, "push", "origin", "main")
        return _git(self.publisher, "rev-parse", "HEAD")

    def run(self, *args: str, **fake: str) -> subprocess.CompletedProcess[str]:
        env = {"PATH": str(self.bin), "HOME": str(self.repo), "FAKE_LOG": str(self.log)}
        env.update({f"FAKE_{k.upper()}": v for k, v in fake.items()})
        return subprocess.run(  # noqa: S603 — the script under test
            [str(self.bin / "bash"), str(self.repo / "update.sh"), *args],
            cwd=self.repo,
            env=env,
            capture_output=True,
            text=True,
            timeout=60,
        )

    @property
    def head(self) -> str:
        return _git(self.repo, "rev-parse", "HEAD")

    @property
    def calls(self) -> list[str]:
        return self.log.read_text().splitlines()

    def index(self, prefix: str) -> int:
        return next(i for i, c in enumerate(self.calls) if c.startswith(prefix))

    def called(self, prefix: str) -> bool:
        return any(c.startswith(prefix) for c in self.calls)

    @property
    def backups(self) -> list[Path]:
        folder = self.repo / "backups"
        return sorted(folder.glob("*.sql")) if folder.exists() else []


@pytest.fixture
def deploy(tmp_path: Path) -> Deployment:
    return Deployment(tmp_path)


def _out(result: subprocess.CompletedProcess[str]) -> str:
    return result.stdout + result.stderr


def _ok(result: subprocess.CompletedProcess[str]) -> str:
    assert result.returncode == 0, _out(result)
    return _out(result)


# ── The normal update ─────────────────────────────────────────────────────────


def test_an_update_backs_up_then_pulls_then_restarts(deploy: Deployment):
    new = deploy.publish("Add a feature")
    out = _ok(deploy.run())
    assert deploy.head == new
    assert deploy.index("docker compose exec -T postgres pg_dump") < deploy.index(
        "docker compose up -d --build --wait"
    )
    assert "Add a feature" in out  # what's coming
    [backup] = deploy.backups
    assert backup.read_text().startswith("-- PostgreSQL database dump")


def test_the_backup_can_be_restored_over_the_database(deploy: Deployment):
    """--clean --if-exists: a plain dump fails on every table that exists."""
    deploy.publish("Add a feature")
    _ok(deploy.run())
    assert (
        "docker compose exec -T postgres pg_dump --clean --if-exists -U fitman fitman"
        in deploy.calls
    )


def test_the_migrations_that_ran_are_shown(deploy: Deployment):
    deploy.publish("Add a column")
    line = "INFO  [alembic.runtime.migration] Running upgrade j6k8 -> k7l9, add muscle mass"
    out = _ok(deploy.run(migrations=line))
    assert "Running upgrade j6k8 -> k7l9, add muscle mass" in out


def test_nothing_new_changes_nothing(deploy: Deployment):
    out = _ok(deploy.run())
    assert "Already up to date" in out
    assert not deploy.called("docker compose up")
    assert deploy.backups == []


def test_rebuild_restarts_even_when_up_to_date(deploy: Deployment):
    _ok(deploy.run("--rebuild"))
    assert deploy.called("docker compose up -d --build --wait")
    assert len(deploy.backups) == 1


def test_a_stopped_stack_is_updated_without_a_backup(deploy: Deployment):
    new = deploy.publish("Add a feature")
    out = _ok(deploy.run(stopped="1"))
    assert "isn't running" in out
    assert deploy.backups == []
    assert deploy.head == new


# ── Stopping before anything changes ──────────────────────────────────────────


def test_local_changes_stop_it(deploy: Deployment):
    deploy.publish("Add a feature")
    before = deploy.head
    (deploy.repo / "docker-compose.yml").write_text("# edited by hand\n")
    result = deploy.run()
    assert result.returncode != 0
    assert "docker-compose.yml" in _out(result)
    assert deploy.head == before
    assert deploy.backups == []


def test_env_does_not_count_as_a_local_change(deploy: Deployment):
    """.env and backups/ are the deployment's own; git ignores them."""
    deploy.publish("Add a feature")
    (deploy.repo / "backups").mkdir()
    (deploy.repo / "backups" / "old.sql").write_text("x")
    _ok(deploy.run())


def test_a_diverged_clone_stops_it(deploy: Deployment):
    deploy.publish("Add a feature")
    (deploy.repo / "LOCAL").write_text("x")
    _git(deploy.repo, "add", "LOCAL")
    _git(deploy.repo, "commit", "-m", "a local commit")
    before = deploy.head
    result = deploy.run()
    assert result.returncode != 0
    assert "diverged" in _out(result)
    assert deploy.head == before and deploy.backups == []


def test_a_missing_required_setting_stops_it_before_anything_changes(
    deploy: Deployment,
):
    """Checked against the new version before it is merged, so running
    update.sh again after setting it just works."""
    compose = (ROOT / "docker-compose.yml").read_text()
    assert compose.count("\nservices:\n") == 1
    compose = compose.replace(
        "\nservices:\n",
        "\nservices:\n  extra:\n    image: busybox\n    environment:\n"
        "      NEW_REQUIRED: ${NEW_REQUIRED:?set it}\n\n",
    )
    deploy.publish("Require a setting", {"docker-compose.yml": compose})
    before = deploy.head
    result = deploy.run()
    assert result.returncode != 0
    assert "NEW_REQUIRED" in _out(result)
    assert "./setup.sh" in _out(result)
    assert deploy.head == before
    assert deploy.backups == [] and not deploy.called("docker compose up")

    (deploy.repo / ".env").write_text(
        (deploy.repo / ".env").read_text() + "NEW_REQUIRED=yes\n"
    )
    _ok(deploy.run())


def test_new_optional_settings_are_listed(deploy: Deployment):
    example = (ROOT / ".env.example").read_text() + "\n# A new knob.\n# NEW_OPTION=1\n"
    deploy.publish("Add an option", {".env.example": example})
    out = _ok(deploy.run())
    assert "NEW_OPTION" in out


def test_an_empty_backup_stops_it(deploy: Deployment):
    deploy.publish("Add a feature")
    before = deploy.head
    result = deploy.run(empty_dump="1")
    assert result.returncode != 0
    assert "backup" in _out(result).lower()
    assert deploy.head == before
    assert not deploy.called("docker compose up")


# ── A failed start ────────────────────────────────────────────────────────────


def test_a_failed_start_says_how_to_go_back(deploy: Deployment):
    before = deploy.head
    deploy.publish("Break something")
    result = deploy.run(up_exit="1")
    assert result.returncode != 0
    out = _out(result)
    [backup] = deploy.backups
    assert f"git reset --hard {before[:12]}" in out
    assert f"backups/{backup.name}" in out
    assert "docker compose logs" in out
    assert "psql" in out


# ── The script itself ─────────────────────────────────────────────────────────


def test_it_is_executable():
    assert os.access(SCRIPT, os.X_OK)


def test_shellcheck_finds_nothing():
    # The pinned ShellCheck from shellcheck-py, as in test_setup_script.py.
    shellcheck = str(Path(sys.executable).parent / "shellcheck")
    result = subprocess.run(  # noqa: S603 — fixed arguments
        [shellcheck, str(SCRIPT)], capture_output=True, text=True
    )
    assert result.returncode == 0, result.stdout


def test_readme_updates_with_the_script():
    commands = README[README.index("### Everyday commands") :][:2000]
    assert "./update.sh" in commands
