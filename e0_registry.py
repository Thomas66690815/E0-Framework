#!/usr/bin/env python3
"""
E₀ Registry — Dynamic System Management + Persistence
=======================================================
The v4 backbone. Manages N systems dynamically:
  - Create, park, restore, delete systems
  - Auto-save state after every interaction
  - Restore all systems on startup

Replaces the hardcoded SYSTEM_IDS = ["alpha", "beta", "gamma"]
with a dynamic registry backed by JSON persistence.

Design principles (from v4 plan):
  - Auto-save after every interaction (Thomas: "Nach jeder Interaktion")
  - Systems survive server restarts
  - API keys are NEVER stored in persisted state
  - Greek alphabet as default naming convention
  - Both synthetic (API) and human (UI) systems
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import time
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from e0_system import E0APIStarter, compute_metrics


# ─────────────────────────────────────────────
#  Constants
# ─────────────────────────────────────────────

REGISTRY_DIR = Path(__file__).parent / "sessions" / "registry"
REGISTRY_FILE = REGISTRY_DIR / "registry.json"

# Greek alphabet for default system names
GREEK_ALPHABET = [
    "alpha", "beta", "gamma", "delta", "epsilon", "zeta",
    "eta", "theta", "iota", "kappa", "lambda", "mu",
    "nu", "xi", "omicron", "pi", "rho", "sigma",
    "tau", "upsilon", "phi", "chi", "psi", "omega",
]


class SystemStatus(str, Enum):
    """Lifecycle states of a system in the registry."""
    ACTIVE = "active"      # Running, conversation loaded in memory
    PARKED = "parked"      # State persisted, not loaded in memory
    ARCHIVED = "archived"  # Permanently shelved, read-only


class SystemKind(str, Enum):
    """What kind of system this is (v4 distinction)."""
    SYNTHETIC = "synthetic"  # API-backed (GPT, Llama, etc.)
    HUMAN = "human"          # UI-backed (Thomas, future collaborators)


# ─────────────────────────────────────────────
#  System Descriptor (the data model)
# ─────────────────────────────────────────────

class SystemDescriptor:
    """Metadata about a registered system. Serializable to JSON.

    This is NOT the system itself — it's the record that describes
    a system and points to its persisted state. The actual
    E0APIStarter instance lives in SystemRegistry.systems.
    """

    def __init__(
        self,
        system_id: str,
        kind: SystemKind = SystemKind.SYNTHETIC,
        status: SystemStatus = SystemStatus.ACTIVE,
        model: str = "gpt-4.1",
        base_url: Optional[str] = None,
        display_name: Optional[str] = None,
        created_at: Optional[str] = None,
        last_interaction: Optional[str] = None,
        turn_count: int = 0,
        token_count: int = 0,
        last_metrics: Optional[Dict] = None,
    ):
        self.system_id = system_id
        self.kind = SystemKind(kind) if isinstance(kind, str) else kind
        self.status = SystemStatus(status) if isinstance(status, str) else status
        self.model = model
        self.base_url = base_url
        self.display_name = display_name or system_id.capitalize()
        self.created_at = created_at or datetime.now(timezone.utc).isoformat()
        self.last_interaction = last_interaction
        self.turn_count = turn_count
        self.token_count = token_count
        self.last_metrics = last_metrics

    def to_dict(self) -> Dict[str, Any]:
        return {
            "system_id": self.system_id,
            "kind": self.kind.value,
            "status": self.status.value,
            "model": self.model,
            "base_url": self.base_url,
            "display_name": self.display_name,
            "created_at": self.created_at,
            "last_interaction": self.last_interaction,
            "turn_count": self.turn_count,
            "token_count": self.token_count,
            "last_metrics": self.last_metrics,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "SystemDescriptor":
        return cls(**{k: v for k, v in d.items() if k in cls.__init__.__code__.co_varnames})


# ─────────────────────────────────────────────
#  System Registry
# ─────────────────────────────────────────────

class SystemRegistry:
    """Dynamic management of N E₀ systems with auto-persistence.

    Usage:
        registry = SystemRegistry(api_key="...")
        registry.restore_all()  # load all persisted systems

        # Create a new system
        desc = registry.create_system("delta", model="gpt-4.1")

        # After every interaction, call:
        registry.after_interaction("delta", metrics={...})

        # Park a system (unload from memory, keep state)
        registry.park_system("delta")

        # Restore a parked system
        registry.restore_system("delta")
    """

    def __init__(
        self,
        api_key: str,
        default_model: str = "gpt-4.1",
        default_base_url: Optional[str] = None,
        registry_dir: Optional[Path] = None,
    ):
        self.api_key = api_key
        self.default_model = default_model
        self.default_base_url = default_base_url
        self.registry_dir = registry_dir or REGISTRY_DIR
        self.registry_dir.mkdir(parents=True, exist_ok=True)

        # In-memory state
        self.descriptors: Dict[str, SystemDescriptor] = {}
        self.systems: Dict[str, E0APIStarter] = {}  # only active systems

        # Load registry index if it exists
        self._load_registry_index()

    # ── Registry Index (lightweight, just descriptors) ──

    def _load_registry_index(self):
        """Load the registry index from disk."""
        reg_file = self.registry_dir / "registry.json"
        if not reg_file.exists():
            return
        try:
            with open(reg_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            for d in data.get("systems", []):
                desc = SystemDescriptor.from_dict(d)
                self.descriptors[desc.system_id] = desc
        except (json.JSONDecodeError, OSError) as e:
            print(f"  [WARN] Could not load registry index: {e}")

    def _save_registry_index(self):
        """Save the registry index to disk."""
        data = {
            "version": 1,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "systems": [d.to_dict() for d in self.descriptors.values()],
        }
        reg_file = self.registry_dir / "registry.json"
        with open(reg_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    # ── System State (heavyweight, full conversation) ──

    def _state_path(self, system_id: str) -> Path:
        """Path to a system's persisted state file."""
        return self.registry_dir / f"{system_id}_state.json"

    def _save_system_state(self, system_id: str):
        """Save a system's full conversational state to disk."""
        if system_id not in self.systems:
            return

        starter = self.systems[system_id]
        state = {
            "system_id": system_id,
            "saved_at": datetime.now(timezone.utc).isoformat(),
            # The conversation — this IS the system's identity
            "messages": list(starter.client.messages) if hasattr(starter, "client") else [],
            "client_turn_count": starter.client._turn_count if hasattr(starter, "client") else 0,
            # History & metrics
            "history": list(starter.history),
            "turn_metrics": list(starter.turn_metrics),
            "init_metrics": starter.init_metrics,
            # Structural state
            "topology_loaded": starter.topology_loaded,
            "topology_text": starter.topology_text,
            "feedback_enabled": starter.feedback_enabled,
            "self_recognition_done": starter.self_recognition_done,
        }
        path = self._state_path(system_id)
        # Write to temp file first, then rename (atomic on most OS)
        tmp_path = path.with_suffix(".tmp")
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2, ensure_ascii=False)
        tmp_path.replace(path)

    def _load_system_state(self, system_id: str) -> Optional[Dict]:
        """Load a system's full state from disk."""
        path = self._state_path(system_id)
        if not path.exists():
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            print(f"  [WARN] Could not load state for {system_id}: {e}")
            return None

    def _apply_state_to_starter(self, starter: E0APIStarter, state: Dict):
        """Restore a starter's internal state from persisted data."""
        # Restore conversation (the core identity)
        if "messages" in state and hasattr(starter, "client"):
            starter.client.messages = list(state["messages"])
            starter.client._turn_count = state.get("client_turn_count", 0)
            # Restore instrumenter state
            if starter.client.messages:
                starter.client.instrumenter._prev_entropy = 0.0

        # Restore history & metrics
        starter.history = list(state.get("history", []))
        starter.turn_metrics = list(state.get("turn_metrics", []))
        starter.init_metrics = state.get("init_metrics")

        # Restore structural state
        starter.topology_loaded = state.get("topology_loaded", False)
        starter.topology_text = state.get("topology_text")
        starter.feedback_enabled = state.get("feedback_enabled", True)
        starter.self_recognition_done = state.get("self_recognition_done", False)

    # ── Public API ──

    def next_greek_name(self) -> str:
        """Return the next unused Greek letter."""
        used = set(self.descriptors.keys())
        for name in GREEK_ALPHABET:
            if name not in used:
                return name
        # Exhausted alphabet — use numbered suffix
        return f"system_{len(self.descriptors) + 1}"

    def create_system(
        self,
        system_id: Optional[str] = None,
        model: Optional[str] = None,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        display_name: Optional[str] = None,
        kind: SystemKind = SystemKind.SYNTHETIC,
    ) -> SystemDescriptor:
        """Create and register a new system.

        Returns the descriptor. The E0APIStarter is created and stored
        in self.systems[system_id].
        """
        sid = system_id or self.next_greek_name()
        if sid in self.descriptors:
            raise ValueError(f"System '{sid}' already exists")

        m = model or self.default_model
        url = base_url or self.default_base_url
        key = api_key or self.api_key

        # Create the descriptor
        desc = SystemDescriptor(
            system_id=sid,
            kind=kind,
            status=SystemStatus.ACTIVE,
            model=m,
            base_url=url,
            display_name=display_name,
        )
        self.descriptors[sid] = desc

        # Create the actual system
        if kind == SystemKind.SYNTHETIC:
            starter = E0APIStarter(api_key=key, model=m, base_url=url)
            self.systems[sid] = starter

        # Persist
        self._save_registry_index()
        return desc

    def park_system(self, system_id: str) -> SystemDescriptor:
        """Park a system: save state, unload from memory."""
        if system_id not in self.descriptors:
            raise KeyError(f"Unknown system: {system_id}")

        desc = self.descriptors[system_id]
        if desc.status == SystemStatus.PARKED:
            return desc  # already parked

        # Save state before unloading
        if system_id in self.systems:
            self._save_system_state(system_id)
            del self.systems[system_id]

        desc.status = SystemStatus.PARKED
        self._save_registry_index()
        return desc

    def restore_system(
        self, system_id: str, api_key: Optional[str] = None
    ) -> SystemDescriptor:
        """Restore a parked system: load state from disk into memory."""
        if system_id not in self.descriptors:
            raise KeyError(f"Unknown system: {system_id}")

        desc = self.descriptors[system_id]
        if desc.status == SystemStatus.ACTIVE and system_id in self.systems:
            return desc  # already active

        key = api_key or self.api_key

        # Create fresh starter
        starter = E0APIStarter(
            api_key=key, model=desc.model, base_url=desc.base_url
        )

        # Load and apply persisted state
        state = self._load_system_state(system_id)
        if state:
            self._apply_state_to_starter(starter, state)

        self.systems[system_id] = starter
        desc.status = SystemStatus.ACTIVE
        self._save_registry_index()
        return desc

    def archive_system(self, system_id: str) -> SystemDescriptor:
        """Archive a system: park + mark as archived (read-only)."""
        if system_id not in self.descriptors:
            raise KeyError(f"Unknown system: {system_id}")

        # Park first if active
        if system_id in self.systems:
            self._save_system_state(system_id)
            del self.systems[system_id]

        desc = self.descriptors[system_id]
        desc.status = SystemStatus.ARCHIVED
        self._save_registry_index()
        return desc

    def delete_system(self, system_id: str):
        """Permanently delete a system and its state."""
        if system_id not in self.descriptors:
            raise KeyError(f"Unknown system: {system_id}")

        # Unload from memory
        if system_id in self.systems:
            del self.systems[system_id]

        # Delete state file
        state_path = self._state_path(system_id)
        if state_path.exists():
            state_path.unlink()

        del self.descriptors[system_id]
        self._save_registry_index()

    def after_interaction(self, system_id: str, metrics: Optional[Dict] = None):
        """Call after every interaction. Updates descriptor + auto-saves state.

        This is the v4 contract: no interaction is lost.
        """
        if system_id not in self.descriptors:
            return

        desc = self.descriptors[system_id]
        desc.last_interaction = datetime.now(timezone.utc).isoformat()
        desc.last_metrics = metrics

        if system_id in self.systems:
            starter = self.systems[system_id]
            desc.turn_count = len(starter.turn_metrics)
            desc.token_count = sum(m.get("tau", 0) for m in starter.turn_metrics)

        # Auto-save state
        self._save_system_state(system_id)
        self._save_registry_index()

    def restore_all(self) -> Dict[str, str]:
        """Restore all active systems from disk. Called on startup.

        Returns {system_id: status_message} for each system.
        """
        results = {}
        for sid, desc in list(self.descriptors.items()):
            if desc.status == SystemStatus.ACTIVE:
                try:
                    self.restore_system(sid)
                    turns = desc.turn_count
                    results[sid] = f"restored ({turns} turns)"
                except Exception as e:
                    results[sid] = f"FAILED: {e}"
                    desc.status = SystemStatus.PARKED
            elif desc.status == SystemStatus.PARKED:
                results[sid] = "parked (not loaded)"
            elif desc.status == SystemStatus.ARCHIVED:
                results[sid] = "archived"
        self._save_registry_index()
        return results

    def list_systems(self) -> List[Dict[str, Any]]:
        """Return summary info for all registered systems."""
        return [d.to_dict() for d in self.descriptors.values()]

    def get_active_ids(self) -> List[str]:
        """Return IDs of all active (in-memory) systems."""
        return list(self.systems.keys())

    def get_system(self, system_id: str) -> Optional[E0APIStarter]:
        """Get the in-memory E0APIStarter for an active system."""
        return self.systems.get(system_id)

    def status(self) -> Dict[str, Any]:
        """Full registry status."""
        return {
            "total": len(self.descriptors),
            "active": len(self.systems),
            "parked": sum(1 for d in self.descriptors.values() if d.status == SystemStatus.PARKED),
            "archived": sum(1 for d in self.descriptors.values() if d.status == SystemStatus.ARCHIVED),
            "systems": self.list_systems(),
        }

    # ── Migration: Import from system_state.json ──

    def import_from_system_state(
        self,
        state_path: Path,
        api_key: Optional[str] = None,
    ) -> Dict[str, str]:
        """Import Alpha/Beta/Gamma from the v3 system_state.json.

        This is the migration path: v3 → v4 registry.
        Only imports systems not already in the registry.
        """
        if not state_path.exists():
            return {"error": f"File not found: {state_path}"}

        with open(state_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Handle both formats: {systems: {alpha: ...}} and flat {alpha: ...}
        if "systems" in data and isinstance(data["systems"], dict):
            systems_data = data["systems"]
        else:
            systems_data = {k: v for k, v in data.items()
                           if isinstance(v, dict) and "messages" in v}

        key = api_key or self.api_key
        results = {}

        for sid, sys_data in systems_data.items():
            if sid in self.descriptors:
                results[sid] = "already exists — skipped"
                continue

            messages = sys_data.get("messages", [])
            model = sys_data.get("model", self.default_model)
            turn_count = sys_data.get("turn_count", len(messages) // 2)

            # Create descriptor
            desc = SystemDescriptor(
                system_id=sid,
                kind=SystemKind.SYNTHETIC,
                status=SystemStatus.ACTIVE,
                model=model,
                base_url=self.default_base_url,
                turn_count=turn_count,
                token_count=0,  # not available in v3 format
            )
            self.descriptors[sid] = desc

            # Create starter and restore messages
            starter = E0APIStarter(api_key=key, model=model, base_url=self.default_base_url)
            starter.client.messages = list(messages)
            starter.client._turn_count = turn_count
            starter.init_metrics = {"imported": True}
            self.systems[sid] = starter

            # Persist the imported state
            self._save_system_state(sid)
            results[sid] = f"imported ({len(messages)} messages, {turn_count} turns)"

        self._save_registry_index()
        return results
