from pathlib import Path

from alembic import command
from alembic.config import Config as AlembicConfig
from sqlalchemy import create_engine, inspect


def test_migrations_upgrade_to_head(tmp_path):
    db_url = f"sqlite:///{tmp_path / 'db.sqlite3'}"

    cfg = AlembicConfig(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", db_url)

    command.upgrade(cfg, "head")
    command.upgrade(cfg, "head")  # idempotent, as on every service start

    tables = set(inspect(create_engine(db_url)).get_table_names())
    assert {"drs_object", "alembic_version"} <= tables
