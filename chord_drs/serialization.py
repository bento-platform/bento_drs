import urllib.parse

from flask import (
    current_app,
    url_for,
)
from urllib.parse import urlparse

from .data_sources import DATA_SOURCE_LOCAL, DATA_SOURCE_MINIO
from .models import DrsBlob
from .types import DRSAccessMethodDict, DRSObjectBentoDict, DRSObjectDict


__all__ = [
    "build_blob_json",
]


def get_drs_host() -> str:
    return urlparse(current_app.config["SERVICE_BASE_URL"]).netloc


def create_drs_uri(object_id: str) -> str:
    return f"drs://{get_drs_host()}/{object_id}"


def build_bento_object_json(drs_object: DrsBlob) -> DRSObjectBentoDict:
    return {
        "project_id": drs_object.project_id,
        "dataset_id": drs_object.dataset_id,
        "data_type": drs_object.data_type,
        "public": drs_object.public,
    }


def build_blob_json(
    drs_blob: DrsBlob,
    inside_container: bool = False,
    with_bento_properties: bool = False,
) -> DRSObjectDict:
    data_source = current_app.config["SERVICE_DATA_SOURCE"]

    blob_url: str = urllib.parse.urljoin(
        current_app.config["SERVICE_BASE_URL"] + "/",
        url_for("drs_service.object_download", object_id=drs_blob.id).lstrip("/"),
    )

    https_access_method: DRSAccessMethodDict = {
        "access_url": {
            # url_for external was giving weird results - build the URL by hand instead using the internal url_for
            "url": blob_url,
            # No headers --> auth will have to be obtained via some
            # out-of-band method, or the object's contents are public. This
            # will depend on how the service is deployed.
        },
        "type": "https",
    }

    access_methods: list[DRSAccessMethodDict] = [https_access_method]

    if inside_container and data_source == DATA_SOURCE_LOCAL:
        access_methods.append(
            {
                "access_url": {
                    "url": f"file://{drs_blob.location}",
                },
                "type": "file",
            }
        )
    elif data_source == DATA_SOURCE_MINIO:
        access_methods.append(
            {
                "access_url": {
                    "url": drs_blob.location,
                },
                "type": "s3",
            }
        )

    return {
        "access_methods": access_methods,
        "checksums": [
            {
                "checksum": drs_blob.checksum,
                "type": "sha-256",
            },
        ],
        "created_time": f"{drs_blob.created.isoformat('T')}Z",
        "size": drs_blob.size,
        "name": drs_blob.name,
        # Description should be excluded if null in the database
        **({"description": drs_blob.description} if drs_blob.description is not None else {}),
        # MIME type should be excluded if null in the database
        **({"mime_type": drs_blob.mime_type} if drs_blob.mime_type is not None else {}),
        "id": drs_blob.id,
        "self_uri": create_drs_uri(drs_blob.id),
        **({"bento": build_bento_object_json(drs_blob)} if with_bento_properties else {}),
    }
