from .conftest import DUMMY_FILE, EMPTY_FILE
from chord_drs.utils import drs_file_checksum


def test_sha256_checksum():
    # see https://crypto.stackexchange.com/questions/26133/sha-256-hash-of-null-input
    assert drs_file_checksum(EMPTY_FILE) == "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"

    # file with content
    assert drs_file_checksum(DUMMY_FILE) == "ca5170c51e4d4e68d4c39832489ea9ad8e275c9f46e0c195c86aaf61ee2ce3d8"
