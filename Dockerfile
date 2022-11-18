FROM ghcr.io/bento-platform/bento_base_image:python-debian-2022.10.11

# TODO: change USER
USER root

RUN mkdir -p /drs/bento_drs && \
    mkdir /wes;

WORKDIR /drs/bento_drs
COPY . .

WORKDIR /drs/bento_drs
RUN mkdir -p /drs/bento_drs/data/obj && \
    mkdir -p /drs/bento_drs/data/db;
RUN ["pip", "install", "-r", "requirements.txt"]

# Run
WORKDIR /drs/bento_drs/chord_drs
COPY startup.sh ./startup.sh
CMD ["sh", "startup.sh"]
