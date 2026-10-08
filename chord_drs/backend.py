from functools import lru_cache

from chord_drs.backends.base import Backend
from chord_drs.config import get_config
from chord_drs.data_sources import DATA_SOURCE_BACKENDS
from chord_drs.logger import logger

__all__ = [
    "get_backend",
]


@lru_cache
def get_backend() -> Backend | None:
    # Instantiate backend if needed
    config = get_config()
    backend_class = DATA_SOURCE_BACKENDS.get(config.service_data_source)
    return backend_class(config, logger) if backend_class else None
