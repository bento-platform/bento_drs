from typing import Generator, Type, TypeVar
import os
import pathlib
import pytest
import shutil

from aioboto3 import Session
from flask import g
from flask.testing import FlaskClient
import pytest_asyncio
from pytest_lazyfixture import lazy_fixture
from unittest.mock import patch


# Must only be imports that don't import authz/app/config/db
from chord_drs.backends.s3 import S3Backend
from chord_drs.data_sources import DATA_SOURCE_LOCAL, DATA_SOURCE_S3

from tests.constants import (
    AUTHZ_URL,
    DATA_TYPE_PHENOPACKET,
    DUMMY_DATASET_ID,
    DUMMY_PROJECT_ID,
    S3_HOST,
    S3_PORT,
    S3_SECRET_KEY,
    S3_ACCESS_KEY,
    SQLALCHEMY_DATABASE_URI,
)


T = TypeVar("T")


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


def create_fake_session(base_class: Type[T], url_overrides: dict[str, str]) -> Type[T]:
    """
    Taken from aioboto3's unit tests: https://github.com/terricain/aioboto3/blob/main/tests/conftest.py

    Creates a mocked session from the provided base class.
    """

    class FakeSession(base_class):
        def __init__(self, *args, **kwargs):
            super(FakeSession, self).__init__(*args, **kwargs)

            self.__url_overrides = url_overrides
            self.__secret_key = S3_SECRET_KEY
            self.__access_key = S3_ACCESS_KEY

        def client(self, *args, **kwargs):
            if "endpoint_url" not in kwargs and args[0] in self.__url_overrides:
                kwargs["endpoint_url"] = self.__url_overrides[args[0]]

            kwargs["aws_access_key_id"] = self.__secret_key
            kwargs["aws_secret_access_key"] = self.__access_key

            return super(FakeSession, self).client(*args, **kwargs)

        def resource(self, *args, **kwargs):
            if "endpoint_url" not in kwargs and args[0] in self.__url_overrides:
                kwargs["endpoint_url"] = self.__url_overrides[args[0]]

            kwargs["aws_access_key_id"] = self.__secret_key
            kwargs["aws_secret_access_key"] = self.__access_key

            return super(FakeSession, self).resource(*args, **kwargs)

    return FakeSession


@pytest.fixture
def s3_session(s3_server):
    """
    Taken from aioboto3's unit tests: https://github.com/terricain/aioboto3/blob/main/tests/conftest.py

    Creates and starts a mocked aioboto3.Session for async S3 tests.
    Parent fixture 's3_server' starts the mock S3 server
    """
    FakeAioboto3Session = create_fake_session(Session, {"s3": s3_server})

    session = patch("aioboto3.Session", FakeAioboto3Session)
    session.start()

    yield

    session.stop()


@pytest.fixture
def drs_base_url():
    base_url = "http://127.0.0.1:5000"
    os.environ["SERVICE_BASE_URL"] = base_url
    from chord_drs.app import application

    application.config["SERVICE_BASE_URL"] = base_url


@pytest.fixture
def s3_config() -> dict:
    return {
        "S3_ENDPOINT": f"{S3_HOST}:{S3_PORT}",
        "S3_ACCESS_KEY": "test_access_key",
        "S3_SECRET_KEY": "test_secret_key",
        "S3_BUCKET": "test",
        "S3_REGION_NAME": "us-east-1",
        "S3_VALIDATE_SSL": False,
        "S3_USE_HTTPS": False,
        "SERVICE_DATA_SOURCE": DATA_SOURCE_S3,
        "AUTHZ_URL": AUTHZ_URL,
    }


@pytest.fixture
def client_s3(s3_session, drs_base_url, s3_config) -> Generator[FlaskClient, None, None]:
    os.environ["BENTO_AUTHZ_SERVICE_URL"] = AUTHZ_URL

    import asyncio
    from chord_drs.app import db, application

    application.config.update(s3_config)

    with application.app_context():
        s3_backend = S3Backend(application.config)
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


pytest_plugins = ["s3_server_mock"]
