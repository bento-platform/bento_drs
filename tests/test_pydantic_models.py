import hashlib

import pytest
from pydantic import TypeAdapter, ValidationError

from chord_drs.pydantic_models import DrsBentoExtension, DrsChecksum, DrsUri


def test_drs_uri():
    ta = TypeAdapter(DrsUri)

    ta.validate_python("drs://some-host.local/0000-0000")

    with pytest.raises(ValidationError, match="URL scheme should be 'drs'"):
        ta.validate_python("https://bento-platform.github.io")


def test_bento_drs_extension_construction():
    DrsBentoExtension(project_id="project-1", dataset_id="dataset-1", data_type="phenopacket", public=False)
    DrsBentoExtension(project_id=None, dataset_id=None, data_type=None, public=True)


def test_drs_checksum_construction():
    cs = hashlib.sha256(data=b"test", usedforsecurity=False)
    DrsChecksum(type="sha-256", checksum=cs.hexdigest())

    with pytest.raises(ValidationError, match="String should have at least 64 characters"):
        DrsChecksum(type="sha-256", checksum="not long enough")
