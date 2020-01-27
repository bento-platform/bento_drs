import os
from pathlib import Path


APP_DIR = Path(__file__).resolve().parents[0]

if "DATABASE" in os.environ:
    # when deployed inside chord_singularity
    BASEDIR = os.environ["DATABASE"]
else:
    BASEDIR = APP_DIR.parent


class Config():
    SQLALCHEMY_DATABASE_URI = 'sqlite:///' + os.path.join(BASEDIR, "db.sqlite3")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    DATA = Path(os.environ.get("DATA", os.path.join(Path.home(), "chord_drs_data"))).resolve()
