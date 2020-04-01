import os
from chord_drs import __version__

__all__ = ["SERVICE_NAME", "SERVICE_TYPE"]

SERVICE_NAME = "CHORD Data Repository Service"
SERVICE_TYPE = "ca.c3g.chord:drs:{}".format(__version__)
SERVICE_ID = os.environ.get("SERVICE_ID", SERVICE_TYPE)
