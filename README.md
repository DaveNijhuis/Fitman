# Fitman

[![CI](https://github.com/DaveNijhuis/Fitman/actions/workflows/ci.yml/badge.svg)](https://github.com/DaveNijhuis/Fitman/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.11+-blue?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/React-19-61DAFB?logo=react&logoColor=black)](https://react.dev/)
[![TypeScript](https://img.shields.io/badge/TypeScript-6-3178C6?logo=typescript&logoColor=white)](https://www.typescriptlang.org/)
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
- **Smart scale weigh-in (opt-in)** — weigh in on an e.volve (iCOMON) Bluetooth scale straight from the web app, no Fitdays account or cloud: your phone's browser relays the scale to your server. The scale shows your name, keeps each user apart, and live weight shows while you stand. Needs HTTPS and a Web Bluetooth browser (Chrome on Android, Bluefy on iPhone); see [SCALE.md](SCALE.md)
- **Body composition analysis** — from the scale's body fat and limb impedances, iCOMON's WLA25 algorithm (the one the scale's own app, Fitdays, uses) derives fat and muscle mass, body water, bone mass, BMR, visceral fat, body age, and fat and muscle per arm, leg and trunk, matching Fitdays to within rounding
- **Body measurements** — manually log weight and body fat % over time with trend charts
- **Exercise library** — browse and search all exercises with muscle and equipment info
- **Workout history** — review past sessions with full set-by-set detail, and delete one after a confirmation
- **User profile** — set display name, birth year, sex, and height; profile fields are used as fallback inputs for BIA body composition formulas
- **Multi-user support** — admin can invite users, enable/disable accounts, and delete users with full data cascade; each user's data is fully isolated
- **Password management** — users can change their own password from settings; admin can set a temporary password when creating accounts
- **FAB navigation** — floating action button opens a speed-dial: Start workout (or Continue workout when a session is active) and Settings; the persistent header gear icon has been replaced by this menu
- **Session discard** — cancel an in-progress workout and permanently delete all logged sets via the Finish sheet; a 2-second countdown prevents accidental taps

## Tech stack

| Layer | Technology |
|---|---|
| Backend API | Python 3.11 + FastAPI |
| Frontend | React 19 + TypeScript 6 + Vite + Tailwind CSS 4 |
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

Edit `.env` and set two required values, each generated:

```bash
python3 -c "import secrets; print(secrets.token_hex(32))"   # → SECRET_KEY
python3 -c "import secrets; print(secrets.token_hex(24))"   # → POSTGRES_PASSWORD

SECRET_KEY=<first value>
POSTGRES_PASSWORD=<second value>
```

The stack refuses to start without `POSTGRES_PASSWORD`. Keep it hex (as generated): it goes into the backend's connection URL.

Then start the app, from the repo directory:

```bash
docker compose up -d
```

That one command starts everything: the PostgreSQL database, the backend, and the web app on port 80. The database is also queryable from the server itself on `localhost:5433` (see [Database access](#database-access)). Migrations run automatically on every start.

### 5. Turn on HTTPS (recommended; required for the smart scale)

Tailscale can put a real HTTPS certificate in front of Fitman, with no change to Fitman or Docker. It's worth doing anyway, and the smart scale's Weigh-in needs it: browsers only allow Web Bluetooth on HTTPS pages (see [SCALE.md](SCALE.md)).

1. In the [Tailscale admin console](https://login.tailscale.com/admin/dns), under **DNS**, enable **HTTPS Certificates**. MagicDNS must be on.
2. On the server, forward HTTPS to Fitman's nginx on port 80:

   ```bash
   sudo tailscale serve --bg 80
   ```

   `tailscale serve status` should show `https://<host>.<tailnet>.ts.net` proxying to `http://127.0.0.1:80`. To undo it: `sudo tailscale serve reset`.

   If you moved the web app with `FITMAN_HTTP_PORT`, forward to that port instead. If another program already serves HTTPS on this server, either let it serve Fitman too (see [Behind an existing reverse proxy](#behind-an-existing-reverse-proxy)), or give Tailscale another HTTPS port, for example `sudo tailscale serve --bg --https=8443 8081`, reached at `https://<host>.<tailnet>.ts.net:8443`.

**Privacy note:** issued certificates are recorded in public Certificate Transparency logs, so your machine's name and your tailnet's name become publicly visible. The app itself stays reachable only from your tailnet.

The API is proxied by nginx on the page's own origin, so `CORS_ORIGINS` needs no change for HTTPS.

### 6. Create your account

On first launch, visit `https://<host>.<tailnet>.ts.net/setup` (or `http://localhost/setup` on the server itself) to create the admin account. Credentials are stored in the database — no plaintext passwords in `.env`.

### 7. Access the app

- From any device on your tailnet: `https://<host>.<tailnet>.ts.net`
- From the server itself: `http://localhost`

Each address is its own origin to the browser, so you log in separately on each.

Install the Tailscale app on your iPhone or laptop and sign in with the same account — you'll have access from anywhere without opening any ports to the internet.

### Ports

What each stack publishes on the server, and how to move it:

| Stack | Port | What | To change |
|---|---|---|---|
| Production | `80`, all interfaces | The web app (nginx) | `FITMAN_HTTP_PORT` in `.env` |
| Production | `5433`, on `127.0.0.1` only | PostgreSQL, for database clients ([Database access](#database-access)) | `FITMAN_DB_PORT` in `.env` |
| Production, HTTPS | `443` on the Tailscale address | `tailscale serve` (step 5) | `--https=<port>` |
| Development | `3000`, `8000` | Vite dev server, backend | `docker-compose.dev.yml` |
| E2E tests | `8080` | The app under test | `docker-compose.e2e.yml` |

If `docker compose up -d` stops with **port is already allocated**, something else holds that port. Find out what:

```bash
sudo ss -ltnp 'sport = :80'
```

Then move Fitman, for example with `FITMAN_HTTP_PORT=8081` in `.env`, and run `docker compose up -d` again. `FITMAN_HTTP_PORT` takes a port (`8081`, reachable from the network) or an address and port (`127.0.0.1:8081`, reachable from this machine only). `FITMAN_DB_PORT` takes a port only, so the database always stays on `127.0.0.1`.

### Behind an existing reverse proxy

If the server already runs a reverse proxy such as Caddy, nginx or Traefik (often the thing holding ports 80 and 443), let it serve Fitman too. It then provides HTTPS, which the smart scale needs, and you don't need `tailscale serve`.

**The proxy runs directly on the server.** Publish Fitman on a local port and point the proxy at it:

```bash
# .env
FITMAN_HTTP_PORT=127.0.0.1:8081
```

```
# Caddyfile
fitman.example.com {
    reverse_proxy 127.0.0.1:8081
}
```

**The proxy runs in Docker.** Inside its container, `127.0.0.1` is the container itself, so it can't reach a port published on the server's `127.0.0.1`. Put the proxy on Fitman's Docker network instead, and address the web app by its service name:

```yaml
# the proxy's docker-compose.yml
services:
  caddy:
    networks: [default, fitman]
networks:
  fitman:
    external: true
    name: fitman_default   # <project>_default; the project is Fitman's directory name
```

```
# Caddyfile
fitman.example.com {
    reverse_proxy frontend:80
}
```

Still move Fitman off port 80 (`FITMAN_HTTP_PORT=127.0.0.1:8081`), so the two don't collide. Start Fitman first, since the proxy's stack needs Fitman's network to exist.

nginx proxies `/api` itself, so the reverse proxy needs nothing Fitman-specific and `CORS_ORIGINS` stays as it is.

### Everyday commands

Run these from the repo directory.

| To | Run |
|---|---|
| Start, or apply a changed `.env` | `docker compose up -d` |
| Update to a new version | `git pull && docker compose up -d --build` |
| Stop (data is kept) | `docker compose down` |
| See what's running | `docker compose ps` |
| Follow the logs | `docker compose logs -f backend` |
| Open a database shell | `docker compose exec postgres psql -U fitman fitman` |

Never add `-v` to `down`: that deletes the database volume.

### Upgrading from docker-compose.prod.yml

Before [#339](https://github.com/DaveNijhuis/Fitman/issues/339), production was started by naming `docker-compose.prod.yml` explicitly, and plain `docker compose` meant the development stack. Now `docker-compose.yml` is production, and the old file is gone. To switch over, update and start as usual:

```bash
git pull
docker compose up -d --build
```

The project name and the `db_data` volume are unchanged, so Compose replaces the running containers in place and your data stays where it is. Update any scripts, cron jobs or aliases that still name `docker-compose.prod.yml`: that file no longer exists, so they'll fail rather than do the wrong thing. From #335 on, `.env` must also set `POSTGRES_PASSWORD` (see [Changing the database password](#changing-the-database-password)).

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
docker compose up -d --build
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

Back up the database with `pg_dump` — safe to run while the app is live. From the repo directory:

```bash
mkdir -p backups
docker compose exec -T postgres pg_dump -U fitman fitman > backups/fitman_$(date +%Y%m%d_%H%M%S).sql
```

**Set up a daily automatic backup with cron:**

```bash
crontab -e
```

Add this line to run every day at 3am. cron starts in your home directory, so it changes into the repo first; Compose finds the stack from there:

```
0 3 * * * cd /path/to/Fitman && docker compose exec -T postgres pg_dump -U fitman fitman > backups/fitman_$(date +\%Y\%m\%d_\%H\%M\%S).sql
```

Check the first file isn't empty: a dump that failed still leaves one behind.

**Restoring from a backup:**

```bash
# 1. Stop the backend (keep postgres running)
docker compose stop backend frontend

# 2. Restore the dump
docker compose exec -T postgres psql -U fitman fitman < backups/fitman_YYYYMMDD_HHMMSS.sql

# 3. Start the app again
docker compose up -d
```

---


### Database access

The production database is published on `127.0.0.1:5433`: reachable from the server itself, never from the network.

- **On the server:** connect any client (e.g. DBeaver) to `localhost:5433`, database `fitman`, user `fitman`, password `POSTGRES_PASSWORD` from `.env`.
- **From another machine:** use an SSH tunnel to the server over Tailscale. In DBeaver: host `localhost`, port `5433`, and on the **SSH** tab the server's Tailscale name, port 22, key authentication. The server needs an SSH server (`sudo systemctl enable --now sshd`); plain OpenSSH works where Tailscale SSH's browser re-check can't.

Tick **Read-only connection** in DBeaver unless you mean to change data.

### Changing the database password

PostgreSQL applies `POSTGRES_PASSWORD` only when it first creates the database. For an existing one, including every instance deployed before this setting existed with the old default `fitman`, change it in place:

```bash
# 1. Generate a password and set it in .env as POSTGRES_PASSWORD=<value>
python3 -c "import secrets; print(secrets.token_hex(24))"

# 2. Apply it to the running database (local connections inside the container need no password)
docker compose exec postgres \
  psql -U fitman -d fitman -c "ALTER USER fitman WITH PASSWORD '<value>'"

# 3. Restart, so the backend connects with the new password
docker compose up -d
```

Set it in `.env` first: once `POSTGRES_PASSWORD` is required, Compose won't run any command without it.

## Development setup

The quickest way is the development stack in Docker: the Vite dev server with hot reload on `http://localhost:3000`, the backend on port 8000, and a throwaway database.

```bash
docker compose -f docker-compose.dev.yml up
```

It's a separate Compose project (`fitman-dev`), with its own containers and database, so it can run beside production without touching it. Stop it with `docker compose -f docker-compose.dev.yml down`; add `-v` to wipe its database.

To run the backend and frontend on the host instead:

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
cd backend  && .venv/bin/pytest    # 523 tests, 90% coverage floor
cd frontend && npm test            # 88 tests, Vitest + jsdom
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

# Run all 13 E2E tests
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

- **What is stored:** workout sessions, sets, cardio entries, body measurements (weight, body fat %, BIA impedance readings), profile fields (display name, birth year, sex, height), and, if you use the smart scale, a random id the scale knows you by
- **What goes to the smart scale:** weighing in sends the scale your height, age, sex, last weight and display name (shown on its screen), over Bluetooth from your phone. The scale keeps them, with its own history of your weigh-ins, until it is reset
- **Where it is stored:** exclusively on your self-hosted server — no data is sent to any third party
- **User rights:** each user can export all their data (`GET /api/gdpr/export`) or permanently delete their account and all associated data (`DELETE /api/gdpr/erase`) at any time
- **Encryption:** data is stored in a PostgreSQL database running on your server; protect it with filesystem-level encryption on the host (see [ARCHITECTURE.md](ARCHITECTURE.md) for the full decision)

## Branch strategy

| Branch | Purpose |
|---|---|
| `main` | Stable, production-ready |
| `dev` | Integration and testing |
| `<type>/<issue>-<name>` | One branch per issue, e.g. `feat/322-weigh-in-relay`, `fix/338-stale-resume-after-finish`; types `feat`, `fix`, `chore`, `docs`, `refactor` |

All work flows through feature branches → `dev` → `main` via pull request.

## Project board

Issues and feature tracking are managed in the [GitHub Project](https://github.com/users/DaveNijhuis/projects/3).

## Built with AI

This project is openly built with [Claude](https://claude.ai) as a pair programmer. No pretence — it's a hobbyist app and AI is part of the workflow from architecture to code.

## License

MIT — see [LICENSE](LICENSE).
