# CHORD Data Repository Service

A proof of concept based on GA4GH's DRS specifications. This flask application
offers an interface to query files in such a fashion: "drs://some-domain/some-ID"

## TODO / Future considerations

 - Currently not checking if a file is already in the repository

## Environment Variables

None are currently needed (the only one being used currently is by pytest, it is
set automatically inside the tox.ini config).

## Running in Development

Development dependencies are described in `requirements.txt` and can be
installed using the following command:

```bash
pip install -r requirements.txt
```

Afterwards we need to setup the DB:

```bash
flask db init
flask db upgrade
```

Most likely you will want to load some objects to serve through this service.
This can be done with this command (currently ingestion is not recursive):

```bash
flask ingest $A_FILE_OR_A_DIRECTORY
```

The Flask development server can be run with the following command:

```bash
FLASK_DEBUG=True flask run
```

## Running Tests

To run all tests and calculate coverage, run the following command:

```bash
tox
```

Tox is configured to run both pytest and flake8, you may want to uncomment
the second line of tox.ini (envlist = ...) so as to run these commands
for multiple versions of Python.

## Deploying

In production, the service should be deployed using a WSGI service like
[uWSGI](https://uwsgi-docs.readthedocs.io/en/latest/).
