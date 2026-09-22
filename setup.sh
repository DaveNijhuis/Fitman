#!/usr/bin/env bash
# Fitman: a guided first-time installation (#349).
#
# Checks the prerequisites, writes .env (generating the secrets), picks ports
# that are free, asks about the smart scale, starts the stack and, if
# Tailscale is installed, offers HTTPS through tailscale serve.
#
# Safe to run again: an existing .env keeps its secrets and settings, and a
# running stack keeps its ports.
#
#   ./setup.sh            ask as it goes
#   ./setup.sh --yes      take every default, ask nothing
#   ./setup.sh --help     all options
set -euo pipefail

usage() {
    cat <<'EOF'
Usage: ./setup.sh [options]

  -y, --yes            Ask nothing; take the defaults and the options below
  --http-port PORT     Web app port (default 80, or the next free one)
  --local-only         Web app reachable from this machine only (127.0.0.1),
                       e.g. behind a reverse proxy on the same host
  --db-port PORT       Database port on 127.0.0.1 (default 5433)
  --scale, --no-scale  Enable or disable the smart scale (SCALE.md)
  --tailscale-serve    Serve over HTTPS with tailscale serve (runs sudo)
  -h, --help           Show this help
EOF
}

say() { printf '%s\n' "$*"; }
die() {
    printf '\nError: %s\n' "$*" >&2
    exit 1
}

YES=0 HTTP_PORT="" DB_PORT="" LOCAL_ONLY="" SCALE="" TS_SERVE=""
while [ $# -gt 0 ]; do
    case "$1" in
    -y | --yes) YES=1 ;;
    --http-port) HTTP_PORT="${2:-}" && shift ;;
    --db-port) DB_PORT="${2:-}" && shift ;;
    --local-only) LOCAL_ONLY=1 ;;
    --scale) SCALE=true ;;
    --no-scale) SCALE=false ;;
    --tailscale-serve) TS_SERVE=1 ;;
    -h | --help) usage && exit 0 ;;
    *) die "unknown option: $1 (see ./setup.sh --help)" ;;
    esac
    shift
done

cd "$(dirname "$0")"

# ── Asking ────────────────────────────────────────────────────────────────────

# ask PROMPT DEFAULT: the answer in REPLY; Enter, end of input or --yes take
# the default.
ask() {
    REPLY="$2"
    if [ "$YES" = 1 ]; then return 0; fi
    local answer=""
    printf '%s [%s]: ' "$1" "$2"
    IFS= read -r answer || true
    if [ -n "$answer" ]; then REPLY="$answer"; fi
}

# yes_no PROMPT DEFAULT(y|n): succeeds for yes.
yes_no() {
    local hint="y/N" answer="$2"
    if [ "$2" = y ]; then hint="Y/n"; fi
    if [ "$YES" != 1 ]; then
        printf '%s [%s]: ' "$1" "$hint"
        IFS= read -r answer || true
        answer="${answer:-$2}"
    fi
    case "$answer" in [Yy]*) return 0 ;; *) return 1 ;; esac
}

valid_port() {
    case "$1" in '' | *[!0-9]*) return 1 ;; esac
    [ "$1" -ge 1 ] && [ "$1" -le 65535 ]
}

# ── .env ──────────────────────────────────────────────────────────────────────

env_get() {
    if [ -f .env ]; then sed -n "s/^$1=//p" .env | tail -n 1; fi
}

# env_set KEY VALUE: replace KEY's line, or its commented-out example, or append.
env_set() {
    if grep -q "^$1=" .env; then
        sed -i "s|^$1=.*|$1=$2|" .env
    elif grep -q "^# *$1=" .env; then
        sed -i "0,/^# *$1=.*/s||$1=$2|" .env
    else
        printf '%s=%s\n' "$1" "$2" >>.env
    fi
}

hex() { od -An -tx1 -N"$1" /dev/urandom | tr -d ' \n'; }

# ── Ports ─────────────────────────────────────────────────────────────────────

# port_holder PORT: what listens on it ("caddy"), or nothing when it's free.
port_holder() {
    command -v ss >/dev/null 2>&1 || return 0
    local line
    line="$(ss -ltnHp "sport = :$1" 2>/dev/null | head -n 1)"
    [ -n "$line" ] || return 0
    case "$line" in
    *'users:(("'*) line="${line#*users:((\"}" && say "${line%%\"*}" && return 0 ;;
    esac
    # Without root, ss names no process. Docker can, for its own containers.
    local name
    name="$(docker ps --format '{{.Names}} {{.Ports}}' 2>/dev/null |
        grep -E ":$1->" | head -n 1 | cut -d ' ' -f 1)" || true
    if [ -n "$name" ]; then
        say "the Docker container $name"
    else
        say "another program (run with sudo to see which)"
    fi
}

next_free() {
    local port="$1"
    while [ -n "$(port_holder "$port")" ]; do port=$((port + 1)); done
    say "$port"
}

# choose_port LABEL DEFAULT EXPLICIT ALWAYS_ASK: a free port in REPLY.
choose_port() {
    local label="$1" port="$2" explicit="$3" always_ask="$4" holder
    if [ -n "$explicit" ]; then
        valid_port "$explicit" || die "$label port must be a number from 1 to 65535, not '$explicit'."
        holder="$(port_holder "$explicit")"
        [ -z "$holder" ] || die "$label port $explicit is already in use by $holder."
        REPLY="$explicit"
        return 0
    fi
    holder="$(port_holder "$port")"
    if [ -n "$holder" ]; then
        say "$label port $port is already in use by $holder."
        port="$(next_free $((port == 80 ? 8081 : port + 1)))"
    elif [ "$always_ask" != 1 ]; then
        REPLY="$port"
        return 0
    fi
    while :; do
        ask "$label port" "$port"
        if ! valid_port "$REPLY"; then
            say "Enter a port number from 1 to 65535."
            continue
        fi
        holder="$(port_holder "$REPLY")"
        if [ -n "$holder" ] && [ "$REPLY" != "$port" ]; then
            say "Port $REPLY is in use by $holder."
            continue
        fi
        return 0
    done
}

# ── 1. Prerequisites: nothing is written until they hold ─────────────────────

say "Fitman setup"
say ""
if [ ! -f docker-compose.yml ] || [ ! -f .env.example ]; then
    die "run this from the Fitman repository: docker-compose.yml and .env.example are missing."
fi
command -v docker >/dev/null 2>&1 ||
    die "Docker is not installed. Install Docker Engine: https://docs.docker.com/engine/install/"
docker compose version >/dev/null 2>&1 ||
    die "Docker Compose v2 is missing (the 'docker compose' command): https://docs.docker.com/compose/install/"
docker info >/dev/null 2>&1 ||
    die "can't reach the Docker daemon. Is Docker running? If it is, add yourself to the docker group: sudo usermod -aG docker \$USER, then log out and back in."

# ── 2. .env and its secrets ───────────────────────────────────────────────────

project="$(basename "$PWD" | tr '[:upper:]' '[:lower:]' | tr -cd 'a-z0-9_-')"
if [ -z "$(env_get POSTGRES_PASSWORD)" ] && docker volume inspect "${project}_db_data" >/dev/null 2>&1; then
    die "a Fitman database already exists (volume ${project}_db_data), but .env has no POSTGRES_PASSWORD.
PostgreSQL only reads the password when it creates the database, so a new one would lock the app out.
Put the database's current password in .env as POSTGRES_PASSWORD (deployments from before that setting
existed use: fitman), or follow \"Changing the database password\" in README.md. Then run ./setup.sh again."
fi

if [ ! -f .env ]; then
    cp .env.example .env
    say "Created .env from .env.example."
fi
case "$(env_get SECRET_KEY)" in
'' | change-me) env_set SECRET_KEY "$(hex 32)" && say "Generated SECRET_KEY." ;;
esac
if [ -z "$(env_get POSTGRES_PASSWORD)" ]; then
    env_set POSTGRES_PASSWORD "$(hex 24)"
    say "Generated POSTGRES_PASSWORD."
fi

# ── 3. Ports ──────────────────────────────────────────────────────────────────

current_http="$(env_get FITMAN_HTTP_PORT)"
current_db="$(env_get FITMAN_DB_PORT)"
web_default="${current_http##*:}"
local_default=n
case "$current_http" in 127.0.0.1:*) local_default=y ;; esac

if [ -n "$(docker compose ps -q 2>/dev/null)" ]; then
    # Already running: the ports it holds are its own, not a conflict.
    say "Fitman is already running; keeping its ports."
    web="${HTTP_PORT:-${web_default:-80}}"
    db="${DB_PORT:-${current_db:-5433}}"
else
    say ""
    choose_port "Web app" "${web_default:-80}" "$HTTP_PORT" 1
    web="$REPLY"
    choose_port "Database" "${current_db:-5433}" "$DB_PORT" 0
    db="$REPLY"
fi

reach_default=y
if [ "$local_default" = y ]; then reach_default=n; fi
if [ -n "$LOCAL_ONLY" ]; then
    local_only=1
elif yes_no "Reachable from other devices (not only this machine)?" "$reach_default"; then
    local_only=0
else
    local_only=1
fi
if [ "$local_only" = 1 ]; then http_value="127.0.0.1:$web"; else http_value="$web"; fi
env_set FITMAN_HTTP_PORT "$http_value"
env_set FITMAN_DB_PORT "$db"

# ── 4. Smart scale ────────────────────────────────────────────────────────────

scale_default=n
if [ "$(env_get SCALE_ENABLED)" = true ]; then scale_default=y; fi
if [ -n "$SCALE" ]; then
    scale="$SCALE"
elif yes_no "Enable the smart scale (see SCALE.md)?" "$scale_default"; then
    scale=true
else
    scale=false
fi
env_set SCALE_ENABLED "$scale"

# ── 5. Start ──────────────────────────────────────────────────────────────────

say ""
say "Building and starting Fitman. The first build takes a few minutes."
docker compose up -d --build --wait ||
    die "Fitman didn't come up healthy. See what went wrong with: docker compose logs"

# ── 6. HTTPS ──────────────────────────────────────────────────────────────────

served=0
if command -v tailscale >/dev/null 2>&1; then
    serve=0
    if [ "$YES" = 1 ]; then
        if [ -n "$TS_SERVE" ]; then serve=1; fi
    elif [ -n "$TS_SERVE" ] || yes_no "Serve Fitman over HTTPS on your tailnet with tailscale serve (runs sudo)?" y; then
        serve=1
    fi
    if [ "$serve" = 1 ]; then
        https=()
        holder="$(port_holder 443)"
        if [ -n "$holder" ] && [ "$holder" != tailscaled ]; then
            say "Port 443 is in use by $holder; tailscale serve will use 8443."
            https=(--https=8443)
        fi
        if sudo tailscale serve --bg "${https[@]}" "$web"; then
            served=1
            say "HTTPS is on: see 'tailscale serve status' for the address. To undo: sudo tailscale serve reset"
        else
            say "tailscale serve failed; HTTPS can be set up later (README.md, step 5)."
        fi
    fi
fi

# ── Done ──────────────────────────────────────────────────────────────────────

suffix=""
if [ "$web" != 80 ]; then suffix=":$web"; fi
say ""
say "Fitman is running. Create your account at http://localhost${suffix}/setup"
if [ "$served" = 0 ]; then
    say "For HTTPS, which the smart scale needs, see README.md: step 5, or \"Behind an existing reverse proxy\"."
fi
