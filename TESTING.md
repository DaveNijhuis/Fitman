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
| `test_database_pool.py` | Connection pool configuration: DB_POOL_SIZE, DB_MAX_OVERFLOW, DB_POOL_TIMEOUT parsed through `Settings` and applied by `_make_engine`, with their defaults; the app's module-level engine is built from `config.settings`; uses `DATABASE_URL` from the environment (PostgreSQL) |
| `test_features.py` | `GET /api/features` reports `{"scale": false}` by default and `true` when enabled, and requires auth; `require_scale_enabled` returns 404 while `SCALE_ENABLED` is off and passes when on, read per request (exercised on a throwaway app until #323 adds real scale endpoints) |
| `test_entrypoint.py` | entrypoint.sh behaviour: non-zero exit and clear error message to stderr when migration fails; uvicorn not invoked on failure, invoked on success |
| `test_exercises.py` | Exercise list (session + search filters), exercise by ID, sessions list |
| `test_gdpr.py` | Right to erasure (401, 204, cascade delete); data export (401, structure, no password hash, Content-Disposition header, workout sessions included); fixture integrity check asserting seeded cardio activity is a valid title-case value |
| `test_formulas.py` | Body composition formula calculations (BMI, fat mass, lean mass, BMR, segmental values) — pure unit tests, no HTTP; without trunk impedance every derived field except skeletal muscle and SMI is still computed and the segments still sum to the totals; visceral fat (WLA25) matches both Fitdays readings exactly (9, 16) and stays within 1–20; trunk fat and trunk muscle are within 0.7 and 0.2 kg of Fitdays (#325) |
| `test_backfill_derived.py` | Stored measurements with raw inputs but no derived fields get them at startup, using the age at the time of the measurement; rows that already have derived values, or lack body fat, are left alone; a second run changes nothing; it runs in the app's startup (#325) |
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
| `test_readme_https.py` | README's self-hosting section documents HTTPS via Tailscale (enable HTTPS Certificates, `sudo tailscale serve --bg 80`, the `https://<host>.<tailnet>.ts.net` address, the Certificate Transparency caveat, and why: Web Bluetooth needs a secure page); no `http://fitman` addresses remain in README or ARCHITECTURE; `.env.example` explains that nginx and the Vite proxy keep the API on the page's own origin (#321) |
| `test_dockerignore.py` | Static parse of `backend/.dockerignore`: asserts `.env`, `.venv`, `tests/`, `__pycache__/`, and `requirements-dev.txt` are excluded from the Docker build context |
| `test_frontend_dockerignore.py` | Asserts `frontend/.dockerignore` excludes `node_modules`, `dist`, `coverage`, `.vite` and `.env*` without excluding anything a Dockerfile reads; that both frontend Dockerfiles install with `npm ci` (never `npm install`) and do so after copying the manifests and before `COPY . .` — otherwise the host's `node_modules` overwrites the lockfile install (#315) |
| `test_hash_password_dedup.py` | Asserts `hash_password` and `verify_password` are defined in `auth.py` and that neither `routers/auth.py` nor `routers/admin.py` defines its own private copy; identity check confirms both routers import the same function object |
| `test_fk_cascade.py` | FK constraint existence on `workout_sessions`, `cardio_entries`, and `body_measurements` `user_id` columns; schema-level assertion that each FK has `ON DELETE CASCADE`; behavioural tests that raw `DELETE FROM users` cascades child rows in all three tables |
| `test_ci_security_scanning.py` | Structural parse of `.github/workflows/ci.yml`: asserts the backend job runs `pip-audit` and the frontend job runs `npm audit --audit-level=high`, each positioned after its dependency install; asserts `pip-audit` is pinned in `requirements-dev.txt` and that `.github/dependabot.yml` covers `/backend`, `/frontend` and `/e2e` weekly |
| `test_lint_config.py` | Parses `pyproject.toml`: asserts ruff selects `B` and `S`, that `fastapi.Depends` is exempt from `B008`, that `S101` is ignored for tests, and that mypy sets `disallow_untyped_defs` with a `tests.*` override enabling `check_untyped_defs` |
| `test_settings.py` | `config.Settings`: documented defaults; comma-split `CORS_ORIGINS`; every missing or invalid variable reported together, by variable name with the bad value, pointing at `.env.example`; empty `SECRET_KEY` treated as missing; out-of-range values rejected; `.env` read from the repo root, env vars overriding it, unrelated keys (`ADMIN_USERNAME`) ignored, absence tolerated; importing `main` with bad config exits 1 without a traceback; AST scan that no application module other than `config.py` reads `os.getenv`/`os.environ` or loads a `.env`; every setting documented in `.env.example` |
| `test_scale_protocol.py` | iCOMON scale framing: the check-byte rule on unaltered captured frames; parse round-trips and rejects a bad check byte, length or truncation; every message builder (ack, guest and user records, profile, BD, name offer) equals a fixture frame; results decode weight (including the status bit), body fat, user id and impedances; `A5` is marked stored; trunk impedance is not exposed; the old `scale_ingest.py` is gone. Fixtures in `scale_frames.py` keep the captured structure, with body values replaced by a made-up person (the repo is public) |
| `test_scale_handshake.py`; resumes from state carried by the phone | The Fitdays handshake order in answer to the hello (ack, guest record, profile, user record, BD, name offer), with sequence numbers and exact frames; sent once; unprompted start; the `A7` result is acknowledged and kept; `A5` stored weigh-ins are acknowledged, kept once and never taken as the result; resumes from the state the phone carries between requests |
| `test_scale_exchange.py` | `POST /api/scale/exchange`: 404 while `SCALE_ENABLED` is off, 401 without auth; a scale user id is created on first use (never all zeros, never a taken one) and reused; a hello returns the handshake built from the user's own profile (height, age, sex, no last weight yet) with the phone's UTC offset; no frames starts it unprompted; carried state resumes it; a result tagged with the user's id is stored exactly once, one tagged with another id is acknowledged but not stored, and `A5` is acknowledged but not stored; the next handshake carries the last weight; an incomplete profile or a height the scale can't represent is refused by name; corrupt, non-hex or oversized frames give 422; the name offer's image id is stable for an unchanged name and changes with the display name; image chunks are returned only after the scale asks (#324) |
| `test_scale_name_image.py` | The name-image header reproduces the one captured from Fitdays and rejects sizes the format can't hold; the checksum is a 16-bit byte sum; chunks carry an index and 148 bytes each; a rendered name has the captured shape, blank margins, and is cut to the display width; the image id is stable and never 0; the font ships with its OFL licence; Pillow is not imported at startup; the BC offer describes the image; the handshake offers it, queues chunks once on `AD 01 00`, none on `AD 01 04`, and without a name still replays the captured offer (#324) |
| `test_migration_scale_user_id.py` | The migration is the single head after `i5j7k9l1m3n4`; its own `downgrade()` then `upgrade()` run against the real schema inside a rolled-back transaction, leaving a nullable `scale_user_id` with a unique constraint. `create_all` alone would pass every other test with no migration at all |
| `test_gitignore.py` | Asserts `.coverage` and `.coverage.*` are gitignored **and** that `backend/.coverage` is absent from the git index — ignoring a tracked file has no effect, so both halves are checked |
| `test_openapi_snapshot.py` | Asserts the committed `backend/openapi.json` matches what the FastAPI app currently produces, that `/api/cardio` and `/api/measurements` still return paginated envelopes, and that CI regenerates the frontend types and fails on a diff |
| `test_compose_config.py` | Static parse of `docker-compose.yml`: the frontend sets `VITE_API_PROXY_TARGET`, it names the `backend` service rather than `localhost`, and the host it names is a service the compose file actually defines |
| `test_db_volume_guard.py` | Asserts both compose files define the `db-guard` service, that it mounts the data volume and names `fitman.db` in its message, that postgres waits on its successful completion, and that the volume is **not** renamed — a rename would start existing instances on an empty database |
| `test_ci_playwright_pin.py` | Asserts `ci.yml` does not hardcode a Playwright image version and resolves it from the installed `@playwright/test` instead, in a step that runs before the tests and in the `e2e` directory |
| `test_conftest_database_guard.py` | Points a real `pytest` subprocess at a scratch database holding a seeded user row and asserts the run is refused, the error names the database, **and the row survives** — asserting identity rather than row count, because conftest drops, recreates and reseeds |

## conftest.py

A single `session`-scoped `TestClient` is shared across all tests. The database is created fresh at the start of the test run (`Base.metadata.drop_all` + `create_all`) and seeded with:

- One user: `testuser` / `testpass`
- The full exercise library (via `seed.py`)

Because the database is shared across tests, individual tests must not rely on the database being empty. Tests that need specific data insert it directly via `SessionLocal`.

An `autouse=True` function-scoped fixture calls `limiter.reset()` before every test, clearing the in-memory rate limit counters so tests do not leak state across each other.

`DATABASE_URL` must be set in the environment before the test session starts. `conftest.py` defaults to `postgresql://fitman:fitman@localhost:5432/fitman_test` if the variable is not set.

**The suite refuses to run against a database whose name does not end in `_test`.** The lines above drop every application table, and the default only applies when `DATABASE_URL` is unset — so running `pytest` in a shell where you had exported it for `alembic upgrade head` or `fastapi dev` would otherwise destroy your working database. The guard reports the database it declined to touch:

```
pytest.UsageError: Refusing to run: DATABASE_URL points at 'fitman_devwork',
which is not a test database. ...
```

Because the schema is built at import rather than in a fixture, every test currently needs a reachable database — including the twelve files that only read config. That is tracked in #283.

## Coverage

The backend suite enforces a **90% coverage floor** via `--cov-fail-under=90` in
`pyproject.toml`; the run fails if coverage drops below it. Actual coverage is
currently ~99%. `alembic/versions/*` is omitted from measurement — migrations are
verified structurally by `test_postgresql.py` and `test_indexes.py` instead.

## Frontend tests (Vitest)

Component and configuration tests run under Vitest with a jsdom environment:

```bash
cd frontend
npm test              # headless run
npx vitest            # watch mode
```

| File | What it covers |
|---|---|
| `src/components/__tests__/ErrorBoundary.test.tsx` | Route-level error boundary: renders children when nothing throws; renders the fallback UI when a child throws; the fallback contains a link back to home; multiple independent boundaries do not interfere with each other |
| `src/__tests__/tsconfig.test.ts` | Parses `tsconfig.app.json` and asserts `strict`, `noUncheckedIndexedAccess`, `exactOptionalPropertyTypes` and `noImplicitOverride` are all declared |
| `src/api/__tests__/pagination.test.ts` | Drives the cardio and measurements clients from the real `{items, total, page, page_size}` envelope with a mocked `fetch`: each returns a usable array, collects every page rather than truncating at the first, and stops requesting once the last page is served |
| `src/api/__tests__/generated-types.test.ts` | Asserts `schema.d.ts` exists, carries the `CardioPage` and `MeasurementPage` envelopes, and that the cardio and measurements modules derive their types from it instead of hand-declaring response shapes |
| `src/api/__tests__/session.test.ts` | A 401 on a request that carried a token clears it and redirects to `/login?expired=1&next=<current page>`, including from the data export, which bypasses `request()`; a 401 with no token, a 403, a 500 and a network failure all leave the session alone; `login()` does not send a stale token with the credentials, so a wrong password stays a form error (#317) |
| `src/pages/__tests__/LoginPage.test.tsx` | The expiry notice appears only after a rejected session; signing in returns to `next`, or home without one; `next` is ignored unless it is a same-site path — another origin, `//host`, `/\host`, a relative path and `/login` itself all go home; a wrong password still shows its error |
| `src/scale/__tests__/relay.test.ts` | The Weigh-in relay against a fake Web Bluetooth scale: asks for an `e.volve` device with the FFB0 service; posts each FFB3 frame to the exchange and writes the returned frames to FFB1 in order, with response; carries the handshake state; handles one frame at a time; starts unprompted when no hello arrives; reports live weight from FFB2 (status bit 16 included); resolves with the stored measurement and disconnects; rejects on a backend error, a result for another scale user (still acknowledged), a dropped connection, a timeout, or a closed device chooser (#322); writes name-image chunks to FFB4 without response, after the FFB1 frames (#324) |
| `src/components/__tests__/WeighIn.test.tsx` | The Weigh-in button appears only when `/api/features` reports the scale on and the browser has Web Bluetooth; without it, a note names Bluefy; a weigh-in shows the stored weight and body fat and hands the measurement to the page; the phone's UTC offset is sent; an incomplete profile links to `/settings`; other failures are shown and the button is re-enabled (#322) |

`strict` is asserted explicitly because TypeScript 6 enables it by default — the
declaration is what keeps the guarantee if the compiler is ever pinned back to 5.x.

## E2E tests (Playwright)

End-to-end tests live in `e2e/` and run against the full app stack in a browser (Chromium). They cover the critical user flows that unit tests cannot: login, navigation guards, workout lifecycle, account deletion, and WCAG 2.1 accessibility.

### Running E2E tests

The E2E stack must be running first:

```bash
docker compose -f docker-compose.e2e.yml up -d --build
```

Then run the suite:

```bash
cd e2e
npm install
npx playwright test          # headless
npx playwright test --headed # headed (watch the browser)
npx playwright show-report   # open HTML report after a run
```

Tear down when done:

```bash
docker compose -f docker-compose.e2e.yml down -v
```

### Per-test user isolation

Each test gets a fresh `e2e_<timestamp>` user created via the admin API before the test runs and erased via `DELETE /api/gdpr/erase` in teardown. Tests never share state.

### E2E test structure

| File | What it covers |
|---|---|
| `tests/auth.spec.ts` | Unauthenticated redirect to `/login`; wrong password shows error; correct credentials navigate home; a stale token lands on `/login` with the expiry notice instead of the "Could not load data" banner, and signing in returns to the original page (#317) |
| `tests/workout.spec.ts` | Workout page loads after starting a session; finishing a session returns to home |
| `tests/progress.spec.ts` | Progress page loads and renders heading; with the scale feature off (the E2E default), the page offers Log measurement and shows no Weigh in button or Web Bluetooth note (#326) |
| `tests/account.spec.ts` | Delete button disabled until `DELETE` is typed; account deletion redirects to `/login` |
| `tests/accessibility.spec.ts` | axe-core WCAG 2.1 A/AA scans on login page and home page |

### Page errors fail the test

An auto-fixture in `e2e/fixtures/index.ts` fails any test whose page threw an
uncaught exception or logged a `console.error`.

Without it, a page that mounts and then dies on data load is indistinguishable
from a working one — an assertion on a heading passes before the fetch resolves.
That is exactly how #267 shipped: `progress.spec.ts` stayed green while the
Progress page crashed into its error boundary milliseconds later.

Uncaught exceptions and console errors are asserted separately. React's error
boundary catches the throw, so that class of bug never surfaces as an uncaught
exception and is only visible through `console.error` — while a test that
deliberately provokes a 401 legitimately logs one. Those opt out:

```ts
test.use({ allowConsoleErrors: true })
```

The fixture depends on `testUser` so that it is torn down *before* the account is
erased. Playwright tears fixtures down in reverse setup order, and without that
dependency the guard observed 401s caused by its own teardown rather than by the
test.

### Accessibility

axe-core runs `wcag2a` and `wcag2aa` rules on the login and home pages. The `color-contrast` rule is deliberately disabled — the app's `#ff5a36` accent on `#f4f3ef` background gives a 2.79:1 ratio, which is a design choice below the 3:1 AA threshold.

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

Every push and pull request runs on GitHub-hosted `ubuntu-latest` runners:

| Job | Trigger | What it does |
|---|---|---|
| **Frontend build** | every push/PR | `npm ci`, `npm audit --audit-level=high`, regenerate the API types and fail on a diff, `npm run lint` (ESLint), `npm test` (Vitest), `npm run build` — TypeScript compile + Vite bundle |
| **Backend quality** | every push/PR | `pip-audit`, `ruff check`, `mypy`, `pytest` against a postgres:16 service container, with a 90% coverage floor |
| **Docker production build** | every push/PR | Builds the production Docker image to catch Dockerfile and dependency errors |
| **E2E tests** | PRs + pushes to `main`/`dev` | Spins up the E2E stack, runs 10 Playwright tests inside `mcr.microsoft.com/playwright:v<version>-jammy`, tears down. The image tag is resolved from the installed `@playwright/test` rather than hardcoded — library and browsers must match, and a Dependabot bump cannot see a tag buried in a `run:` block |

The backend job caches both the `uv` wheel store (keyed on requirements files) and the `.mypy_cache` directory. The frontend and E2E jobs cache `node_modules` keyed on the respective lock/package files. The E2E job runs the Playwright tests inside the official Docker image so no browser installation or system dependencies are needed on the runner.

### Dependency scanning

`pip-audit` resolves the full transitive tree from `requirements.txt` and
`requirements-dev.txt`, so unpinned indirect dependencies are covered too.
`npm audit` gates on `--audit-level=high`: moderate advisories in the transitive
dev tree would make the check noise rather than signal.

`.github/dependabot.yml` opens weekly dependency update PRs for `/backend` (pip),
`/frontend` and `/e2e` (npm).

## Lint and type gates

| Tool | Scope | Configuration |
|---|---|---|
| **ruff** | whole repo | Selects `E`, `F`, `I`, `B` (bugbear), `S` (bandit). `fastapi.Depends` is exempt from `B008` — dependency injection in an argument default is the framework idiom, not a mutable-default bug. `tests/**` ignores `S101`/`S105`/`S106`/`S107`/`S607`, since pytest is built on bare `assert` and fixture credentials are not secrets. |
| **mypy** | backend | `disallow_untyped_defs` for application code. `tests.*` instead sets `check_untyped_defs` — annotating test functions `-> None` carries no type information, whereas checking their bodies does, and mypy skips unannotated bodies by default. |
| **tsc** | frontend | `strict` plus `noUncheckedIndexedAccess`, `exactOptionalPropertyTypes` and `noImplicitOverride`. |
| **ESLint** | frontend | Runs as a CI gate; errors fail the build, warnings do not. |

Two ruff configs exist: `ruff.toml` at the repo root and `[tool.ruff]` in
`backend/pyproject.toml`. Ruff applies the nearest config to each file, so
without the root one, anything outside `backend/` (at the time, the smart scale
scripts, since replaced by `backend/scale/`) fell back to ruff's built-in defaults. Those are not a stable contract: bumping
ruff from 0.15 to 0.16 widened them and the pre-commit hook began failing on
files nobody had touched, under rules absent from the project's own `select`
list. The hook runs `ruff check --fix` from the repo root with
`pass_filenames: false`, so it lints everything and everything needs a
deliberate ruleset. `test_lint_config.py` asserts the two configs select and
ignore the same rules, so a file's lint result cannot depend on which directory
it lives in.
