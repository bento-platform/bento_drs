import os
from pathlib import Path
from typing import Optional


__all__ = [
    "APP_DIR",
    "BASEDIR",
    "Config",
]


APP_DIR = Path(__file__).resolve().parents[0]

# when deployed inside chord_singularity, DATABASE will be set
BASEDIR = os.environ.get("DATABASE", APP_DIR.parent)


class Config:
    SQLALCHEMY_DATABASE_URI = 'sqlite://' + str(Path(os.path.join(BASEDIR, "db.sqlite3")).expanduser().resolve())
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    CHORD_URL: Optional[str] = os.environ.get("CHORD_URL", None)
    CHORD_SERVICE_URL_BASE_PATH: Optional[str] = os.environ.get("SERVICE_URL_BASE_PATH", None)
    DATA = Path(os.environ.get("DATA", os.path.join(Path.home(), "chord_drs_data"))).expanduser().resolve()
