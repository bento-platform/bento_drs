from typing import Generator
import os
import pathlib
import pytest
import shutil

from flask import g
from flask.testing import FlaskClient
import pytest_asyncio
from pytest_lazyfixture import lazy_fixture
from unittest.mock import patch, MagicMock

# Must only be imports that don't import authz/app/config/db
from chord_drs.backends.s3 import S3Backend
from chord_drs.data_sources import DATA_SOURCE_LOCAL, DATA_SOURCE_S3


AUTHZ_URL = "http://bento-authz.local"
SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"

DUMMY_PROJECT_ID = "b1738ea3-6ea7-4f43-a13f-51f4398818c4"
DUMMY_DATASET_ID = "c96aa217-e07d-4d52-8c5c-df03f054fd3d"

DATA_TYPE_PHENOPACKET = "phenopacket"


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
def s3_app():
    from chord_drs.app import application

    application.config["S3_ENDPOINT"] = "http://127.0.0.1:9000"
    application.config["S3_USE_HTTPS"] = True
    application.config["S3_BUCKET"] = "test"
    application.config["S3_ACCESS_KEY"] = "test_access_key"
    application.config["S3_SECRET_KEY"] = "test_secret_key"
    application.config["S3_VALIDATE_SSL"] = True
    application.config["S3_REGION_NAME"] = "us-east-1"
    application.config["SERVICE_DATA_SOURCE"] = DATA_SOURCE_S3

    yield application


@pytest.fixture
def client_s3(s3_app) -> Generator[FlaskClient, None, None]:
    os.environ["BENTO_AUTHZ_SERVICE_URL"] = AUTHZ_URL

    from chord_drs.app import db

    with s3_app.app_context(), patch("aioboto3.Session", new_callable=MagicMock) as mock_session:
        mock_s3_session = MagicMock()
        mock_session.return_value = mock_s3_session

        s3_backend = S3Backend(s3_app.config)
        g.backend = s3_backend

        db.create_all()

        yield s3_app.test_client()

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
def client_local(local_volume: pathlib.Path) -> Generator[FlaskClient, None, None]:
    os.environ["BENTO_AUTHZ_SERVICE_URL"] = AUTHZ_URL
    os.environ["DATA"] = str(local_volume)

    from chord_drs.app import application, db

    application.config["SQLALCHEMY_DATABASE_URI"] = SQLALCHEMY_DATABASE_URI
    application.config["SERVICE_DATA_SOURCE"] = DATA_SOURCE_LOCAL
    application.config["SERVICE_DATA"] = str(local_volume)

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
        dataset_id=DUMMY_DATASET_ID,
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

    for f in dummy_directory_path().glob("*"):
        if f.is_file():
            obj = await DrsBlob.create(
                location=str(f),
                project_id=DUMMY_PROJECT_ID,
                dataset_id=DUMMY_DATASET_ID,
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

    drs_object = await DrsBlob.create(
        location=dummy_file_path(),
        project_id=DUMMY_PROJECT_ID,
        dataset_id=DUMMY_DATASET_ID,
        data_type=DATA_TYPE_PHENOPACKET,
    )

    db.session.add(drs_object)
    db.session.commit()

    yield drs_object
