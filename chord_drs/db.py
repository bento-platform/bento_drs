from collections.abc import Iterator
from functools import lru_cache
from typing import Annotated

from fastapi import Depends
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from .config import get_config

__all__ = [
    "get_engine",
    "get_session_maker",
    "get_session",
    "SessionDep",
]


@lru_cache
def get_engine() -> Engine:
    # check_same_thread=False: sessions are used from FastAPI's threadpool and from the event bus thread.
    return create_engine(get_config().database_url, connect_args={"check_same_thread": False})


@lru_cache
def get_session_maker() -> sessionmaker[Session]:
    return sessionmaker(get_engine(), expire_on_commit=False)


def get_session() -> Iterator[Session]:
    with get_session_maker()() as session:
        yield session


SessionDep = Annotated[Session, Depends(get_session)]
