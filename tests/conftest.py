import signal
import time
from typing import Generator, Type, TypeVar
import os
import pathlib
import pytest
import requests
import subprocess as sp
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


_proxy_bypass = {
    "http": None,
    "https": None,
}


def start_service(service_name, host, port):
    moto_svr_path = shutil.which("moto_server")
    args = [moto_svr_path, "-H", host, "-p", str(port)]
    process = sp.Popen(args, stdin=sp.PIPE, stdout=sp.PIPE, stderr=sp.PIPE)  # shell=True
    url = "http://{host}:{port}".format(host=host, port=port)

    for i in range(0, 30):
        output = process.poll()
        if output is not None:
            print("moto_server exited status {0}".format(output))
            stdout, stderr = process.communicate()
            print("moto_server stdout: {0}".format(stdout))
            print("moto_server stderr: {0}".format(stderr))
            pytest.fail("Can not start service: {}".format(service_name))

        try:
            # we need to bypass the proxies due to monkeypatches
            requests.get(url, timeout=5, proxies=_proxy_bypass)
            break
        except requests.exceptions.ConnectionError:
            time.sleep(0.5)
    else:
        stop_process(process)  # pytest.fail doesn't call stop_process
        pytest.fail("Can not start service: {}".format(service_name))

    return process


def stop_process(process):
    try:
        process.send_signal(signal.SIGTERM)
        process.communicate(timeout=20)
    except sp.TimeoutExpired:
        process.kill()
        outs, errors = process.communicate(timeout=20)
        exit_code = process.returncode
        msg = "Child process finished {} not in clean way: {} {}".format(exit_code, outs, errors)
        raise RuntimeError(msg)


S3_HOST = "127.0.0.1"
S3_PORT = "9000"
S3_SERVER_URL = f"http://{S3_HOST}:{S3_PORT}"
S3_ACCESS_KEY = "test_access_key"
S3_SECRET_KEY = "test_secret_key"


@pytest.fixture
def s3_server():
    process = start_service("s3", S3_HOST, S3_PORT)
    yield S3_SERVER_URL
    stop_process(process)


T = TypeVar("T")


def create_fake_session(base_class: Type[T], url_overrides: dict[str, str]) -> Type[T]:
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
def client_s3(s3_session, drs_base_url) -> Generator[FlaskClient, None, None]:
    os.environ["BENTO_AUTHZ_SERVICE_URL"] = AUTHZ_URL

    import asyncio
    from chord_drs.app import db, application

    application.config["S3_ENDPOINT"] = f"{S3_HOST}:{S3_PORT}"
    application.config["S3_ACCESS_KEY"] = "test_access_key"
    application.config["S3_SECRET_KEY"] = "test_secret_key"
    application.config["S3_BUCKET"] = "test"
    application.config["S3_REGION_NAME"] = "us-east-1"
    application.config["S3_VALIDATE_SSL"] = False
    application.config["S3_USE_HTTPS"] = False
    application.config["SERVICE_DATA_SOURCE"] = DATA_SOURCE_S3
    application.config["AUTHZ_URL"] = AUTHZ_URL

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
