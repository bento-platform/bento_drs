from abc import ABC, abstractmethod


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
