FROM ghcr.io/bento-platform/bento_base_image:python-debian-2022.10.11

# TODO: change USER
USER root

RUN apt install libffi-dev -y

RUN mkdir -p /drs/bento_drs && \
    mkdir /wes;

RUN echo "Building DRS in Development Mode";

WORKDIR /drs/bento_drs
COPY ./requirements.txt .

WORKDIR /drs/bento_drs
RUN mkdir -p /drs/bento_drs/data/obj && \
    mkdir -p /drs/bento_drs/data/db;
RUN ["pip", "install", "debugpy", "-r", "requirements.txt"]

# Run
WORKDIR /drs/bento_drs/chord_drs
COPY startup.sh ./startup.sh