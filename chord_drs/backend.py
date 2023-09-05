import boto3
from flask import current_app, g
from urllib.parse import urlparse


__all__ = [
    "get_backend",
    "close_backend",
]


class Backend:
    def __init__(self, resource=None):
        self._client = resource or boto3.resource(
            "s3",
            endpoint_url=current_app.config["DRS_S3_API_URL"],
            aws_access_key_id=current_app.config["DRS_S3_ACCESS_KEY"],
            aws_secret_access_key=current_app.config["DRS_S3_SECRET_KEY"]
        )

        self.bucket = self._client.Bucket(current_app.config["DRS_S3_BUCKET"])

    @staticmethod
    def build_minio_location(obj):
        host = urlparse(current_app.config["MINIO_URL"]).netloc
        return f"s3://{host}/{obj.bucket_name}/{obj.key}"

    def get_minio_object(self, location: str):
        obj = self.bucket.Object(location.split("/")[-1])
        return obj.get()

    def save(self, current_location: str, filename: str) -> str:
        with open(current_location, "rb") as f:
            obj = self.bucket.put_object(Key=filename, Body=f)
            return self.build_minio_location(obj)


def get_backend() -> Backend:
    if "backend" not in g:
        g.backend = Backend()
    return g.backend


def close_backend(_e=None) -> None:
    g.pop("backend", None)
