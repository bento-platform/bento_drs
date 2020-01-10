import os
from pathlib import Path


BASEDIR = Path(__file__).resolve().parents[1]
TESTING = 'CHORD_DRS_TESTING' in os.environ

if TESTING:
    DB_NAME = 'test.sqlite3'
else:
    DB_NAME = 'db.sqlite3'


class Config(object):
    SQLALCHEMY_DATABASE_URI = 'sqlite:///' + os.path.join(BASEDIR, DB_NAME)
    SQLALCHEMY_TRACK_MODIFICATIONS = False
