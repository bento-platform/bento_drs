from flask import current_app, g
from typing import Optional

from chord_drs.backends.base import Backend
from chord_drs.backends.local import LocalBackend
from chord_drs.backends.minio import MinioBackend


__all__ = [
    "get_backend",
    "close_backend",
]


def _get_backend() -> Optional[Backend]:
    # Make data directory/ies if needed
    if current_app.config['SERVICE_DATA_SOURCE'] == 'local':
        return LocalBackend()

    elif current_app.config['SERVICE_DATA_SOURCE'] == 'minio':
        return MinioBackend()

    return None


def get_backend() -> Optional[Backend]:
    if "backend" not in g:
        g.backend = _get_backend()
    return g.backend


def close_backend(_e=None):
    g.pop("backend", None)
