import configparser
import os

from chord_drs.config import BASEDIR


config = configparser.ConfigParser()
config.read(os.path.join(os.path.dirname(os.path.realpath(__file__)), "package.cfg"))

name = config["package"]["name"]
__version__ = config["package"]["version"]
