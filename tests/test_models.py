import pytest

from chord_drs.backends.exceptions import BackendImproperlyConfigured

from .conftest import dummy_file_path, reset_caches


@pytest.mark.asyncio
async def test_drs_blob_init_bad_file():
    from chord_drs.models import DrsBlob

    with pytest.raises(FileNotFoundError):
        await DrsBlob.create(location="path/to/dne")


@pytest.mark.asyncio
async def test_drs_blob_init_bad_backend(monkeypatch):
    from chord_drs import backend
    from chord_drs.models import DrsBlob

    monkeypatch.setattr(backend, "DATA_SOURCE_BACKENDS", {})  # no valid backends
    reset_caches()

    with pytest.raises(Exception) as e:
        await DrsBlob.create(location=dummy_file_path())

    assert "not properly configured" in str(e)


@pytest.mark.asyncio
async def test_s3_method_wrong_backend(client_local, drs_object):
    assert await drs_object.return_s3_object() is None


@pytest.mark.asyncio
async def test_s3_method_wrong_backend_2(client_s3, drs_object_s3, monkeypatch):
    monkeypatch.delenv("S3_ENDPOINT")
    reset_caches()  # force a backend re-init with local source, mismatching with DRS object

    with pytest.raises(BackendImproperlyConfigured) as e:
        await drs_object_s3.return_s3_object()
        assert "not properly configured" in str(e)


@pytest.mark.asyncio
async def test_s3_stream_range(client_s3, drs_object_s3):
    with pytest.raises(Exception) as e:
        bytes_range = [0, 100]
        await drs_object_s3.get_streaming_generator(bytes_range)
        assert "S3 range requests are not implemented in the S3 backend" in str(e)
