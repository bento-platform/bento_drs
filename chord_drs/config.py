import os
from pathlib import Path
from typing import Optional

from chord_drs.constants import SERVICE_NAME


__all__ = [
    "APP_DIR",
    "BASEDIR",
    "Config",
]


APP_DIR = Path(__file__).resolve().parents[0]

# when deployed inside chord_singularity, DATABASE will be set
BASEDIR = os.environ.get("DATABASE", APP_DIR.parent)
MINIO_URL = os.environ.get("MINIO_URL", None)
SERVICE_DATA = Path(os.environ.get("DATA", os.path.join(Path.home(), "chord_drs_data"))).expanduser().resolve()


class Config:
    SQLALCHEMY_DATABASE_URI = 'sqlite:///' + str(Path(os.path.join(BASEDIR, "db.sqlite3")).expanduser().resolve())
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    CHORD_URL: Optional[str] = os.environ.get("CHORD_URL", None)
    CHORD_SERVICE_URL_BASE_PATH: Optional[str] = os.environ.get("SERVICE_URL_BASE_PATH", None)
    SERVICE_DATA_SOURCE: str = 'minio' if MINIO_URL else 'local'
    SERVICE_DATA: Optional[str] = None if MINIO_URL else SERVICE_DATA
    MINIO_URL: Optional[str] = MINIO_URL
    MINIO_USERNAME: Optional[str] = os.environ.get('MINIO_USERNAME') if MINIO_URL else None
    MINIO_PASSWORD: Optional[str] = os.environ.get('MINIO_PASSWORD') if MINIO_URL else None
    MINIO_BUCKET: Optional[str] = os.environ.get('MINIO_BUCKET') if MINIO_URL else None


print(f"[{SERVICE_NAME}] Using: database URI {Config.SQLALCHEMY_DATABASE_URI}")
print(f"[{SERVICE_NAME}] The data source is  {Config.SERVICE_DATA_SOURCE}")
print(f"[{SERVICE_NAME}]           data path {Config.SERVICE_DATA}")
print(f"[{SERVICE_NAME}]           minio url {Config.MINIO_URL}", flush=True)
