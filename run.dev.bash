#!/bin/bash

# CWD: /drs

# Set .gitconfig for development
/set_gitconfig.bash

export FLASK_ENV='development'
export FLASK_APP='chord_drs.app:application'

# Set default internal port to 5000
: "${INTERNAL_PORT:=5000}"

# Set internal debug port, falling back to default in a Bento deployment
: "${DEBUGGER_PORT:=5682}"

python -m pip install --no-cache-dir -r requirements.txt

flask db upgrade

python -m debugpy --listen "0.0.0.0:${DEBUGGER_PORT}" -m flask run \
  --host 0.0.0.0 \
  --port "${INTERNAL_PORT}"
