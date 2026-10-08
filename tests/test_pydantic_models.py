import hashlib
from datetime import UTC, datetime

import pytest
from pydantic import FileUrl, HttpUrl, TypeAdapter, ValidationError

from chord_drs.pydantic_models import (
    DrsAccessMethod,
    DrsAccessUrl,
    DrsBentoExtension,
    DrsBlobResponse,
    DrsChecksum,
    DrsUri,
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
    DrsAccessMethod(type="https", access_url=DrsAccessUrl(url=HttpUrl("https://dlougheed.com")))
    # noinspection HttpUrlsUsage
    DrsAccessMethod(type="https", access_url=DrsAccessUrl(url=HttpUrl("http://dlougheed.com")))
    DrsAccessMethod(type="s3", access_url=DrsAccessUrl(url=S3Url("s3://bucket/object")))

    with pytest.raises(ValidationError, match="access method URL scheme does not match type"):
        DrsAccessMethod(type="file", access_url=DrsAccessUrl(url=HttpUrl("https://dlougheed.com")))
    with pytest.raises(ValidationError, match="access method URL scheme does not match type"):
        DrsAccessMethod(type="https", access_url=DrsAccessUrl(url=S3Url("s3://bucket/object")))
    with pytest.raises(ValidationError, match="access method URL scheme does not match type"):
        DrsAccessMethod(type="s3", access_url=DrsAccessUrl(url=FileUrl("file:///whatever.txt")))


def test_drs_blob_response_construction():
    cs = hashlib.sha256(b"test", usedforsecurity=False)
    a = DrsBlobResponse(
        id="asdf",
        self_uri=DrsUri("drs://bento-project.github.io/asdf"),
        name="asdf.txt",
        description="Some file",
        created_time=datetime.now(UTC),
        updated_time=None,
        size=1000,
        checksums=[DrsChecksum(type="sha-256", checksum=cs.hexdigest())],
        access_methods=[DrsAccessMethod(type="file", access_url=DrsAccessUrl(url=FileUrl("file:///whatever.txt")))],
        bento=DrsBentoExtension(project_id=None, dataset_id=None, data_type=None, public=True),
    )

    ser = a.model_dump(mode="json")
    ct = ser["created_time"]

    assert "T" in ct
    assert ct.endswith("Z")

    assert ser == {
        "id": "asdf",
        "name": "asdf.txt",
        "description": "Some file",
        "created_time": ct,
        "self_uri": "drs://bento-project.github.io/asdf",
        "size": 1000,
        "checksums": [{"type": "sha-256", "checksum": cs.hexdigest()}],
        "access_methods": [{"type": "file", "access_url": {"url": "file:///whatever.txt"}}],
        "bento": {"project_id": None, "dataset_id": None, "data_type": None, "public": True},
    }
