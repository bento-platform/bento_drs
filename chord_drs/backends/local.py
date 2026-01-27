from logging import Logger
from shutil import copy
from pathlib import Path
from typing import Generator

from bento_lib.streaming.file import stream_file

from chord_drs.constants import CHUNK_SIZE
from chord_drs.utils import sync_generator_stream

from .base import Backend


__all__ = ["LocalBackend"]


class LocalBackend(Backend):
    """
    Default backend class for the location of the objects served
    by this service. Lives on the current filesystem, in a directory
    specified by the DATA var env, the default being in ~/chord_drs_data
    """

    def __init__(self, config: dict, logger: Logger):  # config is dict or flask.Config, which is a subclass of dict.
        self.base_location = Path(config["SERVICE_DATA"])
        # We can use mkdir, since resolve has been called in config.py
        self.base_location.mkdir(parents=True, exist_ok=True)
        self.logger = logger

    async def save(self, current_location: str | Path, filename: str) -> str:
        new_location = self.base_location / filename
        copy(current_location, new_location)
        return str(new_location.resolve())

    async def delete(self, location: str | Path) -> None:
        loc = location if isinstance(location, Path) else Path(location)
        if self.base_location in loc.parents:
            loc.unlink()
            return
        raise ValueError(f"Location {loc} is not a subpath of backend base location {self.base_location}")

    async def get_stream_generator(
        self, location: str, range: tuple[int, int] | None = None
    ) -> Generator[bytes, None, None]:
        location_path = Path(location)
        generator = stream_file(location_path, range, CHUNK_SIZE)
        return sync_generator_stream(generator, self.logger)
