#!/bin/bash

set -e

echo "Starting Celery worker..."

celery -A backend worker -l info &

CELERY_PID=$!

echo "Starting Daphne server..."

daphne -b 0.0.0.0 -p "${PORT:-8000}" backend.asgi:application &
DAPHNE_PID=$!

# Stop both processes if either one exits.
wait -n "$CELERY_PID" "$DAPHNE_PID"
EXIT_CODE=$?

kill "$CELERY_PID" "$DAPHNE_PID" 2>/dev/null || true

exit "$EXIT_CODE"