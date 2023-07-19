import os
from chord_drs.utils import drs_file_checksum
from .conftest import AUTHZ_URL, dummy_file_path, empty_file_path


def test_sha256_checksum_empty():
    os.environ["BENTO_AUTHZ_SERVICE_URL"] = AUTHZ_URL
    # see https://crypto.stackexchange.com/questions/26133/sha-256-hash-of-null-input
    assert drs_file_checksum(empty_file_path()) == "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"


def test_sha256_checksum_dummy():
    os.environ["BENTO_AUTHZ_SERVICE_URL"] = AUTHZ_URL
    # file with content
    assert drs_file_checksum(dummy_file_path()) == "ca5170c51e4d4e68d4c39832489ea9ad8e275c9f46e0c195c86aaf61ee2ce3d8"
