"""The committed OpenAPI snapshot must match the live app (#268).

The frontend derives its response types from openapi.json rather than
hand-written interfaces. That only prevents drift if the snapshot itself stays
current, so a response-shape change that is not regenerated fails here — at the
commit that makes it, rather than as an undefined in a browser weeks later.

#227 changed GET /api/cardio and GET /api/measurements from a bare array to a
paginated envelope. The frontend kept its array types, every call site kept
compiling because client.ts casts rather than checks, and #267 was the result.
"""

import json
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[2]
_SNAPSHOT = _ROOT / "backend" / "openapi.json"

_REGENERATE = "Run: python -m scripts.dump_openapi (see README)"


def _live_schema() -> dict[str, Any]:
    from main import app

    schema: dict[str, Any] = app.openapi()
    return schema


def _snapshot() -> dict[str, Any]:
    data: dict[str, Any] = json.loads(_SNAPSHOT.read_text())
    return data


def test_snapshot_exists() -> None:
    assert _SNAPSHOT.is_file(), f"openapi.json is missing. {_REGENERATE}"


def test_snapshot_matches_the_live_app() -> None:
    """The whole contract, not just the paths — field types matter most."""
    assert _snapshot() == _live_schema(), (
        f"openapi.json is out of date with the FastAPI app. {_REGENERATE}"
    )


def test_paginated_endpoints_are_in_the_snapshot() -> None:
    """Regression guard for the shapes that caused #267."""
    paths = _snapshot()["paths"]
    for path in ("/api/cardio", "/api/measurements"):
        schema = paths[path]["get"]["responses"]["200"]["content"]["application/json"][
            "schema"
        ]
        assert "$ref" in schema, f"{path} GET has no referenced response schema"
        assert schema["$ref"].endswith("Page"), (
            f"{path} GET no longer returns a paginated envelope: {schema['$ref']}"
        )


def test_ci_checks_the_generated_types_are_current() -> None:
    """The snapshot test above guards backend -> openapi.json. This guards
    openapi.json -> schema.d.ts, so the chain is unbroken end to end."""
    import yaml

    workflow = yaml.safe_load((_ROOT / ".github" / "workflows" / "ci.yml").read_text())
    runs = [
        str(step["run"])
        for step in workflow["jobs"]["frontend"]["steps"]
        if "run" in step
    ]
    assert any("generate:api" in r and "git diff" in r for r in runs), (
        "no CI step regenerates the API types and fails on a diff"
    )
