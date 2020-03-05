import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from chord_drs.config import Config, APP_DIR


MIGRATION_DIR = os.path.join(APP_DIR, "migrations")

application = Flask(__name__)
application.config.from_object(Config)

db = SQLAlchemy(application)
migrate = Migrate(application, db, directory=MIGRATION_DIR)

from chord_drs.routes import drs_service  # noqa: E402
application.register_blueprint(drs_service)

from chord_drs.commands import ingest  # noqa: E402
application.cli.add_command(ingest)

# TODO: would be nice to deal with backends the same way we deal with commands
# that is not be importing application, running in context and using current_app
from chord_drs import backends  # noqa: E402,F401
