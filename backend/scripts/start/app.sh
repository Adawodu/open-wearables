#!/bin/bash
set -e -x

# Init database
echo 'Applying migrations...'
uv run alembic upgrade head

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
