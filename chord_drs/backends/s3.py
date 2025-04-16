import aioboto3
from boto3.s3.transfer import S3TransferConfig
from typing import Any, AsyncIterator, Generator, TypedDict
import botocore

from bento_lib.streaming.exceptions import StreamingException

from chord_drs.constants import CHUNK_SIZE
from chord_drs.utils import sync_generator_stream

from .base import Backend

__all__ = ["S3Backend"]


class S3ObjectGenerator(TypedDict):
    generator: AsyncIterator[bytes]
    headers: dict[str, str]


class S3Backend(Backend):
    def __init__(self, config: dict):  # config is dict or flask.Config, which is a subclass of dict.
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
        # Where location is a full s3 path
        object_key = location.split(f"s3://{self.bucket_name}/")[-1]
        headers = await self._retrieve_headers(object_key)

        async def stream_object():
            async with await self._create_s3_client() as s3_client:
                response = await s3_client.get_object(Bucket=self.bucket_name, Key=location.split("/")[-1])
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
        async with await self._create_s3_client() as s3_client:
            await s3_client.delete_object(Bucket=self.bucket_name, Key=location.split("/")[-1])

    async def get_stream_generator(
        self, location: str, range: tuple[int, int] | None = None
    ) -> Generator[Any, None, None]:
        if range:
            raise S3StreamRangeException("S3 range requests are not implemented in the S3 backend")
        s3_dict = await self.get_s3_object_dict(location)
        return sync_generator_stream(s3_dict["generator"])


class S3StreamRangeException(StreamingException):
    pass
