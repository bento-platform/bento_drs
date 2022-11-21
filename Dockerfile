FROM ghcr.io/bento-platform/bento_base_image:python-debian-2022.10.11

# TODO: change USER
USER root

RUN apt install gcc libffi-dev -y

RUN echo "Building DRS in Production Mode";
WORKDIR /drs/bento_drs
RUN mkdir /wes && \
    mkdir -p /drs/bento_drs/data/obj && \
    mkdir -p /drs/bento_drs/data/db;
COPY requirements.txt requirements.txt
RUN ["pip", "install", "-r", "requirements.txt"]
COPY . .

# Run
WORKDIR /drs/bento_drs/chord_drs
COPY startup.sh ./startup.sh
CMD ["sh", "startup.sh"]
