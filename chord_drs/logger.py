import logging

__all__ = [
    "logger",
]

logging.basicConfig(level=logging.NOTSET)

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# Remove `DEBUG:asyncio:Using selector: EpollSelector` spam
logging.getLogger("asyncio").setLevel(logging.INFO)
# Remove `DEBUG:urllib3.connectionpool:Starting new HTTPS connection` spam
logging.getLogger("urllib3.connectionpool").setLevel(logging.INFO)
