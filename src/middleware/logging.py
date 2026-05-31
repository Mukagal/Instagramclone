import time
import logging
from fastapi import Request

logger = logging.getLogger("api")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

async def logging_middleware(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    duration_ms = (time.perf_counter() - start) * 1000

    client = request.client
    ip = client.host if client else "unknown"
    port = client.port if client else 0

    log_line = (
        f"{ip}:{port} - {request.method} - {request.url.path} "
        f"- {response.status_code} - {duration_ms:.2f}ms"
    )

    if response.status_code >= 500:
        logger.error(log_line)
    elif response.status_code >= 400:
        logger.warning(log_line)
    else:
        logger.info(log_line)

    return response