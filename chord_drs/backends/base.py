from abc import ABC, abstractmethod


__all__ = ["Backend"]


class Backend(ABC):
    @abstractmethod
    def save(self, current_location: str, filename: str) -> str:  # pragma: no cover
        pass

    @abstractmethod
    def delete(self, location: str) -> None:  # pragma: no cover
        pass
