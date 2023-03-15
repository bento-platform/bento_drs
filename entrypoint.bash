#!/bin/bash

cd /drs || exit

# Create bento_user + home
source /create_service_user.bash

# Fix permissions on /drs and /env; make data directories if needed
chown -R bento_user:bento_user /drs
chown -R bento_user:bento_user /env
if [[ -z "${DATABASE}" ]]; then
  # DATABASE is a folder; confusing naming
  mkdir -p "${DATABASE}"
  chown -R bento_user:bento_user "${DATABASE}"
fi
if [[ -z "${DATA}" ]]; then
  # DATA is another folder; confusing naming
  mkdir -p "${DATA}"
  chown -R bento_user:bento_user "${DATA}"
fi

# Drop into bento_user from root and execute the CMD specified for the image
exec gosu bento_user "$@"
