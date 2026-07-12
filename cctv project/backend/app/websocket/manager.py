"""
VisionGuard — WebSocket Connection Manager.

Manages connected WebSocket clients and broadcasts
real-time updates for environmental readings, alerts,
and dashboard statistics.
"""

import json
import logging
from typing import Any

from fastapi import WebSocket

logger = logging.getLogger("visionguard.websocket")


class ConnectionManager:
    """
    Manages active WebSocket connections and broadcasts messages.

    Usage:
        manager = ConnectionManager()

        # In a WS route:
        await manager.connect(websocket)
        ...
        manager.disconnect(websocket)

        # From any service / scheduler:
        await manager.broadcast("reading", data)
    """

    def __init__(self) -> None:
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket) -> None:
        """Accept and register a WebSocket connection."""
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(
            "WebSocket connected. Active connections: %d",
            len(self.active_connections),
        )

    def disconnect(self, websocket: WebSocket) -> None:
        """Remove a WebSocket connection from the active pool."""
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        logger.info(
            "WebSocket disconnected. Active connections: %d",
            len(self.active_connections),
        )

    async def broadcast(self, event_type: str, data: Any) -> None:
        """
        Send a typed JSON message to all connected clients.

        Message format:
            { "type": "<event_type>", "data": <payload> }

        Args:
            event_type: Event discriminator (e.g. "reading", "alert", "historyChanged").
            data: JSON-serializable payload.
        """
        if not self.active_connections:
            return

        message = json.dumps({"type": event_type, "data": data}, default=str)
        disconnected: list[WebSocket] = []

        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except Exception:
                disconnected.append(connection)

        # Clean up broken connections
        for conn in disconnected:
            self.disconnect(conn)


# Singleton instance used across the application
ws_manager = ConnectionManager()
