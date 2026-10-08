import hashlib

import pytest
from pydantic import FileUrl, TypeAdapter, ValidationError

from chord_drs.pydantic_models import (
    DrsAccessMethod,
    DrsAccessUrl,
    DrsBentoExtension,
    DrsChecksum,
    DrsUri,
    HttpsUrl,
    S3Url,
)


def test_drs_uri():
    ta = TypeAdapter(DrsUri)

    ta.validate_python("drs://some-host.local/0000-0000")

    with pytest.raises(ValidationError, match="URL scheme should be 'drs'"):
        ta.validate_python("https://bento-platform.github.io")


def test_bento_drs_extension_construction():
    DrsBentoExtension(project_id="project-1", dataset_id="dataset-1", data_type="phenopacket", public=False)
    DrsBentoExtension(project_id=None, dataset_id=None, data_type=None, public=True)


def test_drs_checksum_construction():
    cs = hashlib.sha256(b"test", usedforsecurity=False)
    DrsChecksum(type="sha-256", checksum=cs.hexdigest())

    with pytest.raises(ValidationError, match="String should have at least 64 characters"):
        DrsChecksum(type="sha-256", checksum="not long enough")


def test_access_method_construction():
    DrsAccessMethod(type="file", access_url=DrsAccessUrl(url=FileUrl("file:///whatever.txt")))
    DrsAccessMethod(type="https", access_url=DrsAccessUrl(url=HttpsUrl("https://dlougheed.com")))
    DrsAccessMethod(type="s3", access_url=DrsAccessUrl(url=S3Url("s3://bucket/object")))

    with pytest.raises(ValidationError, match="access method URL scheme does not match type"):
        DrsAccessMethod(type="file", access_url=DrsAccessUrl(url=HttpsUrl("https://dlougheed.com")))
    with pytest.raises(ValidationError, match="access method URL scheme does not match type"):
        DrsAccessMethod(type="https", access_url=DrsAccessUrl(url=S3Url("s3://bucket/object")))
    with pytest.raises(ValidationError, match="access method URL scheme does not match type"):
        DrsAccessMethod(type="s3", access_url=DrsAccessUrl(url=FileUrl("file:///whatever.txt")))
