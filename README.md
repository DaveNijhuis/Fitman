# Fitman

[![CI](https://github.com/Dave-Nijhuis/Fitman/actions/workflows/ci.yml/badge.svg)](https://github.com/Dave-Nijhuis/Fitman/actions/workflows/ci.yml)

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

In the [Tailscale admin console](https://login.tailscale.com/admin/machines), rename your server to `fitman`. The app will then be reachable at `http://fitman` from any device on your Tailscale network.

### 4. Deploy Fitman

```bash
# Clone the repo on your server
git clone https://github.com/Dave-Nijhuis/Fitman.git
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

### 5. Create your account

On first launch, visit `http://localhost/setup` (or `http://fitman/setup` via Tailscale) to create the admin account. Credentials are stored in the database — no plaintext passwords in `.env`.

### 6. Access the app

- From your server: `http://localhost`
- From any device on Tailscale: `http://fitman` (or `http://<tailscale-ip>`)

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

If you ran a previous version of Fitman backed by SQLite, your data is in a `fitman.db` file. PostgreSQL is not compatible with SQLite backups directly — you need to export and re-import your data.

**Option A — Fresh start (recommended for personal use)**

1. Note down any data you want to keep manually
2. Deploy the new version: `docker compose -f docker-compose.prod.yml up -d --build`
3. Visit `/setup` to create a new admin account

**Option B — Data migration**

1. Export your data via the old app: `GET /api/gdpr/export` (returns JSON)
2. Bring up the new PostgreSQL-backed version
3. Re-import your workout history via the API or manually

### Backups

Run a backup manually at any time (safe while the app is live):

```bash
chmod +x scripts/backup.sh
./scripts/backup.sh
```

Backups are saved to `backups/fitman_YYYYMMDD_HHMMSS.db`. The script keeps the last 7 and deletes older ones automatically.

**Set up a daily automatic backup with cron:**

```bash
crontab -e
```

Add this line to run every day at 3am:

```
0 3 * * * /path/to/Fitman/scripts/backup.sh >> /path/to/Fitman/backups/backup.log 2>&1
```

**Restoring from a backup:**

```bash
# 1. Stop the app
docker compose -f docker-compose.prod.yml down

# 2. Copy the backup into the Docker volume
docker run --rm \
  -v fitman_db_data:/data \
  -v $(pwd)/backups:/backups \
  alpine cp /backups/fitman_YYYYMMDD_HHMMSS.db /data/fitman.db

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

The frontend dev server runs on `http://localhost:5173` and proxies `/api` requests to the backend automatically.

See [ARCHITECTURE.md](ARCHITECTURE.md) for the full project structure and API reference.

See [TESTING.md](TESTING.md) for the test suite structure, TDD workflow, and CI pipeline.

See [SCALE.md](SCALE.md) for the smart scale BLE protocol, packet decoding, and body composition calculation methodology.

> ⚠️ **Medical disclaimer:** Body composition metrics beyond raw weight are estimates from BIA formulas for personal informational use only. The developers are not medical professionals. Do not use these values for medical diagnosis or treatment.

## Privacy notice

If you share this app with others on your Tailscale network, users should know:

- **What is stored:** workout sessions, sets, cardio entries, body measurements (weight, body fat %, BIA impedance readings), and profile fields (display name, birth year, sex, height)
- **Where it is stored:** exclusively on your self-hosted server — no data is sent to any third party
- **User rights:** each user can export all their data (`GET /api/gdpr/export`) or permanently delete their account and all associated data (`DELETE /api/gdpr/erase`) at any time
- **Encryption:** data is stored in a SQLite database file; protect it with filesystem-level encryption on the host (see [ARCHITECTURE.md](ARCHITECTURE.md) for the full decision)

## Branch strategy

| Branch | Purpose |
|---|---|
| `main` | Stable, production-ready |
| `dev` | Integration and testing |
| `feature/<name>` | One branch per new feature |
| `fix/<name>` | Bug fixes |

All work flows through feature branches → `dev` → `main` via pull request.

## Project board

Issues and feature tracking are managed in the [GitHub Project](https://github.com/users/Dave-Nijhuis/projects/3).

## Built with AI

This project is openly built with [Claude](https://claude.ai) as a pair programmer. No pretence — it's a hobbyist app and AI is part of the workflow from architecture to code.

## License

MIT — see [LICENSE](LICENSE).
