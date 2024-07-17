from click.testing import CliRunner
from chord_drs.commands import ingest
from chord_drs.models import DrsBlob
from tests.conftest import (
    non_existant_dummy_file_path,
    dummy_file_path,
)


# TODO: Issue with app context and backends. On hold for now
def test_ingest_fail(client_local):
    runner = CliRunner()
    result = runner.invoke(ingest, [non_existant_dummy_file_path()])

    assert result.exit_code == 1


def test_ingest(client_local):
    dummy_file = dummy_file_path()

    runner = CliRunner()
    result = runner.invoke(ingest, [dummy_file])

    filename = dummy_file.split("/")[-1]
    obj = DrsBlob.query.filter_by(name=filename).first()

    assert result.exit_code == 0
    assert obj.name == filename
    assert obj.location
