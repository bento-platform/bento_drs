import os
import pytest
from chord_drs.app import application, db
from chord_drs.models import DrsObject
from chord_drs.config import BASEDIR, APP_DIR


NON_EXISTENT_DUMMY_FILE = os.path.join(BASEDIR, 'potato')
DUMMY_FILE = os.path.join(BASEDIR, "README.md")
DUMMY_DIRECTORY = os.path.join(APP_DIR, "migrations")


@pytest.fixture(scope='session')
def client():
    db.create_all()

    yield application.test_client()

    db.session.remove()
    db.drop_all()


@pytest.fixture
def drs_object():
    drs_object = DrsObject(location=DUMMY_FILE)

    db.session.add(drs_object)
    db.session.commit()

    yield drs_object
