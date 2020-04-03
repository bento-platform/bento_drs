from abc import ABC, abstractmethod


class Backend(ABC):
    @abstractmethod
    def save(self, current_location: str, filename: str) -> str:
        pass


class FakeBackend(Backend):
    """
    For the tests
    """
    def save(self, current_location: str, filename: str) -> str:
        return current_location
