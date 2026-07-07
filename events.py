"""Event log + live WebSocket fan-out to connected browsers."""
import json

from fastapi import WebSocket

import db


class WsManager:
    def __init__(self):
        self._clients: set[WebSocket] = set()

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        self._clients.add(ws)

    def disconnect(self, ws: WebSocket) -> None:
        self._clients.discard(ws)

    async def broadcast(self, message: dict) -> None:
        dead = []
        for ws in self._clients:
            try:
                await ws.send_text(json.dumps(message))
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)


ws_manager = WsManager()


async def emit(type_: str, detail: str) -> None:
    """Persist an event and push it to all connected clients."""
    event = db.log_event(type_, detail)
    await ws_manager.broadcast({"kind": "event", "event": event})
