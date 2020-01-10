import os
import click
from click import ClickException
from chord_drs.app import application, db
from chord_drs.models import DrsObject


def create_drs_object(location):
    drs_object = DrsObject(location=location)

    db.session.add(drs_object)
    db.session.commit()

    print(f"Created a new object, filename: {drs_object.location} ID : {drs_object.id}")


@application.cli.command("ingest")
@click.argument("source")
def ingest(source):
    """
    When provided with a file or a directory, this command will add these
    to our list of objects, to be served by the application.

    Should we go through the directories recursively?
    """
    if os.path.exists(source):
        source = os.path.abspath(source)

        if os.path.isfile(source):
            create_drs_object(source)
        else:
            for f in os.listdir(source):
                f = os.path.abspath(os.path.join(source, f))

                if os.path.isfile(f):
                    create_drs_object(f)
    else:
        raise ClickException('File or directory provided does not exists')
