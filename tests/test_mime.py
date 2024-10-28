import pytest

from chord_drs.constants import RE_INGESTABLE_MIME_TYPE


@pytest.mark.parametrize(
    "val",
    [
        "image/jpeg",
        "video/mp4",
        "application/octet-stream",
        "application/json+test;charset=UTF-8",
        'application/json+test; charset="UTF-8"',
        "text/html",
        "text/x-fasta",
        "text/plain;charset=UTF-8",
        'text/plain; charset="UTF-8"',
    ],
)
def test_ingestable_mime_type_pattern(val: str):
    assert RE_INGESTABLE_MIME_TYPE.match(val) is not None


@pytest.mark.parametrize(
    "val",
    [
        "image",
        "multipart/form-data",
        "text/*",
        "image/;;;;;;;;",
        "image/jpeg;",
        'text/plain charset="UTF-8"',
        "invalid/octet-stream",
    ],
)
def test_non_ingestable_mime_type_pattern(val: str):
    assert RE_INGESTABLE_MIME_TYPE.match(val) is None
