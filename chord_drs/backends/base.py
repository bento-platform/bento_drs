from abc import ABC, abstractmethod
from typing import Any, Generator


__all__ = ["Backend"]


# noinspection PyUnusedLocal
class Backend(ABC):
    @abstractmethod
    def __init__(self, config: dict):  # pragma: no cover
        pass

    @abstractmethod
    async def save(self, current_location: str, filename: str) -> str:  # pragma: no cover
        pass

    @abstractmethod
    async def delete(self, location: str) -> None:  # pragma: no cover
        pass

    @abstractmethod
    async def get_stream_generator(
        self, location: str, range: tuple[int, int] | None = None
    ) -> Generator[Any, None, None]:  # pragma: no cover
        pass
