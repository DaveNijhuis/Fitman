# Testing

## Philosophy

Fitman is developed using **Test-Driven Development (TDD)**. For every bug fix or new feature:

1. **Red** — write a failing test that defines the correct behaviour
2. **Green** — write the minimum code to make the test pass
3. **Refactor** — clean up without breaking the tests

The test is reviewed and agreed before any implementation code is written. This keeps the test suite honest: every test was genuinely red before the fix, so it will catch a regression if the code breaks again.

## Running the tests

```bash
cd backend
.venv/bin/pytest
```

Run with verbose output:

```bash
.venv/bin/pytest -v
```

Run a single file:

```bash
.venv/bin/pytest tests/test_auth.py -v
```

## Test structure

All tests live in `backend/tests/`. The suite uses a single in-memory SQLite database (see `conftest.py`) seeded with one test user and the full exercise library.

| File | What it covers |
|---|---|
| `test_auth.py` | Password hashing, login, registration validation (min length), JWT-protected endpoints |
| `test_cardio.py` | Cardio entry logging, list, delete, activity validation, schema contract (no `session_id`) |
| `test_exercises.py` | Exercise list (session + search filters), exercise by ID, sessions list |
| `test_formulas.py` | Body composition formula calculations (BMI, fat mass, lean mass, BMR, segmental values) — pure unit tests, no HTTP |
| `test_logs.py` | Set logging validation (`weight >= 0`, `reps > 0`), POST edge cases (bad IDs), GET last log, GET log list |
| `test_measurements.py` | Body measurement CRUD, auth enforcement, full BIA formula application with impedance inputs |
| `test_progress.py` | Muscle balance, `epley_1rm` unit tests, strength progression (structure + daily best), volume over time, consistency heatmap, personal records |
| `test_sessions.py` | Full workout session flow: start → log sets → end → list → get logs; edge cases (unknown session, already ended, 404) |
| `test_admin.py` | Admin user management: list users, create, disable/enable, delete (with data cascade); 403 for non-admins, self-disable/delete blocked |
| `test_isolation.py` | Per-user data isolation: user B cannot read user A's sessions, cardio, or measurements |
| `test_profile.py` | GET /api/profile structure and auth, PATCH updates (display_name, birth_year, sex, height_cm), unknown fields ignored, BIA falls back to profile height |
| `test_stats.py` | Home stats structure, streak calculation (unit + UTC correctness), week bounds (UTC correctness) |

## conftest.py

A single `session`-scoped `TestClient` is shared across all tests. The database is created fresh at the start of the test run (`Base.metadata.drop_all` + `create_all`) and seeded with:

- One user: `testuser` / `testpass`
- The full exercise library (via `seed.py`)

Because the database is shared across tests, individual tests must not rely on the database being empty. Tests that need specific data insert it directly via `SessionLocal`.

## Pre-commit hooks

Two hooks run automatically on every `git commit`:

```bash
ruff check --fix   # lint and auto-fix
ruff format        # format
```

Install them once after cloning:

```bash
cd backend
pre-commit install
```

If a commit is blocked, ruff has either auto-fixed files (stage and retry) or found an error it cannot fix (fix manually).

## CI pipeline

Every push and pull request runs three jobs on a self-hosted runner:

| Job | What it does |
|---|---|
| **backend-quality** | `ruff check`, `mypy`, `pytest` |
| **docker-build** | Builds the production Docker image to catch Dockerfile and dependency errors |
| **frontend-build** | `npm ci`, `npm run build` — TypeScript compile + Vite bundle |

The backend job uses `uv` for fast dependency installation with a cached wheel store. Typical CI time is ~30s per job.
