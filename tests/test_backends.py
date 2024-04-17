import pathlib
import pytest

from chord_drs.backends.local import LocalBackend


def test_local_backend(local_volume):
    backend = LocalBackend({"SERVICE_DATA": str(local_volume)})

    file_to_ingest = pathlib.Path(__file__).parent / "dummy_file.txt"

    backend.save(file_to_ingest, "dummy_file.txt")
    assert (local_volume / "dummy_file.txt").exists()

    backend.delete(local_volume / "dummy_file.txt")
    assert not (local_volume / "dummy_file.txt").exists()


def test_local_backend_raises(local_volume):
    backend = LocalBackend({"SERVICE_DATA": str(local_volume)})

    with pytest.raises(ValueError):
        # before we can even figure out file does not exist, this is not a local volume subpath:
        backend.delete("/tmp/does_not_exist.txt")
