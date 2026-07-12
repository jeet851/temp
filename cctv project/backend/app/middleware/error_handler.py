"""
VisionGuard — Global Error Handler Middleware.

Catches unhandled exceptions and returns consistent JSON responses.
Never exposes internal stack traces to the client.
"""

import logging
import traceback

from fastapi import Request, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger("visionguard.errors")


class ErrorHandlerMiddleware(BaseHTTPMiddleware):
    """Catches all unhandled exceptions and returns a clean JSON error."""

    async def dispatch(self, request: Request, call_next):
        try:
            response = await call_next(request)
            return response
        except Exception as exc:
            logger.error(
                "Unhandled exception on %s %s: %s\n%s",
                request.method,
                request.url.path,
                str(exc),
                traceback.format_exc(),
            )
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={
                    "success": False,
                    "message": "An internal server error occurred.",
                    "code": 500,
                },
            )
