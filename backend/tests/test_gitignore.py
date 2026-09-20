"""Generated artefacts must be ignored and untracked (#247).

backend/.coverage is a SQLite file rewritten by every pytest run. While it is
tracked it appears as a modified file on any branch where tests were run, and
lands in review diffs as binary churn unrelated to the change.
"""

import subprocess
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_GITIGNORE = _ROOT / ".gitignore"
_COVERAGE = _ROOT / "backend" / ".coverage"


def _entries() -> set[str]:
    return {
        line.strip()
        for line in _GITIGNORE.read_text().splitlines()
        if line.strip() and not line.startswith("#")
    }


def test_coverage_file_is_gitignored():
    assert ".coverage" in _entries()


def test_coverage_data_files_are_gitignored():
    """pytest-cov writes .coverage.<host>.<pid> shards under xdist."""
    assert ".coverage.*" in _entries()


def test_coverage_file_is_not_tracked():
    """Ignoring it does nothing on its own — it must also leave the index."""
    result = subprocess.run(
        ["git", "ls-files", "--error-unmatch", "backend/.coverage"],
        cwd=_ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0, (
        "backend/.coverage is still tracked; run: git rm --cached backend/.coverage"
    )
