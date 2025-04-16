import asyncio
from hashlib import sha256
from typing import Any, AsyncGenerator, Generator

from flask import current_app


__all__ = ["drs_file_checksum"]

CHUNK_SIZE = 16 * 1024


def drs_file_checksum(path: str) -> str:
    hash_obj = sha256()

    with open(path, "rb") as f:
        while chunk := f.read(CHUNK_SIZE):
            hash_obj.update(chunk)

    return hash_obj.hexdigest()


def _iter_over_async(async_generator: AsyncGenerator):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    iterator = async_generator.__aiter__()

    async def get_next() -> tuple[bool, Any]:
        try:
            obj = await iterator.__anext__()
            return False, obj
        except StopAsyncIteration:
            return True, None
        except Exception as e:
            current_app.logger.error(e)
            return True, None

    try:
        while True:
            done, obj = loop.run_until_complete(get_next())
            if done:
                break
            yield obj
    finally:
        loop.close()


def sync_generator_stream(async_generator: AsyncGenerator) -> Generator:
    """
    Flask cannot handle async generators for streaming responses on its own.
    This function takes in an AsyncGenerator and returns a sync Generator
    bridge that yields the chunks as they arrive.

    Adopted from: https://medium.com/@mr.murga/streaming-ai-responses-with-flask-a-practical-guide-677c15e82cdd
    """

    async def iter():
        async for chunk in async_generator:
            yield chunk

    return _iter_over_async(iter())
