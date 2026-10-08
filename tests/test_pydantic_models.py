import pytest
from pydantic import TypeAdapter, ValidationError

from chord_drs.pydantic_models import DrsUri


def test_drs_uri():
    ta = TypeAdapter(DrsUri)

    ta.validate_python("drs://some-host.local/0000-0000")

    with pytest.raises(ValidationError, match="URL scheme should be 'drs'"):
        ta.validate_python("https://bento-platform.github.io")
