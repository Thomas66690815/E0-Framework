"""REST routes for E₀ API Gateway (Layer C).

All session management, lifecycle control, data retrieval.
WebSocket handling is in ws_handler.py.

C84.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException

from e0_controller.primitives import Outcome
from e0_controller.service import (
    ServiceSession,
    SessionManager,
    SessionState,
    StepEvent,
)
from e0_controller.peer_bridge import PeerBridge
from e0_controller.snapshot_codec import encode_landscape, encode_strategy_profile
from e0_controller.canon_loader import list_canons, load_canon, CanonInfo

from server.models import (
    CreateSessionRequest,
    CreateSessionResponse,
    StartRequest,
    SessionInfo,
    SessionListItem,
    StepEventModel,
    CanonSummary,
    StrategyEntry,
    HealthResponse,
)

router = APIRouter()

# The SessionManager is injected from main.py via app.state
# Routes access it via the request object, but for simplicity
# we use a module-level reference set during app startup.
_manager: Optional[SessionManager] = None


def set_manager(manager: SessionManager) -> None:
    global _manager
    _manager = manager


def _get_manager() -> SessionManager:
    if _manager is None:
        raise RuntimeError("SessionManager not initialized")
    return _manager


def _get_session(session_id: str) -> ServiceSession:
    mgr = _get_manager()
    session = mgr.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail=f"Session {session_id!r} not found")
    return session


# ── Default execute_fn for API sessions ──────────────────

def _default_execute_fn(source: str, target: str) -> Outcome:
    """Default execute_fn: always succeeds.

    Real applications override this via controller_kwargs or
    use LLM-backed execution via the adapter.
    """
    return Outcome.SUCCESS


# ── Session CRUD ─────────────────────────────────────────

@router.post("/sessions", response_model=CreateSessionResponse, status_code=201)
def create_session(req: CreateSessionRequest):
    """Create a new E₀ session from JSON spec, text, or canon."""
    mgr = _get_manager()

    peer_bridge = None
    if req.enable_peer:
        peer_bridge = PeerBridge(session_id="pending", timeout=req.peer_timeout)

    kwargs = req.controller_kwargs or {}

    try:
        if req.mode == "json":
            if req.spec is None:
                raise HTTPException(400, "'spec' required when mode='json'")
            session = mgr.create_from_json(
                req.spec, _default_execute_fn,
                controller_kwargs=kwargs, peer_bridge=peer_bridge,
            )
        elif req.mode == "canon":
            if req.canon_name is None:
                raise HTTPException(400, "'canon_name' required when mode='canon'")
            session = mgr.create_from_canon(
                req.canon_name, _default_execute_fn,
                controller_kwargs=kwargs, peer_bridge=peer_bridge,
            )
        elif req.mode == "text":
            if req.text is None:
                raise HTTPException(400, "'text' required when mode='text'")
            session = mgr.create_from_text(
                req.text, _default_execute_fn,
                controller_kwargs=kwargs, peer_bridge=peer_bridge,
            )
        else:
            raise HTTPException(400, f"Unknown mode: {req.mode!r}")
    except HTTPException:
        raise
    except FileNotFoundError as exc:
        raise HTTPException(404, str(exc))
    except Exception as exc:
        raise HTTPException(422, str(exc))

    # Update peer_bridge session_id now that we have it
    if peer_bridge is not None:
        peer_bridge.session_id = session.id

    return CreateSessionResponse(
        session_id=session.id,
        state=session.state.value,
        landscape_states=len(session.landscape.states),
        landscape_edges=len(session.landscape.edges),
    )


@router.get("/sessions", response_model=List[SessionListItem])
def list_sessions():
    """List all active sessions."""
    return _get_manager().list_sessions()


@router.get("/sessions/{session_id}", response_model=SessionInfo)
def get_session(session_id: str):
    """Get session info and current state."""
    s = _get_session(session_id)
    return SessionInfo(
        session_id=s.id,
        state=s.state.value,
        current_position=s.current_position,
        goal=s._goal,
        history_length=len(s.history),
        mode=s.mode_controller.current_mode().value,
        landscape_states=len(s.landscape.states),
        landscape_edges=len(s.landscape.edges),
    )


@router.delete("/sessions/{session_id}", status_code=204)
def delete_session(session_id: str):
    """Terminate and remove a session."""
    if not _get_manager().remove(session_id):
        raise HTTPException(404, f"Session {session_id!r} not found")


# ── Session Lifecycle ────────────────────────────────────

@router.post("/sessions/{session_id}/start", response_model=SessionInfo)
def start_session(session_id: str, req: StartRequest):
    """Start a session run."""
    s = _get_session(session_id)
    try:
        s.start(req.start, goal=req.goal, max_cycles=req.max_cycles)
    except ValueError as exc:
        raise HTTPException(422, str(exc))
    return get_session(session_id)


@router.post("/sessions/{session_id}/pause", response_model=SessionInfo)
def pause_session(session_id: str):
    """Pause a running session."""
    s = _get_session(session_id)
    s.pause()
    return get_session(session_id)


@router.post("/sessions/{session_id}/resume", response_model=SessionInfo)
def resume_session(session_id: str):
    """Resume a paused session."""
    s = _get_session(session_id)
    s.resume()
    return get_session(session_id)


@router.post("/sessions/{session_id}/step", response_model=Optional[StepEventModel])
def step_session(session_id: str):
    """Execute a single controller cycle."""
    s = _get_session(session_id)
    if s.state == SessionState.CREATED:
        raise HTTPException(409, "Session not started — call /start first")
    if s.state == SessionState.COMPLETED:
        raise HTTPException(409, "Session already completed")
    if s.state == SessionState.WAITING_PEER:
        raise HTTPException(409, "Session waiting for peer response")

    event = s.step()
    if event is None:
        return None
    return StepEventModel(**event.to_dict())


# ── Data Retrieval ───────────────────────────────────────

@router.get("/sessions/{session_id}/history", response_model=List[StepEventModel])
def get_history(session_id: str):
    """Full step history."""
    s = _get_session(session_id)
    return [StepEventModel(**e.to_dict()) for e in s.history]


@router.get("/sessions/{session_id}/strategy", response_model=List[StrategyEntry])
def get_strategy(session_id: str, top_n: int = 0):
    """What did E₀ learn? Strategy profile sorted by trace_quality."""
    s = _get_session(session_id)
    return s.strategy(top_n=top_n)


@router.get("/sessions/{session_id}/snapshot")
def get_snapshot(session_id: str):
    """Current landscape snapshot (full JSON)."""
    s = _get_session(session_id)
    return s.snapshot()


# ── Canons ───────────────────────────────────────────────

@router.get("/canons", response_model=List[str])
def get_canons():
    """List available canon names."""
    return list_canons()


@router.get("/canons/{name}", response_model=CanonSummary)
def get_canon(name: str):
    """Get canon metadata."""
    try:
        cl = load_canon(name)
    except FileNotFoundError as exc:
        raise HTTPException(404, str(exc))
    info = cl.info
    return CanonSummary(
        name=info.name,
        description=info.description,
        node_count=len(info.nodes),
        edge_count=len(info.edges),
        goal_states=info.goal_states,
    )


# ── Health ───────────────────────────────────────────────

@router.get("/health", response_model=HealthResponse)
def health():
    """Server health check."""
    mgr = _get_manager()
    return HealthResponse(active_sessions=len(mgr._sessions))
