"""The frontend images must be built from the lockfile, not the host (#315).

frontend/ had no .dockerignore, so `COPY . .` in both Dockerfiles copied the
host's node_modules over the dependencies just installed in the image. After
Dependabot bumps were pulled without a local `npm install`, the dev container
crash-looped on a vite 8.3.0 / rolldown 1.0.3 mix that matched neither the
lockfile nor the host. The prod build had the same exposure, where a mixed
tree can build successfully and ship.
"""

from pathlib import Path

import pytest

FRONTEND_DIR = Path(__file__).resolve().parents[2] / "frontend"
_DOCKERIGNORE = FRONTEND_DIR / ".dockerignore"
_DOCKERFILES = ["Dockerfile", "Dockerfile.prod"]


def _entries() -> set[str]:
    return {
        line.strip()
        for line in _DOCKERIGNORE.read_text().splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }


def _instructions(dockerfile: str) -> list[str]:
    """Each instruction as one whitespace-normalised line."""
    lines = (FRONTEND_DIR / dockerfile).read_text().splitlines()
    return [
        " ".join(line.split())
        for line in lines
        if line.strip() and not line.lstrip().startswith("#")
    ]


def test_dockerignore_exists():
    assert _DOCKERIGNORE.is_file()


@pytest.mark.parametrize(
    ("entry", "why"),
    [
        ("node_modules", "host packages would overwrite the lockfile install"),
        ("dist", "a stale host build must not reach the image"),
        ("coverage", "test output has no place in an image"),
        (".vite", "Vite's dependency cache is host-specific"),
        (".env*", "secrets must never enter the build context"),
    ],
)
def test_dockerignore_excludes(entry, why):
    assert entry in _entries(), f"{entry} not ignored: {why}"


@pytest.mark.parametrize(
    "needed",
    ["package.json", "package-lock.json", "src", "index.html", "nginx.conf"],
)
def test_dockerignore_keeps_what_the_build_needs(needed):
    """Guard against over-ignoring: these are all read by a Dockerfile."""
    assert needed not in _entries()
    assert f"{needed}/" not in _entries()


@pytest.mark.parametrize("dockerfile", _DOCKERFILES)
def test_dependencies_install_from_the_lockfile(dockerfile):
    """npm install may re-resolve and ignore the lockfile; npm ci may not."""
    steps = _instructions(dockerfile)
    assert "RUN npm ci" in steps
    assert not any(s.startswith("RUN npm install") for s in steps)


@pytest.mark.parametrize("dockerfile", _DOCKERFILES)
def test_install_runs_before_the_source_copy(dockerfile):
    """Manifests first, install, then source — the order the ignore file protects."""
    steps = _instructions(dockerfile)
    manifests = steps.index("COPY package*.json ./")
    install = steps.index("RUN npm ci")
    source = steps.index("COPY . .")
    assert manifests < install < source
