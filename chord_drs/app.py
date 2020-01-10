from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from chord_drs.config import Config


application = Flask(__name__)
application.config.from_object(Config)

db = SQLAlchemy(application)
migrate = Migrate(application, db)


from chord_drs import routes, models, commands  # noqa: E402,F401
