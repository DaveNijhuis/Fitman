# Architecture

## Overview

Fitman is a two-service web application: a Python REST API and a React single-page app. Both run as Docker containers on a home server and are accessed remotely via Tailscale.

```
                         ┌─────────────────────────────────────────┐
                         │              Your Home Server            │
                         │                                          │
  iPhone / Laptop        │   ┌─────────────┐   ┌───────────────┐  │
  ──────────────         │   │    nginx    │   │    Backend    │  │
   Tailscale VPN ────────┼──▶│  Port 80   │──▶│   FastAPI     │  │
                         │   │  (static +  │   │   Port 8000   │  │
                         │   │   proxy)    │   └───────┬───────┘  │
                         │   └─────────────┘           │           │
                         │                     ┌───────▼───────┐  │
                         │                     │  PostgreSQL   │  │
                         │                     │  Port 5432    │  │
                         │                     └───────────────┘  │
                         └─────────────────────────────────────────┘
```

`tailscale serve` terminates HTTPS in front of nginx (README, step 5). PostgreSQL is also published on `127.0.0.1:5433`, for database clients on the server itself or through an SSH tunnel; the backend's port is never published.

## Services

### Backend — FastAPI (Python)

- Serves a REST JSON API consumed by the frontend
- Handles authentication (JWT tokens, bcrypt password hashing via `hash_password` / `verify_password` in `auth.py`)
- Reads and writes all data to PostgreSQL via SQLAlchemy
- Runs database migrations automatically on startup via Alembic, then seeds the exercise library and fills in derived body-composition fields for measurements stored without them (`measurement_backfill.py`, #325)
- Attaches a `X-Request-ID` UUID header to every response, and injects the same
  id into every Python log record emitted while handling that request
- Emits structured JSON logs by default (`FITMAN_LOG_FORMAT=text` for plain output)
- Rate-limits the login endpoint to 5 requests per minute per IP (SlowAPI)
- Runs on port `8000` inside Docker (internal only — not exposed to the host)

### Frontend — React + TypeScript

- Single-page app, mobile-first responsive layout
- Communicates with the backend via nginx proxy (no direct connection to port 8000)
- Tailwind CSS v4 for styling
- In production: built to static files and served by nginx
- nginx adds five HTTP security headers on every response: `X-Frame-Options`, `X-Content-Type-Options`, `Referrer-Policy`, `Content-Security-Policy`, and `Permissions-Policy`
- In development: Vite dev server on port `3000` with `/api` proxied to the backend. The proxy target comes from `VITE_API_PROXY_TARGET`, defaulting to `http://localhost:8000` for running on the host; the dev compose stack sets it to `http://backend:8000`, the service name, because inside a container `localhost` is the frontend itself
- API response types are generated from the backend's OpenAPI document, not hand-written — see [API contract](#api-contract)

### Database — PostgreSQL 16

- Runs as a `postgres:16` Docker service with a named volume (`db_data`)
- Supports concurrent writes — required for multi-user deployment
- Accessed by the backend via `DATABASE_URL`. In production the compose file builds it from `POSTGRES_PASSWORD` in `.env`, so the two can't drift (#335); `.env`'s own `DATABASE_URL` is for the dev stack and host runs
- Schema managed by Alembic; migrations run automatically on container start

## Directory structure

```
Fitman/
├── backend/
│   ├── main.py              # FastAPI app entry point + startup (seed, backfill)
│   ├── config.py            # The only reader of the environment: validated Settings (#250)
│   ├── auth.py              # JWT creation and verification
│   ├── database.py          # DB connection and session setup
│   ├── limiter.py           # SlowAPI rate limiter
│   ├── seed.py              # Initial exercise data
│   ├── formulas.py          # BIA body-composition formulas, incl. WLA25 estimates (#325)
│   ├── measurement_backfill.py  # Startup: derive fields for measurements stored without them
│   ├── features.py          # require_scale_enabled: scale endpoints 404 unless SCALE_ENABLED
│   ├── entrypoint.sh        # Docker entrypoint: runs migrations then uvicorn
│   ├── routers/             # API route handlers
│   │   ├── auth.py          # POST /api/auth/login, /register, /change-password
│   │   ├── exercises.py     # GET /api/exercises
│   │   ├── sessions.py      # Workout session management
│   │   ├── logs.py          # Set logging
│   │   ├── progress.py      # Progress calculations
│   │   ├── measurements.py  # Body measurements
│   │   ├── cardio.py        # Cardio logging
│   │   ├── stats.py         # Home dashboard stats
│   │   ├── profile.py       # GET/PATCH /api/profile
│   │   ├── admin.py         # Admin user management
│   │   ├── features.py      # GET /api/features: optional features switched on (#326)
│   │   ├── scale.py         # POST /api/scale/exchange: smart scale relay, opt-in (#323)
│   │   └── gdpr.py          # Data export and account erasure
│   ├── scale/               # Smart scale protocol, no radio code (see SCALE.md)
│   │   ├── protocol.py      # Framing, messages, result decoding
│   │   ├── handshake.py     # What to send back for each scale message
│   │   ├── name_image.py    # The user's name as a bitmap for the scale's display (#324)
│   │   └── fonts/           # Noto Sans Bold + its SIL Open Font License (OFL.txt)
│   ├── models/              # SQLAlchemy database models
│   │   ├── user.py
│   │   ├── exercise.py
│   │   ├── workout.py
│   │   ├── cardio.py
│   │   └── measurement.py
│   ├── alembic/             # Database migrations
│   │   └── versions/        # One file per schema change
│   ├── alembic.ini
│   ├── Dockerfile
│   ├── .dockerignore        # Excludes .env, .venv, tests/, __pycache__, dev deps from image
│   ├── requirements.txt
│   ├── requirements-dev.txt # Dev/CI dependencies (pytest, ruff, mypy)
│   ├── pyproject.toml       # Ruff and mypy configuration
│   ├── openapi.json         # Committed API contract (see API contract)
│   ├── scripts/dump_openapi.py  # Regenerates openapi.json
│   └── tests/               # pytest test suite
│
├── frontend/
│   ├── src/
│   │   ├── pages/           # Top-level route pages
│   │   ├── components/      # Reusable UI components (BottomNav, RestTimer, WeighIn, etc.)
│   │   ├── hooks/           # Shared React hooks
│   │   ├── scale/           # Web Bluetooth relay for the smart scale, loaded on first use (#322)
│   │   └── api/             # API client functions; schema.d.ts is generated
│   ├── nginx.conf           # nginx config used in production Docker image
│   ├── Dockerfile.prod      # Multi-stage: Node build → nginx serve
│   ├── Dockerfile           # Dev only: Vite dev server
│   └── package.json
│
├── setup.sh                 # Guided first-time installation: .env, secrets, free ports, start, HTTPS (#349)
├── docker-compose.yml       # Production: nginx static build + backend + postgres (`docker compose up -d`)
├── docker-compose.dev.yml   # Development: Vite dev server + backend + postgres, project fitman-dev
├── docker-compose.e2e.yml   # E2E testing: isolated stack, tmpfs DB, port 8080
├── e2e/                     # Playwright E2E test suite (TypeScript)
│   ├── tests/               # Test files (auth, workout, progress, account, accessibility)
│   ├── pages/               # Page Object Model classes
│   ├── fixtures/            # Per-test user isolation via admin API
│   ├── global-setup.ts      # Seeds admin user before test run
│   └── playwright.config.ts
├── .env                     # Secrets and config (project root) — read by docker-compose.yml via env_file; never committed (gitignored)
├── .env.example             # Template documenting all variables
├── README.md
├── ARCHITECTURE.md
├── DESIGN.md
└── SCALE.md                 # Smart scale BLE protocol documentation
```

## Database schema

### Users

```
users
  id              INTEGER PRIMARY KEY
  username        TEXT NOT NULL UNIQUE
  email           TEXT UNIQUE
  hashed_password TEXT NOT NULL         -- bcrypt hash
  display_name    TEXT
  birth_year      INTEGER               -- year only (not full DOB); age calculated as current_year - birth_year
  sex             TEXT                  -- "male" | "female" | "other"
  height_cm       REAL
  is_active       BOOLEAN NOT NULL DEFAULT 1
  is_admin        BOOLEAN NOT NULL DEFAULT 0
  created_at      TIMESTAMPTZ NOT NULL
  consent_given_at TIMESTAMPTZ             -- NULL for users created before #138
  scale_user_id   VARCHAR(8) UNIQUE      -- the user's id on the smart scale, 4 random bytes as hex; created on first weigh-in (#323)
```

### Strength training

```
exercises
  id         INTEGER PRIMARY KEY
  name       TEXT NOT NULL          -- e.g. "Flat DB Bench Press"
  muscles    TEXT                   -- e.g. "Chest, Front Delt, Triceps"
  session    TEXT NOT NULL          -- "Push A" | "Pull A" | "Legs A"
  position   INTEGER NOT NULL       -- display order within the session
  type       TEXT NOT NULL          -- "weight" | "bodyweight"
  equip      TEXT NOT NULL          -- "Dumbbell" | "Bodyweight"

workout_sessions
  id          INTEGER PRIMARY KEY
  user_id     INTEGER REFERENCES users(id) ON DELETE CASCADE
  session     TEXT NOT NULL          -- "Push A" | "Pull A" | "Legs A"
  started_at  TIMESTAMPTZ NOT NULL
  ended_at    TIMESTAMPTZ             -- null while in progress

logs
  id          INTEGER PRIMARY KEY
  exercise_id INTEGER REFERENCES exercises(id)
  session_id  INTEGER REFERENCES workout_sessions(id)
  weight      REAL NOT NULL          -- kg (0 for bodyweight exercises)
  reps        INTEGER NOT NULL
  logged_at   TIMESTAMPTZ NOT NULL
```

### Cardio

```
cardio_entries
  id           INTEGER PRIMARY KEY
  user_id      INTEGER REFERENCES users(id) ON DELETE CASCADE
  activity     TEXT NOT NULL          -- "Run" | "Walk" | "Bike" | "Swim" | "Row" | "Other"
  distance_m   REAL                   -- metres (null if not tracked)
  duration_s   INTEGER                -- seconds (null if not tracked)
  notes        TEXT
  logged_at    TIMESTAMPTZ NOT NULL
```

### Body measurements

```
body_measurements
  id                  INTEGER PRIMARY KEY
  user_id             INTEGER REFERENCES users(id) ON DELETE CASCADE
  recorded_at         TIMESTAMPTZ NOT NULL
  weight_kg           REAL
  height_cm           REAL
  notes               TEXT
  -- Whole-body composition (calculated via BIA formulae)
  body_fat_pct        REAL
  bmi                 REAL
  fat_mass_kg         REAL
  lean_mass_kg        REAL
  skeletal_muscle_kg  REAL
  fat_free_weight_kg  REAL
  body_water_pct      REAL
  protein_kg          REAL
  inorganic_salt_kg   REAL
  bmr_kcal            REAL
  visceral_fat_grade  REAL
  subcutaneous_fat_pct REAL
  body_age            INTEGER
  whr_estimate        REAL              -- no longer estimated (#344); older rows keep theirs
  smi                 REAL
  muscle_mass_kg      REAL              -- WLA25 (#344)
  bone_mass_kg        REAL              -- WLA25 (#344)
  -- Segmental fat (kg) — 5 body segments
  ra_fat_kg / la_fat_kg / trunk_fat_kg / rl_fat_kg / ll_fat_kg  REAL
  -- Segmental muscle (kg)
  ra_muscle_kg / la_muscle_kg / trunk_muscle_kg / rl_muscle_kg / ll_muscle_kg  REAL
  -- Raw impedance at 20 kHz and 100 kHz (Ω)
  ra_z20 / la_z20 / rl_z20 / ll_z20 / trunk_z20    REAL
  ra_z100 / la_z100 / rl_z100 / ll_z100 / trunk_z100  REAL
```

## API routes

```
# Auth
GET    /api/auth/setup-required          Returns {required: true} if no users exist yet
POST   /api/auth/register                Create first admin user (only available on empty DB)
POST   /api/auth/login                   Returns JWT token
POST   /api/auth/change-password         Change own password (requires current_password + new_password)

# Profile
GET    /api/profile                       Current user's profile (username, email, display_name, birth_year, sex, height_cm, is_admin)
PATCH  /api/profile                       Update profile fields

# Admin
GET    /api/admin/users                  List all users (admin only)
POST   /api/admin/users                  Create a new user (admin only)
PATCH  /api/admin/users/{id}            Enable or disable a user account (admin only)
DELETE /api/admin/users/{id}            Delete a user and all their data (admin only)

# Exercises
GET    /api/exercises/sessions            List session names (Push A, Pull A, Legs A)
GET    /api/exercises                     All exercises (optional ?session= and ?search= filters)
GET    /api/exercises/{id}               Single exercise by ID

# Strength logging
POST   /api/sessions                      Start a workout session
DELETE /api/sessions/{id}                Delete a session and all its logs: discard one in progress, or delete a finished one from History (#336)
PATCH  /api/sessions/{id}/end            End a workout session (400 if already ended)
GET    /api/sessions                      List completed sessions with volume + set count
GET    /api/sessions/{id}                One session; ended_at tells whether it is still in progress (#338)
GET    /api/sessions/{id}/logs           All logs for a session
POST   /api/logs                          Log a set { exercise_id, session_id, weight, reps }; 409 once the session has ended (#338)
GET    /api/logs/last/{exercise_id}      Most recent set for an exercise

# Progress
GET    /api/progress/strength?exercise_id=X   Estimated 1RM over time (Epley formula)
GET    /api/progress/volume                    Total kg lifted per week
GET    /api/progress/consistency              17-week training heatmap data
GET    /api/progress/balance                  Volume % breakdown by muscle group
GET    /api/progress/prs                      Personal records per exercise

# Home stats
GET    /api/stats/home                    Streak, weekly volume, workouts this week

# Cardio
GET    /api/cardio/activities             List supported activity types
POST   /api/cardio                        Log a cardio entry { activity, distance_m, duration_s, notes }
GET    /api/cardio                        Cardio entries, newest first — paginated
DELETE /api/cardio/{id}                  Delete a cardio entry

# Body measurements
POST   /api/measurements                  Log a measurement { weight_kg, body_fat_pct, ... }
GET    /api/measurements                  Measurements, newest first — paginated
DELETE /api/measurements/{id}            Delete a measurement

# Features
GET    /api/features                      Optional features this instance has on: { scale: bool } (#326)

# Smart scale (404 unless SCALE_ENABLED; see Smart scale below and SCALE.md)
POST   /api/scale/exchange               Relay scale frames from the phone; returns frames to send back and, once measured, the stored measurement (#323)

# GDPR
DELETE /api/gdpr/erase                   Delete own account and all associated data (GDPR Article 17)
GET    /api/gdpr/export                  Download all own data as JSON (GDPR Article 20)

# System
GET    /health                            200 {"status": "ok"} if DB is reachable; 503 {"status": "error"} if not
```

### Pagination

`GET /api/cardio` and `GET /api/measurements` are paginated. Both take the same
query parameters and return the same envelope:

```
?page=1          1-indexed, default 1
&page_size=50    default 50, maximum 200

{ "items": [...], "total": 1234, "page": 1, "page_size": 50 }
```

## Smart scale

Opt-in (`SCALE_ENABLED`, #326). The server never talks Bluetooth: it may run
anywhere, and the scale is only in range of the phone. The phone's browser is a
relay:

```
iCOMON scale ⇄ BLE ⇄ phone browser (Web Bluetooth: Bluefy on iPhone, Chrome on Android)
                         ⇄ HTTPS: POST /api/scale/exchange ⇄ backend/scale/ ⇄ body_measurements
```

- `frontend/src/scale/relay.ts` forwards every frame the scale sends and writes
  back what the backend returns, including the name image's chunks. The only
  thing it decodes itself is the live weight shown while measuring.
- `backend/scale/` holds the whole protocol: framing and decoding
  (`protocol.py`), what to answer each message with (`handshake.py`), and the
  user's name rendered for the scale's display (`name_image.py`, #324).
- The exchange is stateless on the server: the phone carries the handshake
  state between requests, and sends its UTC offset for the scale's clock.
- The scale matches a weigh-in to a user by `users.scale_user_id`, created on
  the first weigh-in. A result tagged with another id is acknowledged but not
  stored. Stored weigh-ins the scale re-offers (`A5`) are acknowledged, never
  stored.
- Web Bluetooth only works on HTTPS pages, hence `tailscale serve`.

SCALE.md documents the protocol, byte by byte, and how body composition is
calculated.

## API contract

The frontend does not restate the API's shapes. `backend/openapi.json` is
committed as the contract between the two halves, and the frontend's types are
generated from it:

```
FastAPI app
  │  python -m scripts.dump_openapi
  ▼
backend/openapi.json          ← committed, reviewable diff on any shape change
  │  npm run generate:api
  ▼
frontend/src/api/schema.d.ts  ← generated, never edited by hand
  │
  ▼
src/api/*.ts                  ← response types taken from the generated schema
```

`request<T>()` in `client.ts` casts rather than validates, so a hand-written
interface is checked against nothing. That is how #267 shipped: #227 changed two
response shapes, all 34 call sites kept compiling, and the Progress page crashed
while Cardio history silently rendered empty.

Three checks make that drift impossible to ship quietly:

| Guard | Catches |
|---|---|
| `test_openapi_snapshot.py` | backend changed, `openapi.json` not regenerated |
| CI: `npm run generate:api` then `git diff --exit-code` | snapshot regenerated, types not |
| `Page<T>` assertion in `client.ts` | both regenerated, frontend still wrong |

**When you change a response model, regenerate both:**

```bash
cd backend  && python -m scripts.dump_openapi
cd frontend && npm run generate:api
```

Generated types are erased at build time, so none of this reaches the bundle.
`openapi-typescript` is invoked through a pinned `npx` rather than installed —
it peer-requires TypeScript 5.x and this project is on 6.x.

## Environment variables

All configuration lives in `.env` at the project root. See `.env.example` for a documented template. Variables set in the environment (for example by compose) take precedence over the file.

`backend/config.py` is the only module that reads the environment: it validates every variable below into a pydantic-settings `Settings` object at import, and the rest of the backend reads `config.settings`. `tests/test_settings.py` fails if any other application module calls `os.getenv` / `os.environ` or loads a `.env` itself.

| Variable | Required | Default | Description |
|---|---|---|---|
| `SECRET_KEY` | ✅ | — | Random string for signing JWT tokens. Changing it invalidates all sessions. |
| `POSTGRES_PASSWORD` | ✅ production | — | Production database password; the production stack refuses to start without it and builds the backend's `DATABASE_URL` from it (#335). Hex, as generated in README step 4, since it goes into a URL. Applied only when the database is first created: README, "Changing the database password" |
| `DATABASE_URL` | ✅ | — | PostgreSQL connection string, e.g. `postgresql://fitman:fitman@postgres:5432/fitman`. Overridden by the production stack (see `POSTGRES_PASSWORD`) |
| `JWT_EXPIRE_DAYS` | | `7` | Token validity in days |
| `CORS_ORIGINS` | | `http://localhost:3000` | Allowed frontend origins, comma-separated |
| `DB_POOL_SIZE` | | `5` | SQLAlchemy connection pool size (at least 1) |
| `DB_MAX_OVERFLOW` | | `10` | Max connections above pool size before blocking |
| `DB_POOL_TIMEOUT` | | `30` | Seconds to wait for a connection before raising an error |
| `RATE_LIMIT_DISABLED` | | `false` | Set to `true` to disable SlowAPI rate limiting (E2E stack only). Accepts `true`/`false`/`1`/`0`; anything else is rejected |
| `FITMAN_LOG_FORMAT` | | `json` | Log output format: `json` (structured, one object per line) or `text` for human-readable local development. Any other value is rejected. |
| `SCALE_ENABLED` | | `false` | Opt in to the smart scale integration (SCALE.md). Off: no scale endpoints (404), no Weigh-in button; manual weight entry either way |
| `SCALE_HEIGHT_CM` | | `0` | Fallback height for body-composition formulas when neither request nor profile has one; `0` = not set |
| `SCALE_AGE` | | `0` | Fallback age, same rules; `0` = not set |
| `SCALE_SEX` | | `1` | Fallback sex for the formulas: `1` = male, `0` = female |

User credentials are stored in the database. On first launch, visit `/setup` to create the admin account. `ADMIN_USERNAME` and `ADMIN_PASSWORD` are no longer used.

The backend refuses to start if any variable is missing or invalid, with one message listing every problem by variable name and the value it got, rather than stopping at the first:

```
ERROR: invalid configuration:
  SECRET_KEY: String should have at least 1 character (got '')
  DB_POOL_SIZE: Input should be a valid integer, unable to parse string as an integer (got 'abc')
Copy .env.example to .env and fill in the values.
```

## Auth flow

1. **First launch**: frontend detects empty DB via `GET /api/auth/setup-required` and redirects to `/setup`
2. User registers via `POST /api/auth/register` — first user is automatically admin
3. **Onboarding**: after registration, `fitman_onboarding_pending` is set in localStorage; the frontend redirects to `/onboarding` for a one-time profile setup step, then clears the flag and proceeds to home
4. Subsequent logins: `POST /api/auth/login` with username + password
5. Backend verifies against bcrypt hash stored in the `users` table. Wrong username or password → 401 `"Invalid credentials"`. Correct credentials on a disabled account → 403 `"Account disabled"`. Returns a JWT on success.
6. Frontend stores the token in localStorage and sends it as `Authorization: Bearer <token>` on every request
7. JWT payload contains `user_id` as `sub` and the user's `token_version` as `ver`; `get_current_user` validates the token, fetches the user from DB, and rejects the token with 401 if `ver` no longer matches the stored `token_version`
8. Changing a password increments `token_version`, which invalidates every token issued before the change — so a stolen token stops working the moment the password is changed
9. Token expires after `JWT_EXPIRE_DAYS` days — user logs in again

Since Tailscale already restricts who can reach the server, JWT here primarily prevents accidents rather than acting as the sole security layer.

## Docker Compose

Three compose files — one per environment. The default file is production, so
the plain command launches the app (#339):

```
# Production (static build served by nginx)
docker compose up -d

# Development (npm run dev inside Docker, hot reload)
docker compose -f docker-compose.dev.yml up

# E2E testing (isolated stack, tmpfs DB, rate limiting off, port 8080)
docker compose -f docker-compose.e2e.yml up -d --build
```

Production takes its project name from the clone's directory (normally `fitman`), and its data lives in the `<project>_db_data` volume. The file pins no name on purpose: pinning one would move an instance cloned elsewhere onto a new, empty volume. The development and E2E stacks pin `fitman-dev` and `fitman-e2e`, so neither can replace production's containers or reach its data. The E2E database lives on tmpfs, so it is wiped on every `down -v`.

In production, nginx (port 80) is exposed to the host, and PostgreSQL on `127.0.0.1:5433` only, for database clients on the server or through an SSH tunnel (#335). `FITMAN_HTTP_PORT` and `FITMAN_DB_PORT` in `.env` move them, for example off a port a reverse proxy already holds; the database stays on `127.0.0.1` whatever the value (#347). The backend runs on an internal Docker network — nginx proxies `/api/` requests to it.

On every container start, `entrypoint.sh` runs `alembic upgrade head` before starting uvicorn, so database migrations apply automatically on deploy.

A `db-guard` service runs before PostgreSQL in the production stack, and postgres waits on its successful completion. It inspects the
`db_data` volume and refuses to let the stack start if the volume holds
something that is not a PostgreSQL cluster — typically `fitman.db` left by the
pre-PostgreSQL version. Without it, postgres reports `initdb: directory exists
but is not empty` in a restart loop, which says nothing about the migration that
caused it, and the whole stack stays down because the other services wait on
postgres being healthy. The volume is deliberately **not** renamed to avoid the
collision: a rename creates an empty volume, so every instance already running
PostgreSQL would start on a blank database and report healthy.

## Design decisions

### `birth_year` instead of `date_of_birth`

The user model stores `birth_year` (integer) rather than a full date-of-birth. Full DOB is PII; birth year alone is not identifying on its own. Age is computed dynamically (`current_year - birth_year`) so it never goes stale. The ±1-year imprecision (birthday not yet passed this calendar year) is within the noise margin of the BIA formulae that consume it.

Symmetric encryption of the full DOB was considered but deferred — it adds key-management complexity that is disproportionate to the threat model of a self-hosted, Tailscale-only app. This can be revisited in the M15 GDPR & data-security milestone if the threat model changes.

### Encryption at rest — filesystem-level, not application-level

GDPR Article 32 requires "appropriate technical and organisational measures" to protect personal data. For Fitman's current scope (self-hosted, single-user or small household, accessed exclusively over Tailscale), the appropriate measure is **filesystem-level encryption on the host** rather than application-level column encryption.

**Options evaluated:**

| Option | Assessment |
|---|---|
| Filesystem / volume encryption | Recommended. Encrypts the PostgreSQL data volume transparently. Zero app code changes. Protects against disk theft or backup exfiltration. |
| pgcrypto / column-level encryption | Most granular, but: requires managing an encryption key in `.env`, breaks `WHERE` queries on encrypted columns, complicates backups and exports. Disproportionate for this scope. |
| Column-level encryption (`cryptography` lib) | Same trade-offs as pgcrypto with more application complexity. Not recommended. |

**Key management (filesystem approach):** Use Linux LUKS or macOS FileVault on the host machine, or encrypt the Docker volume via the host's block device. `SECRET_KEY` and `POSTGRES_PASSWORD` in `.env` are the only application-level secrets; `.env` is gitignored and must never be committed.

**Backup note:** Encrypted backups are only as strong as the decryption key. Store backups on an encrypted medium and never in the same location as the key.

**Revisit trigger:** If Fitman is ever deployed as a shared multi-user service (beyond household use), column-level encryption for health measurements should be implemented to comply with GDPR Article 32 in a multi-tenant context.

## Hosting & access

- The server runs Docker Compose continuously (`docker compose up -d`)
- Tailscale is installed on the server and on your phone/laptop
- No port forwarding or public IP needed — Tailscale creates a private encrypted network
- Access the app at `https://<host>.<tailnet>.ts.net`: `tailscale serve` terminates HTTPS in front of nginx (README, step 5)
