FROM ghcr.io/bento-platform/bento_base_image:python-debian-2023.03.21

RUN apt-get update -y && \
    apt-get install gcc libffi-dev -y && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /drs
RUN mkdir /wes

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir gunicorn==20.1.0 -r requirements.txt

# Copy only what's required for a production instance
COPY chord_drs chord_drs
COPY entrypoint.bash .
COPY run.bash .

ENTRYPOINT ["/bin/bash", "/drs/entrypoint.bash"]
CMD ["/bin/bash", "/drs/run.bash"]
