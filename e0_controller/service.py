"""E₀ Service Layer — event-emitting session management.

Provides:
  - ServiceSession: wraps E0Controller with event emission per cycle
  - SessionManager: manages multiple concurrent sessions
  - StepEvent: the single event contract between E₀ and any consumer

This is Layer B — sits between E₀ Core (Layer A) and the API Gateway
(Layer C).  It never modifies Layer A.  Any consumer (UI, CLI, embedded,
another AI) uses this layer.

Part of Layer B (Service Layer).  C83.
"""

from __future__ import annotations

import enum
import time
import uuid
from dataclasses import dataclass, field
from typing import (
    Any,
    AsyncIterator,
    Callable,
    Dict,
    List,
    Optional,
    Set,
)

from e0_controller.primitives import Edge, Outcome
from e0_controller.controller import (
    E0Controller,
    EscalationType,
    HybridMode,
    RunTrace,
    StepResult,
)
from e0_controller.landscape import Landscape
from e0_controller.mode_controller import ModeController, OperatingMode
from e0_controller.snapshot_codec import (
    encode_landscape,
    encode_step,
    encode_edge_info,
    encode_run_trace,
    encode_strategy_profile,
    decode_landscape,
)
from e0_controller.peer_bridge import PeerBridge
from e0_controller.input_pipeline import InputPipeline, PipelineResult
from e0_controller.observation_controller import ObservationController
from e0_controller.rendering_adapter import render_observation, render_observation_landscape


# ── Session State ────────────────────────────────────────

class SessionState(enum.Enum):
    CREATED = "created"
    RUNNING = "running"
    WAITING_PEER = "waiting_peer"
    PAUSED = "paused"
    COMPLETED = "completed"
    ERROR = "error"


# ── Step Event ───────────────────────────────────────────

@dataclass
class StepEvent:
    """Single event emitted per controller cycle.

    This is the contract between E₀ and any consumer.
    """
    tau: int
    source: str
    target: str
    outcome: str                          # Outcome.value
    s_eff: float
    r_eff_before: float
    r_eff_after: float
    candidates: List[str]
    escalated: bool
    escalation_type: str                  # EscalationType.value
    hybrid_overridden: bool
    mode: str                             # OperatingMode.value
    overload_index: Optional[float]
    timestamp: float
    # Overlay summary (C92)
    override_confidence: float
    geometry: Optional[str]               # amplitude geometry used
    horizon: Optional[int]                # lookahead depth
    amplitude_choice: Optional[str]       # what amplitude would pick
    total_paths: Optional[int]            # sum of path counts across actions

    @staticmethod
    def from_step(
        step: StepResult,
        mode: OperatingMode,
        oi: Optional[float] = None,
    ) -> StepEvent:
        return StepEvent(
            tau=step.tau,
            source=step.source,
            target=step.target,
            outcome=step.outcome.value,
            s_eff=step.s_eff,
            r_eff_before=step.r_eff_before,
            r_eff_after=step.r_eff_after,
            candidates=step.candidates,
            escalated=step.escalated,
            escalation_type=step.escalation_type.value,
            hybrid_overridden=step.hybrid_overridden,
            mode=mode.value,
            overload_index=oi,
            timestamp=time.time(),
            override_confidence=step.override_confidence,
            geometry=step.overlay.geometry if step.overlay else None,
            horizon=step.overlay.horizon_edges if step.overlay else None,
            amplitude_choice=step.overlay.amplitude_choice if step.overlay else None,
            total_paths=sum(ai.path_count for ai in step.overlay.action_infos) if step.overlay else None,
        )

    def to_dict(self) -> dict:
        return {
            "tau": self.tau,
            "source": self.source,
            "target": self.target,
            "outcome": self.outcome,
            "s_eff": self.s_eff,
            "r_eff_before": self.r_eff_before,
            "r_eff_after": self.r_eff_after,
            "candidates": self.candidates,
            "escalated": self.escalated,
            "escalation_type": self.escalation_type,
            "hybrid_overridden": self.hybrid_overridden,
            "mode": self.mode,
            "overload_index": self.overload_index,
            "timestamp": self.timestamp,
            "override_confidence": self.override_confidence,
            "geometry": self.geometry,
            "horizon": self.horizon,
            "amplitude_choice": self.amplitude_choice,
            "total_paths": self.total_paths,
        }


# ── Service Session ──────────────────────────────────────

class ServiceSession:
    """Event-emitting wrapper around E0Controller.

    Provides lifecycle management and per-cycle event emission.
    Does NOT handle persistence (that's Session in session.py).
    """

    def __init__(
        self,
        landscape: Landscape,
        execute_fn: Callable,
        *,
        session_id: Optional[str] = None,
        controller_kwargs: Optional[Dict[str, Any]] = None,
        peer_bridge: Optional[PeerBridge] = None,
    ):
        self.id = session_id or uuid.uuid4().hex[:12]
        self.landscape = landscape
        self.execute_fn = execute_fn
        self.state = SessionState.CREATED
        self.history: List[StepEvent] = []

        # Build controller
        kwargs = dict(controller_kwargs or {})
        if peer_bridge is not None:
            kwargs["peer_fn"] = peer_bridge.as_peer_fn()
        self.peer_bridge = peer_bridge

        self.controller = E0Controller(landscape, execute_fn, **kwargs)
        self.mode_controller = ModeController(landscape)

        # Run configuration (set on start)
        self._current: Optional[str] = None
        self._goal: Optional[str] = None
        self._max_cycles: int = 50
        self._paused = False

        # Event subscribers
        self._listeners: List[Callable[[str, dict], None]] = []

        # Observation (lazy)
        self._observation_ctrl: Optional[ObservationController] = None

    def add_listener(self, callback: Callable[[str, dict], None]) -> None:
        """Register an event listener: callback(event_type, data)."""
        self._listeners.append(callback)

    def _emit(self, event_type: str, data: dict) -> None:
        for cb in self._listeners:
            cb(event_type, data)

    @property
    def current_position(self) -> Optional[str]:
        return self._current

    def step(self) -> Optional[StepEvent]:
        """Execute a single controller cycle.

        Returns StepEvent or None if no transition possible.
        Updates session state accordingly.
        """
        if self._current is None:
            raise RuntimeError("Session not started — call start() first")
        if self.state == SessionState.COMPLETED:
            return None

        self.state = SessionState.RUNNING

        # Check if peer bridge is waiting
        if self.peer_bridge and self.peer_bridge.is_waiting:
            self.state = SessionState.WAITING_PEER
            return None

        result = self.controller.cycle(self._current)

        if result is None:
            self.state = SessionState.COMPLETED
            self._emit("completed", {"reason": "dead_end", "tau": len(self.history)})
            return None

        # Build event
        mode = self.mode_controller.current_mode()
        oi = None
        neighbors = self.controller._admissible_neighbors(result.source)
        if neighbors:
            oi = self.controller._overload_index(result.source, neighbors)

        event = StepEvent.from_step(result, mode, oi)
        self.history.append(event)

        # Update position
        self._current = result.target

        # Emit events
        self._emit("step", event.to_dict())
        if result.escalated:
            self._emit("escalation", event.to_dict())

        # Check goal reached
        if self._goal and self._current == self._goal:
            self.state = SessionState.COMPLETED
            self._emit("completed", {
                "reason": "goal_reached",
                "tau": len(self.history),
                "goal": self._goal,
            })

        # Check max cycles
        elif len(self.history) >= self._max_cycles:
            self.state = SessionState.COMPLETED
            self._emit("completed", {
                "reason": "max_cycles",
                "tau": len(self.history),
            })

        return event

    def start(
        self,
        start: str,
        goal: Optional[str] = None,
        max_cycles: int = 50,
    ) -> None:
        """Initialize the session for running."""
        if start not in self.landscape.states:
            raise ValueError(f"Start state {start!r} not in landscape")
        if goal is not None and goal not in self.landscape.states:
            raise ValueError(f"Goal state {goal!r} not in landscape")
        self._current = start
        self._goal = goal
        self._max_cycles = max_cycles
        self.state = SessionState.RUNNING
        self._emit("started", {
            "start": start,
            "goal": goal,
            "max_cycles": max_cycles,
        })

    def run_sync(
        self,
        start: str,
        goal: Optional[str] = None,
        max_cycles: int = 50,
    ) -> List[StepEvent]:
        """Run to completion synchronously. Returns all events."""
        self.start(start, goal=goal, max_cycles=max_cycles)
        events = []
        while self.state == SessionState.RUNNING:
            event = self.step()
            if event is not None:
                events.append(event)
            if self.state == SessionState.WAITING_PEER:
                break  # Can't proceed without peer in sync mode
        return events

    def pause(self) -> None:
        if self.state == SessionState.RUNNING:
            self.state = SessionState.PAUSED
            self._emit("paused", {"tau": len(self.history)})

    def resume(self) -> None:
        if self.state == SessionState.PAUSED:
            self.state = SessionState.RUNNING
            self._emit("resumed", {"tau": len(self.history)})

    def snapshot(self) -> dict:
        """Full serialized session state."""
        return {
            "session_id": self.id,
            "state": self.state.value,
            "current_position": self._current,
            "goal": self._goal,
            "max_cycles": self._max_cycles,
            "history_length": len(self.history),
            "landscape": encode_landscape(self.landscape),
            "mode": self.mode_controller.current_mode().value,
            "coverage": self.mode_controller.coverage(),
        }

    def strategy(self, top_n: int = 0) -> List[dict]:
        """What did E₀ learn? Returns strategy profile."""
        return encode_strategy_profile(
            self.landscape.historization, top_n=top_n,
        )

    # ── Observation ──────────────────────────────────────

    @property
    def observation_ctrl(self) -> ObservationController:
        """Lazy-init ObservationController for this session's landscape."""
        if self._observation_ctrl is None:
            self._observation_ctrl = ObservationController(self.landscape)
        return self._observation_ctrl

    def observation_snapshot(self) -> dict:
        """Current observation view as a snapshot compatible with GraphView.

        Wraps render_observation output so landscape key holds states/edges.
        """
        raw = render_observation(self.observation_ctrl)
        return {
            "session_id": self.id,
            "state": self.state.value,
            "current_position": self._current,
            "landscape": {
                "states": raw["states"],
                "edges": raw["edges"],
            },
            "modulation": raw.get("modulation", {}),
            "observation": raw.get("observation", {}),
        }

    def observation_meta_snapshot(self) -> dict:
        """O-Landscape itself (meta-view) as a GraphView-compatible snapshot."""
        raw = render_observation_landscape(self.observation_ctrl)
        return {
            "session_id": self.id,
            "state": self.state.value,
            "current_position": self.observation_ctrl.current,
            "landscape": {
                "states": raw["states"],
                "edges": raw["edges"],
            },
            "modulation": raw.get("modulation", {}),
            "observation": raw.get("observation", {}),
        }

    def observation_navigate(self, action: str, node_id: Optional[str] = None) -> dict:
        """Execute an observation navigation action.

        Returns the StepResult as a dict.
        """
        ctrl = self.observation_ctrl
        if action == "focus":
            if node_id is None:
                raise ValueError("focus requires node_id")
            result = ctrl.focus(node_id)
        elif action == "defocus":
            result = ctrl.defocus()
        elif action == "deepen":
            result = ctrl.deepen()
        elif action == "retreat":
            result = ctrl.retreat()
        elif action == "move":
            if node_id is None:
                raise ValueError("move requires node_id")
            result = ctrl.move(node_id)
        else:
            raise ValueError(f"Unknown observation action: {action!r}")

        return {
            "success": result.success,
            "previous": result.previous,
            "current": result.current,
            "r_eff": result.r_eff,
            "s_eff": result.s_eff,
        }


# ── Session Manager ──────────────────────────────────────

class SessionManager:
    """Manages multiple concurrent ServiceSessions."""

    def __init__(self):
        self._sessions: Dict[str, ServiceSession] = {}
        self._pipeline = InputPipeline()

    def create_from_json(
        self,
        spec: dict,
        execute_fn: Callable,
        *,
        controller_kwargs: Optional[Dict[str, Any]] = None,
        peer_bridge: Optional[PeerBridge] = None,
    ) -> ServiceSession:
        """Create a session from structured JSON spec."""
        result = self._pipeline.from_json(spec)
        return self._register(result.landscape, execute_fn,
                              controller_kwargs=controller_kwargs,
                              peer_bridge=peer_bridge)

    def create_from_text(
        self,
        description: str,
        execute_fn: Callable,
        *,
        api_key: Optional[str] = None,
        controller_kwargs: Optional[Dict[str, Any]] = None,
        peer_bridge: Optional[PeerBridge] = None,
    ) -> ServiceSession:
        """Create a session from unstructured text via LLM."""
        result = self._pipeline.from_text(description, api_key=api_key)
        return self._register(result.landscape, execute_fn,
                              controller_kwargs=controller_kwargs,
                              peer_bridge=peer_bridge)

    def create_from_canon(
        self,
        name: str,
        execute_fn: Callable,
        *,
        controller_kwargs: Optional[Dict[str, Any]] = None,
        peer_bridge: Optional[PeerBridge] = None,
    ) -> ServiceSession:
        """Create a session from a named canon."""
        result = self._pipeline.from_canon(name)
        return self._register(result.landscape, execute_fn,
                              controller_kwargs=controller_kwargs,
                              peer_bridge=peer_bridge)

    def create_from_landscape(
        self,
        landscape: Landscape,
        execute_fn: Callable,
        *,
        controller_kwargs: Optional[Dict[str, Any]] = None,
        peer_bridge: Optional[PeerBridge] = None,
    ) -> ServiceSession:
        """Create a session from an existing Landscape."""
        return self._register(landscape, execute_fn,
                              controller_kwargs=controller_kwargs,
                              peer_bridge=peer_bridge)

    def _register(
        self,
        landscape: Landscape,
        execute_fn: Callable,
        *,
        controller_kwargs: Optional[Dict[str, Any]] = None,
        peer_bridge: Optional[PeerBridge] = None,
    ) -> ServiceSession:
        session = ServiceSession(
            landscape, execute_fn,
            controller_kwargs=controller_kwargs,
            peer_bridge=peer_bridge,
        )
        self._sessions[session.id] = session
        return session

    def get(self, session_id: str) -> Optional[ServiceSession]:
        return self._sessions.get(session_id)

    def remove(self, session_id: str) -> bool:
        return self._sessions.pop(session_id, None) is not None

    def list_sessions(self) -> List[dict]:
        return [
            {
                "session_id": s.id,
                "state": s.state.value,
                "current_position": s.current_position,
                "history_length": len(s.history),
            }
            for s in self._sessions.values()
        ]
