from typing import Type

from .backends.base import Backend
from .backends.local import LocalBackend
from .backends.minio import MinioBackend


__all__ = [
    "DATA_SOURCE_LOCAL",
    "DATA_SOURCE_MINIO",
    "DATA_SOURCE_BACKENDS",
]


DATA_SOURCE_LOCAL = "local"
DATA_SOURCE_MINIO = "minio"

DATA_SOURCE_BACKENDS: dict[str, Type[Backend]] = {
    DATA_SOURCE_LOCAL: LocalBackend,
    DATA_SOURCE_MINIO: MinioBackend,
}
