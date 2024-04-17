import urllib.parse

from flask import (
    current_app,
    url_for,
)
from urllib.parse import urlparse

from .data_sources import DATA_SOURCE_LOCAL, DATA_SOURCE_MINIO
from .models import DrsMixin, DrsBlob, DrsBundle
from .types import DRSAccessMethodDict, DRSContentsDict, DRSObjectBentoDict, DRSObjectDict


__all__ = [
    "build_bundle_json",
    "build_blob_json",
]


def get_drs_host() -> str:
    return urlparse(current_app.config["SERVICE_BASE_URL"]).netloc


def create_drs_uri(object_id: str) -> str:
    return f"drs://{get_drs_host()}/{object_id}"


def build_contents(bundle: DrsBundle, expand: bool) -> list[DRSContentsDict]:
    content: list[DRSContentsDict] = []
    bundles = DrsBundle.query.filter_by(parent_bundle=bundle).all()

    for b in bundles:
        content.append(
            {
                **({"contents": build_contents(b, expand)} if expand else {}),
                "drs_uri": create_drs_uri(b.id),
                "id": b.id,
                "name": b.name,  # TODO: Can overwrite... see spec
            }
        )

    for c in bundle.objects:
        content.append(
            {
                "drs_uri": create_drs_uri(c.id),
                "id": c.id,
                "name": c.name,  # TODO: Can overwrite... see spec
            }
        )

    return content


def build_bento_object_json(drs_object: DrsMixin) -> DRSObjectBentoDict:
    return {
        "project_id": drs_object.project_id,
        "dataset_id": drs_object.dataset_id,
        "data_type": drs_object.data_type,
        "public": drs_object.public,
    }


def build_bundle_json(
    drs_bundle: DrsBundle,
    expand: bool = False,
    with_bento_properties: bool = False,
) -> DRSObjectDict:
    return {
        "contents": build_contents(drs_bundle, expand),
        "checksums": [
            {
                "checksum": drs_bundle.checksum,
                "type": "sha-256",
            },
        ],
        "created_time": f"{drs_bundle.created.isoformat('T')}Z",
        "size": drs_bundle.size,
        "name": drs_bundle.name,
        # Description should be excluded if null in the database
        **({"description": drs_bundle.description} if drs_bundle.description is not None else {}),
        "id": drs_bundle.id,
        "self_uri": create_drs_uri(drs_bundle.id),
        **({"bento": build_bento_object_json(drs_bundle)} if with_bento_properties else {}),
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
        "id": drs_blob.id,
        "self_uri": create_drs_uri(drs_blob.id),
        **({"bento": build_bento_object_json(drs_blob)} if with_bento_properties else {}),
    }
