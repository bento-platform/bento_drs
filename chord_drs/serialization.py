import urllib.parse
from urllib.parse import urlparse

from flask import current_app, url_for
from pydantic import FileUrl

from .data_sources import DATA_SOURCE_LOCAL, DATA_SOURCE_S3
from .models import DrsBlob
from .pydantic_models import (
    DrsAccessMethod,
    DrsAccessUrl,
    DrsBentoExtension,
    DrsBlobResponse,
    DrsChecksum,
    DrsUri,
    HttpsUrl,
    S3Url,
)

__all__ = [
    "build_blob_response",
]


def get_drs_host() -> str:
    return urlparse(current_app.config["SERVICE_BASE_URL"]).netloc


def create_drs_uri(object_id: str) -> DrsUri:
    return DrsUri(f"drs://{get_drs_host()}/{object_id}")


def build_bento_extension_obj(drs_object: DrsBlob) -> DrsBentoExtension:
    return DrsBentoExtension(
        project_id=drs_object.project_id or None,
        dataset_id=drs_object.dataset_id or None,
        data_type=drs_object.data_type or None,
        public=drs_object.public,
    )


def build_blob_response(
    drs_blob: DrsBlob,
    inside_container: bool = False,
    with_bento_properties: bool = False,
) -> DrsBlobResponse:
    data_source = current_app.config["SERVICE_DATA_SOURCE"]

    blob_url: str = urllib.parse.urljoin(
        current_app.config["SERVICE_BASE_URL"] + "/",
        url_for("drs_service.object_download", object_id=drs_blob.id).lstrip("/"),
    )

    https_access_method = DrsAccessMethod(
        type="https",
        access_url=DrsAccessUrl(
            # url_for external was giving weird results - build the URL by hand instead using the internal url_for
            url=HttpsUrl(blob_url),
            # No headers --> auth will have to be obtained via some
            # out-of-band method, or the object's contents are public. This
            # will depend on how the service is deployed.
        ),
    )

    access_methods: list[DrsAccessMethod] = [https_access_method]

    if inside_container and data_source == DATA_SOURCE_LOCAL:
        access_methods.append(
            DrsAccessMethod(type="file", access_url=DrsAccessUrl(url=FileUrl(f"file://{drs_blob.location}")))
        )
    elif data_source == DATA_SOURCE_S3:
        access_methods.append(DrsAccessMethod(type="s3", access_url=DrsAccessUrl(url=S3Url(drs_blob.location))))

    return DrsBlobResponse(
        access_methods=access_methods,
        checksums=[DrsChecksum(type="sha-256", checksum=drs_blob.checksum)],
        created_time=drs_blob.created,
        size=drs_blob.size,
        name=drs_blob.name,
        description=drs_blob.description or "",
        mime_type=drs_blob.mime_type or "",
        id=drs_blob.id,
        self_uri=create_drs_uri(drs_blob.id),
        bento=build_bento_extension_obj(drs_blob) if with_bento_properties else None,
    )
