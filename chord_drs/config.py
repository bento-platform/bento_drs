import os
import urllib3
from pathlib import Path

from dotenv import load_dotenv

from .constants import SERVICE_NAME, SERVICE_TYPE
from .data_sources import DATA_SOURCE_LOCAL, DATA_SOURCE_MINIO
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


def str_to_bool(value: str) -> bool:
    return value.strip().lower() in ("true", "1", "t", "yes")


BENTO_DEBUG: bool = str_to_bool(os.environ.get("BENTO_DEBUG", os.environ.get("FLASK_DEBUG", "false")))
BENTO_VALIDATE_SSL = str_to_bool(os.environ.get("BENTO_VALIDATE_SSL", str(not BENTO_DEBUG)))

if not BENTO_VALIDATE_SSL:
    # Don't let urllib3 spam us with SSL validation warnings if we're operating with SSL validation off, most likely in
    # a development/test context where we're using self-signed certificates.
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

APP_DIR = Path(__file__).resolve().parent.absolute()

# when deployed inside chord_singularity, DATABASE will be set
BASEDIR = os.environ.get("DATABASE", APP_DIR.parent)
SERVICE_DATA: str = str(
    Path(os.environ.get("DATA", os.path.join(Path.home(), "chord_drs_data"))).expanduser().absolute().resolve()
)

# Authorization variables
AUTHZ_ENABLED = str_to_bool(os.environ.get("AUTHZ_ENABLED", "true"))
AUTHZ_URL: str = _get_from_environ_or_fail("BENTO_AUTHZ_SERVICE_URL").strip().rstrip("/") if AUTHZ_ENABLED else ""

# MinIO-related, check if the credentials have been provided in a file
MINIO_URL = os.environ.get("MINIO_URL")
MINIO_ACCESS_KEY_FILE = os.environ.get("MINIO_ACCESS_KEY_FILE")
MINIO_SECRET_KEY_FILE = os.environ.get("MINIO_ACCESS_KEY_FILE")

MINIO_USERNAME = os.environ.get("MINIO_USERNAME")
MINIO_PASSWORD = os.environ.get("MINIO_PASSWORD")

if MINIO_SECRET_KEY_FILE:
    MINIO_ACCESS_KEY_PATH = Path(MINIO_ACCESS_KEY_FILE).resolve()

    if MINIO_ACCESS_KEY_PATH.exists():
        with open(MINIO_ACCESS_KEY_PATH, "r") as f:
            MINIO_USERNAME = f.read().strip()

if MINIO_SECRET_KEY_FILE:
    MINIO_SECRET_KEY_PATH = Path(MINIO_SECRET_KEY_FILE).resolve()
    if MINIO_SECRET_KEY_PATH.exists():
        with open(MINIO_SECRET_KEY_PATH, "r") as f:
            MINIO_PASSWORD = f.read().strip()


class Config:
    SQLALCHEMY_DATABASE_URI = "sqlite:///" + str(Path(os.path.join(BASEDIR, "db.sqlite3")).expanduser().resolve())
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    PROMETHEUS_ENABLED: bool = str_to_bool(os.environ.get("PROMETHEUS_ENABLED", "false"))

    SERVICE_ID: str = os.environ.get("SERVICE_ID", ":".join(list(SERVICE_TYPE.values())[:2]))
    SERVICE_DATA_SOURCE: str = DATA_SOURCE_MINIO if MINIO_URL else DATA_SOURCE_LOCAL
    SERVICE_DATA: str | None = None if MINIO_URL else SERVICE_DATA
    SERVICE_BASE_URL: str = os.environ.get("SERVICE_BASE_URL", "http://127.0.0.1").strip().rstrip("/")

    MINIO_URL: str | None = MINIO_URL
    MINIO_USERNAME: str | None = MINIO_USERNAME
    MINIO_PASSWORD: str | None = MINIO_PASSWORD
    MINIO_BUCKET: str | None = os.environ.get("MINIO_BUCKET") if MINIO_URL else None
    BENTO_DEBUG: bool = BENTO_DEBUG
    BENTO_VALIDATE_SSL: bool = BENTO_VALIDATE_SSL
    BENTO_CONTAINER_LOCAL: bool = str_to_bool(os.environ.get("BENTO_CONTAINER_LOCAL", "false"))

    # Temporary directory to write files to while they're being ingested - useful in containerized contexts, so we can
    # choose to write temporary files to a volume bound to a host directory with sufficient space for ingesting large
    # files such as reference genomes.
    DRS_INGEST_TMP_DIR: str | None = os.environ.get("DRS_INGEST_TMP_DIR", "").strip() or None

    # CORS
    CORS_ORIGINS: list[str] | str = [x for x in os.environ.get("CORS_ORIGINS", "").split(";") if x] or "*"

    # Authn/z-related configuration
    AUTHZ_URL: str = AUTHZ_URL
    AUTHZ_ENABLED: bool = AUTHZ_ENABLED


print(f"[{SERVICE_NAME}] Using: database URI {Config.SQLALCHEMY_DATABASE_URI}")
print(f"[{SERVICE_NAME}]         data source {Config.SERVICE_DATA_SOURCE}")
print(f"[{SERVICE_NAME}]           data path {Config.SERVICE_DATA}")
print(f"[{SERVICE_NAME}]           minio URL {Config.MINIO_URL}", flush=True)
