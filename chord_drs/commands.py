import asyncio
import os

import click
from click import ClickException

from .db import get_session_maker
from .logger import logger
from .models import DrsBlob

__all__ = ["ingest"]


async def create_drs_blob(
    location: str,
    project_id: str | None = None,
    dataset_id: str | None = None,
    data_type: str | None = None,
) -> DrsBlob:
    return await DrsBlob.create(
        location=location,
        project_id=project_id,
        dataset_id=dataset_id,
        data_type=data_type,
    )


@click.command("ingest")
@click.argument("source")
@click.option("--project", default="", help="Project ID this object is attached to.")
@click.option("--dataset", default="", help="Dataset ID this object is attached to.")
@click.option("--data-type", default="", help="Data type this object is attached to.")
def ingest(source: str, project: str, dataset: str, data_type: str) -> None:
    """
    When provided with a file or a directory, this command will add these
    to our list of objects, to be served by the application.

    Should we go through the directories recursively?
    """

    # TODO: ingestion for remote files or archives

    if not os.path.exists(source):
        raise ClickException("Path provided does not exist")

    source = os.path.abspath(source)

    perms_kwargs = {"project_id": project or None, "dataset_id": dataset or None, "data_type": data_type or None}

    if not os.path.isfile(source):
        raise ClickException("Directories cannot be ingested")

    drs_blob = asyncio.run(create_drs_blob(source, **perms_kwargs))
    with get_session_maker()() as session:
        session.add(drs_blob)
        session.commit()

    logger.info(f"Created a new blob, filename: {drs_blob.location} ID : {drs_blob.id}")


if __name__ == "__main__":  # pragma: no cover
    ingest()
