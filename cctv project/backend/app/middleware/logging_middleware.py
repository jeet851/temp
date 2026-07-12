"""
VisionGuard — Request/Response Logging Middleware.

Logs every HTTP request with method, path, status code, and duration.
"""

import time
import logging

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger("visionguard.api")


class LoggingMiddleware(BaseHTTPMiddleware):
    """Logs incoming requests and outgoing response status codes."""

    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        response = await call_next(request)
        duration_ms = round((time.time() - start_time) * 1000, 1)

        logger.info(
            "%s %s -> %s (%sms)",
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
        )
        return response
