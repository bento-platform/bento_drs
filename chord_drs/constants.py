import re
from bento_lib.service_info.helpers import build_service_type

__all__ = [
    "BENTO_SERVICE_KIND",
    "SERVICE_NAME",
    "SERVICE_ARTIFACT",
    "DRS_SPEC_VERSION",
    "SERVICE_TYPE",
    "RE_INGESTABLE_MIME_TYPE",
    "MIME_OCTET_STREAM",
]

BENTO_SERVICE_KIND = "drs"
SERVICE_NAME = "Bento Data Repository Service"
SERVICE_ARTIFACT = BENTO_SERVICE_KIND
DRS_SPEC_VERSION = "1.4.0"  # update to match whatever version of the DRS spec is implemented.
SERVICE_TYPE = build_service_type("org.ga4gh", SERVICE_ARTIFACT, DRS_SPEC_VERSION)

# See https://datatracker.ietf.org/doc/html/rfc2045#section-5.1
#  - only allow discrete-type content types
#  - allow parameters specifying encoding and whatnot
RE_INGESTABLE_MIME_TYPE = re.compile(
    r"^(application|audio|font|image|model|text|video)"
    r"/[a-zA-Z0-9+\-._]+"
    r"(;\s?[a-zA-Z0-9\-_.]+=\"?[a-zA-Z0-9\-_./+ ]*\"?)?$"
)
MIME_OCTET_STREAM = "application/octet-stream"
