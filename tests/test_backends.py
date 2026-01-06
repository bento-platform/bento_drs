import pathlib
import pytest

from chord_drs.backends.local import LocalBackend
from chord_drs.backends.s3 import S3Backend


@pytest.mark.asyncio
async def test_local_backend(local_volume, test_logger):
    backend = LocalBackend({"SERVICE_DATA": str(local_volume)}, test_logger)

    file_to_ingest = pathlib.Path(__file__).parent / "dummy_file.txt"

    await backend.save(file_to_ingest, "dummy_file.txt")
    assert (local_volume / "dummy_file.txt").exists()

    await backend.delete(local_volume / "dummy_file.txt")
    assert not (local_volume / "dummy_file.txt").exists()


@pytest.mark.asyncio
async def test_local_backend_raises(local_volume, test_logger):
    backend = LocalBackend({"SERVICE_DATA": str(local_volume)}, test_logger)

    with pytest.raises(ValueError):
        # before we can even figure out file does not exist, this is not a local volume subpath:
        await backend.delete("/tmp/does_not_exist.txt")


def test_s3_backend_location_handling(s3_config, test_logger):
    backend = S3Backend(s3_config, test_logger)

    # S3 location: DRS blobs created on an S3 backend
    s3_location = f"s3://{backend.bucket_name}/some-blob"
    s3_object_key = backend._location_to_object_key(s3_location)
    assert s3_object_key == "some-blob"

    # File system location: DRS blobs created on a local backend
    s3_fs_location = "/drs/bento_drs/data/obj/some-blob"
    s3_fs_object_key = backend._location_to_object_key(s3_fs_location)
    assert s3_fs_object_key == s3_fs_location[1:]

    # Invalid location: not an S3 path OR not an absolute fs path
    invalid_location = "some-blob"
    with pytest.raises(ValueError):
        backend._location_to_object_key(invalid_location)
