"""Static checks that CI scans dependencies for known CVEs and Dependabot is configured."""

from pathlib import Path
from typing import Any

import yaml

_ROOT = Path(__file__).resolve().parents[2]
_CI = _ROOT / ".github" / "workflows" / "ci.yml"
_DEPENDABOT = _ROOT / ".github" / "dependabot.yml"
_DEV_REQUIREMENTS = Path(__file__).resolve().parents[1] / "requirements-dev.txt"


def _steps(job: str) -> list[dict[str, Any]]:
    workflow = yaml.safe_load(_CI.read_text())
    return workflow["jobs"][job]["steps"]


def _run_commands(job: str) -> list[str]:
    return [step["run"] for step in _steps(job) if "run" in step]


def _index_of_run(job: str, needle: str) -> int:
    """Position of the first step whose run block contains needle, or -1."""
    for i, command in enumerate(_run_commands(job)):
        if needle in command:
            return i
    return -1


def test_backend_job_runs_pip_audit():
    """Python dependencies must be scanned for known CVEs."""
    assert _index_of_run("backend", "pip-audit") != -1


def test_pip_audit_runs_after_dependencies_are_installed():
    """pip-audit resolves against the installed venv, so install must come first."""
    install = _index_of_run("backend", "uv pip install")
    audit = _index_of_run("backend", "pip-audit")
    assert install != -1
    assert audit > install


def test_frontend_job_runs_npm_audit():
    """npm packages must be scanned for known CVEs."""
    assert _index_of_run("frontend", "npm audit") != -1


def test_npm_audit_gates_on_high_severity_only():
    """Moderate advisories in the transitive dev tree would make the gate pure noise."""
    commands = [c for c in _run_commands("frontend") if "npm audit" in c]
    assert commands
    assert any("--audit-level=high" in c for c in commands)


def test_npm_audit_runs_after_dependencies_are_installed():
    install = _index_of_run("frontend", "npm ci")
    audit = _index_of_run("frontend", "npm audit")
    assert install != -1
    assert audit > install


def test_pip_audit_pinned_in_dev_requirements():
    """Every dev dependency is pinned; an unpinned scanner would drift silently."""
    pins = {
        line.strip().split("==")[0]
        for line in _DEV_REQUIREMENTS.read_text().splitlines()
        if "==" in line
    }
    assert "pip-audit" in pins


def test_dependabot_config_exists():
    assert _DEPENDABOT.is_file()


def test_dependabot_covers_backend_and_both_npm_directories():
    """Backend, frontend and the E2E suite each have their own lockfile to keep current."""
    config = yaml.safe_load(_DEPENDABOT.read_text())
    covered = {
        (entry["package-ecosystem"], entry["directory"]) for entry in config["updates"]
    }
    assert ("pip", "/backend") in covered
    assert ("npm", "/frontend") in covered
    assert ("npm", "/e2e") in covered


def test_dependabot_updates_are_scheduled_weekly():
    config = yaml.safe_load(_DEPENDABOT.read_text())
    assert config["updates"]
    for entry in config["updates"]:
        assert entry["schedule"]["interval"] == "weekly"


def test_dependabot_targets_the_dev_integration_branch():
    """Dependency PRs must go through dev, not straight to main (#276).

    Without target-branch, Dependabot defaults to the repository default
    branch, inverting the feature -> dev -> main flow and putting untested
    dependency changes on the production branch.
    """
    config = yaml.safe_load(_DEPENDABOT.read_text())
    assert config["updates"]
    for entry in config["updates"]:
        assert entry.get("target-branch") == "dev", (
            f"{entry['package-ecosystem']} {entry['directory']} does not target dev. "
            "The key is target-branch (hyphen); Dependabot silently ignores "
            "unrecognised keys such as target_branch."
        )
