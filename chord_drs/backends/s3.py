import logging
import aioboto3
import botocore
from bento_lib.streaming.exceptions import StreamingException
from bento_lib.logging import log_level_from_str
from boto3.s3.transfer import S3TransferConfig
from typing import AsyncIterator, Generator, TypedDict

from chord_drs.constants import CHUNK_SIZE
from chord_drs.utils import sync_generator_stream

from .base import Backend

__all__ = ["S3Backend"]


class S3ObjectGenerator(TypedDict):
    generator: AsyncIterator[bytes]
    headers: dict[str, str]


class S3Backend(Backend):
    def __init__(self, config: dict):  # config is dict or flask.Config, which is a subclass of dict.
        logging.getLogger("boto3").setLevel(log_level_from_str(config["LOG_LEVEL"]))
        logging.getLogger("botocore").setLevel(log_level_from_str(config["LOG_LEVEL"]))
        logging.getLogger("aiobotocore").setLevel(log_level_from_str(config["LOG_LEVEL"]))
        protocol = "https" if config["S3_USE_HTTPS"] else "http"
        endpoint_url = f"{protocol}://{config['S3_ENDPOINT']}"

        self._s3_url = endpoint_url
        self.s3_access_key_id = config["S3_ACCESS_KEY"]
        self.s3_secret_access_key = config["S3_SECRET_KEY"]
        self.verify = config["S3_VALIDATE_SSL"]
        self.region_name = config["S3_REGION_NAME"]
        self.bucket_name = config["S3_BUCKET"]

        self.session = aioboto3.Session()

    async def _create_s3_client(self):
        return self.session.client(
            "s3",
            endpoint_url=self._s3_url,
            aws_access_key_id=self.s3_access_key_id,
            aws_secret_access_key=self.s3_secret_access_key,
            region_name=self.region_name,
            verify=False,
        )

    async def _init_bucket_if_required(self):
        # Mostly for tests with S3 mocks
        async with await self._create_s3_client() as s3_client:
            try:
                # Raises ClientError 404 if the bucket is missing
                return await s3_client.head_bucket(Bucket=self.bucket_name)
            except botocore.exceptions.ClientError as err:
                if err.response["ResponseMetadata"]["HTTPStatusCode"] == 404:
                    return await s3_client.create_bucket(Bucket=self.bucket_name)

    def _build_s3_location(self, object_key: str):
        return f"s3://{self.bucket_name}/{object_key}"

    async def _retrieve_headers(self, object_key: str):
        async with await self._create_s3_client() as s3:
            head = await s3.head_object(Bucket=self.bucket_name, Key=object_key)
        return {
            "Content-Length": str(head["ContentLength"]),
            "Content-Type": head["ContentType"],
            "ETag": head["ETag"],
            "Last-Modified": str(head["LastModified"]),
        }

    async def get_s3_object_dict(self, location: str) -> S3ObjectGenerator:
        object_key = self._location_to_object_key(location)
        headers = await self._retrieve_headers(object_key)

        async def stream_object():
            async with await self._create_s3_client() as s3_client:
                response = await s3_client.get_object(Bucket=self.bucket_name, Key=object_key)
                body_stream = response["Body"]
                while chunk := await body_stream.read(CHUNK_SIZE):
                    yield chunk

        return {
            "generator": stream_object(),
            "headers": headers,
        }

    async def save(self, current_location: str, filename: str) -> str:
        async with await self._create_s3_client() as s3_client:
            transfer_config = S3TransferConfig(
                multipart_threshold=5 * 1024 * 1024,  # 5MB threshold for multipart
                multipart_chunksize=5 * 1024 * 1024,  # 5MB chunk size
            )
            await s3_client.upload_file(
                Bucket=self.bucket_name, Key=filename, Filename=current_location, Config=transfer_config
            )
            location = self._build_s3_location(filename)
            return location

    async def delete(self, location: str) -> None:
        object_key = self._location_to_object_key(location)
        async with await self._create_s3_client() as s3_client:
            await s3_client.delete_object(Bucket=self.bucket_name, Key=object_key)

    async def get_stream_generator(
        self, location: str, range: tuple[int, int] | None = None
    ) -> Generator[bytes, None, None]:
        if range:
            raise S3StreamRangeException("S3 range requests are not implemented in the S3 backend")
        s3_dict = await self.get_s3_object_dict(location)
        return sync_generator_stream(s3_dict["generator"])

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


class S3StreamRangeException(StreamingException):
    pass
