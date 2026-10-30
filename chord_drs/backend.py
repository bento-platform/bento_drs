from typing import Annotated

from fastapi import Depends

from chord_drs.backends.base import Backend
from chord_drs.config import ConfigDep
from chord_drs.data_sources import DATA_SOURCE_BACKENDS
from chord_drs.logger import logger

__all__ = [
    "get_backend",
    "BackendDep",
]


def get_backend(config: ConfigDep) -> Backend | None:
    # Instantiate backend if needed
    backend_class = DATA_SOURCE_BACKENDS.get(config.service_data_source)
    return backend_class(config, logger) if backend_class else None


BackendDep = Annotated[Backend | None, Depends(get_backend)]
