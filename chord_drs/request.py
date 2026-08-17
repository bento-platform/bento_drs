from tempfile import SpooledTemporaryFile
from typing import IO

from flask import Request, current_app

__all__ = ["DrsRequest"]

MAX_IN_MEMORY_SIZE = 1024 * 1024 * 10  # 10 MB


class DrsRequest(Request):
    def _get_file_stream(
        self,
        total_content_length: int | None,
        content_type: str | None,
        filename: str | None = None,
        content_length: int | None = None,
    ) -> IO[bytes]:
        return SpooledTemporaryFile(max_size=MAX_IN_MEMORY_SIZE, dir=current_app.config["DRS_INGEST_TMP_DIR"])
