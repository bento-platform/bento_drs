import boto3

from urllib.parse import urlparse

from .base import Backend


__all__ = ["MinioBackend"]


class MinioBackend(Backend):
    def __init__(self, config: dict, resource=None):  # config is dict or flask.Config, which is a subclass of dict.
        self._minio_url = config["MINIO_URL"]

        self.minio = resource or boto3.resource(
            "s3",
            endpoint_url=self._minio_url,
            aws_access_key_id=config["MINIO_USERNAME"],
            aws_secret_access_key=config["MINIO_PASSWORD"],
        )

        self.bucket = self.minio.Bucket(config["MINIO_BUCKET"])

    def build_minio_location(self, obj):
        host = urlparse(self._minio_url).netloc
        return f"s3://{host}/{obj.bucket_name}/{obj.key}"

    def get_minio_object(self, location: str):
        return self.bucket.Object(location.split("/")[-1])

    def get_minio_object_dict(self, location: str) -> dict:
        return self.get_minio_object(location).get()

    def save(self, current_location: str, filename: str) -> str:
        with open(current_location, "rb") as f:
            obj = self.bucket.put_object(Key=filename, Body=f)
            return self.build_minio_location(obj)

    def delete(self, location: str) -> None:
        obj = self.get_minio_object(location)
        obj.delete()
