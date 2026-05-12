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


# ── Observation ──────────────────────────────────────────

class ObservationNavigateRequest(BaseModel):
    """Navigate observation: focus/defocus/deepen/retreat/move."""
    action: str = Field(
        ...,
        description="Navigation action: focus, defocus, deepen, retreat, move",
        pattern="^(focus|defocus|deepen|retreat|move)$",
    )
    node_id: Optional[str] = Field(
        None, description="Target node ID (required for focus and move)"
    )


# ── Domain Studio (ARC-K, C307) ──────────────────────────

class CreateDomainRequest(BaseModel):
    """Create a new named domain workspace."""
    name: str = Field(..., description="Unique domain name (slug)", min_length=1, max_length=64)
    description: str = Field("", description="Human-readable description")
    topic: str = Field("", description="Domain topic / subject area")
    mode: str = Field("learn", description="Initial mode: learn / apply / hybrid",
                      pattern="^(learn|apply|hybrid)$")


class DomainStatusResponse(BaseModel):
    name: str
    description: str
    topic: str
    mode: str
    episode_count: int
    states: int
    edges: int
    total_inscriptions: float
    cold_start: bool
    created_at: str


class DomainListItem(BaseModel):
    name: str


class LearnRequest(BaseModel):
    """Trigger a supervised learning run on a domain."""
    n_episodes: int = Field(10, ge=1, le=1000)
    oracle_type: str = Field(
        "always_success",
        description="Pre-defined oracle: always_success | random | topology_aware",
        pattern="^(always_success|random|topology_aware)$",
    )
    start: Optional[str] = Field(None, description="Start state (defaults to first state)")
    goal: Optional[str] = Field(None, description="Goal state")
    max_steps: int = Field(30, ge=1, le=500)


class LearnResponse(BaseModel):
    episodes: int
    total_steps: int
    success_count: int
    failure_count: int
    partial_count: int
    edges_explored: int
    goal_rate: float
    warnings: List[str]


class SetModeRequest(BaseModel):
    mode: str = Field(..., pattern="^(learn|apply|hybrid)$")


class RecommendRequest(BaseModel):
    state: str = Field(..., description="Current state")
    candidates: List[str] = Field(..., description="Candidate next states")


class RecommendResponse(BaseModel):
    recommended: Optional[str]
    reason: str
    quality: float
    conviction_score: float
    candidates: List[str]
    cold_start: bool


class RecordRequest(BaseModel):
    source: str
    target: str
    outcome: str = Field(..., description="success | failure | partial")


class RecordResponse(BaseModel):
    ok: bool
    message: str


class InjectResponse(BaseModel):
    edges_added: int
    inscriptions: int
    skipped: int
    warnings: List[str]


class ConvictionMapResponse(BaseModel):
    edges: Dict[str, float]
