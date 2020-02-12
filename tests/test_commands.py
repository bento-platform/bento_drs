from click.testing import CliRunner
from chord_drs.commands import ingest
from tests.conftest import (
    NON_EXISTENT_DUMMY_FILE,
    DUMMY_FILE,
    DUMMY_DIRECTORY,
)


def test_ingest_fail(client):
    runner = CliRunner()
    result = runner.invoke(ingest, [NON_EXISTENT_DUMMY_FILE])

    assert result.exit_code == 1


def test_ingest(client):
    runner = CliRunner()
    result = runner.invoke(ingest, [DUMMY_FILE])

    assert result.exit_code == 0
    assert "Created a new object" in result.output

    result = runner.invoke(ingest, [DUMMY_DIRECTORY])

    assert result.exit_code == 0
    assert "Created a new object" in result.output
    # TODO: kinda clunky, to refactor at some point
    # 2 inside travis-si, no __pycache__ folders
    assert (
        result.output.count("Created a new bundle") == 4 or
        result.output.count("Created a new bundle") == 2
    )
