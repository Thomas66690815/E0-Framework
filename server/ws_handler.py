"""WebSocket handler for E₀ API Gateway (Layer C).

Manages live event streaming and peer interaction per session.

Protocol:
  Server → Client: {"event": "step"|"escalation"|"peer_request"|"completed"|"error",
                     "session_id": "...", "tau": N, "data": {...}}
  Client → Server: {"event": "peer_response", "data": {"target": "..."}}
                   {"event": "pause"}
                   {"event": "resume"}

C84.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Dict, Optional, Set

from fastapi import WebSocket, WebSocketDisconnect

from e0_controller.service import ServiceSession, SessionState
from e0_controller.peer_bridge import PeerRequest

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manages WebSocket connections per session."""

    def __init__(self):
        self._connections: Dict[str, Set[WebSocket]] = {}

    async def connect(self, session_id: str, ws: WebSocket) -> None:
        await ws.accept()
        if session_id not in self._connections:
            self._connections[session_id] = set()
        self._connections[session_id].add(ws)

    def disconnect(self, session_id: str, ws: WebSocket) -> None:
        if session_id in self._connections:
            self._connections[session_id].discard(ws)
            if not self._connections[session_id]:
                del self._connections[session_id]

    async def send_event(
        self, session_id: str, event: str, data: dict, tau: Optional[int] = None
    ) -> None:
        """Send event to all WebSocket clients of a session."""
        msg = {"event": event, "session_id": session_id, "data": data}
        if tau is not None:
            msg["tau"] = tau
        connections = self._connections.get(session_id, set())
        dead = []
        for ws in connections:
            try:
                await ws.send_json(msg)
            except Exception:
                dead.append(ws)
        for ws in dead:
            connections.discard(ws)


# Module-level singleton
ws_manager = ConnectionManager()


def _make_session_listener(session_id: str):
    """Create a synchronous listener that queues events for async sending."""
    # We use a list as a simple event queue — the WebSocket loop drains it
    queue: asyncio.Queue = asyncio.Queue()

    def listener(event_type: str, data: dict) -> None:
        try:
            queue.put_nowait((event_type, data))
        except Exception:
            pass

    return listener, queue


async def _drain_events(session_id: str, queue: asyncio.Queue) -> None:
    """Send queued events to WebSocket clients."""
    while not queue.empty():
        event_type, data = queue.get_nowait()
        tau = data.get("tau")
        await ws_manager.send_event(session_id, event_type, data, tau=tau)


def bind_peer_bridge_to_ws(session: ServiceSession) -> None:
    """Wire peer_bridge.on_request to push peer_request via WebSocket."""
    if session.peer_bridge is None:
        return

    def on_peer_request(request: PeerRequest) -> None:
        session.state = SessionState.WAITING_PEER
        # The actual WebSocket push happens in the event drain loop
        # We emit a synthetic event that the listener can pick up
        # This is handled by _handle_peer_request in the WS loop

    session.peer_bridge.on_request = on_peer_request


async def handle_websocket(
    ws: WebSocket,
    session_id: str,
    get_session,
) -> None:
    """Main WebSocket handler for a session.

    Handles:
      - Event streaming (step, escalation, completed)
      - Peer interaction (peer_request → peer_response)
      - Client commands (pause, resume)
    """
    session = get_session(session_id)
    if session is None:
        await ws.close(code=4004, reason="Session not found")
        return

    await ws_manager.connect(session_id, ws)

    # Set up event listener
    listener, queue = _make_session_listener(session_id)
    session.add_listener(listener)

    try:
        while True:
            # Check for peer request to push
            if session.peer_bridge and session.peer_bridge.is_waiting:
                req = session.peer_bridge.pending_request
                if req is not None:
                    await ws_manager.send_event(session_id, "peer_request", {
                        "current": req.current,
                        "neighbors": req.neighbors,
                        "edge_info": req.edge_info,
                        "overload_index": req.overload_index,
                        "tau": req.tau,
                    })

            # Drain any queued events
            await _drain_events(session_id, queue)

            # Wait for client message with timeout (allows periodic drain)
            try:
                raw = await asyncio.wait_for(ws.receive_text(), timeout=0.5)
            except asyncio.TimeoutError:
                continue
            except WebSocketDisconnect:
                break

            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                await ws.send_json({
                    "event": "error",
                    "session_id": session_id,
                    "data": {"message": "Invalid JSON"},
                })
                continue

            event = msg.get("event", "")

            if event == "peer_response":
                target = msg.get("data", {}).get("target")
                if target and session.peer_bridge:
                    ok = session.peer_bridge.submit_response(target)
                    if ok:
                        session.state = SessionState.RUNNING
                    else:
                        await ws.send_json({
                            "event": "error",
                            "session_id": session_id,
                            "data": {"message": "No pending peer request"},
                        })

            elif event == "pause":
                session.pause()

            elif event == "resume":
                session.resume()

            else:
                await ws.send_json({
                    "event": "error",
                    "session_id": session_id,
                    "data": {"message": f"Unknown event: {event!r}"},
                })

    except WebSocketDisconnect:
        pass
    finally:
        ws_manager.disconnect(session_id, ws)
