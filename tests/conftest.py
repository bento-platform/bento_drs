import os
import pytest
from chord_drs.app import application, db
from chord_drs.models import DrsObject
from chord_drs.config import BASEDIR, APP_DIR
from chord_drs.commands import create_drs_bundle
from chord_drs.backends import FakeBackend


SQLALCHEMY_DATABASE_URI = 'sqlite:///' + os.path.join(BASEDIR, "test.sqlite3")
NON_EXISTENT_DUMMY_FILE = os.path.join(BASEDIR, 'potato')
DUMMY_FILE = os.path.join(BASEDIR, "README.md")
DUMMY_DIRECTORY = os.path.join(APP_DIR, "migrations")


@pytest.fixture(scope='session')
def client():
    application.config["SQLALCHEMY_DATABASE_URI"] = SQLALCHEMY_DATABASE_URI
    application.config["BACKEND"] = FakeBackend()

    db.create_all()

    ctx = application.app_context()
    ctx.push()

    yield application.test_client()

    db.session.remove()
    db.drop_all()


@pytest.fixture(scope='session')
def drs_object():
    drs_object = DrsObject(location=DUMMY_FILE)

    db.session.add(drs_object)
    db.session.commit()

    yield drs_object


@pytest.fixture(scope='session')
def drs_bundle():
    bundle = create_drs_bundle(DUMMY_DIRECTORY)

    db.session.commit()

    yield bundle
