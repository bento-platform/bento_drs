# Bento Data Repository Service

![Test Status](https://github.com/bento-platform/bento_drs/workflows/Test/badge.svg)
![Lint Status](https://github.com/bento-platform/bento_drs/workflows/Lint/badge.svg)
[![codecov](https://codecov.io/gh/bento-platform/bento_drs/branch/master/graph/badge.svg)](https://codecov.io/gh/bento-platform/bento_drs)

A data repository / object storage service based on 
[GA4GH's DRS specifications](https://ga4gh.github.io/data-repository-service-schemas/preview/release/drs-1.4.0/docs/).

For storing the files, two methods are currently supported: on-disk, or in an S3-compatible storage backend such as 
[MinIO](https://github.com/minio/minio).


## Configuration

At the root of this project there is a sample dotenv file (.env-sample). These can be
exported as environment variables or used as is. Simply copy the sample file and
provide the missing values.

```bash
cp .env-sample .env
```


## Running in Development

Development dependencies are described in `requirements.txt` and can be
installed using the following command:

```bash
poetry install
```

Afterward, we need to set up the DB:

```bash
poetry run alembic upgrade head
```

Most likely you will want to load some objects to serve through this service.
This can be done with this command:

```bash
poetry run drs-ingest $A_FILE
```

The development server (with auto-reload) can be run with the following command:

```bash
BENTO_DEBUG=True poetry run uvicorn --factory chord_drs.app:create_app --reload
```


## Generating Migrations

To generate migrations while in the shell of a development Docker container, 
run the following command:

```bash
poetry run alembic revision --autogenerate -m "describe what has changed here"
```

Migrations will be automatically applied in the Docker environment (dev/prod) 
on container restart, but if you want to run them manually, use the following 
command:

```bash
poetry run alembic upgrade head
```


## Running Tests

To run all tests and calculate coverage, run the following command:

```bash
poetry run tox
```

Tox is configured to run ruff (format + lint) and pytest. You may want to uncomment
the second line of tox.ini (envlist = ...) so as to run these commands
for multiple versions of Python.


## Deploying

In production, the service is an ASGI application, run with
[uvicorn](https://www.uvicorn.org/) (see `run.bash`):

```bash
uvicorn --factory chord_drs.app:create_app
```


## API

##### GET a single object

`/objects/<string:object_id>`

`/ga4gh/drs/v1/objects/<string:object_id>`

Returns a standard GA4GH record for the object.

##### GET search

`/search`

exact match `/search?name=P-1001.hc.g.vcf.gz` 

partial match `/search?fuzzy_name=1001`

##### GET download a single object

`/objects/<string:object_id>/download`


##### POST ingest

`/ingest`

e.g. POST body (multipart form-encoded)

```
path=examples/P-1001.hc.g.vcf.gz
```

This will automatically deduplicate with existing DRS objects if the file matches.

To ingest and force-create a duplicate record, provide the `deduplicate` parameter, set to `false`:

```
path=examples/P-1001.hc.g.vcf.gz&deduplicate=false
```

If `path` is left out and instead a file is provided, the file will be uploaded instead
of copied from the specified local filesystem path.


##### GET service info

`/service-info`

Returns a GA4GH+Bento-formatted service info response.
