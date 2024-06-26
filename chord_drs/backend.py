from flask import current_app, g

from chord_drs.backends.base import Backend
from chord_drs.data_sources import DATA_SOURCE_BACKENDS


__all__ = [
    "get_backend",
    "close_backend",
]


def _get_backend() -> Backend | None:
    # Instantiate backend if needed
    backend_class = DATA_SOURCE_BACKENDS.get(current_app.config["SERVICE_DATA_SOURCE"])
    return backend_class(current_app.config) if backend_class else None


def get_backend() -> Backend | None:
    if "backend" not in g:
        g.backend = _get_backend()
    return g.backend


def close_backend(_e=None) -> None:
    g.pop("backend", None)
