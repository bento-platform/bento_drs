FROM ghcr.io/bento-platform/bento_base_image:python-debian-2023.02.21

RUN apt install libffi-dev -y

WORKDIR /drs
RUN mkdir /wes

# Install dependencies
COPY requirements.txt .
RUN pip install debugpy -r requirements.txt

# Copy in just the entrypoint + runner so we have somewhere to start
COPY entrypoint.bash .
COPY run.dev.bash .

# Don't copy any code in - the dev compose file will mount the repo

ENTRYPOINT ["/bin/bash", "./entrypoint.bash"]
CMD ["/bin/bash", "./run.dev.bash"]
