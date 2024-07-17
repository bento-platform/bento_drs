# CHORD Data Repository Service

![Test Status](https://github.com/bento-platform/bento_drs/workflows/Test/badge.svg)
![Lint Status](https://github.com/bento-platform/bento_drs/workflows/Lint/badge.svg)
[![codecov](https://codecov.io/gh/bento-platform/bento_drs/branch/master/graph/badge.svg)](https://codecov.io/gh/bento-platform/bento_drs)

A proof of concept based on [GA4GH's DRS specifications](https://ga4gh.github.io/data-repository-service-schemas/preview/release/drs-1.0.0/docs/).
This flask application offers an interface to query files in such 
a fashion: `drs://some-domain/some-ID`.

For storing the files, two methods are currently supported : in the current filesystem
or inside a MinIO instance (which is a s3-like software).


## TODO / Future considerations

 - Ingesting is either through the command line or by the endpoint of the same name
 (which will create a single object).
 - Consider how to be aware of http vs https depending on the deployment setup
 (in singularity, docker, as is).


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
poetry run flask db upgrade
```

Most likely you will want to load some objects to serve through this service.
This can be done with this command (ingestion is recursive for directories):

```bash
poetry run flask ingest $A_FILE_OR_A_DIRECTORY
```

The Flask development server can be run with the following command:

```bash
FLASK_DEBUG=True poetry run flask run
```


## Generating Migrations

To generate migrations while in the shell of a development Docker container, 
run the following command:

```bash
poetry run flask db migrate -m "describe what has changed here"
```

Migrations will be automatically applied in the Docker environment (dev/prod) 
on container restart, but if you want to run them manually, use the following 
command:

```bash
poetry run flask db upgrade
```


## Running Tests

To run all tests and calculate coverage, run the following command:

```bash
poetry run tox
```

Tox is configured to run both pytest and flake8, you may want to uncomment
the second line of tox.ini (envlist = ...) so as to run these commands
for multiple versions of Python.


## Deploying

In production, the service should be deployed using a WSGI service like
[uWSGI](https://uwsgi-docs.readthedocs.io/en/latest/).

With uWSGI you should point to chord_drs.app:application, the wsgi.py file
at the root of the project is there to simplify executing the commands (such
as "ingest")


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
