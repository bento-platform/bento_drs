import os
import pytest
from chord_drs.app import app, db
from chord_drs.models import DrsObject
from config import BASEDIR


@pytest.fixture(scope='session')
def client():
    db.create_all()

    yield app.test_client()

    db.session.remove()
    db.drop_all()


@pytest.fixture
def drs_object():
    drs_object = DrsObject(location=os.path.join(BASEDIR, "README.md"))

    db.session.add(drs_object)
    db.session.commit()

    yield drs_object
