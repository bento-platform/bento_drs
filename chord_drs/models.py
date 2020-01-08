import os
from uuid import uuid4
from hashlib import sha256
from sqlalchemy.sql import func
from chord_drs.app import db


class DrsObject(db.Model):
    id = db.Column(db.String, primary_key=True)
    created = db.Column(db.DateTime, server_default=func.now())
    checksum = db.Column(db.String(64), nullable=False)
    size = db.Column(db.Integer, nullable=False)
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
