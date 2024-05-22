from flask import Request, current_app
from tempfile import SpooledTemporaryFile
from typing import IO, Optional

__all__ = ["DrsRequest"]

MAX_IN_MEMORY_SIZE = 1024 * 1024 * 10  # 10 MB


class DrsRequest(Request):
    def _get_file_stream(
        self,
        total_content_length: Optional[int],
        content_type: Optional[str],
        filename: Optional[str] = None,
        content_length: Optional[int] = None,
    ) -> IO[bytes]:
        return SpooledTemporaryFile(max_size=MAX_IN_MEMORY_SIZE, dir=current_app.config["DRS_INGEST_TMP_DIR"])
