import asyncio
from collections.abc import AsyncGenerator
from logging import Logger
from pathlib import Path
from shutil import copy

from bento_lib.streaming.file import stream_file

from chord_drs.config import Config
from chord_drs.constants import CHUNK_SIZE

from .base import Backend

__all__ = ["LocalBackend"]


class LocalBackend(Backend):
    """
    Default backend class for the location of the objects served
    by this service. Lives on the current filesystem, in a directory
    specified by the DATA var env, the default being in ~/chord_drs_data
    """

    def __init__(self, config: Config, logger: Logger):
        self.base_location = config.service_data
        # We can use mkdir, since resolve has been called in config.py
        self.base_location.mkdir(parents=True, exist_ok=True)
        self.logger = logger

    async def save(self, current_location: str | Path, filename: str) -> str:
        new_location = self.base_location / filename
        await asyncio.to_thread(copy, current_location, new_location)
        return str(new_location.resolve())

    async def delete(self, location: str | Path) -> None:
        loc = location if isinstance(location, Path) else Path(location)
        if self.base_location in loc.parents:
            loc.unlink()
            return
        raise ValueError(f"Location {loc} is not a subpath of backend base location {self.base_location}")

    async def get_stream_generator(
        self, location: str, range: tuple[int, int] | None = None
    ) -> AsyncGenerator[bytes, None]:
        return stream_file(Path(location), range, CHUNK_SIZE)
