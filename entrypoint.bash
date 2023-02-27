#!/bin/bash

cd /drs || exit

# Create bento_user + home
source /create_service_user.bash

# Make data directories if needed
# TODO: Don't hardcode these; this should be determined by an environment variable
mkdir -p /drs/data/db
mkdir -p /drs/data/obj

# Fix permissions on /drs
chown -R bento_user:bento_user /drs

# Drop into bento_user from root and execute the CMD specified for the image
exec gosu bento_user "$@"
