import pytest

from chord_drs.backend import get_backend
from chord_drs.backends.exceptions import BackendImproperlyConfigured
from chord_drs.config import get_config

from .conftest import dummy_file_path


def _backend():
    return get_backend(get_config())


@pytest.mark.asyncio
async def test_drs_blob_init_bad_file():
    from chord_drs.models import DrsBlob

    with pytest.raises(FileNotFoundError):
        await DrsBlob.create(backend=_backend(), location="path/to/dne")


@pytest.mark.asyncio
async def test_drs_blob_init_bad_backend():
    from chord_drs.models import DrsBlob

    with pytest.raises(BackendImproperlyConfigured, match="not properly configured"):
        await DrsBlob.create(backend=None, location=dummy_file_path())


def test_get_backend_unknown_data_source(monkeypatch):
    from chord_drs import backend

    monkeypatch.setattr(backend, "DATA_SOURCE_BACKENDS", {})  # no valid backends

    assert get_backend(get_config()) is None


@pytest.mark.asyncio
async def test_s3_method_wrong_backend(client_local, drs_object):
    assert await drs_object.return_s3_object(_backend()) is None


@pytest.mark.asyncio
async def test_s3_method_wrong_backend_2(client_s3, drs_object_s3, monkeypatch):
    monkeypatch.delenv("S3_BUCKET")
    from chord_drs.config import Config

    # re-init the backend with the local source, mismatching with the S3 DRS object
    with pytest.raises(BackendImproperlyConfigured, match="not properly configured"):
        await drs_object_s3.return_s3_object(get_backend(Config()))


@pytest.mark.asyncio
async def test_s3_stream_range(client_s3, drs_object_s3):
    with pytest.raises(Exception) as e:
        bytes_range = [0, 100]
        await drs_object_s3.get_streaming_generator(_backend(), bytes_range)
        assert "S3 range requests are not implemented in the S3 backend" in str(e)


class _FailingBackend:
    def __init__(self, exc: Exception):
        self._exc = exc

    async def save(self, *_args, **_kwargs):
        raise self._exc


@pytest.mark.asyncio
async def test_drs_blob_create_s3_client_error():
    from botocore.exceptions import ClientError

    from chord_drs.exceptions import DrsBlobSaveError
    from chord_drs.models import DrsBlob

    err = ClientError({"Error": {"Code": "500", "Message": "bad"}}, "PutObject")

    with pytest.raises(DrsBlobSaveError, match="S3 related error"):
        await DrsBlob.create(backend=_FailingBackend(err), location=dummy_file_path())


@pytest.mark.asyncio
async def test_drs_blob_create_unexpected_backend_error():
    from chord_drs.models import DrsBlob

    with pytest.raises(RuntimeError, match="disk on fire"):
        await DrsBlob.create(backend=_FailingBackend(RuntimeError("disk on fire")), location=dummy_file_path())


@pytest.mark.asyncio
async def test_s3_method(client_s3, drs_object_s3):
    s3_object = await drs_object_s3.return_s3_object(_backend())

    assert s3_object is not None
    assert s3_object["headers"]["Content-Length"] == str(drs_object_s3.size)
