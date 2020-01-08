import os


BASEDIR = os.path.abspath(os.path.dirname(__file__))
TESTING = 'CHORD_DRS_TESTING' in os.environ

if TESTING:
    DB_NAME = 'test.sqlite3'
else:
    DB_NAME = 'db.sqlite3'


class Config(object):
    SQLALCHEMY_DATABASE_URI = 'sqlite:///' + os.path.join(BASEDIR, DB_NAME)
    SQLALCHEMY_TRACK_MODIFICATIONS = False
