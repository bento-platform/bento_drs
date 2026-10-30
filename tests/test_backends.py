import hashlib
import os
import pathlib
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from botocore.exceptions import ClientError

from chord_drs.backends import s3 as s3_module
from chord_drs.backends.local import LocalBackend
from chord_drs.backends.s3 import S3Backend
from chord_drs.config import get_config

from .conftest import reset_caches

MIB = 1024 * 1024
TESTS_DIR = pathlib.Path(__file__).parent


@pytest.mark.asyncio
async def test_local_backend(local_volume, monkeypatch, test_logger):
    monkeypatch.setenv("DATA", str(local_volume))
    reset_caches()
    backend = LocalBackend(get_config(), test_logger)

    file_to_ingest = pathlib.Path(__file__).parent / "dummy_file.txt"

    await backend.save(file_to_ingest, "dummy_file.txt")
    assert (local_volume / "dummy_file.txt").exists()

    await backend.delete(local_volume / "dummy_file.txt")
    assert not (local_volume / "dummy_file.txt").exists()


@pytest.mark.asyncio
async def test_local_backend_raises(local_volume, monkeypatch, test_logger):
    monkeypatch.setenv("DATA", str(local_volume))
    reset_caches()
    backend = LocalBackend(get_config(), test_logger)

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


def test_s3_backend_requires_bucket(s3_config, test_logger):
    with pytest.raises(ValueError):
        S3Backend(s3_config.model_copy(update={"s3_bucket": None}), test_logger)


@pytest.mark.parametrize(
    "ca_bundle, validate_ssl, expected_verify",
    [
        (None, True, True),
        ("/ca.pem", True, None),  # None lets botocore use AWS_CA_BUNDLE
        ("/ca.pem", False, False),
    ],
)
def test_s3_backend_verify(s3_config, test_logger, monkeypatch, ca_bundle, validate_ssl, expected_verify):
    monkeypatch.setattr(s3_module, "AWS_CA_BUNDLE", ca_bundle)
    backend = S3Backend(s3_config.model_copy(update={"s3_validate_ssl": validate_ssl}), test_logger)
    assert backend.verify is expected_verify


@pytest.mark.asyncio
async def test_s3_backend_init_bucket_non_404_raises(s3_config, test_logger, monkeypatch):
    backend = S3Backend(s3_config, test_logger)

    # Mock backend's aiobotocore client to get 403 ClientError
    client = AsyncMock()
    client.__aenter__.return_value = client
    client.head_bucket.side_effect = ClientError(
        {"Error": {"Code": "403"}, "ResponseMetadata": {"HTTPStatusCode": 403}}, "HeadBucket"
    )
    monkeypatch.setattr(backend, "_create_s3_client", lambda: client)

    with pytest.raises(ClientError):
        await backend._init_bucket_if_required()

    # "create_bucket" should only be called on 404 ClientError
    client.create_bucket.assert_not_awaited()


@pytest_asyncio.fixture
async def s3_backend(s3_mock_env, s3_config, test_logger) -> S3Backend:
    backend = S3Backend(s3_config, test_logger)
    await backend._init_bucket_if_required()
    return backend


async def _head_object(backend: S3Backend, key: str):
    async with backend._create_s3_client() as s3_client:
        return await s3_client.head_object(Bucket=backend.bucket_name, Key=key)


async def _download(backend: S3Backend, location: str) -> bytes:
    obj = await backend.get_s3_object_dict(location)
    return b"".join([chunk async for chunk in obj["generator"]])


@pytest.mark.asyncio
@pytest.mark.parametrize("file_name", ["dummy_file.txt", "empty_file.txt"])
async def test_s3_backend_save_single_request(s3_backend: S3Backend, file_name: str):
    path = TESTS_DIR / file_name

    location = await s3_backend.save(str(path), file_name)
    assert location == f"s3://{s3_backend.bucket_name}/{file_name}"

    head = await _head_object(s3_backend, file_name)
    assert head["ContentLength"] == path.stat().st_size
    assert "-" not in head["ETag"]  # multipart ETags end in -<number of parts>
    assert await _download(s3_backend, location) == path.read_bytes()


@pytest.mark.asyncio
async def test_s3_backend_save_multipart(s3_backend: S3Backend, tmp_path, monkeypatch):
    monkeypatch.setattr(s3_module, "MULTIPART_PART_SIZE", 5 * MIB)  # moto's minimum size for non-last parts

    # Random bytes data that should be uploaded in 3 parts
    data = os.urandom(int(12.5 * MIB))
    path = tmp_path / "big_file.bin"
    path.write_bytes(data)

    location = await s3_backend.save(str(path), "big_file.bin")

    head = await _head_object(s3_backend, "big_file.bin")
    assert head["ContentLength"] == len(data)
    assert head["ETag"].endswith('-3"')
    downloaded = await _download(s3_backend, location)
    assert hashlib.sha256(downloaded).hexdigest() == hashlib.sha256(data).hexdigest()


@pytest.mark.asyncio
async def test_s3_backend_multipart_abort(s3_backend: S3Backend, tmp_path, monkeypatch):
    monkeypatch.setattr(s3_module, "MULTIPART_PART_SIZE", 5 * MIB)

    # 50 MIB / 5 MIB/part = 10 parts upload
    path = tmp_path / "big_file.bin"
    path.write_bytes(os.urandom(50 * MIB))

    # Needs to be referenced before monkeypatch, or causes a recursion
    upload_part = S3Backend._upload_part

    # Force error on part upload #7, should abort the other parts and the whole upload.
    async def fail_on_part_7(self, s3_client, path, key, upload_id, part_number, *args):
        if part_number == 7:
            raise ClientError({"Error": {"Code": "InternalError", "Message": "test"}}, "UploadPart")
        return await upload_part(self, s3_client, path, key, upload_id, part_number, *args)

    monkeypatch.setattr(S3Backend, "_upload_part", fail_on_part_7)

    # Check that ClientError is raised during multipart upload
    with pytest.raises(ClientError):
        await s3_backend.save(str(path), "big_file.bin")

    # Check that the other part uploads have been purged
    async with s3_backend._create_s3_client() as s3_client:
        uploads = await s3_client.list_multipart_uploads(Bucket=s3_backend.bucket_name)
    assert not uploads.get("Uploads")

    # Check that the object was not created
    with pytest.raises(ClientError):
        await _head_object(s3_backend, "big_file.bin")


def test_s3_backend_part_size():
    assert S3Backend._part_size(10 * MIB) == s3_module.MULTIPART_PART_SIZE

    huge = 200 * 1024 * MIB  # 200 GiB: needs bigger parts to stay under the part count limit
    assert S3Backend._part_size(huge) > s3_module.MULTIPART_PART_SIZE
    assert S3Backend._part_size(huge) * s3_module.MULTIPART_MAX_PARTS >= huge


@pytest.mark.asyncio
async def test_s3_backend_delete(s3_backend: S3Backend):
    location = await s3_backend.save(str(TESTS_DIR / "dummy_file.txt"), "dummy_file.txt")
    await s3_backend.delete(location)

    with pytest.raises(ClientError) as e:
        await _head_object(s3_backend, "dummy_file.txt")
    assert e.value.response["ResponseMetadata"]["HTTPStatusCode"] == 404
