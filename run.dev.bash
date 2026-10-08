#!/bin/bash

# CWD: /drs

# Update dependencies and install module locally
/poetry_user_install_dev.bash

# Set default internal port to 5000
: "${INTERNAL_PORT:=5000}"

# Set internal debug port, falling back to default in a Bento deployment
: "${DEBUGGER_PORT:=5682}"

# Run migrations if necessary
alembic upgrade head

# Start API server + debugger, with auto-reload on code changes
python -m debugpy --listen "0.0.0.0:${DEBUGGER_PORT}" -m uvicorn \
  --factory chord_drs.app:create_app \
  --host 0.0.0.0 \
  --port "${INTERNAL_PORT}" \
  --reload
