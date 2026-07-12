# Testing

## Philosophy

Fitman is developed using **Test-Driven Development (TDD)**. For every bug fix or new feature:

1. **Red** — write a failing test that defines the correct behaviour
2. **Green** — write the minimum code to make the test pass
3. **Refactor** — clean up without breaking the tests

The test is reviewed and agreed before any implementation code is written. This keeps the test suite honest: every test was genuinely red before the fix, so it will catch a regression if the code breaks again.

## Running the tests

Tests run against a real PostgreSQL database. Start one first if you don't have it running:

```bash
docker run -d --name fitman-postgres \
  -e POSTGRES_DB=fitman_test -e POSTGRES_USER=fitman -e POSTGRES_PASSWORD=fitman \
  -p 5432:5432 postgres:16
```

Then run the suite:

```bash
cd backend
DATABASE_URL=postgresql://fitman:fitman@localhost:5432/fitman_test .venv/bin/pytest
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

All tests live in `backend/tests/`. The suite runs against a real PostgreSQL database (see `conftest.py`) seeded with one test user and the full exercise library.

| File | What it covers |
|---|---|
| `test_indexes.py` | Schema index assertions: verifies that `logs.session_id`, `logs.exercise_id`, `workout_sessions.user_id`, `body_measurements.user_id`, and `cardio_entries.user_id` are indexed |
| `test_admin.py` | Admin user management: list users, create, disable/enable, delete (with data cascade); 403 for non-admins, self-disable/delete blocked |
| `test_auth.py` | Password hashing, login, registration validation (min length, consent required), JWT-protected endpoints, password change (wrong current → 400, short new → 422, success); expired JWT rejected with 401; disabled account returns 403 with distinct message |
| `test_cardio.py` | Cardio entry logging, list, delete, activity validation, schema contract (no `session_id`) |
| `test_database_pool.py` | Connection pool configuration: verifies DB_POOL_SIZE, DB_MAX_OVERFLOW, DB_POOL_TIMEOUT env vars are read and applied; default values; uses `DATABASE_URL` from the environment (PostgreSQL) |
| `test_entrypoint.py` | entrypoint.sh behaviour: non-zero exit and clear error message to stderr when migration fails; uvicorn not invoked on failure, invoked on success |
| `test_exercises.py` | Exercise list (session + search filters), exercise by ID, sessions list |
| `test_gdpr.py` | Right to erasure (401, 204, cascade delete); data export (401, structure, no password hash, Content-Disposition header, workout sessions included); fixture integrity check asserting seeded cardio activity is a valid title-case value |
| `test_formulas.py` | Body composition formula calculations (BMI, fat mass, lean mass, BMR, segmental values) — pure unit tests, no HTTP |
| `test_isolation.py` | Per-user data isolation: user B cannot read user A's sessions, cardio, or measurements |
| `test_logs.py` | Set logging validation (`weight >= 0`, `reps > 0`), POST edge cases (bad IDs), GET last log, GET log list |
| `test_measurements.py` | Body measurement CRUD, auth enforcement, full BIA formula application with impedance inputs |
| `test_profile.py` | GET /api/profile structure and auth, PATCH updates (display_name, birth_year, sex, height_cm), unknown fields ignored, BIA falls back to profile height; sex rejects invalid values (422), birth_year rejects values outside 1900–current year (422) |
| `test_progress.py` | Muscle balance, `epley_1rm` unit tests, strength progression (structure + daily best), volume over time, consistency heatmap, personal records; N+1 regression guard on consistency endpoint (asserts ≤2 SELECT statements) |
| `test_sessions.py` | Full workout session flow: start → log sets → end → list → get logs; edge cases (unknown session, already ended, 404); N+1 query regression guard (asserts ≤2 SELECT statements on list endpoint); discard session (204 happy path, log cascade, cross-user 404, already-ended 400) |
| `test_stats.py` | Home stats structure, streak calculation (unit + UTC correctness), week bounds (UTC correctness); memory regression guard asserting all workout_sessions SELECTs contain a started_at date bound |
| `test_postgresql.py` | PostgreSQL migration structural tests: engine dialect is postgresql, no TZDateTime custom type in any model |
| `test_middleware.py` | Request ID middleware: `X-Request-ID` header present on all responses, value is a valid UUID4, unique per request |
| `test_health.py` | `GET /health` returns 200 under normal conditions; returns 503 with `{"status": "error"}` when the database is unreachable (tested via dependency override) |
| `test_ratelimit.py` | Login rate limiting: 6th request within a minute returns 429; health endpoint is not rate-limited |
| `test_nginx_conf.py` | Static parse of `frontend/nginx.conf`: asserts all five security headers (`X-Frame-Options`, `X-Content-Type-Options`, `Referrer-Policy`, `Content-Security-Policy`, `Permissions-Policy`) are present |
| `test_dockerignore.py` | Static parse of `backend/.dockerignore`: asserts `.env`, `.venv`, `tests/`, `__pycache__/`, and `requirements-dev.txt` are excluded from the Docker build context |
| `test_hash_password_dedup.py` | Asserts `hash_password` and `verify_password` are defined in `auth.py` and that neither `routers/auth.py` nor `routers/admin.py` defines its own private copy; identity check confirms both routers import the same function object |
| `test_fk_cascade.py` | FK constraint existence on `workout_sessions`, `cardio_entries`, and `body_measurements` `user_id` columns; schema-level assertion that each FK has `ON DELETE CASCADE`; behavioural tests that raw `DELETE FROM users` cascades child rows in all three tables |

## conftest.py

A single `session`-scoped `TestClient` is shared across all tests. The database is created fresh at the start of the test run (`Base.metadata.drop_all` + `create_all`) and seeded with:

- One user: `testuser` / `testpass`
- The full exercise library (via `seed.py`)

Because the database is shared across tests, individual tests must not rely on the database being empty. Tests that need specific data insert it directly via `SessionLocal`.

An `autouse=True` function-scoped fixture calls `limiter.reset()` before every test, clearing the in-memory rate limit counters so tests do not leak state across each other.

`DATABASE_URL` must be set in the environment before the test session starts. `conftest.py` defaults to `postgresql://fitman:fitman@localhost:5432/fitman_test` if the variable is not set.

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

The backend job caches both the `uv` wheel store (keyed on requirements files) and the `.mypy_cache` directory (keyed on requirements files; mypy invalidates per-file internally). The frontend job caches `node_modules` keyed on `package-lock.json` and skips `npm ci` entirely on a cache hit.
