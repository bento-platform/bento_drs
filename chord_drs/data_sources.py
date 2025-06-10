from typing import Type

from .backends.base import Backend
from .backends.local import LocalBackend
from .backends.s3 import S3Backend


__all__ = [
    "DATA_SOURCE_LOCAL",
    "DATA_SOURCE_S3",
    "DATA_SOURCE_BACKENDS",
]


DATA_SOURCE_LOCAL = "local"
DATA_SOURCE_S3 = "s3"

DATA_SOURCE_BACKENDS: dict[str, Type[Backend]] = {
    DATA_SOURCE_LOCAL: LocalBackend,
    DATA_SOURCE_S3: S3Backend,
}
