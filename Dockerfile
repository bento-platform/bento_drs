FROM ghcr.io/bento-platform/bento_base_image:python-debian-2023.02.09

# TODO: change USER
USER root

RUN apt install gcc libffi-dev -y

RUN echo "Building DRS in Production Mode";
WORKDIR /drs
RUN mkdir /wes && \
    mkdir -p /drs/data/obj && \
    mkdir -p /drs/data/db

# Install dependencies
COPY requirements.txt requirements.txt
RUN ["pip", "install", "-r", "requirements.txt"]

# Copy only what's required for a production instance
COPY chord_drs chord_drs
COPY entrypoint.bash .

ENTRYPOINT ["/bin/bash", "./entrypoint.bash"]
