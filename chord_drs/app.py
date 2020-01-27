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


from chord_drs import routes, models, commands, backends  # noqa: E402,F401
