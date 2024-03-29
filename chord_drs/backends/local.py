from shutil import copy
from flask import current_app
from pathlib import Path

from .base import Backend


__all__ = ["LocalBackend"]


class LocalBackend(Backend):
    """
    Default backend class for the location of the objects served
    by this service. Lives on the current filesystem, in a directory
    specified by the DATA var env, the default being in ~/chord_drs_data
    """
    def __init__(self):
        self.base_location = Path(current_app.config["SERVICE_DATA"])
        # We can use mkdir, since resolve has been called in config.py
        self.base_location.mkdir(exist_ok=True)

    def save(self, current_location: str | Path, filename: str) -> str:
        new_location = self.base_location / filename
        copy(current_location, new_location)
        return str(new_location.resolve())
