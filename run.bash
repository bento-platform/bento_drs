#!/bin/bash

# CWD: /drs

# Set default internal port to 5000
: "${INTERNAL_PORT:=5000}"

# Run migrations if necessary
alembic upgrade head

# Start API server - explicitly 1 worker for now
exec uvicorn \
  --factory chord_drs.app:create_app \
  --host 0.0.0.0 \
  --port "${INTERNAL_PORT}" \
  --workers 1 \
  --proxy-headers
