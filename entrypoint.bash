#!/bin/bash

cd /drs || exit

# Create bento_user + home
source /create_service_user.bash

# Fix permissions on /drs; fix data directory permissions more specifically if needed
chown -R bento_user:bento_user /drs
if [[ -z "${BENTO_DRS_CONTAINER_DATA_VOLUME_DIR}" ]]; then
  # Location of volume mount - run chown here.
  chown -R bento_user:bento_user "${BENTO_DRS_CONTAINER_DATA_VOLUME_DIR}"
else
  # Otherwise, use the database and object folders more directly to set up paths & permissions.
  if [[ -z "${DATABASE}" ]]; then
    # DATABASE is a folder; confusing naming
    chown -R bento_user:bento_user "${DATABASE}"
  fi
  if [[ -z "${DATA}" ]]; then
    # DATA is another folder; confusing naming
    chown -R bento_user:bento_user "${DATA}"
  fi
fi

# Set .gitconfig for development, since we're overriding the base image entrypoint
gosu bento_user /bin/bash -c '/set_gitconfig.bash'

# Drop into bento_user from root and execute the CMD specified for the image
exec gosu bento_user "$@"
