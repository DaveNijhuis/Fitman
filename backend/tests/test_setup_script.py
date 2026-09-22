"""setup.sh: a guided first-time installation (#349).

The script runs in a temporary copy of the repo. PATH holds fake docker, ss,
sudo and tailscale commands, which log their calls, plus the few real tools
the script needs. So nothing is installed or started, and the real Docker is
out of reach. The fakes are steered through environment variables:

    FAKE_TAKEN     ports something else listens on ("80 5433")
    FAKE_NO_DAEMON set: `docker info` fails (no daemon access)
    FAKE_VOLUME    set: the project's db_data volume exists
    FAKE_RUNNING   set: the stack is already running
    FAKE_UP_EXIT   exit code of `docker compose up`
    FAKE_SS_ANONYMOUS set: ss shows no process names, as without root
    FAKE_CONTAINER `docker ps` output: "name ports"
"""

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "setup.sh"
README = (ROOT / "README.md").read_text()

# Real tools the script may use; anything else is deliberately unavailable.
TOOLS = (
    "bash sh env cat cp mv rm sed grep tr od head tail basename dirname "
    "mktemp awk cut printf sort seq wc chmod tee id"
).split()

FAKE_DOCKER = r"""#!/bin/bash
echo "docker $*" >> "$FAKE_LOG"
case "$*" in
  "compose version"*) echo "Docker Compose version v2.40.0" ;;
  "info"*) [ -z "$FAKE_NO_DAEMON" ] || { echo "permission denied" >&2; exit 1; } ;;
  "volume inspect"*) [ -n "$FAKE_VOLUME" ] || exit 1 ;;
  "compose ps"*) [ -z "$FAKE_RUNNING" ] || echo "fitman-frontend-1" ;;
  "compose up"*) exit "${FAKE_UP_EXIT:-0}" ;;
  "ps --format"*) [ -z "$FAKE_CONTAINER" ] || printf '%s\n' "$FAKE_CONTAINER" ;;
esac
exit 0
"""

FAKE_SS = r"""#!/bin/bash
echo "ss $*" >> "$FAKE_LOG"
port="${@: -1}"; port="${port##*:}"
for taken in $FAKE_TAKEN; do
  if [ "$taken" = "$port" ]; then
    if [ -n "$FAKE_SS_ANONYMOUS" ]; then
      echo "LISTEN 0 4096 *:$port *:*"  # no process names without root
    else
      echo "LISTEN 0 4096 *:$port *:* users:((\"caddy\",pid=812,fd=7))"
    fi
  fi
done
exit 0
"""

FAKE_SUDO = r"""#!/bin/bash
echo "sudo $*" >> "$FAKE_LOG"
exec "$@"
"""

FAKE_TAILSCALE = r"""#!/bin/bash
echo "tailscale $*" >> "$FAKE_LOG"
exit 0
"""


class Setup:
    def __init__(self, tmp_path: Path, tailscale: bool = False, docker: bool = True):
        self.repo = tmp_path / "Fitman"  # the project name comes from this
        self.repo.mkdir()
        for name in ("setup.sh", ".env.example", "docker-compose.yml"):
            shutil.copy(ROOT / name, self.repo / name)
        self.bin = tmp_path / "bin"
        self.bin.mkdir()
        for tool in TOOLS:
            real = shutil.which(tool)
            if real:
                (self.bin / tool).symlink_to(real)
        fakes = {"ss": FAKE_SS, "sudo": FAKE_SUDO}
        if docker:
            fakes["docker"] = FAKE_DOCKER
        if tailscale:
            fakes["tailscale"] = FAKE_TAILSCALE
        for name, body in fakes.items():
            path = self.bin / name
            path.write_text(body)
            path.chmod(0o755)
        self.log = tmp_path / "calls.log"
        self.log.touch()

    def run(
        self, *args: str, stdin: str = "", **fake: str
    ) -> subprocess.CompletedProcess[str]:
        env = {"PATH": str(self.bin), "HOME": str(self.repo), "FAKE_LOG": str(self.log)}
        env.update({f"FAKE_{k.upper()}": v for k, v in fake.items()})
        return subprocess.run(  # noqa: S603 — the script under test
            [str(self.bin / "bash"), str(self.repo / "setup.sh"), *args],
            cwd=self.repo,
            env=env,
            input=stdin,
            capture_output=True,
            text=True,
            timeout=30,
        )

    @property
    def env(self) -> dict[str, str]:
        values = {}
        for line in (self.repo / ".env").read_text().splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                key, _, value = line.partition("=")
                values[key.strip()] = value.strip()
        return values

    @property
    def calls(self) -> list[str]:
        return self.log.read_text().splitlines()


@pytest.fixture
def setup(tmp_path: Path) -> Setup:
    return Setup(tmp_path)


def _ok(result: subprocess.CompletedProcess[str]) -> str:
    assert result.returncode == 0, result.stdout + result.stderr
    return result.stdout + result.stderr


# ── A fresh install ───────────────────────────────────────────────────────────


def test_fresh_install_generates_hex_secrets(setup: Setup):
    _ok(setup.run("--yes"))
    env = setup.env
    assert re.fullmatch(r"[0-9a-f]{64}", env["SECRET_KEY"])
    assert re.fullmatch(r"[0-9a-f]{48}", env["POSTGRES_PASSWORD"])


def test_fresh_install_starts_the_stack_and_says_where_to_go(setup: Setup):
    out = _ok(setup.run("--yes"))
    assert "docker compose up -d --build --wait" in setup.calls
    assert "http://localhost/setup" in out


def test_defaults_when_nothing_is_in_the_way(setup: Setup):
    _ok(setup.run("--yes"))
    env = setup.env
    assert (env["FITMAN_HTTP_PORT"], env["FITMAN_DB_PORT"]) == ("80", "5433")
    assert env["SCALE_ENABLED"] == "false"


def test_the_rest_of_env_example_is_kept(setup: Setup):
    _ok(setup.run("--yes"))
    text = (setup.repo / ".env").read_text()
    assert "JWT_EXPIRE_DAYS=7" in text
    assert "# ── Smart scale" in text  # comments survive


# ── An existing .env ──────────────────────────────────────────────────────────


def _existing(setup: Setup, body: str) -> None:
    (setup.repo / ".env").write_text(body)


def test_an_existing_env_keeps_its_secrets_and_settings(setup: Setup):
    """A new database password would lock the app out of its database, and a
    new secret key logs everyone out."""
    _existing(setup, "SECRET_KEY=aa11\nPOSTGRES_PASSWORD=bb22\nJWT_EXPIRE_DAYS=3\n")
    _ok(setup.run("--yes", volume="1"))
    env = setup.env
    assert (env["SECRET_KEY"], env["POSTGRES_PASSWORD"]) == ("aa11", "bb22")
    assert env["JWT_EXPIRE_DAYS"] == "3"


def test_the_placeholder_secret_key_is_replaced(setup: Setup):
    _existing(setup, "SECRET_KEY=change-me\nPOSTGRES_PASSWORD=bb22\n")
    _ok(setup.run("--yes"))
    assert re.fullmatch(r"[0-9a-f]{64}", setup.env["SECRET_KEY"])


def test_a_missing_db_password_with_an_existing_database_stops(setup: Setup):
    """Postgres only reads the password when it creates the database: a new
    one would lock the app out. That's the README's manual procedure."""
    _existing(setup, "SECRET_KEY=aa11\n")
    result = setup.run("--yes", volume="1")
    assert result.returncode != 0
    assert "Changing the database password" in result.stdout + result.stderr
    assert "POSTGRES_PASSWORD" not in setup.env
    assert not any(c.startswith("docker compose up") for c in setup.calls)


# ── Ports ─────────────────────────────────────────────────────────────────────


def test_a_taken_web_port_is_reported_and_moved(setup: Setup):
    out = _ok(setup.run("--yes", taken="80"))
    assert "caddy" in out  # what holds it
    assert setup.env["FITMAN_HTTP_PORT"] == "8081"
    assert "http://localhost:8081/setup" in out


def test_a_port_held_by_a_container_names_the_container(setup: Setup):
    """Without root, ss can't say who listens; Docker can, for its containers."""
    out = _ok(
        setup.run(
            "--yes",
            taken="80",
            ss_anonymous="1",
            container="caddy 0.0.0.0:80->80/tcp, [::]:80->80/tcp, 0.0.0.0:443->443/tcp",
        )
    )
    assert "the Docker container caddy" in out


def test_an_unknown_holder_is_reported_honestly(setup: Setup):
    out = _ok(setup.run("--yes", taken="80", ss_anonymous="1"))
    assert "run with sudo to see which" in out
    assert setup.env["FITMAN_HTTP_PORT"] == "8081"


def test_a_taken_database_port_is_moved(setup: Setup):
    _ok(setup.run("--yes", taken="5433"))
    assert setup.env["FITMAN_DB_PORT"] == "5434"


def test_local_only_binds_to_localhost(setup: Setup):
    _ok(setup.run("--yes", "--local-only"))
    assert setup.env["FITMAN_HTTP_PORT"] == "127.0.0.1:80"


def test_an_explicit_port_is_used(setup: Setup):
    _ok(setup.run("--yes", "--http-port", "9000"))
    assert setup.env["FITMAN_HTTP_PORT"] == "9000"


def test_an_explicit_port_that_is_taken_stops(setup: Setup):
    result = setup.run("--yes", "--http-port", "9000", taken="9000")
    assert result.returncode != 0
    assert "9000" in result.stdout + result.stderr


def test_a_running_stack_is_not_in_its_own_way(setup: Setup):
    """Re-running setup: port 80 is held by Fitman itself, not a conflict."""
    _existing(setup, "SECRET_KEY=aa11\nPOSTGRES_PASSWORD=bb22\nFITMAN_HTTP_PORT=80\n")
    _ok(setup.run("--yes", taken="80 5433", running="1", volume="1"))
    assert (setup.env["FITMAN_HTTP_PORT"], setup.env["FITMAN_DB_PORT"]) == (
        "80",
        "5433",
    )


# ── Scale and HTTPS ───────────────────────────────────────────────────────────


def test_the_scale_can_be_enabled(setup: Setup):
    _ok(setup.run("--yes", "--scale"))
    assert setup.env["SCALE_ENABLED"] == "true"


def test_tailscale_serve_is_only_run_when_asked(tmp_path: Path):
    s = Setup(tmp_path, tailscale=True)
    _ok(s.run("--yes"))
    assert not any("tailscale serve" in c for c in s.calls)


def test_tailscale_serve_forwards_https_to_the_web_port(tmp_path: Path):
    s = Setup(tmp_path, tailscale=True)
    _ok(s.run("--yes", "--tailscale-serve", "--local-only", taken="80"))
    assert "sudo tailscale serve --bg 8081" in s.calls


def test_tailscale_serve_moves_off_a_taken_443(tmp_path: Path):
    s = Setup(tmp_path, tailscale=True)
    _ok(s.run("--yes", "--tailscale-serve", taken="80 443"))
    assert "sudo tailscale serve --bg --https=8443 8081" in s.calls


# ── Interactive ───────────────────────────────────────────────────────────────


def test_questions_are_answered_from_the_keyboard(setup: Setup):
    """Web port (an invalid answer is asked again), reachable from other
    devices, smart scale."""
    _ok(setup.run(stdin="abc\n8085\nn\ny\n"))
    env = setup.env
    assert env["FITMAN_HTTP_PORT"] == "127.0.0.1:8085"
    assert env["SCALE_ENABLED"] == "true"


def test_enter_takes_the_defaults(setup: Setup):
    _ok(setup.run(stdin="\n\n\n"))
    env = setup.env
    assert (env["FITMAN_HTTP_PORT"], env["SCALE_ENABLED"]) == ("80", "false")


# ── Prerequisites ─────────────────────────────────────────────────────────────


def test_without_docker_it_stops_before_writing_anything(tmp_path: Path):
    s = Setup(tmp_path, docker=False)
    result = s.run("--yes")
    assert result.returncode != 0
    assert "https://docs.docker.com" in result.stdout + result.stderr
    assert not (s.repo / ".env").exists()


def test_without_daemon_access_it_stops_before_writing_anything(setup: Setup):
    result = setup.run("--yes", no_daemon="1")
    assert result.returncode != 0
    assert "docker group" in result.stdout + result.stderr
    assert not (setup.repo / ".env").exists()


def test_a_failed_start_says_where_to_look(setup: Setup):
    result = setup.run("--yes", up_exit="1")
    assert result.returncode != 0
    assert "docker compose logs" in result.stdout + result.stderr


# ── The script itself ─────────────────────────────────────────────────────────


def test_it_is_executable():
    assert os.access(SCRIPT, os.X_OK)


def test_shellcheck_finds_nothing():
    # From shellcheck-py (requirements-dev.txt), next to this Python.
    shellcheck = shutil.which("shellcheck") or str(
        Path(sys.executable).parent / "shellcheck"
    )
    result = subprocess.run(  # noqa: S603 — fixed arguments
        [shellcheck, str(SCRIPT)], capture_output=True, text=True
    )
    assert result.returncode == 0, result.stdout


def test_readme_leads_the_install_with_the_script():
    deploy = README[README.index("### 4. Deploy Fitman") : README.index("### 5.")]
    assert "./setup.sh" in deploy
