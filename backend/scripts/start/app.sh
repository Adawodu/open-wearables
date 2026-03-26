#!/bin/bash
set -x

# Init database - stamp to head if migration history is inconsistent
echo 'Applying migrations...'
if ! uv run alembic upgrade head 2>&1; then
    echo 'Migration upgrade failed — stamping DB to current head...'
    uv run alembic stamp head
fi

# Initialize provider settings
echo 'Initializing provider settings...'
uv run python scripts/init_provider_settings.py

# Init app
echo "Starting the FastAPI application..."
if [ "$ENVIRONMENT" = "local" ]; then
    uv run fastapi dev app/main.py --host 0.0.0.0 --port 8000
else
    # Start Celery worker + beat in background
    echo "Starting Celery worker..."
    uv run celery -A app.main:celery_app worker --loglevel=info --concurrency=2 &

    echo "Starting Celery beat..."
    uv run celery -A app.main:celery_app beat --loglevel=info &

    # Start FastAPI (foreground)
    uv run fastapi run app/main.py --host 0.0.0.0 --port 8000
fi
