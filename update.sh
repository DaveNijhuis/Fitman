#!/usr/bin/env bash
# Fitman: a safe update for a running deployment (#350).
#
# Fetches the new version and checks it against .env before changing
# anything, backs up the database, updates the code, rebuilds and restarts,
# and shows the migrations that ran. If the new version won't start, it says
# exactly how to go back.
#
#   ./update.sh            update to the latest version of this branch
#   ./update.sh --rebuild  rebuild and restart even when already up to date
set -euo pipefail

usage() {
    cat <<'EOF'
Usage: ./update.sh [options]

  --rebuild    Back up, rebuild and restart even when already up to date
  -h, --help   Show this help
EOF
}

say() { printf '%s\n' "$*"; }
die() {
    printf '\nError: %s\n' "$*" >&2
    exit 1
}

REBUILD=0
while [ $# -gt 0 ]; do
    case "$1" in
    --rebuild) REBUILD=1 ;;
    -h | --help) usage && exit 0 ;;
    *) die "unknown option: $1 (see ./update.sh --help)" ;;
    esac
    shift
done

cd "$(dirname "$0")"

env_get() {
    if [ -f .env ]; then sed -n "s/^$1=//p" .env | tail -n 1; fi
}

# Settings a compose file refuses to start without: ${NAME:?message}.
required_settings() { grep -oE '\$\{[A-Za-z0-9_]+:\?' | sed -E 's/^\$\{//; s/:\?$//' | sort -u; }

# Setting names an .env.example offers, set or commented out.
offered_settings() { sed -nE 's/^#? *([A-Z][A-Z0-9_]*)=.*/\1/p' | sort -u; }

# ── 1. Prerequisites ──────────────────────────────────────────────────────────

say "Fitman update"
say ""
command -v git >/dev/null 2>&1 || die "git is not installed."
command -v docker >/dev/null 2>&1 || die "Docker is not installed."
docker compose version >/dev/null 2>&1 || die "Docker Compose v2 is missing (the 'docker compose' command)."
docker info >/dev/null 2>&1 ||
    die "can't reach the Docker daemon. Is Docker running, and are you in the docker group?"
[ -f .env ] || die "there's no .env here. For a first installation, run ./setup.sh."

# ── 2. What's new ─────────────────────────────────────────────────────────────

upstream="$(git rev-parse --abbrev-ref --symbolic-full-name '@{u}' 2>/dev/null)" ||
    die "this branch doesn't track a remote branch, so there's nothing to update from."
git fetch --quiet || die "couldn't fetch from $upstream. Check the network, then try again."

old="$(git rev-parse HEAD)"
new="$(git rev-parse "$upstream")"
old_short="$(git rev-parse --short=12 HEAD)"

if [ "$old" = "$new" ]; then
    if [ "$REBUILD" = 0 ]; then
        say "Already up to date ($old_short)."
        say "To rebuild and restart anyway: ./update.sh --rebuild"
        exit 0
    fi
    say "Already up to date ($old_short); rebuilding as asked."
elif ! git merge-base --is-ancestor HEAD "$upstream"; then
    die "this clone has diverged from $upstream: it has commits that aren't there, so it can't simply move forward.
See them with: git log $upstream..HEAD"
else
    say "Updating $old_short to $(git rev-parse --short=12 "$upstream"):"
    git log --oneline --no-decorate "HEAD..$upstream" | sed 's/^/  /'
fi

# ── 3. Nothing changes until these hold ───────────────────────────────────────

changed="$(git status --porcelain --untracked-files=no)"
if [ -n "$changed" ]; then
    die "files that belong to Fitman have been changed here:
$changed
An update would overwrite them. Keep your changes somewhere else (settings belong in .env), then undo
them with: git checkout -- <file>"
fi

# The new version's requirements, read before it is merged: a missing setting
# stops the update with nothing changed, and running it again then just works.
missing=""
for name in $(git show "$upstream:docker-compose.yml" | required_settings); do
    if [ -z "$(env_get "$name")" ] && [ -z "${!name:-}" ]; then missing="$missing $name"; fi
done
if [ -n "$missing" ]; then
    die "the new version needs settings your .env doesn't have:$missing
Add them to .env (.env.example explains each), or run ./setup.sh, which adds what's missing.
Then run ./update.sh again. Nothing has been changed."
fi

# Offered by the new .env.example but not the current one.
added="$(git show "$upstream:.env.example" | offered_settings |
    grep -vxF -f <(git show "HEAD:.env.example" | offered_settings) || true)"
if [ -n "$added" ]; then
    say ""
    say "New optional settings (see .env.example):"
    printf '%s\n' "$added" | sed 's/^/  /'
fi

# ── 4. Back up the database ───────────────────────────────────────────────────

backup=""
say ""
if [ -z "$(docker compose ps -q postgres 2>/dev/null)" ]; then
    say "Fitman isn't running, so there's no database to back up. Skipping the backup."
else
    mkdir -p backups
    backup="backups/fitman_$(date +%Y%m%d_%H%M%S).sql"
    say "Backing up the database to $backup"
    # --clean --if-exists: the dump can be restored over the existing database.
    if ! docker compose exec -T postgres pg_dump --clean --if-exists -U fitman fitman >"$backup" ||
        [ ! -s "$backup" ]; then
        rm -f "$backup"
        die "the database backup failed or came out empty, so the update stopped. Nothing has been changed."
    fi
fi

# ── 5. Update and restart ─────────────────────────────────────────────────────

if [ "$old" != "$new" ]; then
    git merge --ff-only --quiet "$upstream"
fi

started="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
say ""
say "Rebuilding and restarting Fitman."
if ! docker compose up -d --build --wait; then
    {
        say ""
        say "Error: Fitman didn't come up healthy after the update."
        say "See what went wrong with: docker compose logs backend"
        say ""
        say "To go back to the version you had ($old_short):"
        say "  git reset --hard $old_short"
        if [ -n "$backup" ]; then
            say "  docker compose stop backend frontend"
            say "  docker compose exec -T postgres psql -U fitman fitman < $backup"
        fi
        say "  docker compose up -d --build --wait"
    } >&2
    exit 1
fi

# ── 6. Report ─────────────────────────────────────────────────────────────────

migrations="$(docker compose logs --no-log-prefix --since "$started" backend 2>/dev/null |
    grep -o 'Running upgrade.*' || true)"
say ""
if [ -n "$migrations" ]; then
    say "Database migrations applied:"
    printf '%s\n' "$migrations" | sed 's/^/  /'
else
    say "No database migrations to apply."
fi
say ""
say "Fitman is up to date ($(git rev-parse --short=12 HEAD)) and running."
if [ -n "$backup" ]; then say "The backup taken just before is $backup."; fi
