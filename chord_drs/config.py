import os
from pathlib import Path

from dotenv import load_dotenv

from .constants import SERVICE_NAME, SERVICE_TYPE
from .logger import logger


__all__ = [
    "APP_DIR",
    "BASEDIR",
    "Config",
]


load_dotenv()


def _get_from_environ_or_fail(var: str) -> str:
    if (val := os.environ.get(var, "")) == "":
        logger.critical(f"{var} must be set")
        exit(1)
    return val


TRUTH_VALUES = ("true", "1")

APP_DIR = Path(__file__).resolve().parent.absolute()

# when deployed inside chord_singularity, DATABASE will be set
BASEDIR = os.environ.get("DATABASE", APP_DIR.parent)
SERVICE_DATA: str = str(
    Path(os.environ.get("DATA", os.path.join(Path.home(), "chord_drs_data")))
    .expanduser()
    .absolute()
    .resolve())

# Authorization variables
AUTHZ_ENABLED = os.environ.get("AUTHZ_ENABLED", "true").strip().lower() in TRUTH_VALUES
AUTHZ_URL: str = _get_from_environ_or_fail("BENTO_AUTHZ_SERVICE_URL").strip().rstrip("/") if AUTHZ_ENABLED else ""

# S3 backend-related, check if the credentials have been provided in a file
DRS_S3_API_URL = os.environ.get("DRS_S3_API_URL")

DRS_S3_ACCESS_KEY = os.environ.get("DRS_S3_ACCESS_KEY")
DRS_S3_SECRET_KEY = os.environ.get("DRS_S3_SECRET_KEY")

if DRS_S3_ACCESS_KEY_FILE := os.environ.get("DRS_S3_ACCESS_KEY_FILE"):
    if (kp := Path(DRS_S3_ACCESS_KEY_FILE).resolve()).exists():
        with open(kp, "r") as f:
            DRS_S3_ACCESS_KEY = f.read().strip()

if DRS_S3_SECRET_KEY_FILE := os.environ.get("DRS_S3_SECRET_KEY_FILE"):
    if (kp := Path(DRS_S3_SECRET_KEY_FILE).resolve()).exists():
        with open(kp, "r") as f:
            DRS_S3_SECRET_KEY = f.read().strip()


class Config:
    SQLALCHEMY_DATABASE_URI = "sqlite:///" + str(Path(os.path.join(BASEDIR, "db.sqlite3")).expanduser().resolve())
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    PROMETHEUS_ENABLED: bool = os.environ.get("PROMETHEUS_ENABLED", "false").strip().lower() in TRUTH_VALUES

    SERVICE_ID: str = os.environ.get("SERVICE_ID", ":".join(list(SERVICE_TYPE.values())[:2]))
    SERVICE_BASE_URL: str = os.environ.get("SERVICE_BASE_URL", "http://127.0.0.1").strip().rstrip("/")

    DRS_S3_API_URL: str | None = DRS_S3_API_URL
    DRS_S3_ACCESS_KEY: str | None = DRS_S3_ACCESS_KEY
    DRS_S3_SECRET_KEY: str | None = DRS_S3_SECRET_KEY
    DRS_S3_BUCKET: str | None = os.environ.get("DRS_S3_BUCKET")
    BENTO_DEBUG = os.environ.get("BENTO_DEBUG", os.environ.get("FLASK_DEBUG", "false")).strip().lower() in TRUTH_VALUES

    # CORS
    CORS_ORIGINS: list[str] | str = [x for x in os.environ.get("CORS_ORIGINS", "").split(";") if x] or "*"

    # Authn/z-related configuration
    AUTHZ_URL: str = AUTHZ_URL
    AUTHZ_ENABLED: bool = AUTHZ_ENABLED


print(f"[{SERVICE_NAME}] Using: database URI {Config.SQLALCHEMY_DATABASE_URI}")
print(f"[{SERVICE_NAME}]              s3 URL {Config.DRS_S3_API_URL}", flush=True)
