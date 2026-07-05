#!/bin/sh
set -e

echo "Running database migrations..."
if ! alembic upgrade head; then
    echo "ERROR: Database migration failed — the server will not start." >&2
    echo "Check the migration output above for details." >&2
    exit 1
fi

echo "Migrations complete. Starting server..."
exec uvicorn main:app --host 0.0.0.0 --port 8000
