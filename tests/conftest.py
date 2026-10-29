import logging
import os
import pathlib
import shutil
from collections.abc import Generator

import pytest
import pytest_asyncio
from flask import g
from flask.testing import FlaskClient
from pytest_lazyfixture import lazy_fixture

# Must only be imports that don't import authz/app/config/db
from chord_drs.backends.s3 import S3Backend
from chord_drs.data_sources import DATA_SOURCE_LOCAL, DATA_SOURCE_S3
from tests.constants import (
    AUTHZ_URL,
    DATA_TYPE_PHENOPACKET,
    DUMMY_DATASET_ID_1,
    DUMMY_DATASET_ID_2,
    DUMMY_PROJECT_ID,
    S3_ACCESS_KEY,
    S3_SECRET_KEY,
    SQLALCHEMY_DATABASE_URI,
)


def non_existant_dummy_file_path() -> str:  # Function rather than constant so we can set environ first
    from chord_drs.config import APP_DIR

    return str(APP_DIR.parent / "potato")


def dummy_file_path() -> str:  # Function rather than constant so we can set environ first
    from chord_drs.config import APP_DIR

    return str(APP_DIR.parent / "tests" / "dummy_file.txt")


def dummy_directory_path() -> pathlib.Path:  # Function rather than constant so we can set environ first
    from chord_drs.config import APP_DIR

    return APP_DIR / "migrations"


def empty_file_path():  # Function rather than constant so we can set environ first
    from chord_drs.config import APP_DIR

    return str(APP_DIR.parent / "tests" / "empty_file.txt")


@pytest.fixture
def test_logger():
    return logging.getLogger("drs_test")


@pytest.fixture
def s3_env(s3_server, monkeypatch):
    """
    Points botocore at the mock S3 server (started by the parent 's3_server' fixture) through the
    standard AWS env vars, the same way a deployment configures the S3 backend.
    """
    monkeypatch.setenv("AWS_ENDPOINT_URL_S3", s3_server)
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", S3_ACCESS_KEY)
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", S3_SECRET_KEY)
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
    # Keep the developer's own AWS config out of the tests
    monkeypatch.delenv("AWS_PROFILE", raising=False)
    monkeypatch.setenv("AWS_CONFIG_FILE", os.devnull)
    monkeypatch.setenv("AWS_SHARED_CREDENTIALS_FILE", os.devnull)


@pytest.fixture
def drs_base_url():
    base_url = "http://127.0.0.1:5000"
    os.environ["SERVICE_BASE_URL"] = base_url
    from chord_drs.app import application

    application.config["SERVICE_BASE_URL"] = base_url


@pytest.fixture
def s3_config() -> dict:
    return {
        "S3_BUCKET": "test",
        "S3_VALIDATE_SSL": False,
        "SERVICE_DATA_SOURCE": DATA_SOURCE_S3,
        "AUTHZ_URL": AUTHZ_URL,
        "LOG_LEVEL": "info",
    }


@pytest.fixture
def client_s3(s3_env, drs_base_url, s3_config, test_logger) -> Generator[FlaskClient, None, None]:
    os.environ["BENTO_AUTHZ_SERVICE_URL"] = AUTHZ_URL

    import asyncio

    from chord_drs.app import application, db

    application.config.update(s3_config)

    with application.app_context():
        s3_backend = S3Backend(application.config, test_logger)
        asyncio.run(s3_backend._init_bucket_if_required())
        g.backend = s3_backend

        db.create_all()

        yield application.test_client()

        db.session.remove()
        db.drop_all()


@pytest.fixture
def local_volume():
    local_test_volume = (pathlib.Path(__file__).parent / "data").absolute()
    local_test_volume.mkdir(parents=True, exist_ok=True)

    yield local_test_volume

    # clear test volume
    shutil.rmtree(local_test_volume)


@pytest.fixture
def client_local(local_volume: pathlib.Path, drs_base_url) -> Generator[FlaskClient, None, None]:
    os.environ["BENTO_AUTHZ_SERVICE_URL"] = AUTHZ_URL
    os.environ["DATA"] = str(local_volume)

    from chord_drs.app import application, db

    application.config["SQLALCHEMY_DATABASE_URI"] = SQLALCHEMY_DATABASE_URI
    application.config["SERVICE_DATA_SOURCE"] = DATA_SOURCE_LOCAL
    application.config["SERVICE_DATA"] = str(local_volume)
    application.config["AUTHZ_URL"] = AUTHZ_URL

    with application.app_context():
        db.create_all()

        yield application.test_client()

        db.session.remove()
        db.drop_all()


@pytest.fixture(params=[lazy_fixture("client_s3"), lazy_fixture("client_local")])
def client(request) -> FlaskClient:
    return request.param


@pytest_asyncio.fixture
async def drs_object():
    os.environ["BENTO_AUTHZ_SERVICE_URL"] = AUTHZ_URL

    from chord_drs.app import db
    from chord_drs.models import DrsBlob

    drs_object = await DrsBlob.create(
        location=dummy_file_path(),
        project_id=DUMMY_PROJECT_ID,
        dataset_id=DUMMY_DATASET_ID_1,
        data_type=DATA_TYPE_PHENOPACKET,
    )

    db.session.add(drs_object)
    db.session.commit()

    yield drs_object


@pytest_asyncio.fixture
async def drs_multi_object():
    os.environ["BENTO_AUTHZ_SERVICE_URL"] = AUTHZ_URL

    from chord_drs.app import db
    from chord_drs.models import DrsBlob

    objs = []

    for f in sorted(dummy_directory_path().glob("*"), key=lambda ff: ff.name.casefold()):
        if f.is_file():
            obj = await DrsBlob.create(
                location=str(f),
                project_id=DUMMY_PROJECT_ID,
                dataset_id=(DUMMY_DATASET_ID_1, DUMMY_DATASET_ID_2)[len(objs) % 2],  # 0, 2 are ID 1; 1, 3 are ID 2
                data_type=DATA_TYPE_PHENOPACKET,
            )

            db.session.add(obj)
            objs.append(obj)

    db.session.commit()

    return objs


@pytest_asyncio.fixture
async def drs_object_s3():
    os.environ["BENTO_AUTHZ_SERVICE_URL"] = AUTHZ_URL

    from chord_drs.app import db
    from chord_drs.models import DrsBlob

    drs_obj = await DrsBlob.create(
        location=dummy_file_path(),
        project_id=DUMMY_PROJECT_ID,
        dataset_id=DUMMY_DATASET_ID_1,
        data_type=DATA_TYPE_PHENOPACKET,
    )

    db.session.add(drs_obj)
    db.session.commit()

    yield drs_obj


pytest_plugins = ["s3_server_mock"]
