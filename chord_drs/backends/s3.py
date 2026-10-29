import asyncio
import logging
import math
import os
from collections.abc import AsyncGenerator, Generator
from contextlib import AbstractAsyncContextManager
from typing import TYPE_CHECKING, Any, TypedDict

import aiofiles
from aiobotocore.session import get_session
from bento_lib.logging import log_level_from_str
from botocore.exceptions import ClientError

from chord_drs.constants import CHUNK_SIZE
from chord_drs.utils import sync_generator_stream

from .base import Backend

if TYPE_CHECKING:
    from types_aiobotocore_s3 import S3Client
    from types_aiobotocore_s3.type_defs import CompletedPartTypeDef

__all__ = ["S3ObjectGenerator", "S3Backend"]

# Files up to this size are uploaded with a single put_object, larger ones with a multipart upload.
# It is also the minimum part size (same default as boto3's transfer manager).
# TODO: make configurable with defaults
MULTIPART_PART_SIZE = 8 * 1024 * 1024
MULTIPART_MAX_PARTS = 10_000  # S3 hard limit on the number of parts in an upload
MULTIPART_CONCURRENCY = 4  # Max parts uploaded at once; memory use is about concurrency * part size

AWS_CA_BUNDLE = os.getenv("AWS_CA_BUNDLE")


class S3ObjectGenerator(TypedDict):
    generator: AsyncGenerator[bytes, None]
    headers: dict[str, str]


class S3Backend(Backend):
    def __init__(
        self,
        config: dict,  # config is dict or flask.Config, which is a subclass of dict.
        logger: logging.Logger,
    ):
        logging.getLogger("botocore").setLevel(log_level_from_str(config["LOG_LEVEL"]))
        logging.getLogger("aiobotocore").setLevel(log_level_from_str(config["LOG_LEVEL"]))
        self.bucket_name = config["S3_BUCKET"]

        self.verify = config["S3_VALIDATE_SSL"]
        if AWS_CA_BUNDLE and self.verify:
            # None lets botocore use AWS_CA_BUNDLE if set, passing True would ignore it.
            self.verify = None

        # Credentials, profile, region and endpoint are resolved by botocore from
        # standard AWS env vars/config files.
        self.session = get_session()

        self.logger = logger

    def _create_s3_client(self) -> AbstractAsyncContextManager["S3Client"]:
        return self.session.create_client("s3", verify=self.verify)

    async def _init_bucket_if_required(self):
        # Mostly for tests with S3 mocks
        async with self._create_s3_client() as s3_client:
            try:
                # Raises ClientError 404 if the bucket is missing
                return await s3_client.head_bucket(Bucket=self.bucket_name)
            except ClientError as err:
                if err.response["ResponseMetadata"]["HTTPStatusCode"] == 404:
                    return await s3_client.create_bucket(Bucket=self.bucket_name)

    def _build_s3_location(self, object_key: str):
        return f"s3://{self.bucket_name}/{object_key}"

    async def _retrieve_headers(self, object_key: str):
        async with self._create_s3_client() as s3:
            head = await s3.head_object(Bucket=self.bucket_name, Key=object_key)
        return {
            "Content-Length": str(head["ContentLength"]),
            "Content-Type": head["ContentType"],
            "ETag": head["ETag"],
            "Last-Modified": str(head["LastModified"]),
        }

    async def get_s3_object_dict(self, location: str, bytes_range: tuple[int, int] | None = None) -> S3ObjectGenerator:
        object_key = self._location_to_object_key(location)
        headers = await self._retrieve_headers(object_key)

        async def stream_object() -> AsyncGenerator[bytes, None]:
            # if a byte range is set, pass a Range: bytes=... header to botocore
            range_args: dict[str, Any] = {"Range": f"bytes={bytes_range[0]}-{bytes_range[1]}"} if bytes_range else {}
            async with self._create_s3_client() as s3_client:
                response = await s3_client.get_object(Bucket=self.bucket_name, Key=object_key, **range_args)
                async with response["Body"] as body_stream:
                    while chunk := await body_stream.read(CHUNK_SIZE):
                        yield chunk

        return {
            "generator": stream_object(),
            "headers": headers,
        }

    async def save(self, current_location: str, filename: str) -> str:
        size = os.path.getsize(current_location)
        async with self._create_s3_client() as s3_client:
            if size <= MULTIPART_PART_SIZE:
                async with aiofiles.open(current_location, "rb") as f:
                    body = await f.read()
                await s3_client.put_object(Bucket=self.bucket_name, Key=filename, Body=body)
            else:
                await self._multipart_upload(s3_client, current_location, filename, size)
        return self._build_s3_location(filename)

    @staticmethod
    def _part_size(file_size: int) -> int:
        # Grow parts for very large files so the upload stays under the S3 part count limit.
        return max(MULTIPART_PART_SIZE, math.ceil(file_size / MULTIPART_MAX_PARTS))

    async def _upload_part(
        self,
        s3_client: "S3Client",
        path: str,
        key: str,
        upload_id: str,
        part_number: int,
        part_size: int,
    ) -> "CompletedPartTypeDef":
        async with aiofiles.open(path, "rb") as f:
            await f.seek((part_number - 1) * part_size)
            body = await f.read(part_size)

        res = await s3_client.upload_part(
            Bucket=self.bucket_name,
            Key=key,
            UploadId=upload_id,
            PartNumber=part_number,
            Body=body,
        )

        part: CompletedPartTypeDef = {"ETag": res["ETag"], "PartNumber": part_number}
        return part

    async def _multipart_upload(self, s3_client: "S3Client", path: str, key: str, size: int) -> None:
        part_size = self._part_size(size)
        n_parts = math.ceil(size / part_size)

        upload = await s3_client.create_multipart_upload(Bucket=self.bucket_name, Key=key)
        upload_id = upload["UploadId"]
        self.logger.debug(f"started multipart upload of {path} to {key}: {n_parts} parts of {part_size} bytes")

        semaphore = asyncio.Semaphore(MULTIPART_CONCURRENCY)

        async def upload_part(part_number: int) -> "CompletedPartTypeDef":
            async with semaphore:
                return await self._upload_part(s3_client, path, key, upload_id, part_number, part_size)

        try:
            # A failed part cancels the parts still in progress
            async with asyncio.TaskGroup() as tg:
                tasks = [tg.create_task(upload_part(n)) for n in range(1, n_parts + 1)]

            parts = [t.result() for t in tasks]  # tasks were created in part number order
            await s3_client.complete_multipart_upload(
                Bucket=self.bucket_name,
                Key=key,
                UploadId=upload_id,
                MultipartUpload={"Parts": parts},
            )
        except BaseException:
            # Abort so the uploaded parts don't stay in the bucket
            try:
                await s3_client.abort_multipart_upload(Bucket=self.bucket_name, Key=key, UploadId=upload_id)
            except Exception:
                self.logger.exception(f"failed to abort multipart upload {upload_id} for {key}")
            raise

    async def delete(self, location: str) -> None:
        object_key = self._location_to_object_key(location)
        async with self._create_s3_client() as s3_client:
            await s3_client.delete_object(Bucket=self.bucket_name, Key=object_key)

    async def get_stream_generator(
        self, location: str, bytes_range: tuple[int, int] | None = None
    ) -> Generator[bytes, None, None]:
        s3_dict = await self.get_s3_object_dict(location, bytes_range)
        return sync_generator_stream(s3_dict["generator"], self.logger)

    def _location_to_object_key(self, location: str) -> str:
        if location.startswith(f"s3://{self.bucket_name}"):
            # Regular S3 object path
            return location.removeprefix(f"s3://{self.bucket_name}/")
        elif location.startswith("/"):
            # Path reconciliation for DRS objects that were created with block-storage.
            # Such DRS objects can be preserved when switching to S3 by uploading the objects to the same path:
            #   A DRS blob created on block-storage has this location:
            #       /drs/bento_drs/data/obj/<some blob>
            #   DRS can work with this location if blobs are uploaded to:
            #       s3://<BUCKET NAME>/drs/bento_drs/data/obj/<some blob>
            # The absolute path location with a leading slash can cause errors when used as a object key.
            return location[1:]
        else:
            raise ValueError(f"Location path is invalid, should be s3 path or absolute file system: {location}")
