import asyncio
import logging
import os
import pathlib
import shutil
from collections.abc import Generator

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from pytest_lazyfixture import lazy_fixture
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Must only be imports that don't import authz/app/config/db
from tests import authz_mock
from tests.constants import (
    AUTHZ_URL,
    DATA_TYPE_PHENOPACKET,
    DUMMY_DATASET_ID_1,
    DUMMY_DATASET_ID_2,
    DUMMY_PROJECT_ID,
    S3_ACCESS_KEY,
    S3_SECRET_KEY,
)


def non_existant_dummy_file_path() -> str:  # Function rather than constant so we can set environ first
    from chord_drs.config import APP_DIR

    return str(APP_DIR.parent / "potato")


def dummy_file_path() -> str:  # Function rather than constant so we can set environ first
    from chord_drs.config import APP_DIR

    return str(APP_DIR.parent / "tests" / "dummy_file.txt")


def dummy_directory_path() -> pathlib.Path:  # Function rather than constant so we can set environ first
    from chord_drs.config import APP_DIR

    return APP_DIR.parent / "tests" / "multi_objects"


def empty_file_path():  # Function rather than constant so we can set environ first
    from chord_drs.config import APP_DIR

    return str(APP_DIR.parent / "tests" / "empty_file.txt")


def reset_caches() -> None:
    """
    Clear all cached configuration-derived objects, so changes to the environment are picked up.
    """
    from chord_drs.authz import get_authz_middleware
    from chord_drs.config import get_config
    from chord_drs.db import get_engine, get_session_maker

    for f in (get_config, get_authz_middleware, get_engine, get_session_maker):
        if hasattr(f, "cache_clear"):  # get_engine is replaced by a plain function in tests using an in-memory DB
            f.cache_clear()


@pytest.fixture(autouse=True)
def config_env(monkeypatch, tmp_path):
    monkeypatch.setenv("BENTO_AUTHZ_SERVICE_URL", AUTHZ_URL)
    monkeypatch.setenv("DATABASE", str(tmp_path))
    monkeypatch.setenv("DATA", str(tmp_path / "data"))
    monkeypatch.setenv("SERVICE_BASE_URL", "http://127.0.0.1:5000")
    reset_caches()
    yield
    reset_caches()


@pytest.fixture(autouse=True)
def mock_authz(monkeypatch):
    """
    Mocks the authorization service; see tests.authz_mock for how to set responses.
    """
    authz_mock.install(monkeypatch)


@pytest.fixture
def test_logger():
    return logging.getLogger("drs_test")


@pytest.fixture
def session_maker(monkeypatch):
    from chord_drs import db
    from chord_drs.models import Base

    # StaticPool: every connection must share the same in-memory database
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)

    monkeypatch.setattr(db, "get_engine", lambda: engine)
    db.get_session_maker.cache_clear()

    yield sessionmaker(engine, expire_on_commit=False)

    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture
def s3_mock_env(s3_server, monkeypatch):
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
def s3_env(monkeypatch):
    monkeypatch.setenv("S3_BUCKET", "test")
    monkeypatch.setenv("S3_VALIDATE_SSL", "false")
    reset_caches()


@pytest.fixture
def s3_config(s3_env):
    from chord_drs.config import get_config

    return get_config()


@pytest.fixture
def local_volume():
    local_test_volume = (pathlib.Path(__file__).parent / "data").absolute()
    local_test_volume.mkdir(parents=True, exist_ok=True)

    yield local_test_volume

    # clear test volume
    shutil.rmtree(local_test_volume)


@pytest.fixture
def authz_disabled(monkeypatch):
    monkeypatch.setenv("BENTO_AUTHZ_ENABLED", "false")
    reset_caches()


@pytest.fixture
def client_s3(s3_mock_env, s3_env, session_maker) -> Generator[TestClient, None, None]:
    from chord_drs.app import create_app
    from chord_drs.backend import get_backend
    from chord_drs.config import get_config

    asyncio.run(get_backend(get_config())._init_bucket_if_required())

    with TestClient(create_app()) as c:
        yield c


@pytest.fixture
def client_local(local_volume: pathlib.Path, monkeypatch, session_maker) -> Generator[TestClient, None, None]:
    from chord_drs.app import create_app

    monkeypatch.setenv("DATA", str(local_volume))
    reset_caches()

    with TestClient(create_app()) as c:
        yield c


@pytest.fixture(params=[lazy_fixture("client_s3"), lazy_fixture("client_local")])
def client(request) -> TestClient:
    return request.param


async def _create_blob(location: str, dataset_id: str):
    from chord_drs.backend import get_backend
    from chord_drs.config import get_config
    from chord_drs.models import DrsBlob

    return await DrsBlob.create(
        backend=get_backend(get_config()),
        location=location,
        project_id=DUMMY_PROJECT_ID,
        dataset_id=dataset_id,
        data_type=DATA_TYPE_PHENOPACKET,
    )


@pytest_asyncio.fixture
async def drs_object(session_maker):
    obj = await _create_blob(dummy_file_path(), DUMMY_DATASET_ID_1)

    with session_maker() as session:
        session.add(obj)
        session.commit()

    yield obj


@pytest_asyncio.fixture
async def drs_multi_object(session_maker):
    objs = []

    for f in sorted(dummy_directory_path().glob("*"), key=lambda ff: ff.name.casefold()):
        if f.is_file():
            # files are sorted by name: 0, 2 are ID 1; 1, 3 are ID 2
            objs.append(await _create_blob(str(f), (DUMMY_DATASET_ID_1, DUMMY_DATASET_ID_2)[len(objs) % 2]))

    with session_maker() as session:
        session.add_all(objs)
        session.commit()

    return objs


@pytest_asyncio.fixture
async def drs_object_s3(session_maker):
    obj = await _create_blob(dummy_file_path(), DUMMY_DATASET_ID_1)

    with session_maker() as session:
        session.add(obj)
        session.commit()

    yield obj


pytest_plugins = ["s3_server_mock"]
