from bento_lib.service_info.helpers import build_service_type

__all__ = [
    "BENTO_SERVICE_KIND",
    "SERVICE_NAME",
    "SERVICE_ARTIFACT",
    "DRS_SPEC_VERSION",
    "SERVICE_TYPE",
]

BENTO_SERVICE_KIND = "drs"
SERVICE_NAME = "Bento Data Repository Service"
SERVICE_ARTIFACT = BENTO_SERVICE_KIND
DRS_SPEC_VERSION = "1.4.0"  # update to match whatever version of the DRS spec is implemented.
SERVICE_TYPE = build_service_type("org.ga4gh", SERVICE_ARTIFACT, DRS_SPEC_VERSION)
