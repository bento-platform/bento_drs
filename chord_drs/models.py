import os
from flask import current_app
from hashlib import sha256
from pathlib import Path
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from urllib.parse import urlparse
from uuid import uuid4

from .backend import get_backend
from .db import db
from .utils import drs_file_checksum


class DrsMixin:
    # IDs (PKs) must remain outside the mixin!
    created = db.Column(db.DateTime, server_default=func.now())
    checksum = db.Column(db.String(64), nullable=False)
    size = db.Column(db.Integer, default=0)
    name = db.Column(db.String(250), nullable=True)
    description = db.Column(db.String(1000), nullable=True)
    # Permissions/Bento-specific project & dataset tagging for DRS items
    # TODO: Make some of these not nullable in the future:
    project_id = db.Column(db.String(64), nullable=True)  # Nullable for backwards-compatibility
    dataset_id = db.Column(db.String(64), nullable=True)  # Nullable for backwards-compatibility / project-only stuff?
    data_type = db.Column(db.String(24), nullable=True)  # NULL if multi-data type or something else


class DrsBundle(db.Model, DrsMixin):
    __tablename__ = "drs_bundle"

    id = db.Column(db.String, primary_key=True)
    parent_bundle_id = db.Column(db.Integer, db.ForeignKey("drs_bundle.id"))
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


class DrsBlob(db.Model, DrsMixin):
    __tablename__ = "drs_object"

    id = db.Column(db.String, primary_key=True)
    bundle_id = db.Column(db.Integer, db.ForeignKey(DrsBundle.id), nullable=True)
    location = db.Column(db.String(500), nullable=False)

    def __init__(self, *args, **kwargs):
        # If set, we are deduplicating with an existing file object
        object_to_copy: DrsBlob | None = kwargs.get("object_to_copy")

        self.id = str(uuid4())

        if object_to_copy:
            self.name = object_to_copy.name
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

            self.name = p.name
            new_filename = f"{self.id[:12]}-{p.name}"  # TODO: use checksum for filename instead

            backend = get_backend()

            try:
                self.location = backend.save(location, new_filename)
                self.size = os.path.getsize(p)
                self.checksum = drs_file_checksum(location)
            except Exception as e:
                current_app.logger.error(f"Encountered exception during DRS object creation: {e}")
                # TODO: implement more specific exception handling
                raise Exception("Well if the file is not saved... we can't do squat")

        if "location" in kwargs:
            del kwargs["location"]

        super().__init__(*args, **kwargs)

    def return_minio_object(self):
        parsed_url = urlparse(self.location)

        if parsed_url.scheme != "s3":
            return None

        return get_backend().get_minio_object(self.location)
