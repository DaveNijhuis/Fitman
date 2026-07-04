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
                         │                     │   SQLite DB   │  │
                         │                     │  fitman.db    │  │
                         │                     └───────────────┘  │
                         └─────────────────────────────────────────┘
```

## Services

### Backend — FastAPI (Python)

- Serves a REST JSON API consumed by the frontend
- Handles authentication (JWT tokens)
- Reads and writes all data to SQLite via SQLAlchemy
- Runs database migrations automatically on startup via Alembic
- Runs on port `8000` inside Docker (internal only — not exposed to the host)

### Frontend — React + TypeScript

- Single-page app, mobile-first responsive layout
- Communicates with the backend via nginx proxy (no direct connection to port 8000)
- Tailwind CSS v4 for styling
- In production: built to static files and served by nginx
- In development: Vite dev server on port `5173` with `/api` proxy to backend

### Database — SQLite

- Single file (`fitman.db`) stored in a Docker volume (`db_data`)
- Easy to back up: just copy the file
- Sufficient for a single-user app — no separate database server needed

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
│   │   ├── auth.py          # POST /api/auth/login
│   │   ├── exercises.py     # GET /api/exercises
│   │   ├── sessions.py      # Workout session management
│   │   ├── logs.py          # Set logging
│   │   ├── progress.py      # Progress calculations
│   │   ├── measurements.py  # Body measurements
│   │   ├── cardio.py        # Cardio logging
│   │   └── stats.py         # Home dashboard stats
│   ├── models/              # SQLAlchemy database models
│   │   ├── exercise.py
│   │   ├── workout.py
│   │   ├── cardio.py
│   │   └── measurement.py
│   ├── alembic/             # Database migrations
│   │   └── versions/        # One file per schema change
│   ├── alembic.ini
│   ├── Dockerfile
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
├── docker-compose.yml       # Development: Vite dev server + backend
├── docker-compose.prod.yml  # Production: nginx static build + backend
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
  date_of_birth   TEXT                  -- ISO date string; age calculated dynamically
  sex             TEXT                  -- "male" | "female" | "other"
  height_cm       REAL
  is_active       BOOLEAN NOT NULL DEFAULT 1
  is_admin        BOOLEAN NOT NULL DEFAULT 0
  created_at      TEXT NOT NULL
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
  session     TEXT NOT NULL          -- "Push A" | "Pull A" | "Legs A"
  started_at  TEXT NOT NULL
  ended_at    TEXT                   -- null while in progress

logs
  id          INTEGER PRIMARY KEY
  exercise_id INTEGER REFERENCES exercises(id)
  session_id  INTEGER REFERENCES workout_sessions(id)
  weight      REAL NOT NULL          -- kg (0 for bodyweight exercises)
  reps        INTEGER NOT NULL
  logged_at   TEXT NOT NULL
```

### Cardio

```
cardio_entries
  id           INTEGER PRIMARY KEY
  activity     TEXT NOT NULL          -- "Run" | "Walk" | "Bike" | "Swim" | "Row" | "Other"
  distance_m   REAL                   -- metres (null if not tracked)
  duration_s   INTEGER                -- seconds (null if not tracked)
  notes        TEXT
  logged_at    TEXT NOT NULL
```

### Body measurements

```
body_measurements
  id                  INTEGER PRIMARY KEY
  recorded_at         TEXT NOT NULL
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

# Exercises
GET    /api/exercises/sessions            List session names (Push A, Pull A, Legs A)
GET    /api/exercises                     All exercises (optional ?session= and ?search= filters)
GET    /api/exercises/{id}               Single exercise by ID

# Strength logging
POST   /api/sessions                      Start a workout session
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

# System
GET    /health                            Health check
```

## Environment variables

All configuration lives in `.env` at the project root. See `.env.example` for a documented template.

| Variable | Required | Default | Description |
|---|---|---|---|
| `SECRET_KEY` | ✅ | — | Random string for signing JWT tokens. Changing it invalidates all sessions. |
| `JWT_EXPIRE_DAYS` | | `7` | Token validity in days |
| `DATA_DIR` | | `./data` | SQLite file location (`/app/data` in Docker) |
| `CORS_ORIGINS` | | `http://localhost:3000` | Allowed frontend origins |

User credentials are stored in the database. On first launch, visit `/setup` to create the admin account. `ADMIN_USERNAME` and `ADMIN_PASSWORD` are no longer used.

The backend refuses to start if `SECRET_KEY` is missing.

## Auth flow

1. **First launch**: frontend detects empty DB via `GET /api/auth/setup-required` and redirects to `/setup`
2. User registers via `POST /api/auth/register` — first user is automatically admin
3. Subsequent logins: `POST /api/auth/login` with username + password
4. Backend verifies against bcrypt hash stored in the `users` table, returns a JWT
5. Frontend stores the token in localStorage and sends it as `Authorization: Bearer <token>` on every request
6. JWT payload contains `user_id` as `sub`; `get_current_user` validates the token and fetches the user from DB
7. Token expires after `JWT_EXPIRE_DAYS` days — user logs in again

Since Tailscale already restricts who can reach the server, JWT here primarily prevents accidents rather than acting as the sole security layer.

## Docker Compose

Two compose files — one for each environment:

```
# Development (npm run dev inside Docker, hot reload)
docker compose up

# Production (static build served by nginx)
docker compose -f docker-compose.prod.yml up -d
```

In production, only nginx (port 80) is exposed to the host. The backend runs on an internal Docker network — nginx proxies `/api/` requests to it.

On every container start, `entrypoint.sh` runs `alembic upgrade head` before starting uvicorn, so database migrations apply automatically on deploy.

## Hosting & access

- The server runs Docker Compose continuously (`docker compose -f docker-compose.prod.yml up -d`)
- Tailscale is installed on the server and on your phone/laptop
- No port forwarding or public IP needed — Tailscale creates a private encrypted network
- Access the app at `http://fitman.local` (or whatever Tailscale hostname you configure)
