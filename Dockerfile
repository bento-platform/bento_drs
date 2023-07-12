FROM ghcr.io/bento-platform/bento_base_image:python-debian-2023.05.12

RUN apt-get update -y && \
    apt-get install gcc libffi-dev -y && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /drs
RUN mkdir /wes

# Install dependencies
COPY pyproject.toml pyproject.toml
COPY poetry.lock poetry.lock
RUN pip install --no-cache-dir gunicorn==20.1.0 && \
    poetry config virtualenvs.create false && \
    poetry install --without dev --no-root

# Copy only what's required for a production instance
COPY chord_drs chord_drs
COPY entrypoint.bash .
COPY run.bash .
COPY LICENSE .
COPY README.md .

# Install the module itself, locally (similar to `pip install -e .`)
RUN poetry install --without dev

ENTRYPOINT ["/bin/bash", "/drs/entrypoint.bash"]
CMD ["/bin/bash", "/drs/run.bash"]
