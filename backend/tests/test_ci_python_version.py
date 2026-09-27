"""CI must test the backend on the Python production runs (#361).

The backend job made its venv with a bare `uv venv`, which takes the runner's
system Python — 3.12 on ubuntu-latest — while the production image, mypy and
the README are all 3.11. That held until a dependency resolved differently on
the two: `deprecated` 3.0.0 requires 3.12 and uses its `type` statement, so
CI's venv got it and mypy, parsing for 3.11, failed on a file inside .venv.

Production is the reference; the other two must follow it.
"""

import re
from pathlib import Path

import tomllib
import yaml

_ROOT = Path(__file__).resolve().parents[2]
_CI = _ROOT / ".github" / "workflows" / "ci.yml"
_DOCKERFILE = _ROOT / "backend" / "Dockerfile"
_PYPROJECT = _ROOT / "backend" / "pyproject.toml"


def _production_python() -> str:
    match = re.search(r"^FROM python:(\d+\.\d+)", _DOCKERFILE.read_text(), re.M)
    assert match, "backend/Dockerfile has no python:X.Y base image"
    return match.group(1)


def _ci_venv_commands() -> list[str]:
    steps = yaml.safe_load(_CI.read_text())["jobs"]["backend"]["steps"]
    return [
        line.strip()
        for step in steps
        for line in str(step.get("run", "")).splitlines()
        if line.strip().startswith("uv venv")
    ]


def test_the_backend_job_makes_a_venv() -> None:
    assert _ci_venv_commands(), "no `uv venv` in the backend job"


def test_ci_venv_uses_the_production_python() -> None:
    production = _production_python()
    for command in _ci_venv_commands():
        match = re.search(r"--python[ =](\S+)", command)
        assert match, f"`{command}` takes the runner's Python, not {production}"
        assert match.group(1) == production


def test_mypy_parses_for_the_production_python() -> None:
    mypy = tomllib.loads(_PYPROJECT.read_text())["tool"]["mypy"]
    assert mypy["python_version"] == _production_python()
