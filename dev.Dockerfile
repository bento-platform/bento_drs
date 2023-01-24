FROM ghcr.io/bento-platform/bento_base_image:python-debian-2022.12.06

# TODO: change USER
USER root

RUN apt install libffi-dev -y

RUN echo "Building DRS in Development Mode";
WORKDIR /drs
RUN mkdir /wes && \
    mkdir -p /drs/data/obj && \
    mkdir -p /drs/data/db;

# Install requirements
COPY requirements.txt .
RUN pip install debugpy -r requirements.txt

# Don't copy anything in - the dev compose file will mount the repo

ENTRYPOINT ["/bin/bash", "./entrypoint.dev.bash"]
