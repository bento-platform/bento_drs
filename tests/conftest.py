import boto3
import os
import pathlib
import pytest
import shutil

from flask import g
from flask.testing import FlaskClient
from moto import mock_s3
from pytest_lazyfixture import lazy_fixture

# Must only be imports that don't import authz/app/config/db
from chord_drs.backends.minio import MinioBackend
from chord_drs.data_sources import DATA_SOURCE_LOCAL, DATA_SOURCE_MINIO


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


def dummy_directory_path() -> str:  # Function rather than constant so we can set environ first
    from chord_drs.config import APP_DIR

    return str(APP_DIR / "migrations")


def empty_file_path():  # Function rather than constant so we can set environ first
    from chord_drs.config import APP_DIR

    return str(APP_DIR.parent / "tests" / "empty_file.txt")


@pytest.fixture
def client_minio() -> FlaskClient:
    os.environ["BENTO_AUTHZ_SERVICE_URL"] = AUTHZ_URL

    from chord_drs.app import application, db

    bucket_name = "test"
    application.config["MINIO_URL"] = "http://127.0.0.1:9000"
    application.config["MINIO_BUCKET"] = bucket_name
    application.config["SERVICE_DATA_SOURCE"] = DATA_SOURCE_MINIO

    with application.app_context(), mock_s3():
        s3 = boto3.resource("s3")
        minio_backend = MinioBackend(application.config, resource=s3)
        g.backend = minio_backend

        s3.create_bucket(Bucket=bucket_name)
        db.create_all()

        yield application.test_client()

        db.session.remove()
        db.drop_all()


@pytest.fixture
def client_local() -> FlaskClient:
    local_test_volume = (pathlib.Path(__file__).parent / "data").absolute()
    local_test_volume.mkdir(parents=True, exist_ok=True)

    os.environ["BENTO_AUTHZ_SERVICE_URL"] = AUTHZ_URL
    os.environ["DATA"] = str(local_test_volume)

    from chord_drs.app import application, db

    application.config["SQLALCHEMY_DATABASE_URI"] = SQLALCHEMY_DATABASE_URI
    application.config["SERVICE_DATA_SOURCE"] = DATA_SOURCE_LOCAL

    with application.app_context():
        db.create_all()

        yield application.test_client()

        db.session.remove()
        db.drop_all()

        # clear test volume
        shutil.rmtree(local_test_volume)


@pytest.fixture(params=[lazy_fixture("client_minio"), lazy_fixture("client_local")])
def client(request) -> FlaskClient:
    return request.param


@pytest.fixture
def drs_object():
    os.environ["BENTO_AUTHZ_SERVICE_URL"] = AUTHZ_URL

    from chord_drs.app import db
    from chord_drs.models import DrsBlob

    drs_object = DrsBlob(
        location=dummy_file_path(),
        project_id=DUMMY_PROJECT_ID,
        dataset_id=DUMMY_DATASET_ID,
        data_type=DATA_TYPE_PHENOPACKET,
    )

    db.session.add(drs_object)
    db.session.commit()

    yield drs_object


@pytest.fixture
def drs_bundle():
    os.environ["BENTO_AUTHZ_SERVICE_URL"] = AUTHZ_URL

    from chord_drs.app import db
    from chord_drs.commands import create_drs_bundle

    bundle = create_drs_bundle(
        dummy_directory_path(),
        project_id=DUMMY_PROJECT_ID,
        dataset_id=DUMMY_DATASET_ID,
        data_type=DATA_TYPE_PHENOPACKET,
    )

    db.session.commit()

    yield bundle


@pytest.fixture
def drs_object_minio():
    os.environ["BENTO_AUTHZ_SERVICE_URL"] = AUTHZ_URL

    from chord_drs.app import db
    from chord_drs.models import DrsBlob

    drs_object = DrsBlob(
        location=dummy_file_path(),
        project_id=DUMMY_PROJECT_ID,
        dataset_id=DUMMY_DATASET_ID,
        data_type=DATA_TYPE_PHENOPACKET,
    )

    db.session.add(drs_object)
    db.session.commit()

    yield drs_object


@pytest.fixture
def drs_bundle_minio():
    os.environ["BENTO_AUTHZ_SERVICE_URL"] = AUTHZ_URL

    from chord_drs.app import db
    from chord_drs.commands import create_drs_bundle

    with mock_s3():
        bundle = create_drs_bundle(
            dummy_directory_path(),
            project_id=DUMMY_PROJECT_ID,
            dataset_id=DUMMY_DATASET_ID,
            data_type=DATA_TYPE_PHENOPACKET,
            exclude=frozenset({"versions", "__pycache__"}),
        )

        db.session.commit()

        yield bundle
