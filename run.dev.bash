#!/bin/bash

# CWD: /drs

# Set .gitconfig for development
/set_gitconfig.bash

export FLASK_ENV=development
export FLASK_APP=chord_drs.app:application

if [ -z "${INTERNAL_PORT}" ]; then
  # Set default internal port to 5000
  export INTERNAL_PORT=5000
fi

python -m pip install --user -r requirements.txt

flask db upgrade

python -m debugpy --listen 0.0.0.0:5678 -m flask run --host 0.0.0.0 --port "${INTERNAL_PORT}"
