"""Pydantic models for E₀ API Gateway (Layer C).

Maps E₀ dataclasses and service layer types to validated API models.
Used by REST endpoints and WebSocket protocol.

C84.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


# ── Session Creation ─────────────────────────────────────

class CreateSessionRequest(BaseModel):
    """Create a new E₀ session."""
    mode: str = Field(
        ...,
        description="Input mode: 'json', 'text', or 'canon'",
        pattern="^(json|text|canon)$",
    )
    spec: Optional[Dict[str, Any]] = Field(
        None, description="DomainSpec JSON (required when mode='json')"
    )
    text: Optional[str] = Field(
        None, description="Natural-language description (required when mode='text')"
    )
    canon_name: Optional[str] = Field(
        None, description="Canon name (required when mode='canon')"
    )
    controller_kwargs: Optional[Dict[str, Any]] = Field(
        None, description="Extra kwargs for E0Controller (focus_k, overload_threshold, etc.)"
    )
    enable_peer: bool = Field(
        False, description="Enable human peer via WebSocket"
    )
    peer_timeout: float = Field(
        60.0, description="Timeout in seconds for peer response"
    )


class CreateSessionResponse(BaseModel):
    session_id: str
    state: str
    landscape_states: int
    landscape_edges: int


# ── Session Control ──────────────────────────────────────

class StartRequest(BaseModel):
    start: str = Field(..., description="Start state name")
    goal: Optional[str] = Field(None, description="Goal state name")
    max_cycles: int = Field(50, ge=1, le=10000)


class SessionInfo(BaseModel):
    session_id: str
    state: str
    current_position: Optional[str]
    goal: Optional[str]
    history_length: int
    mode: str
    landscape_states: int
    landscape_edges: int


class SessionListItem(BaseModel):
    session_id: str
    state: str
    current_position: Optional[str]
    history_length: int


# ── Step / Events ────────────────────────────────────────

class StepEventModel(BaseModel):
    tau: int
    source: str
    target: str
    outcome: str
    s_eff: float
    r_eff_before: float
    r_eff_after: float
    candidates: List[str]
    escalated: bool
    escalation_type: str
    hybrid_overridden: bool
    mode: str
    overload_index: Optional[float]
    timestamp: float
    # Overlay summary (C92)
    override_confidence: float = 0.0
    geometry: Optional[str] = None
    horizon: Optional[int] = None
    amplitude_choice: Optional[str] = None
    total_paths: Optional[int] = None


# ── WebSocket Protocol ───────────────────────────────────

class WSMessage(BaseModel):
    """WebSocket wire format (both directions)."""
    event: str
    session_id: str
    tau: Optional[int] = None
    data: Optional[Dict[str, Any]] = None


class PeerResponseMessage(BaseModel):
    """Client → Server: peer's chosen target."""
    target: str


# ── Canon ────────────────────────────────────────────────

class CanonSummary(BaseModel):
    name: str
    description: str
    node_count: int
    edge_count: int
    goal_states: List[str]


# ── Strategy ─────────────────────────────────────────────

class StrategyEntry(BaseModel):
    edge: str
    source: str
    target: str
    trace_quality: float
    trace_load: float


# ── Health ───────────────────────────────────────────────

class HealthResponse(BaseModel):
    status: str = "ok"
    active_sessions: int
    version: str = "0.8.0"
