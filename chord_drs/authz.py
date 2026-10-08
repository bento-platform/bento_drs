from functools import lru_cache
from typing import Annotated

from bento_lib.auth.middleware.fastapi import FastApiAuthMiddleware
from fastapi import Depends

from .config import get_config
from .logger import logger

__all__ = [
    "get_authz_middleware",
    "AuthzMiddlewareDep",
]


@lru_cache
def get_authz_middleware() -> FastApiAuthMiddleware:
    return FastApiAuthMiddleware.build_from_fastapi_pydantic_config(get_config(), logger, drs_compat=True)


AuthzMiddlewareDep = Annotated[FastApiAuthMiddleware, Depends(get_authz_middleware)]
