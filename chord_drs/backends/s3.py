import boto3

from urllib.parse import urlparse

from .base import Backend


__all__ = ["S3Backend"]


class S3Backend(Backend):
    def __init__(self, config: dict, resource=None):  # config is dict or flask.Config, which is a subclass of dict.
        protocol = "https" if config["S3_USE_HTTPS"] else "http"
        endpoint_url = f"{protocol}://{config['S3_ENDPOINT']}"

        self._s3_url = endpoint_url

        self.s3 = resource or boto3.resource(
            "s3",
            endpoint_url=self._s3_url,
            aws_access_key_id=config["S3_ACCESS_KEY"],
            aws_secret_access_key=config["S3_SECRET_KEY"],
        )

        self.bucket = self.s3.Bucket(config["S3_BUCKET"])

    def build_s3_location(self, obj):
        host = urlparse(self._s3_url).netloc
        return f"s3://{host}/{obj.bucket_name}/{obj.key}"

    def get_s3_object(self, location: str):
        return self.bucket.Object(location.split("/")[-1])

    def get_s3_object_dict(self, location: str) -> dict:
        return self.get_s3_object(location).get()

    def save(self, current_location: str, filename: str) -> str:
        with open(current_location, "rb") as f:
            obj = self.bucket.put_object(Key=filename, Body=f)
            return self.build_s3_location(obj)

    def delete(self, location: str) -> None:
        obj = self.get_s3_object(location)
        obj.delete()
