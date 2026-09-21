# Fitman

[![CI](https://github.com/DaveNijhuis/Fitman/actions/workflows/ci.yml/badge.svg)](https://github.com/DaveNijhuis/Fitman/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.11+-blue?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/React-18-61DAFB?logo=react&logoColor=black)](https://react.dev/)
[![TypeScript](https://img.shields.io/badge/TypeScript-5-3178C6?logo=typescript&logoColor=white)](https://www.typescriptlang.org/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-336791?logo=postgresql&logoColor=white)](https://www.postgresql.org/)
[![Docker](https://img.shields.io/badge/Docker-ready-2496ED?logo=docker&logoColor=white)](https://www.docker.com/)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-backend%20%7C%20frontend%20%7C%20E2E-brightgreen)](TESTING.md)
[![Coverage](https://img.shields.io/badge/coverage-%E2%89%A590%25-brightgreen)](TESTING.md)

A self-hosted fitness tracking app. Log workouts, track progress, own your data.

## Why self-hosted?

Commercial fitness apps either cost a recurring subscription or monetise your training data. Fitman runs on your own hardware, accessed securely via Tailscale from anywhere — home gym, outdoor gym, wherever.

## Features

- **Workout logging** — log sets, reps, and weight per exercise in real time with a rest timer
- **Cardio tracking** — log runs, rides, swims and more with distance and duration
- **Progress dashboard** — strength progression, weekly volume, consistency heatmap, muscle balance, personal records, and interactive body composition trends
- **Body composition analysis** — connect an e.volve BLE smart scale to capture segmental impedance data; BIA formulae (Janssen, Watson, Katch-McArdle) derive fat mass, muscle mass, BMR, visceral fat grade, and more
- **Body measurements** — manually log weight and body fat % over time with trend charts
- **Exercise library** — browse and search all exercises with muscle and equipment info
- **Workout history** — review past sessions with full set-by-set detail
- **User profile** — set display name, birth year, sex, and height; profile fields are used as fallback inputs for BIA body composition formulas
- **Multi-user support** — admin can invite users, enable/disable accounts, and delete users with full data cascade; each user's data is fully isolated
- **Password management** — users can change their own password from settings; admin can set a temporary password when creating accounts
- **FAB navigation** — floating action button opens a speed-dial: Start workout (or Continue workout when a session is active) and Settings; the persistent header gear icon has been replaced by this menu
- **Session discard** — cancel an in-progress workout and permanently delete all logged sets via the Finish sheet; a 2-second countdown prevents accidental taps

## Tech stack

| Layer | Technology |
|---|---|
| Backend API | Python 3.11 + FastAPI |
| Frontend | React 18 + TypeScript + Tailwind CSS |
| Database | PostgreSQL 16 (via SQLAlchemy) |
| Auth | JWT |
| Infra | Docker Compose + nginx + Tailscale |

## Self-hosting setup

### 1. Prerequisites

- A home server or always-on machine (Linux recommended)
- [Docker](https://docs.docker.com/engine/install/) and Docker Compose installed
- A [Tailscale](https://tailscale.com) account (free tier is fine)

### 2. Install Tailscale on the server

```bash
curl -fsSL https://tailscale.com/install.sh | sh
sudo tailscale up
```

Log in when prompted. Your server will get a Tailscale IP (e.g. `100.x.x.x`) and optionally a hostname.

### 3. Set a Tailscale hostname (optional but recommended)

In the [Tailscale admin console](https://login.tailscale.com/admin/machines), rename your server, e.g. to `fitman`. That name becomes part of its HTTPS address in step 5.

### 4. Deploy Fitman

```bash
# Clone the repo on your server
git clone https://github.com/DaveNijhuis/Fitman.git
cd Fitman

# Set up environment variables
cp .env.example .env
```

Edit `.env` and set one required value:

```bash
# Generate a secure key:
python3 -c "import secrets; print(secrets.token_hex(32))"

SECRET_KEY=<paste generated key here>
```

Then start the app:

```bash
docker compose -f docker-compose.prod.yml up -d
```

### 5. Turn on HTTPS (recommended; required for the smart scale)

Tailscale can put a real HTTPS certificate in front of Fitman, with no change to Fitman or Docker. It's worth doing anyway, and the smart scale's Weigh-in needs it: browsers only allow Web Bluetooth on HTTPS pages (see [SCALE.md](SCALE.md)).

1. In the [Tailscale admin console](https://login.tailscale.com/admin/dns), under **DNS**, enable **HTTPS Certificates**. MagicDNS must be on.
2. On the server, forward HTTPS to Fitman's nginx on port 80:

   ```bash
   sudo tailscale serve --bg 80
   ```

   `tailscale serve status` should show `https://<host>.<tailnet>.ts.net` proxying to `http://127.0.0.1:80`. To undo it: `sudo tailscale serve reset`.

**Privacy note:** issued certificates are recorded in public Certificate Transparency logs, so your machine's name and your tailnet's name become publicly visible. The app itself stays reachable only from your tailnet.

The API is proxied by nginx on the page's own origin, so `CORS_ORIGINS` needs no change for HTTPS.

### 6. Create your account

On first launch, visit `https://<host>.<tailnet>.ts.net/setup` (or `http://localhost/setup` on the server itself) to create the admin account. Credentials are stored in the database — no plaintext passwords in `.env`.

### 7. Access the app

- From any device on your tailnet: `https://<host>.<tailnet>.ts.net`
- From the server itself: `http://localhost`

Each address is its own origin to the browser, so you log in separately on each.

Install the Tailscale app on your iPhone or laptop and sign in with the same account — you'll have access from anywhere without opening any ports to the internet.

### Updating to a new version

```bash
git pull
docker compose -f docker-compose.prod.yml up -d --build
```

### Stopping the app

```bash
docker compose -f docker-compose.prod.yml down
```

### Migrating from SQLite (M18 → M19 upgrade)

If you ran a version of Fitman backed by SQLite, your data is a `fitman.db` file
living in the `db_data` Docker volume. That volume is now where PostgreSQL keeps
its cluster, and PostgreSQL will not initialise over a directory that already has
something in it. **Upgrading without clearing it first leaves the stack unable to
start** — postgres restart-loops and, because the other services wait on it, nothing
comes up.

Fitman detects this and stops with an explanatory message rather than looping. Do
the steps below in order.

**Step 1 — Recover the old file before you do anything else**

Do this first. Once the compose file is replaced, the old SQLite-backed app can no
longer start, so exporting through its API is no longer possible.

```bash
docker compose down
docker run --rm -v fitman_db_data:/d -v "$(pwd)":/out postgres:16 cp /d/fitman.db /out/
```

`fitman.db` is now in your current directory. Keep it somewhere safe — it is the
only copy of your pre-PostgreSQL history.

**Step 2 — Clear the volume**

```bash
docker volume rm fitman_db_data
```

**Step 3 — Start the new version**

```bash
docker compose -f docker-compose.prod.yml up -d --build
```

Visit `/setup` to create your admin account.

**Step 4 — Optional: bring the old data across**

There is no automated importer. The recovered `fitman.db` is a standard SQLite
file, so you can read it with any SQLite client and re-enter what matters:

```bash
sqlite3 fitman.db "SELECT COUNT(*) FROM workout_sessions;"
sqlite3 fitman.db "SELECT COUNT(*) FROM logs;"
```

For a personal instance, re-entering recent history by hand is usually quicker than
scripting an import. The file keeps the rest indefinitely if you change your mind.

### Backups

Back up the database with `pg_dump` — safe to run while the app is live:

```bash
docker exec fitman-postgres pg_dump -U fitman fitman > backups/fitman_$(date +%Y%m%d_%H%M%S).sql
```

**Set up a daily automatic backup with cron:**

```bash
crontab -e
```

Add this line to run every day at 3am:

```
0 3 * * * docker exec fitman-postgres pg_dump -U fitman fitman > /path/to/Fitman/backups/fitman_$(date +\%Y\%m\%d_\%H\%M\%S).sql
```

**Restoring from a backup:**

```bash
# 1. Stop the backend (keep postgres running)
docker compose -f docker-compose.prod.yml stop backend frontend

# 2. Restore the dump
docker exec -i fitman-postgres psql -U fitman fitman < backups/fitman_YYYYMMDD_HHMMSS.sql

# 3. Start the app again
docker compose -f docker-compose.prod.yml up -d
```

---

## Development setup

```bash
# Start PostgreSQL for local development (requires Docker)
docker run -d --name fitman-postgres \
  -e POSTGRES_DB=fitman -e POSTGRES_USER=fitman -e POSTGRES_PASSWORD=fitman \
  -p 5432:5432 postgres:16

# Backend — run from the backend/ directory
cd backend
uv venv .venv --python 3.11
source .venv/bin/activate
uv pip install -r requirements.txt -r requirements-dev.txt
pre-commit install
DATABASE_URL=postgresql://fitman:fitman@localhost:5432/fitman alembic upgrade head
DATABASE_URL=postgresql://fitman:fitman@localhost:5432/fitman fastapi dev main.py

# Frontend — run from the frontend/ directory
cd frontend
npm install
npm run dev
```

Run the test suites:

```bash
cd backend  && .venv/bin/pytest    # 356 tests, 90% coverage floor
cd frontend && npm test            # 50 tests, Vitest + jsdom
```

The frontend dev server runs on `http://localhost:3000` and proxies `/api` requests to the backend automatically.

**After changing any API response model**, regenerate the contract the frontend
types are built from — CI fails if either is stale:

```bash
cd backend  && python -m scripts.dump_openapi   # updates backend/openapi.json
cd frontend && npm run generate:api             # updates src/api/schema.d.ts
```

### Running E2E tests

E2E tests require the app running via the dedicated test stack (isolated from production):

```bash
# Start the E2E stack (fresh DB, rate limiting disabled, port 8080)
docker compose -f docker-compose.e2e.yml up -d --build

# Run all 10 E2E tests
cd e2e
npm install
npx playwright test

# Tear down when done
docker compose -f docker-compose.e2e.yml down -v
```

See [ARCHITECTURE.md](ARCHITECTURE.md) for the full project structure and API reference.

See [TESTING.md](TESTING.md) for the test suite structure, TDD workflow, and CI pipeline.

See [SCALE.md](SCALE.md) for the smart scale BLE protocol, packet decoding, and body composition calculation methodology.

> ⚠️ **Medical disclaimer:** Body composition metrics beyond raw weight are estimates from BIA formulas for personal informational use only. The developers are not medical professionals. Do not use these values for medical diagnosis or treatment.

## Privacy notice

If you share this app with others on your Tailscale network, users should know:

- **What is stored:** workout sessions, sets, cardio entries, body measurements (weight, body fat %, BIA impedance readings), and profile fields (display name, birth year, sex, height)
- **Where it is stored:** exclusively on your self-hosted server — no data is sent to any third party
- **User rights:** each user can export all their data (`GET /api/gdpr/export`) or permanently delete their account and all associated data (`DELETE /api/gdpr/erase`) at any time
- **Encryption:** data is stored in a PostgreSQL database running on your server; protect it with filesystem-level encryption on the host (see [ARCHITECTURE.md](ARCHITECTURE.md) for the full decision)

## Branch strategy

| Branch | Purpose |
|---|---|
| `main` | Stable, production-ready |
| `dev` | Integration and testing |
| `feature/<name>` | One branch per new feature |
| `fix/<name>` | Bug fixes |

All work flows through feature branches → `dev` → `main` via pull request.

## Project board

Issues and feature tracking are managed in the [GitHub Project](https://github.com/users/DaveNijhuis/projects/3).

## Built with AI

This project is openly built with [Claude](https://claude.ai) as a pair programmer. No pretence — it's a hobbyist app and AI is part of the workflow from architecture to code.

## License

MIT — see [LICENSE](LICENSE).
