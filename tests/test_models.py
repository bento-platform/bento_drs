import pytest

from .conftest import dummy_file_path


def test_drs_blob_init_bad_file():
    from chord_drs.models import DrsBlob

    with pytest.raises(FileNotFoundError):
        DrsBlob(location="path/to/dne")


def test_drs_blob_init():
    from chord_drs.app import application
    from chord_drs.models import DrsBlob

    application.config["SERVICE_DATA_SOURCE"] = "aaa"  # invalid backend

    with application.app_context():
        with pytest.raises(Exception) as e:
            DrsBlob(location=dummy_file_path())

        assert "not properly configured" in str(e)


def test_minio_method_wrong_backend(client_local, drs_object):
    assert drs_object.return_minio_object() is None
