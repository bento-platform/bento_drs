import os
from uuid import uuid4
from hashlib import sha256
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from chord_drs.app import db


class DrsMixin():
    created = db.Column(db.DateTime, server_default=func.now())
    checksum = db.Column(db.String(64), nullable=False)
    size = db.Column(db.Integer, nullable=False)
    description = db.Column(db.String(1000), nullable=True)


class DrsBundle(db.Model, DrsMixin):
    ___tablename__ = 'drs_bundle'
    id = db.Column(db.String, primary_key=True)
    parent_bundle_id = db.Column(db.Integer, db.ForeignKey('drs_bundle.id'))
    parent_bundle = relationship("DrsBundle", remote_side=[id])
    objects = relationship("DrsObject", cascade="all, delete-orphan", backref="bundle")


class DrsObject(db.Model, DrsMixin):
    id = db.Column(db.String, primary_key=True)
    bundle_id = db.Column(db.Integer, db.ForeignKey(DrsBundle.id), nullable=True)
    location = db.Column(db.String(500), nullable=False)

    def __init__(self, *args, **kwargs):
        location = kwargs.get('location', None)

        if os.path.exists(location):
            hash_obj = sha256()
            self.size = os.path.getsize(location)

            with open(location, 'rb') as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_obj.update(chunk)

            self.checksum = hash_obj.hexdigest()

        self.id = str(uuid4())
        super().__init__(*args, **kwargs)
