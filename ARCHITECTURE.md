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

## Services

### Backend — FastAPI (Python)

- Serves a REST JSON API consumed by the frontend
- Handles authentication (JWT tokens, bcrypt password hashing via `hash_password` / `verify_password` in `auth.py`)
- Reads and writes all data to PostgreSQL via SQLAlchemy
- Runs database migrations automatically on startup via Alembic
- Attaches a `X-Request-ID` UUID header to every response for log tracing
- Rate-limits the login endpoint to 5 requests per minute per IP (SlowAPI)
- Runs on port `8000` inside Docker (internal only — not exposed to the host)

### Frontend — React + TypeScript

- Single-page app, mobile-first responsive layout
- Communicates with the backend via nginx proxy (no direct connection to port 8000)
- Tailwind CSS v4 for styling
- In production: built to static files and served by nginx
- nginx adds five HTTP security headers on every response: `X-Frame-Options`, `X-Content-Type-Options`, `Referrer-Policy`, `Content-Security-Policy`, and `Permissions-Policy`
- In development: Vite dev server on port `5173` with `/api` proxy to backend

### Database — PostgreSQL 16

- Runs as a `postgres:16` Docker service with a named volume (`db_data`)
- Supports concurrent writes — required for multi-user deployment
- Accessed by the backend via `DATABASE_URL` in `.env`
- Schema managed by Alembic; migrations run automatically on container start

## Directory structure

```
Fitman/
├── backend/
│   ├── main.py              # FastAPI app entry point + startup validation
│   ├── auth.py              # JWT creation and verification
│   ├── database.py          # DB connection and session setup
│   ├── seed.py              # Initial exercise data
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
│   │   └── gdpr.py          # Data export and account erasure
│   ├── models/              # SQLAlchemy database models
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
│   └── tests/               # pytest test suite
│
├── frontend/
│   ├── src/
│   │   ├── pages/           # Top-level route pages
│   │   ├── components/      # Reusable UI components (BottomNav, RestTimer, etc.)
│   │   └── api/             # API client functions
│   ├── nginx.conf           # nginx config used in production Docker image
│   ├── Dockerfile.prod      # Multi-stage: Node build → nginx serve
│   ├── Dockerfile           # Dev only: Vite dev server
│   └── package.json
│
├── docker-compose.yml       # Development: Vite dev server + backend + postgres
├── docker-compose.prod.yml  # Production: nginx static build + backend + postgres
├── docker-compose.e2e.yml   # E2E testing: isolated stack, tmpfs DB, port 8080
├── e2e/                     # Playwright E2E test suite (TypeScript)
│   ├── tests/               # Test files (auth, workout, progress, account, accessibility)
│   ├── pages/               # Page Object Model classes
│   ├── fixtures/            # Per-test user isolation via admin API
│   ├── global-setup.ts      # Seeds admin user before test run
│   └── playwright.config.ts
├── .env                     # Secrets and config — never committed (gitignored)
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
  whr_estimate        REAL
  smi                 REAL
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
DELETE /api/sessions/{id}                Discard an in-progress session and all its logs (active sessions only)
PATCH  /api/sessions/{id}/end            End a workout session
GET    /api/sessions                      List completed sessions with volume + set count
GET    /api/sessions/{id}/logs           All logs for a session
POST   /api/logs                          Log a set { exercise_id, session_id, weight, reps }
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
GET    /api/cardio                        All cardio entries (newest first)
DELETE /api/cardio/{id}                  Delete a cardio entry

# Body measurements
POST   /api/measurements                  Log a measurement { weight_kg, body_fat_pct, ... }
GET    /api/measurements                  All measurements (newest first)
DELETE /api/measurements/{id}            Delete a measurement

# GDPR
DELETE /api/gdpr/erase                   Delete own account and all associated data (GDPR Article 17)
GET    /api/gdpr/export                  Download all own data as JSON (GDPR Article 20)

# System
GET    /health                            200 {"status": "ok"} if DB is reachable; 503 {"status": "error"} if not
```

## Environment variables

All configuration lives in `.env` at the project root. See `.env.example` for a documented template.

| Variable | Required | Default | Description |
|---|---|---|---|
| `SECRET_KEY` | ✅ | — | Random string for signing JWT tokens. Changing it invalidates all sessions. |
| `DATABASE_URL` | ✅ | — | PostgreSQL connection string, e.g. `postgresql://fitman:fitman@postgres:5432/fitman` |
| `JWT_EXPIRE_DAYS` | | `7` | Token validity in days |
| `CORS_ORIGINS` | | `http://localhost:3000` | Allowed frontend origins |
| `DB_POOL_SIZE` | | `5` | SQLAlchemy connection pool size |
| `DB_MAX_OVERFLOW` | | `10` | Max connections above pool size before blocking |
| `DB_POOL_TIMEOUT` | | `30` | Seconds to wait for a connection before raising an error |
| `RATE_LIMIT_DISABLED` | | `false` | Set to `true` to disable SlowAPI rate limiting (E2E stack only) |

User credentials are stored in the database. On first launch, visit `/setup` to create the admin account. `ADMIN_USERNAME` and `ADMIN_PASSWORD` are no longer used.

The backend refuses to start if `SECRET_KEY` is missing.

## Auth flow

1. **First launch**: frontend detects empty DB via `GET /api/auth/setup-required` and redirects to `/setup`
2. User registers via `POST /api/auth/register` — first user is automatically admin
3. **Onboarding**: after registration, `fitman_onboarding_pending` is set in localStorage; the frontend redirects to `/onboarding` for a one-time profile setup step, then clears the flag and proceeds to home
4. Subsequent logins: `POST /api/auth/login` with username + password
5. Backend verifies against bcrypt hash stored in the `users` table. Wrong username or password → 401 `"Invalid credentials"`. Correct credentials on a disabled account → 403 `"Account disabled"`. Returns a JWT on success.
6. Frontend stores the token in localStorage and sends it as `Authorization: Bearer <token>` on every request
7. JWT payload contains `user_id` as `sub`; `get_current_user` validates the token and fetches the user from DB
8. Token expires after `JWT_EXPIRE_DAYS` days — user logs in again

Since Tailscale already restricts who can reach the server, JWT here primarily prevents accidents rather than acting as the sole security layer.

## Docker Compose

Three compose files — one per environment:

```
# Development (npm run dev inside Docker, hot reload)
docker compose up

# Production (static build served by nginx)
docker compose -f docker-compose.prod.yml up -d

# E2E testing (isolated stack, tmpfs DB, rate limiting off, port 8080)
docker compose -f docker-compose.e2e.yml up -d --build
```

The E2E stack uses project name `fitman-e2e` to avoid colliding with a running production stack. Its PostgreSQL database lives on tmpfs so it is wiped on every `down -v`.

In production, only nginx (port 80) is exposed to the host. The backend runs on an internal Docker network — nginx proxies `/api/` requests to it.

On every container start, `entrypoint.sh` runs `alembic upgrade head` before starting uvicorn, so database migrations apply automatically on deploy.

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

**Key management (filesystem approach):** Use Linux LUKS or macOS FileVault on the host machine, or encrypt the Docker volume via the host's block device. The `SECRET_KEY` in `.env` remains the only application-level secret and should not be committed to version control.

**Backup note:** Encrypted backups are only as strong as the decryption key. Store backups on an encrypted medium and never in the same location as the key.

**Revisit trigger:** If Fitman is ever deployed as a shared multi-user service (beyond household use), column-level encryption for health measurements should be implemented to comply with GDPR Article 32 in a multi-tenant context.

## Hosting & access

- The server runs Docker Compose continuously (`docker compose -f docker-compose.prod.yml up -d`)
- Tailscale is installed on the server and on your phone/laptop
- No port forwarding or public IP needed — Tailscale creates a private encrypted network
- Access the app at `http://fitman.local` (or whatever Tailscale hostname you configure)
