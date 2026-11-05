from collections.abc import AsyncIterator
from functools import lru_cache
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from .config import get_config

__all__ = [
    "get_engine",
    "get_session_maker",
    "get_session",
    "SessionDep",
]


@lru_cache
def get_engine() -> AsyncEngine:
    return create_async_engine(get_config().async_database_url)


@lru_cache
def get_session_maker() -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(get_engine(), expire_on_commit=False)


async def get_session() -> AsyncIterator[AsyncSession]:
    async with get_session_maker()() as session:
        yield session


SessionDep = Annotated[AsyncSession, Depends(get_session)]
