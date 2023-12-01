import os
from flask import current_app
from hashlib import sha256
from pathlib import Path
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.sql import func
from sqlalchemy.orm import declarative_base, relationship
from werkzeug.utils import secure_filename
from urllib.parse import urlparse
from uuid import uuid4

from .backend import get_backend
from .backends.minio import MinioBackend
from .utils import drs_file_checksum

__all__ = [
    "Base",
    "DrsMixin",
    "DrsBlob",
    "DrsBundle",
]

Base = declarative_base()


class DrsMixin:
    # IDs (PKs) must remain outside the mixin!
    created = Column(DateTime, server_default=func.now())
    checksum = Column(String(64), nullable=False)
    size = Column(Integer, default=0)
    name = Column(String(250), nullable=True)
    description = Column(String(1000), nullable=True)
    # Permissions/Bento-specific project & dataset tagging for DRS items
    project_id = Column(String(64), nullable=True)  # Nullable for backwards-compatibility
    dataset_id = Column(String(64), nullable=True)  # Nullable for backwards-compatibility / project-only stuff?
    data_type = Column(String(24), nullable=True)  # NULL if multi-data type or something else


class DrsBundle(Base, DrsMixin):
    __tablename__ = "drs_bundle"

    id = Column(String, primary_key=True)
    parent_bundle_id = Column(Integer, ForeignKey("drs_bundle.id"))
    parent_bundle = relationship("DrsBundle", remote_side=[id])
    objects = relationship("DrsBlob", cascade="all, delete-orphan", backref="bundle")

    def __init__(self, *args, **kwargs):
        self.id = str(uuid4())
        super().__init__(*args, **kwargs)

    def update_checksum_and_size(self):
        # For bundle checksumming logic, see the `checksums` field in
        # https://ga4gh.github.io/data-repository-service-schemas/preview/release/drs-1.3.0/docs/#tag/DrsObjectModel

        checksums = []
        total_size = 0

        for obj in self.objects:
            total_size += obj.size
            checksums.append(obj.checksum)

        checksums.sort()
        concat_checksums = "".join(checksums)

        hash_obj = sha256()
        hash_obj.update(concat_checksums.encode())

        self.checksum = hash_obj.hexdigest()
        self.size = total_size


class DrsBlob(Base, DrsMixin):
    __tablename__ = "drs_object"

    id = Column(String, primary_key=True)
    bundle_id = Column(Integer, ForeignKey(DrsBundle.id), nullable=True)
    location = Column(String(500), nullable=False)

    def __init__(self, *args, **kwargs):
        logger = current_app.logger

        # If set, we are deduplicating with an existing file object
        object_to_copy: DrsBlob | None = kwargs.get("object_to_copy")

        # If set, we are overriding the filename to save the file to
        filename: str | None = kwargs.get("filename")

        self.id = str(uuid4())

        if object_to_copy:
            self.name = secure_filename(filename) if filename else object_to_copy.name
            self.location = object_to_copy.location
            self.size = object_to_copy.size
            self.checksum = object_to_copy.checksum
            del kwargs["object_to_copy"]
        else:
            location = kwargs.get("location")

            try:
                p = Path(location).resolve(strict=True)
            except FileNotFoundError:
                # TODO: we will need to account for URLs at some point
                raise FileNotFoundError("Provided file path does not exists")

            self.name = secure_filename(filename or p.name)
            new_filename = f"{self.id[:12]}-{self.name}"  # TODO: use checksum for filename instead

            backend = get_backend()

            if not backend:
                raise Exception("The backend for this instance is not properly configured.")
            try:
                self.location = backend.save(location, new_filename)
                self.size = os.path.getsize(p)
                self.checksum = drs_file_checksum(location)
            except Exception as e:
                logger.error(f"Encountered exception during DRS object creation: {e}")
                # TODO: implement more specific exception handling
                raise Exception("Well if the file is not saved... we can't do squat")

            logger.info(f"Creating new DRS object: name={self.name}; size={self.size}; sha256={self.checksum}")

        for key_to_remove in ("location", "filename"):
            if key_to_remove in kwargs:
                del kwargs[key_to_remove]

        super().__init__(*args, **kwargs)

    def return_minio_object(self):
        parsed_url = urlparse(self.location)

        if parsed_url.scheme != "s3":
            return None

        backend = get_backend()

        if not backend or not isinstance(backend, MinioBackend):
            raise Exception("The backend for this instance is not properly configured.")

        return backend.get_minio_object(self.location)
