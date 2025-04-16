import aiofiles
from shutil import copy
from pathlib import Path
from typing import Any, Generator

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

    def __init__(self, config: dict):  # config is dict or flask.Config, which is a subclass of dict.
        self.base_location = Path(config["SERVICE_DATA"])
        # We can use mkdir, since resolve has been called in config.py
        self.base_location.mkdir(parents=True, exist_ok=True)

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

    async def get_stream_generator(self, location: str, range: tuple[int, int]) -> Generator[Any, None, None]:
        if range:
            start, end = range
            generator = self._stream_range(location, start, end)
        else:
            generator = self._stream_whole(location)
        return sync_generator_stream(generator)

    async def _stream_range(self, location: str, start: int, end: int):
        async with aiofiles.open(location, mode="rb") as file:
            # First, skip over <start> bytes to get to the beginning of the range
            await file.seek(start)

            # Then, read in either CHUNK_SIZE byte segments or however many bytes are left to send, whichever is
            # left. This avoids filling memory with the contents of large files.
            byte_offset: int = start
            while True:
                # Add a 1 to the amount to read if it's below chunk size, because the last coordinate is inclusive.
                data = await file.read(min(CHUNK_SIZE, end + 1 - byte_offset))
                byte_offset += len(data)
                yield data

                # If we've hit the end of the file and are reading empty byte strings, or we've reached the
                # end of our range (inclusive), then escape the loop.
                # This is guaranteed to terminate with a finite-sized file.
                if len(data) == 0 or byte_offset > end:
                    break

    async def _stream_whole(self, location: str):
        """
        Streams the whole file by chunk size.
        """
        async with aiofiles.open(location, mode="rb") as file:
            while chunk := await file.read(CHUNK_SIZE):
                yield chunk
