from urllib.parse import urlparse

from pydantic import AnyUrl

from .config import Config
from .constants import DATA_SOURCE_LOCAL, DATA_SOURCE_S3
from .models import DrsBlob
from .pydantic_models import DrsAccessMethod, DrsAccessUrl, DrsBentoExtension, DrsBlobResponse, DrsChecksum, DrsUri

__all__ = [
    "build_blob_response",
]


def create_drs_uri(config: Config, object_id: str) -> DrsUri:
    return DrsUri(f"drs://{urlparse(config.service_base_url).netloc}/{object_id}")


def build_bento_extension_obj(drs_object: DrsBlob) -> DrsBentoExtension:
    return DrsBentoExtension(
        project_id=drs_object.project_id or None,
        dataset_id=drs_object.dataset_id or None,
        data_type=drs_object.data_type or None,
        public=drs_object.public,
    )


def build_blob_response(
    config: Config,
    drs_blob: DrsBlob,
    inside_container: bool = False,
    with_bento_properties: bool = False,
) -> DrsBlobResponse:
    data_source = config.service_data_source

    https_access_method = DrsAccessMethod(
        type="https",
        access_url=DrsAccessUrl(
            url=AnyUrl(f"{config.service_base_url}/objects/{drs_blob.id}/download"),
            # No headers --> auth will have to be obtained via some
            # out-of-band method, or the object's contents are public. This
            # will depend on how the service is deployed.
        ),
    )

    access_methods: list[DrsAccessMethod] = [https_access_method]

    if inside_container and data_source == DATA_SOURCE_LOCAL:
        access_methods.append(
            DrsAccessMethod(type="file", access_url=DrsAccessUrl(url=AnyUrl(f"file://{drs_blob.location}")))
        )
    elif data_source == DATA_SOURCE_S3:
        access_methods.append(DrsAccessMethod(type="s3", access_url=DrsAccessUrl(url=AnyUrl(drs_blob.location))))

    return DrsBlobResponse(
        access_methods=access_methods,
        checksums=[DrsChecksum(type="sha-256", checksum=drs_blob.checksum)],
        created_time=drs_blob.created,
        size=drs_blob.size,
        name=drs_blob.name,
        description=drs_blob.description or "",
        mime_type=drs_blob.mime_type or "",
        id=drs_blob.id,
        self_uri=create_drs_uri(config, drs_blob.id),
        bento=build_bento_extension_obj(drs_blob) if with_bento_properties else None,
    )
