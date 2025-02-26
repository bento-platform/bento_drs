import pytest

from .conftest import dummy_file_path


def test_drs_blob_init_bad_file():
    from chord_drs.app import application
    from chord_drs.models import DrsBlob

    with application.app_context():
        with pytest.raises(FileNotFoundError):
            DrsBlob(location="path/to/dne")


def test_drs_blob_init_bad_backend():
    from chord_drs.app import application
    from chord_drs.models import DrsBlob

    application.config["SERVICE_DATA_SOURCE"] = "aaa"  # invalid backend

    with application.app_context():
        with pytest.raises(Exception) as e:
            DrsBlob(location=dummy_file_path())

        assert "not properly configured" in str(e)


def tests3_method_wrong_backend(client_local, drs_object):
    assert drs_object.return_s3_object() is None


def test_s3_method_wrong_backend_2(client_s3, drs_object_s3):
    from flask import g
    from chord_drs.app import application

    application.config["SERVICE_DATA_SOURCE"] = "local"
    with pytest.raises(Exception) as e:
        g.backend = None  # force a backend re-init with local source, mismatching with DRS object
        drs_object_s3.return_s3_object()
        assert "not properly configured" in str(e)
