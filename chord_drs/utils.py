import asyncio
from hashlib import sha256
from logging import Logger
from typing import Any, AsyncGenerator, Generator


__all__ = [
    "drs_file_checksum",
    "sync_generator_stream",
]

CHUNK_SIZE = 16 * 1024


def drs_file_checksum(path: str) -> str:
    hash_obj = sha256()

    with open(path, "rb") as f:
        while chunk := f.read(CHUNK_SIZE):
            hash_obj.update(chunk)

    return hash_obj.hexdigest()


def _iter_over_async(async_generator: AsyncGenerator, logger: Logger):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    iterator = async_generator.__aiter__()

    async def get_next() -> tuple[bool, Any]:
        try:
            obj_ = await iterator.__anext__()
            return False, obj_
        except StopAsyncIteration:
            return True, None
        except Exception as e:  # pragma: no cover
            logger.exception(e)
            return True, None

    try:
        while True:
            done, next_obj = loop.run_until_complete(get_next())
            if done:
                break
            yield next_obj
    finally:
        loop.close()


def sync_generator_stream(async_generator: AsyncGenerator, logger: Logger) -> Generator[bytes, None, None]:
    """
    Flask cannot handle async generators for streaming responses on its own.
    This function takes in an AsyncGenerator and returns a sync Generator
    bridge that yields the chunks as they arrive.

    Adopted from: https://medium.com/@mr.murga/streaming-ai-responses-with-flask-a-practical-guide-677c15e82cdd
    """

    async def iterator():
        async for chunk in async_generator:
            yield chunk

    return _iter_over_async(iterator(), logger)
