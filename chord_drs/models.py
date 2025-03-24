import os
import botocore
import botocore.exceptions
from flask import current_app
from pathlib import Path
from sqlalchemy import Boolean, Column, DateTime, Integer, String
from sqlalchemy.sql import func
from sqlalchemy.orm import declarative_base
from werkzeug.utils import secure_filename
from urllib.parse import urlparse
from uuid import uuid4

from .backend import get_backend
from .backends.s3 import S3Backend
from .constants import RE_INGESTABLE_MIME_TYPE
from .utils import drs_file_checksum

__all__ = [
    "Base",
    "DrsBlob",
]

Base = declarative_base()


class DrsBlob(Base):
    __tablename__ = "drs_object"

    id = Column(String, primary_key=True)
    location = Column(String(500), nullable=False)

    created = Column(DateTime, server_default=func.now())
    checksum = Column(String(64), nullable=False)
    size = Column(Integer, default=0)
    name = Column(String(250), nullable=True)
    description = Column(String(1000), nullable=True)

    mime_type = Column(String(128), nullable=True)  # if null, MIME type has not been set / isn't known

    # Permissions/Bento-specific project & dataset tagging for DRS items
    # TODO: Make some of these not nullable in the future:
    project_id = Column(String(64), nullable=True)  # Nullable for backwards-compatibility
    dataset_id = Column(String(64), nullable=True)  # Nullable for backwards-compatibility / project-only stuff?
    data_type = Column(String(24), nullable=True)  # NULL if multi-data type or something else
    public = Column(Boolean, default=False, nullable=False)  # If true, the object is accessible by anyone

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    @classmethod
    async def create(cls, *args, **kwargs):
        logger = current_app.logger

        # If set, we are deduplicating with an existing file object
        object_to_copy: DrsBlob | None = kwargs.pop("object_to_copy", None)

        # If set, we are overriding the filename to save the file to
        filename: str | None = kwargs.pop("filename", None)

        instance = cls(*args, **kwargs)
        instance.id = str(uuid4())

        if object_to_copy:
            instance.name = secure_filename(filename) if filename else object_to_copy.name
            instance.location = object_to_copy.location
            instance.size = object_to_copy.size
            instance.checksum = object_to_copy.checksum
            instance.mime_type = object_to_copy.mime_type
        else:
            location = kwargs.get("location")
            try:
                p = Path(location).resolve(strict=True)
            except FileNotFoundError:
                # TODO: we will need to account for URLs at some point
                raise FileNotFoundError("Provided file path does not exists")

            instance.name = secure_filename(filename or p.name)
            new_filename = f"{instance.id[:12]}-{instance.name}"  # TODO: use checksum for filename instead

            # MIME type, if set, must be a valid ingestable mime type (not a made up supertype and not, e.g.,
            # multipart/form-data.
            mime_type: str | None = kwargs.get("mime_type")
            if mime_type is not None and not RE_INGESTABLE_MIME_TYPE.match(mime_type):
                raise ValueError("Invalid MIME type")
            instance.mime_type = mime_type

            backend = get_backend()

            if not backend:
                raise Exception("The backend for this instance is not properly configured.")
            try:
                instance.location = await backend.save(location, new_filename)
                instance.size = os.path.getsize(p)
                instance.checksum = drs_file_checksum(location)
            except botocore.exceptions.ClientError as err:
                msg = f"S3 related error during DRS object creation: {err}"
                logger.error(msg)
                raise Exception(msg)
            except Exception as e:
                logger.error(f"Encountered exception during DRS object creation: {e}")
                # TODO: implement more specific exception handling
                raise Exception("Well if the file is not saved... we can't do squat")

            logger.info(
                f"Creating new DRS object: name={instance.name}; size={instance.size}; sha256={instance.checksum}"
            )

        return instance

    async def return_s3_object(self) -> dict:
        parsed_url = urlparse(self.location)

        if parsed_url.scheme != "s3":
            return None

        backend = get_backend()

        if not backend or not isinstance(backend, S3Backend):
            raise Exception("The backend for this instance is not properly configured.")

        return await backend.get_s3_object_dict(self.location)
