"""Static checks that the ruff and mypy gates are configured strictly (#222)."""

from pathlib import Path
from typing import Any

import tomllib

_PYPROJECT = Path(__file__).resolve().parents[1] / "pyproject.toml"


def _config() -> dict[str, Any]:
    return tomllib.loads(_PYPROJECT.read_text())


def _ruff_lint() -> dict[str, Any]:
    return _config()["tool"]["ruff"]["lint"]


def test_ruff_selects_bugbear():
    """B catches mutable default arguments and loop-variable capture."""
    assert "B" in _ruff_lint()["select"]


def test_ruff_selects_bandit():
    """S catches hardcoded secrets and unsafe subprocess usage."""
    assert "S" in _ruff_lint()["select"]


def test_bugbear_exempts_fastapi_depends():
    """Depends() in a default is the FastAPI idiom, not a B008 defect."""
    immutable = _ruff_lint()["flake8-bugbear"]["extend-immutable-calls"]
    assert "fastapi.Depends" in immutable


def test_bandit_assert_rule_disabled_for_tests():
    """S101 bans assert; pytest is built on it, so tests must be exempt."""
    per_file = _ruff_lint()["per-file-ignores"]
    test_globs = [glob for glob in per_file if "tests" in glob]
    assert test_globs, "no per-file-ignores entry covers the tests directory"
    assert any("S101" in per_file[glob] for glob in test_globs)


def test_mypy_disallows_untyped_defs():
    """Without this, an unannotated function passes the type gate silently."""
    assert _config()["tool"]["mypy"]["disallow_untyped_defs"] is True


def _tests_override() -> dict[str, Any]:
    overrides = _config()["tool"]["mypy"].get("overrides", [])
    for override in overrides:
        module = override["module"]
        modules = [module] if isinstance(module, str) else module
        if any(m.startswith("tests") for m in modules):
            return override
    raise AssertionError("no [[tool.mypy.overrides]] entry targets tests.*")


def test_tests_are_exempt_from_annotation_ceremony():
    """`-> None` on 263 test functions carries no type information."""
    assert _tests_override()["disallow_untyped_defs"] is False


def test_test_bodies_are_still_type_checked():
    """The flag that actually finds bugs: mypy skips unannotated bodies by default,
    so without this the entire test suite goes type-unverified."""
    assert _tests_override()["check_untyped_defs"] is True
