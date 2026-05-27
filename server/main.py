"""E₀ API Gateway — FastAPI application.

Start with:
    py -3 -m uvicorn server.main:app --reload

OpenAPI docs at:
    http://localhost:8000/docs

C84.
"""

from __future__ import annotations

import pathlib

from fastapi import FastAPI, WebSocket
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from e0_controller.service import SessionManager

from server.routes_sessions import router, set_manager
from server.routes_tests import router as tests_router
from server.routes_domains import router as domains_router
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
app.include_router(tests_router)
app.include_router(domains_router)

# ── Static UI (Domain Studio) ────────────────────────────

_static_dir = pathlib.Path(__file__).parent / "static"
app.mount("/studio", StaticFiles(directory=str(_static_dir), html=True), name="studio")


@app.get("/", include_in_schema=False)
def root_redirect():
    return RedirectResponse(url="/studio/")


# ── WebSocket endpoint ───────────────────────────────────

@app.websocket("/sessions/{session_id}/ws")
async def websocket_endpoint(ws: WebSocket, session_id: str):
    await handle_websocket(ws, session_id, manager.get)
