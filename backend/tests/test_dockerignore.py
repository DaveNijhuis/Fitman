"""Static checks that backend/.dockerignore excludes security-sensitive and unnecessary paths."""

from pathlib import Path

_DOCKERIGNORE = Path(__file__).resolve().parents[1] / ".dockerignore"


def _entries() -> set[str]:
    return {
        line.strip()
        for line in _DOCKERIGNORE.read_text().splitlines()
        if line.strip() and not line.startswith("#")
    }


def test_dockerignore_exists():
    assert _DOCKERIGNORE.is_file()


def test_env_file_excluded():
    """Secrets must never be baked into the production image."""
    assert ".env" in _entries()


def test_venv_excluded():
    """.venv would shadow the pip-installed packages inside the image."""
    assert ".venv" in _entries()


def test_tests_directory_excluded():
    """Test code and fixtures have no place in a production image."""
    assert "tests/" in _entries()


def test_pycache_excluded():
    assert "__pycache__/" in _entries()


def test_dev_requirements_excluded():
    assert "requirements-dev.txt" in _entries()
