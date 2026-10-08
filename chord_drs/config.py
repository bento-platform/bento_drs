from functools import lru_cache
from pathlib import Path
from typing import Annotated

from bento_lib.config.pydantic import BentoFastAPIBaseConfig
from bento_lib.logging import LogLevelLiteral
from bento_lib.service_info.types import BentoExtraServiceInfo
from fastapi import Depends
from pydantic import AliasChoices, Field, field_validator, model_validator
from pydantic_settings import SettingsConfigDict

from .constants import (
    APP_DIR,
    BENTO_SERVICE_KIND,
    DATA_SOURCE_LOCAL,
    DATA_SOURCE_S3,
    GIT_REPOSITORY,
    SERVICE_NAME,
    SERVICE_TYPE,
)

__all__ = [
    "APP_DIR",
    "BENTO_EXTRA_SERVICE_INFO",
    "Config",
    "get_config",
    "ConfigDep",
]

BENTO_EXTRA_SERVICE_INFO: BentoExtraServiceInfo = {
    "serviceKind": BENTO_SERVICE_KIND,
    "gitRepository": GIT_REPOSITORY,
}


class Config(BentoFastAPIBaseConfig):
    model_config = SettingsConfigDict(extra="ignore", frozen=True)

    # FLASK_DEBUG is the legacy (pre-FastAPI) name for this variable
    bento_debug: bool = Field(False, validation_alias=AliasChoices("BENTO_DEBUG", "FLASK_DEBUG"))
    # In a development context, we're likely using self-signed certificates, so don't validate SSL by default
    bento_validate_ssl: bool = Field(default_factory=lambda c: not c["bento_debug"])

    service_id: str = ":".join(list(SERVICE_TYPE.values())[:2])
    service_name: str = SERVICE_NAME
    service_description: str = "Data repository service (based on GA4GH's specs) for a Bento platform node."

    # Base URL (including any path prefix) the service is exposed at; used to build object download URLs
    service_base_url: str = "http://127.0.0.1"

    log_level: LogLevelLiteral = "info"

    # AUTHZ_ENABLED is the legacy (pre-FastAPI) name for this variable
    bento_authz_enabled: bool = Field(True, validation_alias=AliasChoices("BENTO_AUTHZ_ENABLED", "AUTHZ_ENABLED"))
    # Only required if authorization is enabled - checked below.
    bento_authz_service_url: str = ""

    # (Misleadingly named) path to the **directory** in which db.sqlite3 can be found or created.
    # When deployed inside chord_singularity, this will be set.
    database: Path = APP_DIR.parent
    # Directory to store objects in, when not using S3
    data: Path = Path.home() / "chord_drs_data"

    s3_endpoint: str | None = None
    s3_access_key: str | None = None
    s3_secret_key: str | None = None
    s3_bucket: str | None = None
    s3_region_name: str | None = None
    s3_validate_ssl: bool = False
    s3_use_https: bool = True

    # Temporary directory to write files to while they're being ingested - useful in containerized contexts, so we can
    # choose to write temporary files to a volume bound to a host directory with sufficient space for ingesting large
    # files such as reference genomes.
    drs_ingest_tmp_dir: str | None = None

    @field_validator("service_base_url", "bento_authz_service_url", mode="after")
    @classmethod
    def _strip_trailing_slash(cls, v: str) -> str:
        return v.strip().rstrip("/")

    @field_validator("s3_endpoint", "drs_ingest_tmp_dir", mode="after")
    @classmethod
    def _blank_to_none(cls, v: str | None) -> str | None:
        return (v or "").strip() or None

    @model_validator(mode="after")
    def _check_authz_url_set_if_enabled(self):
        if self.bento_authz_enabled and not self.bento_authz_service_url:
            raise ValueError("BENTO_AUTHZ_SERVICE_URL must be set when authorization is enabled")
        return self

    @property
    def database_url(self) -> str:
        return f"sqlite:///{(self.database / 'db.sqlite3').expanduser().resolve()}"

    @property
    def service_data_source(self) -> str:
        return DATA_SOURCE_S3 if self.s3_endpoint else DATA_SOURCE_LOCAL

    @property
    def service_data(self) -> Path | None:
        return None if self.s3_endpoint else self.data.expanduser().resolve()


@lru_cache
def get_config() -> Config:
    return Config()


ConfigDep = Annotated[Config, Depends(get_config)]
