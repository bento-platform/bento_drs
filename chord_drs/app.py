import os

from bento_lib.responses import flask_errors
from flask import Flask
from flask_cors import CORS
from flask_migrate import Migrate
from werkzeug.exceptions import BadRequest, Forbidden, NotFound

from .authz import authz_middleware
from .backend import close_backend
from .commands import ingest
from .config import Config, APP_DIR
from .constants import SERVICE_NAME
from .db import db
from .metrics import metrics
from .routes import drs_service


MIGRATION_DIR = os.path.join(APP_DIR, "migrations")

application = Flask(__name__)
application.config.from_object(Config)

# Set up CORS
CORS(application, origins=Config.CORS_ORIGINS)

# Attach authz middleware to Flask instance
authz_middleware.attach(application)

# Register exception handlers, to return nice JSON responses
# - Generic catch-all
application.register_error_handler(
    Exception,
    flask_errors.flask_error_wrap_with_traceback(
        flask_errors.flask_internal_server_error,
        service_name=SERVICE_NAME,
        drs_compat=True,
        logger=application.logger,
        authz=authz_middleware,
    ))
application.register_error_handler(
    BadRequest,
    flask_errors.flask_error_wrap(
        flask_errors.flask_bad_request_error,
        drs_compat=True,
        authz=authz_middleware,
    ))
application.register_error_handler(
    Forbidden,
    flask_errors.flask_error_wrap(
        flask_errors.flask_forbidden_error,
        drs_compat=True,
        authz=authz_middleware,
    ))
application.register_error_handler(
    NotFound,
    lambda e: flask_errors.flask_error_wrap(
        flask_errors.flask_not_found_error,
        str(e),
        drs_compat=True,
        authz=authz_middleware,
    )(e))

# Attach the database to the application and run migrations if needed
db.init_app(application)
migrate = Migrate(application, db, directory=MIGRATION_DIR)

# Register routes
application.register_blueprint(drs_service)

# Register application commands
application.cli.add_command(ingest)

# Add callback to handle tearing down backend when a context is closed
application.teardown_appcontext(close_backend)

# Attach Prometheus metrics exporter (if enabled)
with application.app_context():  # pragma: no cover
    if application.config["PROMETHEUS_ENABLED"]:
        metrics.init_app(application)
