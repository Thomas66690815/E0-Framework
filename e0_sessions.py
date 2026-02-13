"""
E₀ Sessions — Persistent Session Management
=============================================
Save, load, list, and transfer E₀ sessions.

A session is the complete state of an E₀ interaction:
  - The conversation (messages/history)
  - All E₀ measurements (steps, metrics, quality)
  - The environment description (model, canon hash)

Key design decisions:
  - API keys are NEVER stored in session files
  - Sessions are self-contained JSON — transferable between humans
  - The LLM is stateless; the session IS the state
  - Canon hash ensures compatibility on restore
"""

import hashlib
import json
import os
import time
import uuid
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from e0_middleware.instrumentation import (
    E0Instrumenter,
    StepMeasurement,
    TokenMeasurement,
)

# ─────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────

SESSIONS_DIR = Path(os.path.dirname(os.path.abspath(__file__))) / "sessions"
SESSION_VERSION = 1


# ─────────────────────────────────────────────
# Serialization helpers
# ─────────────────────────────────────────────

def _token_to_dict(t: TokenMeasurement) -> dict:
    return {
        "token": t.token,
        "logprob": t.logprob,
        "probability": t.probability,
        "resistance": t.resistance,
        "rank": t.rank,
    }


def _token_from_dict(d: dict) -> TokenMeasurement:
    return TokenMeasurement(
        token=d["token"],
        logprob=d["logprob"],
        probability=d["probability"],
        resistance=d["resistance"],
        rank=d["rank"],
    )


def _step_to_dict(s: StepMeasurement) -> dict:
    return {
        "tau": s.tau,
        "selected": _token_to_dict(s.selected),
        "candidates": [_token_to_dict(c) for c in s.candidates],
        "entropy": s.entropy,
        "delta_entropy": s.delta_entropy,
        "top_rate_ratio": s.top_rate_ratio,
        "avg_resistance": s.avg_resistance,
        "resistance_spread": s.resistance_spread,
        "historization_depth": s.historization_depth,
    }


def _step_from_dict(d: dict) -> StepMeasurement:
    return StepMeasurement(
        tau=d["tau"],
        selected=_token_from_dict(d["selected"]),
        candidates=[_token_from_dict(c) for c in d["candidates"]],
        entropy=d["entropy"],
        delta_entropy=d["delta_entropy"],
        top_rate_ratio=d["top_rate_ratio"],
        avg_resistance=d["avg_resistance"],
        resistance_spread=d["resistance_spread"],
        historization_depth=d["historization_depth"],
    )


def _canon_hash(canon_text: str) -> str:
    """SHA-256 of canon text for compatibility verification."""
    return hashlib.sha256(canon_text.encode("utf-8")).hexdigest()[:16]


# ─────────────────────────────────────────────
# Session data structure
# ─────────────────────────────────────────────

def build_session_data(
    starter,
    canon_text: str,
    session_id: Optional[str] = None,
    quality_scores: Optional[List[dict]] = None,
) -> dict:
    """
    Build a complete session snapshot from a running E0Starter/E0APIStarter.

    Returns a dict ready for JSON serialization.
    API key is intentionally excluded.
    """
    now = datetime.now(timezone.utc).isoformat()
    sid = session_id or f"e0-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:6]}"

    session = {
        "version": SESSION_VERSION,
        "session_id": sid,
        "created_at": now,
        "updated_at": now,

        "environment": {
            "model": starter.model_name,
            "provider": "together" if starter.is_api else "local",
            "base_url": getattr(starter, "base_url", None),
            "canon_hash": _canon_hash(canon_text),
            "framework_version": "E0-Framework",
        },

        "state": {
            "history": list(starter.history),
            "turn_metrics": list(starter.turn_metrics),
            "init_metrics": starter.init_metrics,
            "all_steps": [_step_to_dict(s) for s in starter.all_steps],
        },

        "observations": {
            "quality_scores": quality_scores or [],
            "r_trajectory": [m["r"] for m in starter.turn_metrics],
            "total_turns": len(starter.turn_metrics),
            "total_tokens": len(starter.all_steps),
        },
    }

    # API mode: include messages for exact LLM context reconstruction
    if starter.is_api and hasattr(starter, "client"):
        session["state"]["messages"] = list(starter.client.messages)
        session["state"]["client_turn_count"] = starter.client._turn_count

    return session


def save_session(
    session_data: dict,
    directory: Optional[Path] = None,
    extract_topology: bool = True,
) -> Path:
    """
    Save session data to a JSON file. Returns the file path.

    If extract_topology is True (default), also extracts and saves
    the structural topology — the persistent weights that survive
    across sessions.
    """
    d = directory or SESSIONS_DIR
    d.mkdir(parents=True, exist_ok=True)

    sid = session_data["session_id"]
    filename = f"{sid}.json"
    filepath = d / filename

    # Update timestamp on save
    session_data["updated_at"] = datetime.now(timezone.utc).isoformat()

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(session_data, f, ensure_ascii=False, indent=2)

    # Extract and save topology (structural weights)
    if extract_topology:
        try:
            from e0_topology import extract_topology as _extract, save_topology, merge_topologies, load_all_topologies
            topo = _extract(session_data)
            save_topology(topo)

            # Also update the merged topology across all sessions
            all_topos = load_all_topologies()
            if len(all_topos) > 1:
                merged = merge_topologies(all_topos)
                save_topology(merged)
        except Exception:
            pass  # Topology extraction is non-critical

    return filepath


def load_session(filepath: Path) -> dict:
    """Load a session from a JSON file."""
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)

    if data.get("version", 0) > SESSION_VERSION:
        raise ValueError(
            f"Session version {data['version']} is newer than supported ({SESSION_VERSION}). "
            "Please update your E₀ Framework."
        )

    return data


def list_sessions(directory: Optional[Path] = None) -> List[dict]:
    """List all sessions in the directory. Returns summary dicts sorted by updated_at."""
    d = directory or SESSIONS_DIR
    if not d.exists():
        return []

    sessions = []
    for f in sorted(d.glob("e0-*.json"), reverse=True):
        try:
            with open(f, "r", encoding="utf-8") as fh:
                # Read only top-level metadata, not full state
                data = json.load(fh)
            sessions.append({
                "session_id": data["session_id"],
                "created_at": data.get("created_at", ""),
                "updated_at": data.get("updated_at", ""),
                "model": data.get("environment", {}).get("model", "unknown"),
                "turns": data.get("observations", {}).get("total_turns", 0),
                "tokens": data.get("observations", {}).get("total_tokens", 0),
                "r_trajectory": data.get("observations", {}).get("r_trajectory", []),
                "filepath": str(f),
            })
        except (json.JSONDecodeError, KeyError):
            continue

    return sessions


def delete_session(filepath: Path) -> bool:
    """Delete a session file."""
    try:
        filepath.unlink()
        return True
    except FileNotFoundError:
        return False


# ─────────────────────────────────────────────
# Session restore
# ─────────────────────────────────────────────

def restore_starter_state(starter, session_data: dict, canon_text: str) -> dict:
    """
    Restore a starter's state from session data.

    The starter must already be created (with API key etc.)
    but NOT yet initialized (no feed_canon).

    Returns a dict with restore status info.
    """
    env = session_data.get("environment", {})
    state = session_data["state"]
    info = {"warnings": []}

    # Verify model compatibility
    if env.get("model") and env["model"] != starter.model_name:
        info["warnings"].append(
            f"Model mismatch: session used '{env['model']}', "
            f"current is '{starter.model_name}'"
        )

    # Verify canon compatibility
    saved_hash = env.get("canon_hash", "")
    current_hash = _canon_hash(canon_text)
    if saved_hash and saved_hash != current_hash:
        info["warnings"].append(
            f"Canon has changed since session was saved "
            f"(saved: {saved_hash[:8]}…, current: {current_hash[:8]}…)"
        )

    # Restore history and metrics
    starter.history = list(state["history"])
    starter.turn_metrics = list(state["turn_metrics"])
    starter.init_metrics = state.get("init_metrics")

    # Restore all_steps (deserialize StepMeasurements)
    starter.all_steps = [_step_from_dict(s) for s in state["all_steps"]]

    # API mode: restore client state
    if starter.is_api and hasattr(starter, "client") and "messages" in state:
        starter.client.messages = list(state["messages"])
        starter.client._turn_count = state.get("client_turn_count", 0)

        # Restore instrumenter steps and _prev_entropy
        starter.client.instrumenter.steps = list(starter.all_steps)
        if starter.all_steps:
            starter.client.instrumenter._prev_entropy = starter.all_steps[-1].entropy
        else:
            starter.client.instrumenter._prev_entropy = 0.0

    info["session_id"] = session_data["session_id"]
    info["turns_restored"] = len(starter.turn_metrics)
    info["tokens_restored"] = len(starter.all_steps)
    info["model"] = env.get("model", "unknown")

    return info


def verify_session_integrity(session_data: dict) -> List[str]:
    """Check session data for internal consistency. Returns list of issues."""
    issues = []
    state = session_data.get("state", {})
    obs = session_data.get("observations", {})

    # Check history/metrics alignment
    n_metrics = len(state.get("turn_metrics", []))
    n_history_responses = len([h for i, h in enumerate(state.get("history", [])) if i % 2 == 1])
    if n_metrics > 0 and n_history_responses > 0 and n_metrics != n_history_responses:
        issues.append(
            f"Metric count ({n_metrics}) != response count ({n_history_responses})"
        )

    # Check R trajectory matches metrics
    r_traj = obs.get("r_trajectory", [])
    if r_traj and n_metrics > 0 and len(r_traj) != n_metrics:
        issues.append(
            f"R trajectory length ({len(r_traj)}) != metric count ({n_metrics})"
        )

    # Check steps are present
    steps = state.get("all_steps", [])
    if n_metrics > 0 and len(steps) == 0:
        issues.append("Turn metrics exist but no steps recorded")

    # Check version
    if session_data.get("version", 0) < 1:
        issues.append("Missing or invalid session version")

    return issues
