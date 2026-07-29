"""
VisionGuard — CORS Middleware Configuration.

Configures Cross-Origin Resource Sharing to allow the
React frontend to communicate with the FastAPI backend.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings


def configure_cors(app: FastAPI) -> None:
    """Attach CORS middleware to the FastAPI application."""
    origins = settings.cors_origin_list
    allow_all = "*" in origins

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"] if allow_all else origins,
        allow_credentials=not allow_all,
        allow_methods=["*"],
        allow_headers=["*"],
    )
