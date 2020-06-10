import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from chord_lib.responses import flask_errors
from werkzeug.exceptions import BadRequest, NotFound

from chord_drs.config import Config, APP_DIR
from chord_drs.constants import SERVICE_NAME
from chord_drs.backend import close_backend
from prometheus_flask_exporter import PrometheusMetrics

MIGRATION_DIR = os.path.join(APP_DIR, "migrations")

application = Flask(__name__)
application.config.from_object(Config)

# Generic catch-all
application.register_error_handler(
    Exception,
    flask_errors.flask_error_wrap_with_traceback(flask_errors.flask_internal_server_error, service_name=SERVICE_NAME)
)
application.register_error_handler(BadRequest, flask_errors.flask_error_wrap(flask_errors.flask_bad_request_error))
application.register_error_handler(NotFound, flask_errors.flask_error_wrap(flask_errors.flask_not_found_error))

db = SQLAlchemy(application)
migrate = Migrate(application, db, directory=MIGRATION_DIR)

from chord_drs.routes import drs_service  # noqa: E402
application.register_blueprint(drs_service)

from chord_drs.commands import ingest  # noqa: E402
application.cli.add_command(ingest)

application.teardown_appcontext(close_backend)
metrics = PrometheusMetrics(application)