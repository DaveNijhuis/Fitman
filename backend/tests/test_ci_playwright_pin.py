"""The Playwright browser image must follow the installed package (#275).

Playwright requires its library and browser binaries to match. The version was
pinned in two places with nothing keeping them in agreement: the image tag in
ci.yml and the dependency in e2e/package.json. Dependabot bumps the package but
cannot see an image tag inside a `run:` block, so the E2E job failed with

    Executable doesn't exist at /ms-playwright/chromium_headless_shell-1243/...

which names a missing binary rather than the mismatch that caused it.
"""

import re
from pathlib import Path
from typing import Any

import yaml

_ROOT = Path(__file__).resolve().parents[2]
_CI = _ROOT / ".github" / "workflows" / "ci.yml"

_PLAYWRIGHT_IMAGE = "mcr.microsoft.com/playwright"
_HARDCODED_TAG = re.compile(rf"{re.escape(_PLAYWRIGHT_IMAGE)}:v\d+\.\d+")


def _e2e_steps() -> list[dict[str, Any]]:
    workflow = yaml.safe_load(_CI.read_text())
    return workflow["jobs"]["e2e"]["steps"]


def _runs() -> list[str]:
    return [str(step["run"]) for step in _e2e_steps() if "run" in step]


def _index_of_run(needle: str) -> int:
    for i, command in enumerate(_runs()):
        if needle in command:
            return i
    return -1


def test_playwright_image_tag_is_not_hardcoded() -> None:
    """A literal version in the workflow cannot track the package."""
    found = _HARDCODED_TAG.findall(_CI.read_text())
    assert not found, f"hardcoded Playwright image tag(s): {found}"


def test_playwright_version_is_resolved_from_the_installed_package() -> None:
    """Reading the installed package is what actually runs, unlike the
    declared range in package.json."""
    assert _index_of_run("@playwright/test/package.json") != -1


def test_resolution_happens_before_the_tests_run() -> None:
    resolve = _index_of_run("@playwright/test/package.json")
    run_tests = _index_of_run(_PLAYWRIGHT_IMAGE)
    assert resolve != -1
    assert run_tests > resolve


def test_image_reference_uses_the_resolved_version() -> None:
    """The docker run must consume the resolved value, not a literal."""
    commands = [c for c in _runs() if _PLAYWRIGHT_IMAGE in c]
    assert commands, "no step runs the Playwright image"
    assert any("steps." in c and "outputs." in c for c in commands)


def test_the_resolving_step_runs_in_the_e2e_directory() -> None:
    """@playwright/test is installed under e2e/node_modules, not the repo root."""
    for step in _e2e_steps():
        if "run" in step and "@playwright/test/package.json" in str(step["run"]):
            assert step.get("working-directory") == "e2e"
            return
    raise AssertionError("no step resolves the Playwright version")
