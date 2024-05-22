from bento_lib.service_info.helpers import build_service_type
from chord_drs import __version__

__all__ = [
    "BENTO_SERVICE_KIND",
    "SERVICE_NAME",
    "SERVICE_ARTIFACT",
    "SERVICE_TYPE",
]

BENTO_SERVICE_KIND = "drs"
SERVICE_NAME = "Bento Data Repository Service"
SERVICE_ARTIFACT = BENTO_SERVICE_KIND
SERVICE_TYPE = build_service_type("ca.c3g.chord", SERVICE_ARTIFACT, __version__)
