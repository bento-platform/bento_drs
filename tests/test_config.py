import tempfile

import pytest
from pydantic import ValidationError

from chord_drs.config import Config, get_config
from chord_drs.constants import DATA_SOURCE_LOCAL, DATA_SOURCE_S3

from .conftest import reset_caches
from .constants import AUTHZ_URL


def test_authz_url_required_if_authz_enabled(monkeypatch):
    monkeypatch.delenv("BENTO_AUTHZ_SERVICE_URL")

    with pytest.raises(ValidationError, match="BENTO_AUTHZ_SERVICE_URL must be set"):
        Config()


@pytest.mark.parametrize("var", ["BENTO_AUTHZ_ENABLED", "AUTHZ_ENABLED"])  # the latter is the legacy name
def test_authz_url_not_required_if_authz_disabled(monkeypatch, var):
    monkeypatch.delenv("BENTO_AUTHZ_SERVICE_URL")
    monkeypatch.setenv(var, "false")

    assert not Config().bento_authz_enabled


def test_urls_have_trailing_slash_stripped(monkeypatch):
    monkeypatch.setenv("BENTO_AUTHZ_SERVICE_URL", f" {AUTHZ_URL}/ ")
    monkeypatch.setenv("SERVICE_BASE_URL", "http://127.0.0.1:5000/api/drs/")

    config = Config()
    assert config.bento_authz_service_url == AUTHZ_URL
    assert config.service_base_url == "http://127.0.0.1:5000/api/drs"


def test_data_source_local_by_default(monkeypatch, tmp_path):
    monkeypatch.setenv("S3_ENDPOINT", "  ")  # blank is the same as unset

    config = get_config()
    assert config.service_data_source == DATA_SOURCE_LOCAL
    assert config.service_data == tmp_path / "data"
    assert config.database_url == f"sqlite:///{(tmp_path / 'db.sqlite3').resolve()}"


def test_data_source_s3(s3_config):
    assert s3_config.service_data_source == DATA_SOURCE_S3
    assert s3_config.service_data is None


def test_validate_ssl_follows_debug_by_default(monkeypatch):
    assert Config().bento_validate_ssl

    monkeypatch.setenv("FLASK_DEBUG", "true")  # legacy name for BENTO_DEBUG
    config = Config()
    assert config.bento_debug
    assert not config.bento_validate_ssl


def test_ingest_tmp_dir_sets_tempdir(monkeypatch, tmp_path):
    from chord_drs.app import create_app

    monkeypatch.setattr(tempfile, "tempdir", None)  # restored after the test
    monkeypatch.setenv("DRS_INGEST_TMP_DIR", str(tmp_path))
    reset_caches()

    create_app()

    assert tempfile.tempdir == str(tmp_path)


def test_get_engine_uses_configured_database(tmp_path):
    from chord_drs.db import get_engine

    assert get_engine().url.database == str((tmp_path / "db.sqlite3").resolve())
