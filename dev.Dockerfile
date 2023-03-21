FROM ghcr.io/bento-platform/bento_base_image:python-debian-2023.03.21

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

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir debugpy -r requirements.txt

# Copy in just the entrypoint + runner so we have somewhere to start
COPY entrypoint.bash .
COPY run.dev.bash .

# Don't copy any code in - the dev compose file will mount the repo

ENTRYPOINT ["/bin/bash", "/drs/entrypoint.bash"]
CMD ["/bin/bash", "/drs/run.dev.bash"]
