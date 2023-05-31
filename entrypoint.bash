#!/bin/bash

cd /drs || exit

# Create bento_user + home
source /create_service_user.bash

# Fix permissions on /drs; fix data directory permissions more specifically if needed
chown -R bento_user:bento_user /drs
if [[ -n "${BENTO_DRS_CONTAINER_DATA_VOLUME_DIR}" ]]; then
  # Location of volume mount - run chown here.
  chown -R bento_user:bento_user "${BENTO_DRS_CONTAINER_DATA_VOLUME_DIR}"
fi

# Use the database and object folder path variables more directly to create them
# and set their permissions.
if [[ -n "${DATABASE}" ]]; then
  # DATABASE is a folder; confusing naming
  mkdir -p "${DATABASE}"
  chown -R bento_user:bento_user "${DATABASE}"
fi

if [[ -n "${DATA}" ]]; then
  # DATA is another folder; confusing naming
  mkdir -p "${DATA}"
  chown -R bento_user:bento_user "${DATA}"
fi

# Set .gitconfig for development, since we're overriding the base image entrypoint
gosu bento_user /bin/bash -c '/set_gitconfig.bash'

# Drop into bento_user from root and execute the CMD specified for the image
exec gosu bento_user "$@"
