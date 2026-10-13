import tempfile
from contextlib import asynccontextmanager

from bento_lib.apps.fastapi import BentoFastAPI
from bento_lib.logging import log_level_from_str

from . import __version__
from .authz import get_authz_middleware
from .config import BENTO_EXTRA_SERVICE_INFO, get_config
from .constants import SERVICE_TYPE
from .logger import logger
from .routes import drs_router

__all__ = ["create_app"]


@asynccontextmanager
async def lifespan(_app: BentoFastAPI):
    yield


def create_app() -> BentoFastAPI:
    config = get_config()
    logger.setLevel(log_level_from_str(config.log_level))

    if config.drs_ingest_tmp_dir:
        # Uploaded files are spooled to disk by Starlette via the tempfile module, so point that at the configured
        # directory in order for large uploads to use it.
        tempfile.tempdir = config.drs_ingest_tmp_dir

    authz = get_authz_middleware()

    # BentoFastAPI sets up CORS, authorization, Bento-formatted error handlers, and the /service-info endpoint.
    application = BentoFastAPI(
        authz,
        config,
        logger,
        BENTO_EXTRA_SERVICE_INFO,
        SERVICE_TYPE,
        __version__,
        exc_handler_kwargs={"drs_compat": True},
        lifespan=lifespan,
    )

    # The DRS spec says the service info should also be available under the DRS API prefix
    @application.get("/ga4gh/drs/v1/service-info", dependencies=[authz.dep_public_endpoint()])
    async def drs_service_info():
        return await application.get_service_info()

    application.include_router(drs_router)

    return application
