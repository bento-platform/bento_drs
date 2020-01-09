import os

from chord_lib.utils import get_own_version
from pathlib import Path

name = "chord_drs"
# TODO: there as to be a cleaner version for such a seemingly simple need
# few ideas there : https://packaging.python.org/guides/single-sourcing-package-version/
# though nothing that great...
__version__ = get_own_version(os.path.join(Path(os.path.dirname(os.path.realpath(__file__))).parent, "setup.py"), name)
