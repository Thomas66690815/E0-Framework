"""E₀ API Gateway — FastAPI application.

Start with:
    py -3 -m uvicorn server.main:app --reload

OpenAPI docs at:
    http://localhost:8000/docs

C84.
"""

from __future__ import annotations

from fastapi import FastAPI, WebSocket

from e0_controller.service import SessionManager

from server.routes_sessions import router, set_manager
from server.ws_handler import handle_websocket

app = FastAPI(
    title="E₀ Framework API",
    description="REST + WebSocket gateway for the E₀ navigation controller",
    version="0.8.0",
)

# ── Startup ──────────────────────────────────────────────

manager = SessionManager()
set_manager(manager)

app.include_router(router)


# ── WebSocket endpoint ───────────────────────────────────

@app.websocket("/sessions/{session_id}/ws")
async def websocket_endpoint(ws: WebSocket, session_id: str):
    await handle_websocket(ws, session_id, manager.get)
