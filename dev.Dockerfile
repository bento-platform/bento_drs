FROM ghcr.io/bento-platform/bento_base_image:python-debian-2023.10.20

LABEL org.opencontainers.image.description="Local development image for Bento DRS."
LABEL devcontainer.metadata='[{ \
  "remoteUser": "bento_user", \
  "customizations": { \
    "vscode": { \
      "extensions": ["ms-python.python", "eamodio.gitlens"], \
      "settings": {"workspaceFolder": "/drs"} \
    } \
  } \
}]'

RUN apt-get update -y && \
    apt-get install libffi-dev -y && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /drs
RUN mkdir /wes

COPY pyproject.toml pyproject.toml
COPY poetry.lock poetry.lock

# Install production + development dependencies
# Without --no-root, we get errors related to the code not being copied in yet.
# But we don't want the code here, otherwise Docker cache doesn't work well.
RUN poetry config virtualenvs.create false && \
    poetry install --no-root

# Copy entrypoint and runner script in, so we have something to start with - even though it'll get
# overwritten by volume mount.
COPY entrypoint.bash .
COPY run.dev.bash .

# Don't copy any code in - the dev compose file will mount the repo

ENTRYPOINT ["/bin/bash", "/drs/entrypoint.bash"]
CMD ["/bin/bash", "/drs/run.dev.bash"]
