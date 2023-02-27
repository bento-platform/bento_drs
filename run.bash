#!/bin/bash

# CWD: /drs

export FLASK_APP="chord_drs.app:application"
if [[ -z "${INTERNAL_PORT}" ]]; then
  # Set default internal port to 5000
  export INTERNAL_PORT=5000
fi

flask db upgrade

# using 1 worker, multiple threads
# see https://stackoverflow.com/questions/38425620/gunicorn-workers-and-threads
gunicorn "${FLASK_APP}" \
  -w 1 \
  --threads $(( 2 * $(nproc --all) + 1)) \
  -b "0.0.0.0:${INTERNAL_PORT}"
