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
SERVICE_TYPE = {
    "group": "ca.c3g.chord",
    "artifact": SERVICE_ARTIFACT,
    "version": __version__,
}
