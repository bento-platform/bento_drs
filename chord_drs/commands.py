import click
import logging
import os

from click import ClickException
from flask import current_app
from flask.cli import with_appcontext

from .db import db
from .models import DrsBlob, DrsBundle


def create_drs_bundle(
    location: str,
    parent: DrsBundle | None = None,
    project_id: str | None = None,
    dataset_id: str | None = None,
    data_type: str | None = None,
    exclude: frozenset[str] = frozenset({}),
) -> DrsBundle:
    perms_kwargs = {"project_id": project_id, "dataset_id": dataset_id, "data_type": data_type}

    bundle = DrsBundle(name=os.path.basename(location), **perms_kwargs)

    if parent:
        bundle.parent_bundle = parent

    for f in os.listdir(location):
        if exclude and f in exclude:
            continue

        f = os.path.abspath(os.path.join(location, f))

        if os.path.isfile(f):
            create_drs_blob(f, parent=bundle, **perms_kwargs)
        else:
            create_drs_bundle(f, parent=bundle, **perms_kwargs)

    bundle.update_checksum_and_size()
    db.session.add(bundle)

    current_app.logger.info(f"Created a new bundle, name: {bundle.name}, ID : {bundle.id}, size: {bundle.size}")

    return bundle


def create_drs_blob(
    location: str,
    parent: DrsBundle | None = None,
    project_id: str | None = None,
    dataset_id: str | None = None,
    data_type: str | None = None,
) -> None:
    drs_blob = DrsBlob(
        location=location,
        project_id=project_id,
        dataset_id=dataset_id,
        data_type=data_type,
    )

    if parent:
        drs_blob.bundle = parent

    db.session.add(drs_blob)

    current_app.logger.info(f"Created a new blob, filename: {drs_blob.location} ID : {drs_blob.id}")


@click.command("ingest")
@click.argument("source")
@click.option("--project", default="", help="Project ID this object is attached to.")
@click.option("--dataset", default="", help="Dataset ID this object is attached to.")
@click.option("--data-type", default="", help="Data type this object is attached to.")
@with_appcontext
def ingest(source: str, project: str, dataset: str, data_type: str) -> None:
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

    perms_kwargs = {"project_id": project or None, "dataset_id": dataset or None, "data_type": data_type or None}

    if os.path.isfile(source):
        create_drs_blob(source, **perms_kwargs)
    else:
        create_drs_bundle(source, **perms_kwargs)

    db.session.commit()
