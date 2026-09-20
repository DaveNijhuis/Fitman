"""Write the app's OpenAPI document to backend/openapi.json (#268).

The frontend generates its API types from this file, so it is the contract
between the two halves of the app rather than a build artefact. Committing it
means a response-shape change shows up as a reviewable diff, and
tests/test_openapi_snapshot.py fails if it is not regenerated.

Run from the backend directory:

    python -m scripts.dump_openapi

Importing main pulls in database.py, which requires DATABASE_URL, and main's
own startup check requires SECRET_KEY. Neither is used to produce the schema,
so placeholders are supplied when they are absent — dumping the contract must
not need a database.
"""

import json
import os
from pathlib import Path

os.environ.setdefault(
    "DATABASE_URL", "postgresql://schema:schema@localhost:5432/schema"
)
os.environ.setdefault("SECRET_KEY", "openapi-dump-placeholder-not-a-real-secret")

from main import app  # noqa: E402  — must follow the environment defaults above

OUTPUT = Path(__file__).resolve().parents[1] / "openapi.json"


def main() -> None:
    schema = app.openapi()
    OUTPUT.write_text(json.dumps(schema, indent=2, sort_keys=True) + "\n")
    paths = len(schema.get("paths", {}))
    models = len(schema.get("components", {}).get("schemas", {}))
    print(
        f"wrote {OUTPUT.relative_to(OUTPUT.parents[1])}: {paths} paths, {models} schemas"
    )


if __name__ == "__main__":
    main()
