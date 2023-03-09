import click
import logging
import os

from click import ClickException
from flask import current_app
from flask.cli import with_appcontext
from typing import Optional

from chord_drs.db import db
from chord_drs.models import DrsBlob, DrsBundle


def create_drs_bundle(location: str, parent: Optional[DrsBundle] = None) -> DrsBundle:
    bundle = DrsBundle(name=os.path.basename(location))

    if parent:
        bundle.parent_bundle = parent

    for f in os.listdir(location):
        f = os.path.abspath(os.path.join(location, f))

        if os.path.isfile(f):
            create_drs_blob(f, parent=bundle)
        else:
            create_drs_bundle(f, parent=bundle)

    bundle.update_checksum_and_size()
    db.session.add(bundle)

    current_app.logger.info(f"Created a new bundle, name: {bundle.name}, ID : {bundle.id}, size: {bundle.size}")

    return bundle


def create_drs_blob(location: str, parent: Optional[DrsBundle] = None) -> None:
    drs_blob = DrsBlob(location=location)

    if parent:
        drs_blob.bundle = parent

    db.session.add(drs_blob)

    current_app.logger.info(f"Created a new blob, filename: {drs_blob.location} ID : {drs_blob.id}")


@click.command("ingest")
@click.argument("source")
@with_appcontext
def ingest(source: str) -> None:
    """
    When provided with a file or a directory, this command will add these
    to our list of objects, to be served by the application.

    Should we go through the directories recursively?
    """

    current_app.logger.setLevel(logging.INFO)
    # TODO: ingestion for remote files or archives
    # TODO: Create directories in minio when ingesting a bundle

    if not os.path.exists(source):
        raise ClickException("File or directory provided does not exist")

    source = os.path.abspath(source)

    if os.path.isfile(source):
        create_drs_blob(source)
    else:
        create_drs_bundle(source)

    db.session.commit()
