from click.testing import CliRunner
from sqlalchemy import select

from chord_drs.commands import ingest
from chord_drs.models import DrsBlob
from tests.conftest import (
    dummy_directory_path,
    dummy_file_path,
    non_existant_dummy_file_path,
)


def test_ingest_fail(client_local):
    # cannot ingest non-existant file

    runner = CliRunner()
    result = runner.invoke(ingest, [non_existant_dummy_file_path()])

    assert result.exit_code == 1


def test_ingest_fail_dir(client_local):
    # cannot ingest directory

    runner = CliRunner()
    result = runner.invoke(ingest, [str(dummy_directory_path())])

    assert result.exit_code == 1


def test_ingest(client_local, session_maker):
    dummy_file = dummy_file_path()

    runner = CliRunner()
    result = runner.invoke(ingest, [dummy_file])

    filename = dummy_file.split("/")[-1]
    with session_maker() as session:
        obj = session.scalars(select(DrsBlob).where(DrsBlob.name == filename)).first()

    assert result.exit_code == 0
    assert obj.name == filename
    assert obj.location
