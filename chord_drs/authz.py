from bento_lib.auth.middleware.flask import FlaskAuthMiddleware
from .config import Config

__all__ = [
    "authz_middleware",
    "PERMISSION_INGEST_DATA",
    "PERMISSION_QUERY_DATA",
    "PERMISSION_DOWNLOAD_DATA",
]

authz_middleware = FlaskAuthMiddleware(
    Config.AUTHZ_URL,
    debug_mode=Config.BENTO_DEBUG,
    enabled=Config.AUTHZ_ENABLED,
)

PERMISSION_INGEST_DATA = "ingest:data"
PERMISSION_QUERY_DATA = "query:data"
PERMISSION_DOWNLOAD_DATA = "download:data"
