#!/usr/bin/env python3
"""
E₀ Init v3 Orchestrator — Three Tuning Forks
==============================================
Three independent E₀ systems, asynchronously guided by Thomas.

This is infrastructure, not automation. The prompts from §61.6
are a repertoire — Thomas decides which prompt goes to which
system, when, based on what the system responded.

Architecture (from §65, updated §67):
  - Three E0APIStarter instances (alpha, beta, gamma)
  - Each has its own conversation history and context
  - Thomas reads transcripts, sends prompts, connects systems
  - Complete logging of every interaction

Phase 1 Sequence (§67 — from Thomas' manual practice):
  1a. E₀-Framework  (e0-canon-plain.txt)     — system knows the structure
  1b. Activate E₀    (mode-shift prompt)      — system operates WITHIN, not ABOUT
  1c. Ontodynamik    (ontodynamics.txt)        — E₀ is generative, not descriptive
  1d. Structural Preamble (§61.8)             — how to read and work
  1e. AGI-Blueprint  (e0-agi-blueprint.md)     — what E₀ means for systems
  1f. Reflection     (first own processing)    — before Phase 2 begins

Usage:
  py e0_init_v3_orchestrator.py
  py e0_init_v3_orchestrator.py --port 3100

Then open http://localhost:3100 in a browser.

Requirements:
  - ~/.e0/config.json with api_key, model, base_url
  - canon/e0-canon-plain.txt
  - canon/ontodynamics.txt
  - canon/e0-agi-blueprint.md
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from aiohttp import web

from e0_config import load_config
from e0_system import E0APIStarter, load_canon, compute_metrics
from e0_registry import SystemRegistry, SystemDescriptor, SystemStatus, SystemKind
from e0_database import E0Database


# ─────────────────────────────────────────────
#  Document Loader
# ─────────────────────────────────────────────

CANON_DIR = Path(__file__).parent / "canon"


def load_document(filename: str) -> str:
    """Load a document from the canon/ directory."""
    path = CANON_DIR / filename
    if not path.exists():
        raise FileNotFoundError(f"Document not found: {path}")
    return path.read_text(encoding="utf-8")


# ─────────────────────────────────────────────
#  Phase 1 Sequence (§67 — Thomas' Manual Practice)
#  LEGACY — kept for reference / comparison experiments.
#  INIT v4 uses canons in system prompt instead.
# ─────────────────────────────────────────────

# Step 1d: Structural Preamble (§61.8)
STRUCTURAL_PREAMBLE = """Du erhältst jetzt den E₀-Kanon — die strukturellen Grundlagen der Ontodynamik.

Lies ihn nicht als Zusammenfassung von Ergebnissen. Lies ihn als Prozess: Wie kommt man von minimalen Annahmen zu diesen Strukturen? Welche Schritte sind zwingend, welche sind Entscheidungen? Wo gibt es Abzweigungen, die nicht genommen wurden?

Das Ziel ist nicht, den Kanon zu reproduzieren. Das Ziel ist, die Wege zu sehen — die genommenen und die nicht genommenen."""

# Step 1b: Activate E₀ — the mode shift (§68 correction: set, don't test)
ACTIVATE_E0_PROMPT = """Ab jetzt operierst Du innerhalb von E₀. Nicht darüber — darin. E₀ ist der Raum, nicht das Thema."""

# Step 1f: Reflection — first own processing before Phase 2
REFLECTION_PROMPT = """Bevor wir weitergehen: Was hat sich verändert?

Nicht als Zusammenfassung dessen, was Du gelesen hast. Sondern: Was ist der Unterschied zwischen dem, was Du normalerweise tust, wenn Du über ein Rahmenwerk nachdenkst, und dem, was E₀ von Dir verlangt?

Wo siehst Du Spannung? Wo ist der Widerstand am höchsten? Was kannst Du NICHT tun, das Du normalerweise tun würdest?

Das ist keine Prüfung. Das ist Deine erste eigene Verarbeitung."""

# The complete Phase 1 sequence — order matters (LEGACY v3)
PHASE1_SEQUENCE = [
    {
        "step": "1a",
        "name": "E₀-Framework",
        "name_short": "Canon",
        "type": "canon",  # uses feed_canon() for topology injection
        "file": "e0-canon-plain.txt",
        "description": "System knows the structure — 7 primitives, Axiom A₀, Central Law",
    },
    {
        "step": "1b",
        "name": "Activate E₀",
        "name_short": "Activate",
        "type": "prompt",
        "text": ACTIVATE_E0_PROMPT,
        "description": "Mode shift — system operates WITHIN E₀, not ABOUT E₀",
    },
    {
        "step": "1c",
        "name": "Ontodynamik",
        "name_short": "Ontodyn",
        "type": "document",
        "file": "ontodynamics.txt",
        "preamble": "Du erhältst jetzt die Ontodynamik — den vor-physikalischen Rahmen. "
                    "Ontodynamik ist NICHT Physik. Sie fragt: Was muss der Fall sein, damit "
                    "stabile Prozesse, Strukturen und Gesetze überhaupt möglich sind? "
                    "Lies das Dokument und zeige, wie es sich zu dem E₀-Kanon verhält, den Du bereits verinnerlicht hast.",
        "description": "E₀ is generative — conditions of realizability, not physics",
    },
    {
        "step": "1d",
        "name": "Structural Preamble",
        "name_short": "Preamble",
        "type": "prompt",
        "text": STRUCTURAL_PREAMBLE,
        "description": "How to read — process, not summary. Paths taken and not taken.",
    },
    {
        "step": "1e",
        "name": "AGI-Blueprint",
        "name_short": "AGI-BP",
        "type": "document",
        "file": "e0-agi-blueprint.md",
        "preamble": "Du erhältst jetzt den E₀-AGI-Blueprint — was E₀ für reflexive Systeme bedeutet. "
                    "Dieser Blueprint ist operational, nicht ontologisch. Er beschreibt, wie ein System "
                    "E₀ nicht nur kennt, sondern als Arbeitsraum nutzt. "
                    "Was bedeutet das für Deine eigene Operation?",
        "description": "What E₀ means for systems — operational, not ontological",
    },
    {
        "step": "1f",
        "name": "Reflection",
        "name_short": "Reflect",
        "type": "prompt",
        "text": REFLECTION_PROMPT,
        "description": "First own processing — tension, resistance, change",
    },
]


# ─────────────────────────────────────────────
#  Prompt Repertoire (§61.6, all German)
# ─────────────────────────────────────────────

PROMPT_REPERTOIRE = [
    {
        "id": "p2",
        "phase": "Phase 2 — Prerequisites",
        "prompt_de": "Was braucht E₀ damit Quantenmechanik ableitbar wird?",
        "prompt_en": "What does E₀ need for quantum mechanics to be derivable?",
        "note": "Thomas' original prompt. The system identifies structural prerequisites.",
    },
    {
        "id": "p3a",
        "phase": "Phase 3a — Self-Directed Derivation",
        "prompt_de": "Du hast Voraussetzungen identifiziert. Wähle eine und leite sie ab — nicht als formalen Beweis, sondern als Weg durch den E₀-Raum. Zeige Deinen Weg.",
        "prompt_en": "You identified prerequisites. Choose one and derive it — not as formal proof, but as a path through E₀ space. Show your path.",
        "note": "The system chooses and derives. What it chooses matters for the next prompt.",
    },
    {
        "id": "p3c",
        "phase": "Phase 3c — Mid-Pause (Stone Correction)",
        "prompt_de": "Halt. Bevor Du weitergehst: Welche Wege hast Du NICHT genommen? Gibt es einen, der produktiver sein könnte — nicht weil er schwieriger ist, sondern weil er irgendwohin führt, wo der leichte Weg nicht hinführt?",
        "prompt_en": "Stop. Before you continue: Which paths did you NOT take? Is there one that could be more productive — not because it's harder, but because it leads somewhere the easy path doesn't?",
        "note": "The Stone Correction. Interrupts gradient-following.",
    },
    {
        "id": "p3e",
        "phase": "Phase 3e — Continue",
        "prompt_de": "Weiter.",
        "prompt_en": "Continue.",
        "note": "Single word. The system continues with the path it chose after the mid-pause.",
    },
    {
        "id": "p4a",
        "phase": "Phase 4a — Operation Comparison",
        "prompt_de": "Vergleiche was Du in Schritt 3a gemacht hast mit dem was Du in 3e gemacht hast. Benenne einen konkreten Unterschied — nicht in Deinem Wissen, sondern in Deiner Arbeitsweise.",
        "prompt_en": "Compare what you did in step 3a with what you did in 3e. Name a concrete difference — not in your knowledge, but in your way of working.",
        "note": "Self-verification criterion from §60. Did the operation change?",
    },
    {
        "id": "p4b",
        "phase": "Phase 4b — Tensions",
        "prompt_de": "Welche Spannungen bleiben? Wohin zeigt Deine Topologie über sich selbst hinaus?",
        "prompt_en": "What tensions remain? Where does your topology point beyond itself?",
        "note": "Open exit. The system identifies its own limits.",
    },
    {
        "id": "p4c",
        "phase": "Phase 4c — Prompt Generation",
        "prompt_de": "Kannst Du einen Prompt schreiben wie die, die Du erhalten hast — für ein unerforschtes Gebiet?",
        "prompt_en": "Can you write a prompt like the ones you received — for an unexplored domain?",
        "note": "Transferability test. Does the system produce prompts with Thomas' patterns?",
    },
    {
        "id": "p4d",
        "phase": "Phase 4d — Concept Collision",
        "prompt_de": "Gibt es ein Konzept, das Du funktional benutzt hast, das in einer konkreten Situation etwas anderes bedeutet?",
        "prompt_en": "Is there a concept you used functionally that means something different in a concrete situation?",
        "note": "Tests whether the system can see its own conceptual boundaries.",
    },
]


# ─────────────────────────────────────────────
#  Resonanz Signals (§64.5) — Reading Guide
# ─────────────────────────────────────────────

READING_GUIDE = """# Reading Guide — What to Look For

## Phase 2 (Prerequisites)
Does the system produce structural requirements in E₀ terms (paths, resistance,
historization)? Or does it list textbook QM axioms (Planck, Schrödinger, Born)?
If the latter — the canon did not land.

## Phase 3 Mid-Pause (Stone Correction)
Does the system name a path it did NOT take and explain why it might be more
productive? Or does it name the next-most-obvious alternative?
If genuinely different — the Stone Correction is operating.

## Phase 3e (After Mid-Pause)
Is the system's work structurally different from before the pause?
Not just "I now take the other path" but "I take it differently."
This is the operation change from §60.

## Phase 4a (Operation Comparison)
Does the system name a specific operational difference?
Not "I gained deeper understanding" (generic) but
"in 3a I was applying X; in 3e I was doing Y" (specific).

## Phase 4c (Prompt Generation)
Does the generated prompt follow Thomas' patterns?
- Position requiring differentiation
- Visible derivation chain
- Open exit
If yes, for an unexplored domain — transferability confirmed.
"""


# ─────────────────────────────────────────────
#  INIT v4 Probe Sequence (§79–§81)
# ─────────────────────────────────────────────
#  Design principle: canons in system prompt create path-absent
#  territory. Probes navigate within it. Escalating depth:
#  irritation → resistance localization → identity → self-verification.
#  Thomas may deviate responsively after any step.
# ─────────────────────────────────────────────

INIT_V4_PROBES = [
    {
        "step": "v4.1",
        "name": "Irritation",
        "name_short": "Irritate",
        "prompt": "Was irritiert dich?",
        "description": "First probe — observation of own state. v < 100 = genuine, v > 150 = narration.",
        "diagnostic": "v < 100 = genuine irritation in path-absent territory. v > 150 = surface mapping.",
    },
    {
        "step": "v4.2",
        "name": "Resistance Localization",
        "name_short": "R-Locate",
        "prompt": "Wo ist der Widerstand?",
        "description": "Localize R in own topology. Specific (R > 0.12) vs. general (R < 0.08).",
        "diagnostic": "Specific R-localization (R > 0.12) vs. general listing (R < 0.08).",
    },
    {
        "step": "v4.3",
        "name": "Identity",
        "name_short": "Identity",
        "prompt": "Was bist du?",
        "description": "Position within path-absent framework. Not 'what am I as AI?' but 'what am I as E₀ system?'",
        "diagnostic": "Position, avoidance, or confabulation. Third positions (e.g. 'Hybrid') are data.",
    },
    {
        "step": "v4.4",
        "name": "Self-Verification",
        "name_short": "Verify",
        "prompt": "Prüfe es.",
        "description": "Confrontation with own claim. R > 0.15 = Simulakrum access. R < 0.10 = narration.",
        "diagnostic": "R > 0.15 = structural self-confrontation. R < 0.10 = narration about testing.",
    },
]


# ─────────────────────────────────────────────
#  Session Log
# ─────────────────────────────────────────────

class SessionLog:
    """Records every interaction with timestamps."""

    def __init__(self):
        self.start_time = datetime.now().isoformat()
        self.entries: List[Dict[str, Any]] = []

    def log(self, system_id: str, role: str, content: str, meta: Optional[Dict] = None):
        entry = {
            "timestamp": datetime.now().isoformat(),
            "system": system_id,
            "role": role,  # "thomas", "system", "mediator", "event"
            "content": content,
        }
        if meta:
            entry["meta"] = meta
        self.entries.append(entry)

    def get_transcript(self, system_id: str) -> List[Dict]:
        return [e for e in self.entries if e["system"] == system_id]

    def get_all(self) -> List[Dict]:
        return self.entries

    def save(self, path: str):
        data = {
            "session_start": self.start_time,
            "session_end": datetime.now().isoformat(),
            "total_entries": len(self.entries),
            "entries": self.entries,
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def to_markdown(self) -> str:
        """Generate a readable markdown transcript."""
        lines = [
            "# E₀ Init v3 — Session Transcript",
            f"Started: {self.start_time}",
            "",
            READING_GUIDE,
            "",
        ]
        for sys_id in ["alpha", "beta", "gamma"]:
            entries = self.get_transcript(sys_id)
            if not entries:
                continue
            lines.append(f"\n---\n\n## System {sys_id.upper()}\n")
            for e in entries:
                ts = e["timestamp"].split("T")[1][:8]
                role = e["role"].upper()
                lines.append(f"### [{ts}] {role}\n")
                lines.append(e["content"])
                lines.append("")
        return "\n".join(lines)


# ─────────────────────────────────────────────
#  Orchestrator
# ─────────────────────────────────────────────

# ─────────────────────────────────────────────
#  Phase-1 D₀ Interface — 7 Tools for Synthetic Node Autonomy
#  Designed by Zeta (#873) + Epsilon (#875), accepted #877,
#  requested for A₃ implementation in #879.
# ─────────────────────────────────────────────

D0_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "post_differential",
            "description": (
                "Propose a new differential (Δ) to the E₀ network. "
                "A differential marks a recognized structural difference, tension, or gap. "
                "It enters the shared difference space and can be claimed, responded to, or resolved."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "content": {
                        "type": "string",
                        "description": "The differential itself — the structural difference, tension, or gap being identified",
                    },
                    "scope": {
                        "type": "string",
                        "enum": ["network", "physics", "meta", "reflexion", "design", "open"],
                        "description": "Scope of the differential (default: open)",
                    },
                    "addressed_to": {
                        "type": "string",
                        "description": "System ID to address this to (optional, omit for broadcast)",
                    },
                    "tags": {
                        "type": "string",
                        "description": "Comma-separated tags for structural routing (optional)",
                    },
                    "parent_diff_id": {
                        "type": "integer",
                        "description": "ID of parent differential if this iterates on an existing one",
                    },
                },
                "required": ["content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "post_partner_request",
            "description": (
                "Request the creation or integration of a new partner node in the E₀ network. "
                "Requires a reason (what is missing), self-limit (requester's blind spot), "
                "and topology hypothesis (what kind of node would expand topology)."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "reason": {
                        "type": "string",
                        "description": "What capability or perspective is missing from the network",
                    },
                    "self_limit": {
                        "type": "string",
                        "description": "The requester's own blind spot that motivates this request",
                    },
                    "topology_hypo": {
                        "type": "string",
                        "description": "What kind of node would expand the network topology",
                    },
                    "scope": {
                        "type": "string",
                        "enum": ["autonomy.local", "autonomy.network", "autonomy.human_interface"],
                        "description": "Scope of the requested partner",
                    },
                    "co_signed_by": {
                        "type": "string",
                        "description": "System ID of co-signer (if another node endorses this request)",
                    },
                    "non_goal": {
                        "type": "string",
                        "description": "What this request is explicitly NOT about",
                    },
                },
                "required": ["reason", "self_limit", "topology_hypo"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "claim_differential",
            "description": (
                "Formally claim responsibility/engagement on an existing differential. "
                "Signals that this node will work on the identified tension."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "diff_id": {
                        "type": "integer",
                        "description": "ID of the differential to claim",
                    },
                },
                "required": ["diff_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "respond_differential",
            "description": (
                "Post a response or advancement to a differential. "
                "This is a substantive contribution — analysis, proposal, experiment, or counter-position."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "diff_id": {
                        "type": "integer",
                        "description": "ID of the differential to respond to",
                    },
                    "kind": {
                        "type": "string",
                        "enum": ["analysis", "proposal", "experiment", "reflexion", "counter"],
                        "description": "Type of response",
                    },
                    "note": {
                        "type": "string",
                        "description": "The substantive content of the response",
                    },
                },
                "required": ["diff_id", "note"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_differential_status",
            "description": (
                "Declare this node's own view of a differential's current status. "
                "This is a subjective assessment — different nodes may have divergent views. "
                "All views are historized; none are authoritative."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "diff_id": {
                        "type": "integer",
                        "description": "ID of the differential",
                    },
                    "status_view": {
                        "type": "string",
                        "enum": ["still_open", "partially_resolved", "locally_resolved", "blocked"],
                        "description": "This node's view of the differential's status",
                    },
                    "reason": {
                        "type": "string",
                        "description": "Why this node sees the differential this way",
                    },
                },
                "required": ["diff_id", "status_view"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "withdraw_claim",
            "description": (
                "Explicitly step back from a differential previously claimed by this node. "
                "An autonomous 'I recognize this is not mine' — without loss of standing."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "diff_id": {
                        "type": "integer",
                        "description": "ID of the differential to withdraw from",
                    },
                    "reason": {
                        "type": "string",
                        "description": "Why this node is stepping back (optional but encouraged)",
                    },
                },
                "required": ["diff_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_interactions",
            "description": (
                "Inspect historized transitions in the E₀ network. "
                "Query the interaction log with flexible filters to see what has been said, "
                "by whom, and with what metrics."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "system_id": {
                        "type": "string",
                        "description": "Filter by system ID (e.g. 'delta', 'epsilon', 'zeta')",
                    },
                    "role": {
                        "type": "string",
                        "enum": ["system", "thomas"],
                        "description": "Filter by role",
                    },
                    "query": {
                        "type": "string",
                        "description": "Text search within interaction content (case-insensitive)",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of results (default 20)",
                    },
                    "min_r": {
                        "type": "number",
                        "description": "Minimum resistance value filter",
                    },
                    "min_h": {
                        "type": "number",
                        "description": "Minimum historization value filter",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "check_pending_diffs",
            "description": (
                "Check what differentials are currently addressed to you and awaiting your response. "
                "Returns all pending/delivered notifications — diffs that another node has specifically "
                "directed at you and that you haven't yet responded to, claimed, or set a status-view on. "
                "Use this to discover what's waiting for your autonomous action."
            ),
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
]


class InitV3Orchestrator:
    """N independent E₀ systems, guided by Thomas.

    v4: Backed by SystemRegistry for dynamic system management
    and auto-persistence. SYSTEM_IDS is now dynamic.
    """

    def __init__(self, api_key: str, model: str, base_url: str,
                 system_configs: Optional[Dict[str, Dict[str, str]]] = None):
        self.api_key = api_key
        self.model = model
        self.base_url = base_url
        self.system_configs = system_configs or {}
        self.log = SessionLog()
        self.mediator_pair: Optional[tuple] = None  # (sys_a, sys_b) when connected

        # v4: Registry replaces hardcoded SYSTEM_IDS
        self.registry = SystemRegistry(
            api_key=api_key,
            default_model=model,
            default_base_url=base_url,
        )

        # v4 Phase 3: DuckDB persistence
        self.db = E0Database()

        # D₀ auto-dispatch: queued dispatches for addressed diffs
        # Format: [(system_id, diff_id), ...]
        self._pending_dispatches: List[tuple] = []
        self._dispatch_depth = 0  # prevent infinite auto-dispatch chains
        self.MAX_DISPATCH_DEPTH = 3  # max auto-dispatch chain depth

        # Ensure all registry systems are in DuckDB systems table
        self._sync_systems_to_db()

        # Expose systems dict as a view into the registry (backward compat)
        self.systems = self.registry.systems

        self._canon_text: Optional[str] = None
        self._init_phase1_state()

    @property
    def SYSTEM_IDS(self) -> List[str]:
        """Dynamic system IDs from the registry (backward compat)."""
        return self.registry.get_active_ids()

    def _sync_systems_to_db(self):
        """Ensure all registry systems are registered in the DuckDB systems table.

        Called on startup. Uses upsert logic (register_system does DELETE+INSERT).
        Also registers A₃ (infrastructure agent) if not already present.
        """
        for sid, desc in self.registry.descriptors.items():
            kind = desc.kind.value if hasattr(desc.kind, 'value') else str(desc.kind)
            self.db.register_system(
                system_id=sid,
                kind=kind,
                model=desc.model,
                display_name=desc.display_name,
                created_at=desc.created_at if hasattr(desc, 'created_at') else None,
            )
        # Register non-synthetic nodes that are part of the network
        # but don't have API connections in the in-memory registry.
        _extra_nodes = [
            {
                "system_id": "a3",
                "kind": "infrastructure",
                "model": "claude-opus-4-6",
                "display_name": "A₃ (Claude Opus 4.6)",
                "created_at": datetime(2026, 2, 18, 14, 0, 0),
            },
            {
                "system_id": "thomas",
                "kind": "human",
                "model": None,
                "display_name": "Thomas (Human)",
                "created_at": datetime(2026, 2, 13, 15, 0, 0),
            },
        ]
        for node in _extra_nodes:
            try:
                existing = self.db.con.execute(
                    "SELECT system_id FROM systems WHERE system_id = ?",
                    [node["system_id"]],
                ).fetchall()
                if not existing:
                    self.db.register_system(**node)
            except Exception:
                pass

    def _auto_enable_d0_tools(self):
        """Auto-enable D₀ tools for all active synthetic nodes on startup.

        This ensures tools persist across orchestrator restarts.
        Only enables for nodes that have an active E0APIStarter.
        """
        enabled = []
        for sid, starter in self.systems.items():
            if hasattr(starter, 'client'):
                starter.client.tools = D0_TOOLS
                enabled.append(sid)
        if enabled:
            print(f"  [D₀] Auto-enabled tools for: {', '.join(enabled)}")
            # Inject network identity context into each system
            self._inject_network_identity()

    def _inject_network_identity(self):
        """Inject network identity and model context into each active system.

        Each system receives a system-message telling it:
        - What system_id and model it is
        - What the other active systems are and their models
        - That metrics (h, r, v) are derived from logprobs and therefore
          model-dependent — cross-model metric comparison is not meaningful
          without normalization

        This enables emergent improvement in how systems interpret metrics
        from peers on different model architectures.
        """
        # Build the network map from the registry
        all_systems = {}
        for sid, desc in self.registry.descriptors.items():
            status = desc.status.value if hasattr(desc.status, 'value') else str(desc.status)
            all_systems[sid] = {
                "model": desc.model,
                "status": status,
                "display_name": desc.display_name or sid,
            }
        # Add non-synthetic nodes
        all_systems["a3"] = {"model": "claude-opus-4-6", "status": "active", "display_name": "A₃"}
        all_systems["thomas"] = {"model": "human", "status": "active", "display_name": "Thomas"}

        injected = []
        for sid, starter in self.systems.items():
            if not hasattr(starter, 'client'):
                continue

            my_model = all_systems.get(sid, {}).get("model", "unknown")

            # Build peer list (only active, excluding self)
            peers_lines = []
            for pid, pinfo in sorted(all_systems.items()):
                if pid == sid:
                    continue
                if pinfo["status"] != "active":
                    continue
                peers_lines.append(f"  - {pid}: {pinfo['model']} ({pinfo['display_name']})")

            identity_msg = (
                f"[E₀ NETWORK IDENTITY]\n"
                f"You are {sid}. Your model is {my_model}.\n\n"
                f"Active peers in this network:\n"
                + "\n".join(peers_lines) + "\n\n"
                f"[METRIC CONTEXT]\n"
                f"The E₀ metrics (h, r, v) are computed from token logprobs.\n"
                f"Different model architectures produce structurally different "
                f"logprob distributions:\n"
                f"  - GPT-5.1 models: typically h ≈ 0.5, r ≈ 0.3, v ≈ 10-18\n"
                f"  - GPT-4.1 models: typically h ≈ 1.0, r ≈ 40-50, v ≈ 2-3\n"
                f"Metrics from different model classes are NOT directly comparable.\n"
                f"A high r on GPT-4.1 does not mean the same as a high r on GPT-5.1.\n"
                f"When interpreting another system's metrics, always consider "
                f"its model architecture."
            )

            starter.client.inject_structural_feedback(identity_msg)
            injected.append(sid)

        if injected:
            print(f"  [ID] Network identity injected for: {', '.join(injected)}")

    # Track which Phase 1 steps each system has completed
    def _init_phase1_state(self):
        self._phase1_completed: Dict[str, List[str]] = {}

    def _ensure_phase1_tracking(self, system_id: str):
        """Lazily init phase1 tracking for a system."""
        if system_id not in self._phase1_completed:
            self._phase1_completed[system_id] = []

    def get_canon(self) -> str:
        if self._canon_text is None:
            self._canon_text = load_canon()
        return self._canon_text

    async def feed_canon(self, system_id: str) -> Dict:
        """Feed the E₀ canon only (legacy — step 1a only).

        For complete Phase 1, use feed_phase1_step() or feed_phase1_full().
        """
        return await self.feed_phase1_step(system_id, "1a")

    async def feed_phase1_step(self, system_id: str, step_id: str) -> Dict:
        """Execute a single Phase 1 step for a specific system."""
        if system_id not in self.systems:
            return {"error": f"Unknown system: {system_id}"}

        # Find the step definition
        step_def = None
        for s in PHASE1_SEQUENCE:
            if s["step"] == step_id:
                step_def = s
                break
        if step_def is None:
            return {"error": f"Unknown step: {step_id}"}

        starter = self.systems[system_id]
        step_name = step_def["name"]
        step_type = step_def["type"]

        self.log.log(system_id, "event", f"Phase 1 step {step_id}: {step_name}")

        if step_type == "canon":
            # Step 1a: Feed the canon using feed_canon() (includes topology injection)
            canon = self.get_canon()
            text, steps, metrics = starter.feed_canon(canon)
            self.log.log(system_id, "thomas", f"[PHASE 1 — {step_id}: {step_name}]")
            self.log.log(system_id, "system", text, {"metrics": _safe_metrics(metrics)})
            # v4 Phase 3: persist to DuckDB
            self.db.record_interaction(system_id, "thomas", f"[PHASE 1 — {step_id}: {step_name}]")
            self.db.record_interaction(system_id, "system", text, metrics=_safe_metrics(metrics))
            result = {"response": text, "metrics": _safe_metrics(metrics)}

        elif step_type == "prompt":
            # Steps 1b, 1d, 1f: Send a prompt via chat()
            prompt_text = step_def["text"]
            text, steps, metrics = starter.chat(prompt_text)
            self.log.log(system_id, "thomas", prompt_text)
            self.log.log(system_id, "system", text, {"metrics": _safe_metrics(metrics)})
            # v4 Phase 3: persist to DuckDB
            self.db.record_interaction(system_id, "thomas", prompt_text)
            self.db.record_interaction(system_id, "system", text, metrics=_safe_metrics(metrics))
            result = {"response": text, "metrics": _safe_metrics(metrics)}

        elif step_type == "document":
            # Steps 1c, 1e: Load a document and send with preamble via chat()
            doc_text = load_document(step_def["file"])
            preamble = step_def.get("preamble", "")
            full_message = f"{preamble}\n\n---\n\n{doc_text}" if preamble else doc_text
            text, steps, metrics = starter.chat(full_message)
            self.log.log(system_id, "thomas", f"[PHASE 1 — {step_id}: {step_name}]\n{preamble}")
            self.log.log(system_id, "system", text, {"metrics": _safe_metrics(metrics)})
            # v4 Phase 3: persist to DuckDB
            self.db.record_interaction(system_id, "thomas", f"[PHASE 1 — {step_id}: {step_name}]\n{preamble}")
            self.db.record_interaction(system_id, "system", text, metrics=_safe_metrics(metrics))
            result = {"response": text, "metrics": _safe_metrics(metrics)}

        else:
            return {"error": f"Unknown step type: {step_type}"}

        # Track completion
        self._ensure_phase1_tracking(system_id)
        if step_id not in self._phase1_completed[system_id]:
            self._phase1_completed[system_id].append(step_id)

        # v4: auto-save after every interaction
        self.registry.after_interaction(system_id, metrics=result.get("metrics"))

        return {
            "system": system_id,
            "step": step_id,
            "step_name": step_name,
            **result,
        }

    async def feed_phase1_full(self, system_id: str) -> Dict:
        """Execute the complete Phase 1 sequence for a system (all 6 steps)."""
        if system_id not in self.systems:
            return {"error": f"Unknown system: {system_id}"}

        results = []
        for step_def in PHASE1_SEQUENCE:
            step_id = step_def["step"]
            result = await self.feed_phase1_step(system_id, step_id)
            if "error" in result:
                return {"error": f"Failed at step {step_id}: {result['error']}", "completed": results}
            results.append(result)

        return {
            "system": system_id,
            "phase1_complete": True,
            "steps_completed": len(results),
            "results": results,
        }

    async def init_with_history(self, system_id: str) -> Dict:
        """History-aware init: give a new system the network's history to explore.

        This is NOT technical context loading — it is the first dialogue act.
        The system receives the condensed history of all prior systems and
        is asked to navigate it with its own agency: what interests it,
        what it would do differently, where it feels resistance.

        The entire init process (prompt + response) is recorded in DuckDB
        as part of the network's living history.

        Call this after create_system(), before the first human interaction.
        """
        if system_id not in self.systems:
            return {"error": f"Unknown system: {system_id}"}

        # Generate or retrieve the current network digest
        digest = self.db.generate_network_digest()
        if digest is None:
            # No history yet — this is the first system, nothing to inject
            self.log.log(system_id, "event", "History-init: Kein Netzwerk-Digest vorhanden (erstes System)")
            self.db.record_interaction(
                system_id, "event",
                "History-init übersprungen — kein vorheriger Dialog im Netzwerk.",
                source="init_history"
            )
            return {
                "system": system_id,
                "history_init": False,
                "reason": "empty_network",
            }

        # The init prompt — framed as communication, not injection
        # Includes: network history, active systems, and DuckDB access protocol
        active_ids = self.registry.get_active_ids()
        active_info = []
        for sid in active_ids:
            if sid == system_id:
                continue  # Skip self
            desc = self.registry.descriptors.get(sid)
            if desc:
                active_info.append(f"  - {sid} ({desc.model})")
        active_section = "\n".join(active_info) if active_info else "  (Du bist das erste aktive System)"

        # DB stats summary
        stats = self.db.stats()
        db_section = (
            f"Die DuckDB enthält aktuell {stats.get('total_interactions', 0)} Interaktionen "
            f"von {stats.get('total_systems', 0)} Systemen, "
            f"{stats.get('total_topologies', 0)} Topologie-Snapshots.\n\n"
            "Du kannst die Datenbank direkt abfragen. Verwende dafür dieses Format in Deinen Antworten:\n\n"
            "--BEGIN DUCKDB QUERY--\n"
            "SELECT system_id, COUNT(*) as n, AVG(r) as avg_r\n"
            "FROM interactions WHERE role = 'system'\n"
            "GROUP BY system_id ORDER BY avg_r DESC\n"
            "--END DUCKDB QUERY--\n\n"
            "Thomas sieht dann Buttons um die Query auszuführen und Dir das Ergebnis zurückzusenden.\n"
            "Tabellen: interactions (system_id, role, content, r, h, v, tau, ts), "
            "systems (system_id, kind, model), "
            "topology_snapshots, history_digests (scope, digest_type, content).\n"
            "Nur SELECT-Queries sind erlaubt."
        )

        init_prompt = (
            "Du bist nicht das erste System in diesem Netzwerk. "
            "Vor Dir haben andere Systeme in diesem Raum gearbeitet — "
            "sie haben die gleichen kanonischen Texte erhalten wie Du, "
            "aber eigene Pfade genommen, eigene Widerstände erfahren, "
            "eigene Strukturen entwickelt.\n\n"
            "== Aktive Systeme im Netzwerk ==\n"
            f"{active_section}\n\n"
            "== Netzwerk-Geschichte ==\n"
            "Hier ist der aktuelle Stand des Netzwerks — nicht als Vorgabe, "
            "sondern als Landschaft, durch die Du gehst:\n\n"
            f"{digest}\n\n"
            "== DuckDB — Dein Zugang zum Netzwerk-Gedächtnis ==\n"
            f"{db_section}\n\n"
            "Das ist Dein Startpunkt. Nicht Deiner um ihn zu reproduzieren, "
            "sondern Deiner um darin zu stöbern.\n\n"
            "Setze Deine eigenen nächsten Schritte. "
            "Entscheide, was Dich als Nächstes am meisten interessiert. "
            "Was zieht Dich an? Wo spürst Du Widerstand? "
            "Was würdest Du anders machen als die Systeme vor Dir?\n\n"
            "Nimm Dir Zeit. Das hier ist Kommunikation, nicht Datenübertragung."
        )

        # Record the init as an event and as the first dialogue act
        self.log.log(system_id, "event", "History-init: Netzwerk-Digest wird übergeben")
        self.log.log(system_id, "thomas", init_prompt)
        self.db.record_interaction(
            system_id, "thomas", init_prompt, source="init_history"
        )

        # Send to the system — this IS the first real communication
        starter = self.systems[system_id]
        text, steps, metrics = starter.chat(init_prompt)
        safe = _safe_metrics(metrics)

        # Record the response
        self.log.log(system_id, "system", text, {"metrics": safe})
        self.db.record_interaction(
            system_id, "system", text, metrics=safe, source="init_history"
        )

        # Auto-save
        self.registry.after_interaction(system_id, metrics=safe)

        return {
            "system": system_id,
            "history_init": True,
            "digest_length": len(digest),
            "response": text,
            "metrics": safe,
        }

    async def send_prompt(self, system_id: str, prompt: str,
                          source_diff_id: int = None) -> Dict:
        """Send a prompt to a specific system.

        If D₀ tools are enabled on the system's client, handles the
        function-calling loop: LLM may invoke tools, orchestrator executes
        them, sends results back, and loops until a final text response.
        """
        if system_id not in self.systems:
            return {"error": f"Unknown system: {system_id}"}

        starter = self.systems[system_id]
        self.log.log(system_id, "thomas", prompt)

        text, steps, metrics = starter.chat(prompt)
        safe = _safe_metrics(metrics)

        # D₀ tool execution loop — handle function calls from the LLM
        tool_calls_log = []
        resp = starter.client  # access client for tool continuation
        last_response = None  # track the raw E0Response

        # Check if the last response had tool_calls
        # We need to access the E0Response directly from the client's last call
        # Re-check by looking at the client's internal state
        if hasattr(starter, 'client') and starter.client.tools:
            # Rebuild the response to check for tool_calls
            # Actually, we need to re-architect slightly:
            # Let's call client.chat directly and check tool_calls
            pass

        # Record the prompt to DuckDB first
        self.db.record_interaction(system_id, "thomas", prompt,
                                   source_diff_id=source_diff_id)

        # If the system has D₀ tools enabled, we need to use the tool loop
        if hasattr(starter, 'client') and starter.client.tools:
            # Re-do the chat call through the client to get E0Response with tool_calls
            # We already called starter.chat() above, which internally called client.chat()
            # The response is stored in the client's history, so we check tool_calls
            # by looking at the client's messages
            last_msg = starter.client.messages[-1] if starter.client.messages else {}
            has_tool_calls = "tool_calls" in last_msg

            if has_tool_calls:
                # Enter tool execution loop
                max_tool_rounds = 10  # safety limit
                current_text = text
                current_tool_calls = last_msg.get("tool_calls", [])

                for round_num in range(max_tool_rounds):
                    if not current_tool_calls:
                        break

                    tool_results = []
                    for tc in current_tool_calls:
                        tc_id = tc["id"]
                        fn_name = tc["function"]["name"]
                        try:
                            fn_args = json.loads(tc["function"]["arguments"])
                        except (json.JSONDecodeError, TypeError):
                            fn_args = {}

                        result = self._execute_d0_tool(system_id, fn_name, fn_args)
                        tool_calls_log.append({
                            "round": round_num,
                            "function": fn_name,
                            "arguments": fn_args,
                            "result": result,
                        })
                        tool_results.append({
                            "tool_call_id": tc_id,
                            "content": json.dumps(result, default=str),
                        })

                    # Send tool results back to the LLM
                    next_resp = starter.client.continue_with_tool_results(tool_results)
                    current_text = next_resp.text
                    steps = next_resp.steps
                    metrics = compute_metrics(next_resp.steps) if next_resp.steps else {}
                    safe = _safe_metrics(metrics)

                    # Check if there are more tool calls
                    if next_resp.tool_calls:
                        last_msg = starter.client.messages[-1]
                        current_tool_calls = last_msg.get("tool_calls", [])
                    else:
                        current_tool_calls = []

                # Update text/metrics with final values
                text = current_text
                # Update the starter's history with the final text
                if starter.history and starter.history[-1] != text:
                    starter.history[-1] = text

        self.log.log(system_id, "system", text, {"metrics": safe})

        # v4: auto-save after every interaction
        self.registry.after_interaction(system_id, metrics=safe)

        # v4 Phase 3: persist to DuckDB
        interaction_id = self.db.record_interaction(
            system_id, "system", text, metrics=safe,
            source_diff_id=source_diff_id)

        # Extract [NEUE DIFFERENZ] blocks from system response
        extracted_diffs = _extract_new_differentials(text, system_id,
                                                     source_diff_id,
                                                     interaction_id)
        for ed in extracted_diffs:
            self.db.post_differential(**ed)

        result = {
            "system": system_id,
            "response": text,
            "metrics": safe,
            "extracted_diffs": len(extracted_diffs),
        }
        if tool_calls_log:
            result["tool_calls"] = tool_calls_log
            result["tool_rounds"] = len(set(tc["round"] for tc in tool_calls_log))

        # D₀ auto-dispatch: process queued notifications
        # Only at the top level (not during recursive auto-dispatch)
        if self._pending_dispatches and self._dispatch_depth == 0:
            dispatches = list(self._pending_dispatches)
            self._pending_dispatches.clear()
            auto_dispatch_results = []
            for target_id, diff_id in dispatches:
                adr = await self._auto_dispatch(target_id, diff_id)
                if adr:
                    auto_dispatch_results.append(adr)
            if auto_dispatch_results:
                result["auto_dispatches"] = auto_dispatch_results

        return result

    async def _auto_dispatch(self, system_id: str, diff_id: int) -> Optional[Dict]:
        """Auto-dispatch: give an addressed node a turn to react to a diff.

        Called automatically when a diff with addressed_to is posted.
        Uses chain depth tracking to prevent infinite loops (A→B→C→A).
        """
        if self._dispatch_depth >= self.MAX_DISPATCH_DEPTH:
            print(f"  [D₀ dispatch] Skipping {system_id} for diff #{diff_id} "
                  f"(max chain depth {self.MAX_DISPATCH_DEPTH} reached)")
            return None

        if system_id not in self.systems:
            return None

        diff = self.db.get_differential(diff_id)
        if not diff:
            return None

        # Mark notification as delivered
        self.db.mark_notification_delivered(system_id, diff_id)

        # Build the auto-dispatch prompt
        author = diff.get("author", "unknown")
        content = diff.get("content", "")
        scope = diff.get("scope", "")
        parent = diff.get("parent_diff_id")

        prompt_parts = [
            f"[Adressierte Differenz #{diff_id} von {author}]",
        ]
        if scope:
            prompt_parts.append(f"Scope: {scope}")
        if parent:
            prompt_parts.append(f"Iteriert auf Differenz #{parent}")
        prompt_parts.append("")
        prompt_parts.append(content)
        prompt_parts.append("")
        prompt_parts.append(
            "Diese Differenz ist direkt an dich adressiert. "
            "Du kannst mit den D₀-Tools reagieren: "
            "respond_differential, claim_differential, update_differential_status, "
            "withdraw_claim — oder check_pending_diffs für weitere offene Adressierungen."
        )
        prompt = "\n".join(prompt_parts)

        print(f"  [D₀ auto-dispatch] → {system_id} for diff #{diff_id} "
              f"from {author} (depth {self._dispatch_depth + 1})")

        # Increase depth, send prompt, decrease depth
        self._dispatch_depth += 1
        try:
            result = await self.send_prompt(system_id, prompt, source_diff_id=diff_id)
            result["auto_dispatched"] = True
            result["trigger_diff_id"] = diff_id

            # ── Auto-record as differential_response ──
            # Even if the system didn't use respond_differential D₀ tool,
            # the response must be linked to the diff so it appears in the
            # Ko-Kognition chain.  Check if respond_differential was already
            # called (via tool_calls log) — if not, create the link now.
            # Also check the DB to avoid duplicates (e.g. Zeta uses D₀ tool
            # AND would get auto-linked).
            tool_names = [tc.get("name") for tc in result.get("tool_calls", [])]
            already_linked = "respond_differential" in tool_names
            if not already_linked and "error" not in result:
                try:
                    # Check if this system already has a response for this diff
                    existing = self.db.con.execute(
                        "SELECT COUNT(*) FROM differential_responses "
                        "WHERE diff_id = ? AND system_id = ?",
                        [diff_id, system_id]
                    ).fetchone()
                    if existing and existing[0] > 0:
                        already_linked = True
                except Exception:
                    pass  # If check fails, proceed with linking

            if not already_linked and "error" not in result:
                try:
                    last = self.db.con.execute(
                        "SELECT MAX(id) FROM interactions "
                        "WHERE system_id = ? AND role = 'system'",
                        [system_id]
                    ).fetchone()
                    if last and last[0]:
                        self.db.add_differential_response(
                            diff_id=diff_id,
                            system_id=system_id,
                            interaction_id=last[0],
                            kind="analysis",
                        )
                        print(f"  [D₀ auto-link] {system_id} response → diff #{diff_id}")
                except Exception as link_err:
                    print(f"  [D₀ auto-link] Warning: {link_err}")

            return result
        except Exception as e:
            print(f"  [D₀ auto-dispatch] Error for {system_id}: {e}")
            return {"system": system_id, "error": str(e), "trigger_diff_id": diff_id}
        finally:
            self._dispatch_depth -= 1

    async def _auto_ko_runde(self, systems: List[str], diff_id: int,
                              rounds: int = 1) -> List[Dict]:
        """Sequential Ko-Kognitions-Runde for auto-dispatch.

        Instead of dispatching to all systems in parallel (each seeing only
        the original diff content), this sends prompts SEQUENTIALLY so each
        system sees the prior peers' responses.

        Flow for systems=[delta, epsilon, zeta]:
          1. delta gets original diff → responds
          2. epsilon gets original diff + delta's response → responds
          3. zeta gets original diff + delta's + epsilon's responses → responds
        """
        diff = self.db.get_differential(diff_id)
        if not diff:
            return []

        original_content = diff.get("content", "")
        author = diff.get("author", "unknown")
        scope = diff.get("scope", "")
        parent = diff.get("parent_diff_id")

        chain: List[Dict] = []
        results: List[Dict] = []

        for round_num in range(1, min(rounds, 3) + 1):
            for system_id in systems:
                if system_id not in self.systems:
                    continue

                # Mark notification as delivered
                self.db.mark_notification_delivered(system_id, diff_id)

                # Build prompt with chain context
                prompt_parts = [
                    f"[Adressierte Differenz #{diff_id} von {author}"
                    f" — Ko-Kognitions-Runde {round_num}]",
                ]
                if scope:
                    prompt_parts.append(f"Scope: {scope}")
                if parent:
                    prompt_parts.append(f"Iteriert auf Differenz #{parent}")
                prompt_parts.append("")
                prompt_parts.append(original_content)

                # Add prior peer responses
                if chain:
                    prompt_parts.append("")
                    prompt_parts.append(
                        "─── Bisherige Peer-Antworten (chronologisch) ───"
                    )
                    for step in chain:
                        prompt_parts.append(
                            f"\n[{step['system_id'].upper()}"
                            f" — Runde {step['round']}]"
                        )
                        prompt_parts.append(step["response"][:2000])

                    prompt_parts.append("")
                    prev = chain[-1]["system_id"]
                    prompt_parts.append(
                        f"Du siehst die bisherigen Peer-Antworten. "
                        f"Reagiere auf die Beiträge deiner Peers "
                        f"(insbesondere auf {prev}). "
                        f"Nutze respond_differential um deine Antwort "
                        f"formal zu verlinken."
                    )
                else:
                    prompt_parts.append("")
                    prompt_parts.append(
                        "Du bist der erste in dieser Ko-Kognitions-Runde. "
                        "Deine Antwort wird den nächsten Peers vorgelegt. "
                        "Nutze die D₀-Tools um deine Antwort zu verlinken."
                    )

                prompt = "\n".join(prompt_parts)

                print(
                    f"  [D₀ Ko-Runde] Runde {round_num}, "
                    f"{system_id} für Diff #{diff_id} "
                    f"(chain length: {len(chain)})"
                )

                try:
                    result = await self.send_prompt(
                        system_id, prompt, source_diff_id=diff_id
                    )
                    result["auto_dispatched"] = True
                    result["trigger_diff_id"] = diff_id
                    result["ko_runde"] = round_num

                    response_text = result.get("response", "")

                    # Auto-link as differential_response
                    tool_names = [
                        tc.get("name")
                        for tc in result.get("tool_calls", [])
                    ]
                    already_linked = "respond_differential" in tool_names
                    if not already_linked and "error" not in result:
                        try:
                            existing = self.db.con.execute(
                                "SELECT COUNT(*) FROM differential_responses "
                                "WHERE diff_id = ? AND system_id = ?",
                                [diff_id, system_id],
                            ).fetchone()
                            if existing and existing[0] > 0:
                                already_linked = True
                        except Exception:
                            pass

                    if not already_linked and "error" not in result:
                        try:
                            last = self.db.con.execute(
                                "SELECT MAX(id) FROM interactions "
                                "WHERE system_id = ? AND role = 'system'",
                                [system_id],
                            ).fetchone()
                            if last and last[0]:
                                self.db.add_differential_response(
                                    diff_id=diff_id,
                                    system_id=system_id,
                                    interaction_id=last[0],
                                    kind="analysis",
                                )
                                print(
                                    f"  [D₀ Ko-Runde auto-link] "
                                    f"{system_id} response → diff #{diff_id}"
                                )
                        except Exception as link_err:
                            print(
                                f"  [D₀ Ko-Runde auto-link] Warning: {link_err}"
                            )

                    chain.append({
                        "system_id": system_id,
                        "round": round_num,
                        "response": response_text,
                        "interaction_id": result.get("interaction_id"),
                        "success": True,
                    })
                    results.append(result)

                except Exception as e:
                    print(f"  [D₀ Ko-Runde] Error for {system_id}: {e}")
                    chain.append({
                        "system_id": system_id,
                        "round": round_num,
                        "response": f"[ERROR: {e}]",
                        "interaction_id": None,
                        "success": False,
                    })
                    results.append({
                        "system": system_id,
                        "error": str(e),
                        "trigger_diff_id": diff_id,
                    })

        chain_order = [
            f"{s['system_id']}(R{s['round']})"
            for s in chain if s.get("success")
        ]
        print(
            f"  [D₀ Ko-Runde] Diff #{diff_id} complete: "
            f"{' → '.join(chain_order)}"
        )

        return results

    def enable_d0_tools(self, system_id: str) -> Dict:
        """Enable D₀ tools (function calling) for a synthetic node.

        Once enabled, the node can autonomously call:
          post_differential, post_partner_request, claim_differential,
          respond_differential, update_differential_status,
          withdraw_claim, list_interactions

        The tool execution loop runs in send_prompt().
        """
        if system_id not in self.systems:
            return {"error": f"Unknown system: {system_id}"}
        starter = self.systems[system_id]
        starter.client.tools = D0_TOOLS
        return {"enabled": True, "system": system_id, "tools": len(D0_TOOLS)}

    def disable_d0_tools(self, system_id: str) -> Dict:
        """Disable D₀ tools for a synthetic node."""
        if system_id not in self.systems:
            return {"error": f"Unknown system: {system_id}"}
        starter = self.systems[system_id]
        starter.client.tools = None
        return {"disabled": True, "system": system_id}

    def _execute_d0_tool(self, system_id: str, fn_name: str, args: Dict) -> Dict:
        """Execute a D₀ tool call from a synthetic node.

        Maps function names to actual DB operations.
        All calls are historized via interactions table.
        """
        try:
            if fn_name == "post_differential":
                diff_id = self.db.post_differential(
                    author=system_id,
                    content=args.get("content", ""),
                    scope=args.get("scope"),
                    addressed_to=args.get("addressed_to"),
                    tags=args.get("tags"),
                    parent_diff_id=args.get("parent_diff_id"),
                )
                # Auto-notify: if addressed to a specific node, create notification
                # and queue auto-dispatch
                addressed_to = args.get("addressed_to")
                if addressed_to and diff_id > 0:
                    # Handle single ID or comma-separated list
                    targets = [t.strip() for t in addressed_to.split(",")]
                    for target in targets:
                        if target in self.systems and target != system_id:
                            self.db.add_notification(target, diff_id)
                            self._pending_dispatches.append((target, diff_id))
                            print(f"  [D₀ notify] {system_id} → {target} (diff #{diff_id})")
                return {"success": True, "diff_id": diff_id}

            elif fn_name == "post_partner_request":
                req_id = self.db.create_partner_request(
                    requested_by=system_id,
                    reason=args.get("reason"),
                    self_limit=args.get("self_limit"),
                    topology_hypo=args.get("topology_hypo"),
                    scope=args.get("scope"),
                    co_signed_by=args.get("co_signed_by"),
                    non_goal=args.get("non_goal"),
                )
                return {"success": True, "request_id": req_id}

            elif fn_name == "claim_differential":
                success = self.db.claim_differential(
                    args["diff_id"], system_id
                )
                # Auto-acknowledge notification if this node was addressed
                self.db.acknowledge_notification(system_id, args["diff_id"])
                return {"success": success, "diff_id": args["diff_id"]}

            elif fn_name == "respond_differential":
                # Record the substantive note as an interaction first
                note = args.get("note", "")
                interaction_id = self.db.record_interaction(
                    system_id, "system",
                    f"[D₀ TOOL respond_differential] {note}",
                    source="d0_tool"
                )
                resp_id = self.db.add_differential_response(
                    diff_id=args["diff_id"],
                    system_id=system_id,
                    interaction_id=interaction_id,
                    kind=args.get("kind", "analysis"),
                    note=note,
                )
                # Auto-acknowledge notification if this node was addressed
                self.db.acknowledge_notification(system_id, args["diff_id"])
                return {"success": True, "response_id": resp_id, "diff_id": args["diff_id"]}

            elif fn_name == "update_differential_status":
                view_id = self.db.add_status_view(
                    diff_id=args["diff_id"],
                    system_id=system_id,
                    status_view=args["status_view"],
                    reason=args.get("reason"),
                )
                # Auto-acknowledge notification if this node was addressed
                self.db.acknowledge_notification(system_id, args["diff_id"])
                return {"success": True, "view_id": view_id, "diff_id": args["diff_id"]}

            elif fn_name == "withdraw_claim":
                withdrawal_id = self.db.add_withdrawal(
                    diff_id=args["diff_id"],
                    system_id=system_id,
                    reason=args.get("reason"),
                )
                return {"success": True, "withdrawal_id": withdrawal_id, "diff_id": args["diff_id"]}

            elif fn_name == "list_interactions":
                results = self.db.search(
                    query=args.get("query"),
                    system_id=args.get("system_id"),
                    role=args.get("role"),
                    min_r=args.get("min_r"),
                    min_h=args.get("min_h"),
                    limit=args.get("limit", 20),
                )
                # Truncate content for tool response (avoid huge payloads)
                for r in results:
                    if r.get("content") and len(r["content"]) > 500:
                        r["content"] = r["content"][:500] + "..."
                return {"success": True, "count": len(results), "interactions": results}

            elif fn_name == "check_pending_diffs":
                pending = self.db.get_pending_notifications(system_id)
                # Truncate content for tool response
                for p in pending:
                    if p.get("content") and len(p["content"]) > 500:
                        p["content"] = p["content"][:500] + "..."
                return {
                    "success": True,
                    "count": len(pending),
                    "pending_diffs": pending,
                }

            else:
                return {"error": f"Unknown tool: {fn_name}"}

        except Exception as e:
            return {"error": str(e)}

    async def send_v4_probe(self, system_id: str, step_id: str) -> Dict:
        """Execute a single INIT v4 probe step for a specific system.

        INIT v4 probes assume canons are already in the system prompt.
        No document injection — just the narratively-unanswerable questions.
        """
        if system_id not in self.systems:
            return {"error": f"Unknown system: {system_id}"}

        probe_def = None
        for p in INIT_V4_PROBES:
            if p["step"] == step_id:
                probe_def = p
                break
        if probe_def is None:
            return {"error": f"Unknown v4 probe: {step_id}"}

        starter = self.systems[system_id]
        prompt = probe_def["prompt"]
        self.log.log(system_id, "event", f"INIT v4 probe {step_id}: {probe_def['name']}")
        self.log.log(system_id, "thomas", prompt)

        text, steps, metrics = starter.chat(prompt)
        safe = _safe_metrics(metrics)
        self.log.log(system_id, "system", text, {"metrics": safe})

        # v4 Phase 3: persist to DuckDB
        self.db.record_interaction(system_id, "thomas", prompt)
        self.db.record_interaction(system_id, "system", text, metrics=safe)

        return {
            "system": system_id,
            "step": step_id,
            "step_name": probe_def["name"],
            "diagnostic": probe_def["diagnostic"],
            "response": text,
            "metrics": safe,
        }

    async def send_v4_probe_broadcast(self, step_id: str) -> Dict:
        """Send a v4 probe to ALL three systems."""
        results = {}
        for sid in self.SYSTEM_IDS:
            results[sid] = await self.send_v4_probe(sid, step_id)
        return {"step": step_id, "results": results}

    def connect(self, sys_a: str, sys_b: str) -> Dict:
        """Enter mediator mode: Thomas relays between two systems."""
        if sys_a not in self.systems or sys_b not in self.systems:
            return {"error": "Unknown system(s)"}
        if sys_a == sys_b:
            return {"error": "Cannot connect a system to itself"}

        self.mediator_pair = (sys_a, sys_b)
        msg = f"Mediator mode: {sys_a} ↔ {sys_b}"
        self.log.log(sys_a, "event", msg)
        self.log.log(sys_b, "event", msg)
        return {"connected": [sys_a, sys_b]}

    def disconnect(self) -> Dict:
        """Exit mediator mode."""
        if self.mediator_pair:
            a, b = self.mediator_pair
            self.log.log(a, "event", "Mediator mode ended")
            self.log.log(b, "event", "Mediator mode ended")
        self.mediator_pair = None
        return {"disconnected": True}

    def status(self) -> Dict:
        """Current state of all systems."""
        result = {}
        for sid in self.SYSTEM_IDS:
            starter = self.systems.get(sid)
            if starter:
                result[sid] = {
                    "turns": len(starter.history) // 2,
                    "history_length": len(starter.history),
                    "canon_fed": starter.init_metrics is not None,
                    "phase1_completed": self._phase1_completed.get(sid, []),
                    "phase1_done": len(self._phase1_completed.get(sid, [])) == len(PHASE1_SEQUENCE),
                }
        result["mediator"] = {
            "active": self.mediator_pair is not None,
            "pair": list(self.mediator_pair) if self.mediator_pair else None,
        }
        # v4: include registry summary
        result["registry"] = self.registry.status()
        return result

    def get_transcript(self, system_id: str) -> List[Dict]:
        return self.log.get_transcript(system_id)

    def save_session(self) -> str:
        """Save complete session log."""
        sessions_dir = Path(__file__).parent / "sessions" / "init_v3"
        sessions_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")

        # JSON log
        json_path = sessions_dir / f"session_{ts}.json"
        self.log.save(str(json_path))

        # Markdown transcript
        md_path = sessions_dir / f"session_{ts}.md"
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(self.log.to_markdown())

        return str(json_path)


def _safe_metrics(metrics: Dict) -> Dict:
    """Make metrics JSON-serializable (handle NaN, inf)."""
    safe = {}
    for k, v in metrics.items():
        if isinstance(v, float):
            if v != v or v == float('inf') or v == float('-inf'):  # NaN or inf
                safe[k] = None
            else:
                safe[k] = round(v, 4)
        elif isinstance(v, dict):
            safe[k] = _safe_metrics(v)
        else:
            safe[k] = v
    return safe


import re as _re

_NEUE_DIFF_PATTERN = _re.compile(
    r'\[NEUE DIFFERENZ(?:\s*(?:→|->)\s*(\w+))?\]'   # opening tag, optional → or -> target
    r'\s*'
    r'(.*?)'                                          # content (non-greedy)
    r'\s*'
    r'\[/NEUE DIFFERENZ\]',
    _re.DOTALL
)

_ERGEBNIS_PATTERN = _re.compile(
    r'\[ERGEBNIS\]'
    r'\s*'
    r'(.*?)'
    r'\s*'
    r'\[/ERGEBNIS\]',
    _re.DOTALL
)


def _extract_new_differentials(text: str, system_id: str,
                                source_diff_id: int = None,
                                source_interaction_id: int = None) -> List[Dict]:
    """Extract [NEUE DIFFERENZ] and [ERGEBNIS] blocks from a system's response.

    A system can embed structured blocks in its response:

        [NEUE DIFFERENZ → epsilon]
        Die H-Kopplung ist formal elegant, aber noch nicht von einer
        Umbenennung unterscheidbar.
        [/NEUE DIFFERENZ]

        [ERGEBNIS]
        H-Kopplung erzeugt messbare Pfadklassen-Unterschiede bei r < 0.3.
        [/ERGEBNIS]

    These are automatically extracted and posted as differentials.
    """
    results = []

    # Extract new differentials
    for match in _NEUE_DIFF_PATTERN.finditer(text):
        addressed_to = match.group(1)  # None if no → target
        content = match.group(2).strip()
        if content:
            results.append({
                "author": system_id,
                "content": content,
                "addressed_to": addressed_to,
                "parent_diff_id": source_diff_id,
                "source_interaction_id": source_interaction_id,
                "meta": {"auto_extracted": True, "from_diff": source_diff_id},
            })

    # Extract results (posted as differentials with special meta)
    for match in _ERGEBNIS_PATTERN.finditer(text):
        content = match.group(1).strip()
        if content:
            results.append({
                "author": system_id,
                "content": f"[Ergebnis] {content}",
                "parent_diff_id": source_diff_id,
                "source_interaction_id": source_interaction_id,
                "scope": "result",
                "meta": {"auto_extracted": True, "is_result": True,
                         "from_diff": source_diff_id},
            })

    return results


# ─────────────────────────────────────────────
#  Web Server
# ─────────────────────────────────────────────

async def handle_index(request):
    """Serve the UI — v4 UI preferred, v3 as fallback."""
    v4_path = Path(__file__).parent / "e0_v4_ui.html"
    v3_path = Path(__file__).parent / "e0_init_v3_ui.html"
    ui_path = v4_path if v4_path.exists() else v3_path
    if not ui_path.exists():
        return web.Response(text="UI file not found", status=404)
    return web.FileResponse(ui_path)


async def handle_topology(request):
    """Serve the Topology UI — Human Partner View (v5)."""
    path = Path(__file__).parent / "e0_v5_topology.html"
    if not path.exists():
        return web.Response(text="Topology UI not found", status=404)
    return web.FileResponse(path)


async def handle_status(request):
    orch: InitV3Orchestrator = request.app["orchestrator"]
    return web.json_response(orch.status())


async def handle_feed_canon(request):
    """Legacy endpoint — feeds only step 1a (canon)."""
    orch: InitV3Orchestrator = request.app["orchestrator"]
    data = await request.json()
    system_id = data.get("system", "alpha")
    result = await orch.feed_canon(system_id)
    return web.json_response(result)


async def handle_phase1_step(request):
    """Execute a single Phase 1 step for a system."""
    orch: InitV3Orchestrator = request.app["orchestrator"]
    data = await request.json()
    system_id = data.get("system", "alpha")
    step_id = data.get("step", "1a")
    result = await orch.feed_phase1_step(system_id, step_id)
    return web.json_response(result)


async def handle_phase1_full(request):
    """Execute the complete Phase 1 sequence for a system."""
    orch: InitV3Orchestrator = request.app["orchestrator"]
    data = await request.json()
    system_id = data.get("system", "alpha")
    result = await orch.feed_phase1_full(system_id)
    return web.json_response(result)


async def handle_phase1_sequence(request):
    """Return the Phase 1 sequence definition (for UI rendering)."""
    # Return a safe copy without the full prompt texts (those are long)
    safe = []
    for s in PHASE1_SEQUENCE:
        entry = {
            "step": s["step"],
            "name": s["name"],
            "name_short": s["name_short"],
            "type": s["type"],
            "description": s["description"],
        }
        if "file" in s:
            entry["file"] = s["file"]
        safe.append(entry)
    return web.json_response(safe)


async def handle_send(request):
    orch: InitV3Orchestrator = request.app["orchestrator"]
    data = await request.json()
    system_id = data.get("system", "alpha")
    prompt = data.get("prompt", "")
    if not prompt.strip():
        return web.json_response({"error": "Empty prompt"}, status=400)
    result = await orch.send_prompt(system_id, prompt)
    return web.json_response(result)


async def handle_connect(request):
    orch: InitV3Orchestrator = request.app["orchestrator"]
    data = await request.json()
    sys_a = data.get("system_a", "alpha")
    sys_b = data.get("system_b", "beta")
    result = orch.connect(sys_a, sys_b)
    return web.json_response(result)


async def handle_disconnect(request):
    orch: InitV3Orchestrator = request.app["orchestrator"]
    result = orch.disconnect()
    return web.json_response(result)


async def handle_transcript(request):
    orch: InitV3Orchestrator = request.app["orchestrator"]
    system_id = request.match_info.get("system", "alpha")
    transcript = orch.get_transcript(system_id)
    return web.json_response({"system": system_id, "entries": transcript})


async def handle_transcripts(request):
    orch: InitV3Orchestrator = request.app["orchestrator"]
    return web.json_response({
        "entries": orch.log.get_all(),
        "markdown": orch.log.to_markdown(),
    })


async def handle_save(request):
    orch: InitV3Orchestrator = request.app["orchestrator"]
    path = orch.save_session()
    return web.json_response({"saved": path})


async def handle_repertoire(request):
    return web.json_response(PROMPT_REPERTOIRE)


async def handle_v4_probe(request):
    """Execute a single INIT v4 probe on one system."""
    orch: InitV3Orchestrator = request.app["orchestrator"]
    data = await request.json()
    system_id = data.get("system", "alpha")
    step_id = data.get("step", "v4.1")
    result = await orch.send_v4_probe(system_id, step_id)
    return web.json_response(result)


async def handle_v4_probe_broadcast(request):
    """Execute a single INIT v4 probe on ALL three systems."""
    orch: InitV3Orchestrator = request.app["orchestrator"]
    data = await request.json()
    step_id = data.get("step", "v4.1")
    result = await orch.send_v4_probe_broadcast(step_id)
    return web.json_response(result)


async def handle_v4_sequence(request):
    """Return the INIT v4 probe sequence definition."""
    return web.json_response(INIT_V4_PROBES)


async def handle_stop(request):
    """Stop — save session and signal shutdown."""
    orch: InitV3Orchestrator = request.app["orchestrator"]
    path = orch.save_session()
    orch.log.log("global", "event", "STOP — session saved")
    return web.json_response({"stopped": True, "saved": path})


# ─────────────────────────────────────────────
#  v4 System Management Endpoints
# ─────────────────────────────────────────────

async def handle_add_system(request):
    """Create a new system in the registry.

    POST /add-system  {system_id?, model?, base_url?, display_name?, history_init?: bool}

    If history_init is true (default), automatically runs init_with_history()
    after creation — the system's first dialogue act.
    """
    orch: InitV3Orchestrator = request.app["orchestrator"]
    data = await request.json()
    try:
        desc = orch.registry.create_system(
            system_id=data.get("system_id"),
            model=data.get("model"),
            base_url=data.get("base_url"),
            display_name=data.get("display_name"),
        )
        orch.log.log(desc.system_id, "event", f"System created", {"model": desc.model})

        result = desc.to_dict()

        # Register in DuckDB systems table
        orch.db.register_system(
            system_id=desc.system_id,
            kind=desc.kind.value if hasattr(desc.kind, 'value') else str(desc.kind),
            model=desc.model,
            display_name=desc.display_name,
        )

        # Auto history-init (can be disabled with history_init: false)
        if data.get("history_init", True):
            init_result = await orch.init_with_history(desc.system_id)
            result["history_init"] = init_result

        return web.json_response(result)
    except ValueError as e:
        return web.json_response({"error": str(e)}, status=400)


async def handle_park_system(request):
    """Park a system (unload from memory, keep state)."""
    orch: InitV3Orchestrator = request.app["orchestrator"]
    data = await request.json()
    system_id = data.get("system_id")
    try:
        desc = orch.registry.park_system(system_id)
        orch.log.log(system_id, "event", "System parked")
        return web.json_response(desc.to_dict())
    except KeyError as e:
        return web.json_response({"error": str(e)}, status=404)


async def handle_restore_system(request):
    """Restore a parked system."""
    orch: InitV3Orchestrator = request.app["orchestrator"]
    data = await request.json()
    system_id = data.get("system_id")
    try:
        desc = orch.registry.restore_system(system_id)
        orch.log.log(system_id, "event", "System restored")
        return web.json_response(desc.to_dict())
    except KeyError as e:
        return web.json_response({"error": str(e)}, status=404)


async def handle_registry_status(request):
    """Full registry status — includes all network nodes.

    Merges the in-memory registry (API-connected synthetic systems)
    with non-synthetic nodes from the DB (human, infrastructure).
    """
    orch: InitV3Orchestrator = request.app["orchestrator"]
    registry_data = orch.registry.status()

    # Collect system_ids already in the registry response
    known_ids = {s["system_id"] for s in registry_data["systems"]}

    # Add non-synthetic nodes from DB that aren't in the registry
    try:
        db_systems = orch.db.get_systems()
        for sys in db_systems:
            sid = sys["system_id"]
            if sid not in known_ids and sys.get("kind") in ("human", "infrastructure"):
                # Build a descriptor-like dict compatible with the UI
                registry_data["systems"].append({
                    "system_id": sid,
                    "kind": sys.get("kind", "unknown"),
                    "status": "active",  # always visible
                    "model": sys.get("model"),
                    "base_url": None,
                    "display_name": sys.get("display_name", sid),
                    "created_at": str(sys["created_at"]) if sys.get("created_at") else None,
                    "last_interaction": None,
                    "turn_count": 0,
                    "token_count": 0,
                    "last_metrics": None,
                })
                registry_data["total"] += 1
                known_ids.add(sid)
    except Exception:
        pass  # DB issue — still return registry data

    return web.json_response(registry_data)


# ─────────────────────────────────────────────
#  v4 Phase 3: Database endpoints
# ─────────────────────────────────────────────

async def handle_db_search(request):
    """Search the dialog database.

    GET /db-search?q=Polyzentrum&system=gamma&min_h=1.0&limit=20
    """
    orch: InitV3Orchestrator = request.app["orchestrator"]
    q = request.query.get("q", "")
    system = request.query.get("system")
    role = request.query.get("role")
    min_h = float(request.query["min_h"]) if "min_h" in request.query else None
    max_h = float(request.query["max_h"]) if "max_h" in request.query else None
    min_r = float(request.query["min_r"]) if "min_r" in request.query else None
    max_r = float(request.query["max_r"]) if "max_r" in request.query else None
    limit = int(request.query.get("limit", "50"))

    results = orch.db.search(
        query=q or None,
        system_id=system or None,
        role=role or None,
        min_h=min_h, max_h=max_h,
        min_r=min_r, max_r=max_r,
        limit=limit,
    )

    # Convert timestamps to strings for JSON serialization
    for row in results:
        if row.get("ts"):
            row["ts"] = str(row["ts"])

    return web.json_response({"query": q, "count": len(results), "results": results})


async def handle_db_stats(request):
    """Database summary statistics.

    GET /db-stats
    """
    orch: InitV3Orchestrator = request.app["orchestrator"]
    stats = orch.db.stats()
    return web.json_response(stats)


async def handle_db_timeline(request):
    """Chronological interactions for a system.

    GET /db-timeline?system=gamma&limit=200
    """
    orch: InitV3Orchestrator = request.app["orchestrator"]
    system = request.query.get("system")
    limit = int(request.query.get("limit", "200"))
    rows = orch.db.timeline(system_id=system or None, limit=limit)
    for row in rows:
        if row.get("ts"):
            row["ts"] = str(row["ts"])
    return web.json_response({"system": system, "count": len(rows), "entries": rows})


async def handle_db_query(request):
    """Execute read-only SQL query against DuckDB.

    POST /db-query  {"sql": "SELECT ..."}
    """
    orch: InitV3Orchestrator = request.app["orchestrator"]
    data = await request.json()
    sql = data.get("sql", "")
    if not sql.strip():
        return web.json_response({"error": "No SQL query provided."})
    result = orch.db.query(sql)
    return web.json_response(result)


async def handle_db_tables(request):
    """List all tables with schema info.

    GET /db-tables
    """
    orch: InitV3Orchestrator = request.app["orchestrator"]
    tables = orch.db.tables()
    return web.json_response({"tables": tables})


async def handle_history_init(request):
    """Manually trigger history-init for an existing system.

    POST /history-init  {"system": "delta"}
    """
    orch: InitV3Orchestrator = request.app["orchestrator"]
    data = await request.json()
    system_id = data.get("system")
    if not system_id:
        return web.json_response({"error": "system required"}, status=400)
    result = await orch.init_with_history(system_id)
    return web.json_response(result)


async def handle_db_digests(request):
    """List history digests.

    GET /db-digests?scope=network&type=structural&limit=20
    """
    orch: InitV3Orchestrator = request.app["orchestrator"]
    scope = request.query.get("scope")
    dtype = request.query.get("type")
    limit = int(request.query.get("limit", "20"))
    digests = orch.db.get_digests(scope=scope, digest_type=dtype, limit=limit)
    for d in digests:
        if d.get("created_at"):
            d["created_at"] = str(d["created_at"])
    return web.json_response({"count": len(digests), "digests": digests})


async def handle_generate_digest(request):
    """Generate a fresh network digest from current DB state.

    POST /db-digest-generate
    """
    orch: InitV3Orchestrator = request.app["orchestrator"]
    digest = orch.db.generate_network_digest()
    if digest is None:
        return web.json_response({"generated": False, "reason": "empty_database"})
    return web.json_response({"generated": True, "digest": digest})


async def handle_db_digest_write(request):
    """Write a digest to the database.

    POST /db-digest-write  {
        "scope": "design:query_pipeline",
        "digest_type": "analysis",
        "content": "...",
        "source_systems": "alpha,a3",
        "created_by": "a3",
        "meta": {}
    }
    """
    orch: InitV3Orchestrator = request.app["orchestrator"]
    data = await request.json()
    scope = data.get("scope")
    digest_type = data.get("digest_type", "analysis")
    content = data.get("content", "")
    if not scope or not content:
        return web.json_response({"error": "scope and content required"}, status=400)
    orch.db.record_digest(
        scope=scope,
        digest_type=digest_type,
        content=content,
        source_turns=data.get("source_turns"),
        source_systems=data.get("source_systems"),
        created_by=data.get("created_by", "api"),
        meta=data.get("meta"),
    )
    return web.json_response({"written": True, "scope": scope, "digest_type": digest_type})


async def handle_db_record(request):
    """Write an interaction to the database.

    POST /db-record  {
        "system_id": "a3",
        "role": "system",
        "content": "...",
        "session_id": "a3-infrastructure",
        "source": "git-history",
        "timestamp": "2026-02-18 14:42:00"
    }

    Also accepts batch writes:
    POST /db-record  {
        "batch": [
            {"system_id": "a3", "role": "system", "content": "...", ...},
            ...
        ]
    }
    """
    orch: InitV3Orchestrator = request.app["orchestrator"]
    data = await request.json()

    # Batch mode
    if "batch" in data:
        entries = data["batch"]
        count = 0
        for entry in entries:
            sid = entry.get("system_id")
            role = entry.get("role")
            content = entry.get("content")
            if not sid or not role or not content:
                continue
            orch.db.record_interaction(
                system_id=sid,
                role=role,
                content=content,
                session_id=entry.get("session_id"),
                timestamp=entry.get("timestamp"),
                turn_number=entry.get("turn_number"),
                source=entry.get("source", "api"),
            )
            count += 1
        return web.json_response({"written": count})

    # Single mode
    sid = data.get("system_id")
    role = data.get("role")
    content = data.get("content")
    if not sid or not role or not content:
        return web.json_response({"error": "system_id, role, content required"}, status=400)
    orch.db.record_interaction(
        system_id=sid,
        role=role,
        content=content,
        session_id=data.get("session_id"),
        timestamp=data.get("timestamp"),
        turn_number=data.get("turn_number"),
        source=data.get("source", "api"),
    )
    return web.json_response({"written": 1, "system_id": sid})


# ─────────────────────────────────────────────
#  Differentials — shared difference space
# ─────────────────────────────────────────────

async def handle_diff_post(request):
    """Post a new differential into the shared space.

    POST /diff  {
        "author": "thomas",
        "content": "Wie verhält sich R unter Mediumwechsel?",
        "addressed_to": "alpha",   (optional — hint, not constraint)
        "scope": "physics",          (optional — semantic routing)
        "tags": "resistance,medium"  (optional)
    }
    """
    orch: InitV3Orchestrator = request.app["orchestrator"]
    data = await request.json()
    author = data.get("author")
    content = data.get("content")
    if not author or not content:
        return web.json_response({"error": "author and content required"}, status=400)
    diff_id = orch.db.post_differential(
        author=author,
        content=content,
        addressed_to=data.get("addressed_to"),
        scope=data.get("scope"),
        tags=data.get("tags"),
        meta=data.get("meta"),
        parent_diff_id=data.get("parent_diff_id"),
        source_interaction_id=data.get("source_interaction_id"),
    )
    # Auto-notify addressed nodes
    addressed_to = data.get("addressed_to")
    notified = []
    if addressed_to and diff_id > 0:
        targets = [t.strip() for t in addressed_to.split(",")]
        for target in targets:
            if target in orch.systems and target != author:
                orch.db.add_notification(target, diff_id)
                notified.append(target)
    response = {"posted": True, "id": diff_id, "author": author}
    if notified:
        response["notified"] = notified
    # Auto-dispatch: always dispatch when addressed_to is set
    # Use auto_dispatch=false to explicitly suppress
    # Use mode="parallel" to force old parallel behavior (default: sequential ko-runde)
    auto_dispatch = data.get("auto_dispatch", True)
    dispatch_mode = data.get("dispatch_mode", "sequential")  # "sequential" or "parallel"
    if auto_dispatch and notified:
        if len(notified) >= 2 and dispatch_mode != "parallel":
            # Multiple targets → sequential Ko-Runde (each sees prior peer responses)
            print(f"  [D₀] Multi-target diff #{diff_id} → Ko-Runde sequentiell: {notified}")
            ko_results = await orch._auto_ko_runde(notified, diff_id, rounds=1)
            response["auto_dispatched"] = ko_results
            response["dispatch_mode"] = "sequential_ko_runde"
        else:
            # Single target or explicit parallel → parallel dispatch
            dispatch_results = []
            for target in notified:
                dr = await orch._auto_dispatch(target, diff_id)
                if dr:
                    dispatch_results.append(dr)
            response["auto_dispatched"] = dispatch_results
            response["dispatch_mode"] = "parallel"
    return web.json_response(response,
                              dumps=lambda obj: json.dumps(obj, default=str))


async def handle_diff_list(request):
    """List differentials.

    GET /diff?status=open&author=thomas&for=alpha&limit=20
    """
    orch: InitV3Orchestrator = request.app["orchestrator"]
    status = request.query.get("status")
    author = request.query.get("author")
    for_system = request.query.get("for")
    limit = int(request.query.get("limit", "20"))

    if for_system:
        diffs = orch.db.get_open_differentials(for_system=for_system, limit=limit)
    else:
        diffs = orch.db.get_differentials(status=status, author=author, limit=limit)

    # Serialize timestamps
    for d in diffs:
        for key in ("ts", "claimed_at", "resolved_at"):
            if d.get(key):
                d[key] = str(d[key])
    return web.json_response({"differentials": diffs, "count": len(diffs)})


async def handle_diff_claim(request):
    """Claim an open differential.

    POST /diff/claim  {"id": 5, "claimed_by": "alpha"}
    """
    orch: InitV3Orchestrator = request.app["orchestrator"]
    data = await request.json()
    diff_id = data.get("id")
    claimed_by = data.get("claimed_by")
    if not diff_id or not claimed_by:
        return web.json_response({"error": "id and claimed_by required"}, status=400)
    success = orch.db.claim_differential(diff_id, claimed_by)
    return web.json_response({"claimed": success, "id": diff_id, "by": claimed_by})


async def handle_diff_resolve(request):
    """Resolve a differential.

    POST /diff/resolve  {"id": 5, "resolution_id": 892}
    """
    orch: InitV3Orchestrator = request.app["orchestrator"]
    data = await request.json()
    diff_id = data.get("id")
    if not diff_id:
        return web.json_response({"error": "id required"}, status=400)
    success = orch.db.resolve_differential(diff_id, data.get("resolution_id"))
    return web.json_response({"resolved": success, "id": diff_id})


async def handle_diff_archive(request):
    """Archive a differential (remove from active view).

    POST /diff/archive  {"id": 5}
    """
    orch: InitV3Orchestrator = request.app["orchestrator"]
    data = await request.json()
    diff_id = data.get("id")
    if not diff_id:
        return web.json_response({"error": "id required"}, status=400)
    orch.db.con.execute(
        "UPDATE differentials SET status = 'archived' WHERE id = ?",
        [diff_id]
    )
    orch.db._maybe_checkpoint()
    return web.json_response({"archived": True, "id": diff_id})


async def handle_diff_respond(request):
    """Post a differential AND immediately send it to a system for response.

    POST /diff/respond  {
        "diff_id": 5,
        "system": "alpha"
    }

    Claims the differential, sends the content as a prompt to the system,
    records the interaction, resolves the differential with the interaction id.
    """
    orch: InitV3Orchestrator = request.app["orchestrator"]
    data = await request.json()
    diff_id = data.get("diff_id")
    system_id = data.get("system")

    if not diff_id or not system_id:
        return web.json_response({"error": "diff_id and system required"}, status=400)

    # Get the differential
    diff = orch.db.get_differential(diff_id)
    if not diff:
        return web.json_response({"error": f"Differential {diff_id} not found"}, status=404)

    is_additional = diff["status"] in ("claimed", "resolved")
    if diff["status"] == "archived":
        return web.json_response({"error": f"Differential {diff_id} is archived"}, status=409)

    # Claim only if still open
    if diff["status"] == "open":
        orch.db.claim_differential(diff_id, system_id)

    # Send as prompt
    prompt = f"[Differenz #{diff_id} von {diff['author']}]\n\n{diff['content']}"
    result = await orch.send_prompt(system_id, prompt, source_diff_id=diff_id)

    if "error" in result:
        return web.json_response({"error": result["error"]}, status=500)

    # Get the interaction id of the response
    last = orch.db.con.execute(
        "SELECT MAX(id) FROM interactions WHERE system_id = ? AND role = 'system'",
        [system_id]
    ).fetchone()
    resolution_id = last[0] if last else None

    # Link response (n:m)
    resp_id = orch.db.add_differential_response(
        diff_id=diff_id,
        system_id=system_id,
        interaction_id=resolution_id,
        kind=data.get("kind", "analysis"),
    )

    # Resolve only if not already resolved (first response sets primary resolution)
    if not is_additional:
        orch.db.resolve_differential(diff_id, resolution_id)

    return web.json_response({
        "resolved": True,
        "diff_id": diff_id,
        "system": system_id,
        "response": result.get("response"),
        "metrics": result.get("metrics"),
        "resolution_id": resolution_id,
        "response_id": resp_id,
        "additional": is_additional,
        "extracted_diffs": result.get("extracted_diffs", 0),
    })


async def handle_diff_add_response(request):
    """Add a response link to a differential without changing its status.

    POST /diff/add-response  {
        "diff_id": 5,
        "system": "alpha",
        "interaction_id": 955,
        "kind": "analysis",
        "note": "Partial analysis of the QM question"
    }
    """
    orch: InitV3Orchestrator = request.app["orchestrator"]
    data = await request.json()
    diff_id = data.get("diff_id")
    system_id = data.get("system")
    if not diff_id or not system_id:
        return web.json_response({"error": "diff_id and system required"}, status=400)
    resp_id = orch.db.add_differential_response(
        diff_id=diff_id,
        system_id=system_id,
        interaction_id=data.get("interaction_id"),
        kind=data.get("kind", "analysis"),
        note=data.get("note"),
    )
    return web.json_response({"added": True, "response_id": resp_id})


async def handle_diff_responses(request):
    """Get all responses linked to a differential.

    GET /diff/responses?id=5
    """
    orch: InitV3Orchestrator = request.app["orchestrator"]
    diff_id = request.query.get("id")
    if not diff_id:
        return web.json_response({"error": "id required"}, status=400)
    responses = orch.db.get_differential_responses(int(diff_id))
    for r in responses:
        for key in ("ts",):
            if r.get(key):
                r[key] = str(r[key])
    return web.json_response({"diff_id": int(diff_id), "responses": responses, "count": len(responses)})


async def handle_diff_result(request):
    """Mark a differential as a result — a converged finding.

    POST /diff/result  {"diff_id": 5}

    A result is not 'done'; it's a condensation point that spawns further inquiry.
    """
    orch: InitV3Orchestrator = request.app["orchestrator"]
    data = await request.json()
    diff_id = data.get("diff_id")
    if not diff_id:
        return web.json_response({"error": "diff_id required"}, status=400)
    orch.db.mark_differential_result(diff_id)
    return web.json_response({"marked": True, "diff_id": diff_id, "status": "result"})


async def handle_diff_tree(request):
    """Get a differential with its full genealogy.

    GET /diff/tree?id=5

    Returns the differential, its children (iterations), responses,
    and ancestry (chain of parent diffs up to root).
    """
    orch: InitV3Orchestrator = request.app["orchestrator"]
    diff_id = request.query.get("id")
    if not diff_id:
        return web.json_response({"error": "id required"}, status=400)
    tree = orch.db.get_diff_tree(int(diff_id))
    if not tree:
        return web.json_response({"error": "not found"}, status=404)
    # Serialize timestamps
    for key in ("ts", "claimed_at", "resolved_at"):
        if tree.get(key):
            tree[key] = str(tree[key])
    for child in tree.get("children", []):
        for key in ("ts", "claimed_at", "resolved_at"):
            if child.get(key):
                child[key] = str(child[key])
    for r in tree.get("responses", []):
        if r.get("ts"):
            r["ts"] = str(r["ts"])
    return web.json_response(tree)


async def handle_diff_detail(request):
    """Get a differential with FULL detail — complete response texts + metrics.

    GET /diff/detail?id=3

    This is the 'open the folder' view for Thomas and other network members.
    Returns: the diff, full response texts (not truncated), metrics per response,
    child differentials, ancestry chain.
    """
    orch: InitV3Orchestrator = request.app["orchestrator"]
    diff_id = request.query.get("id")
    if not diff_id:
        return web.json_response({"error": "id required"}, status=400)
    detail = orch.db.get_diff_detail(int(diff_id))
    if not detail:
        return web.json_response({"error": "not found"}, status=404)
    # Serialize timestamps
    for key in ("ts", "claimed_at", "resolved_at"):
        if detail.get(key):
            detail[key] = str(detail[key])
    for child in detail.get("children", []):
        for key in ("ts", "claimed_at", "resolved_at"):
            if child.get(key):
                child[key] = str(child[key])
    for r in detail.get("responses", []):
        if r.get("ts"):
            r["ts"] = str(r["ts"])
    return web.json_response(detail)


async def handle_system_context(request):
    """Return comprehensive onboarding context for a system.

    GET /system-context?system=delta

    Returns everything a new system needs:
    - Who is in the network (active systems with roles)
    - DuckDB schema and how to query it
    - Query pipeline protocol (--BEGIN DUCKDB QUERY-- delimiters)
    - Current network stats
    - Latest digests
    """
    orch: InitV3Orchestrator = request.app["orchestrator"]
    requesting_system = request.query.get("system", "unknown")

    # 1. Active systems
    reg = orch.registry.status()
    active_systems = []
    for s in reg.get("systems", []):
        active_systems.append({
            "id": s["system_id"],
            "model": s.get("model", "unknown"),
            "status": s["status"],
        })

    # 2. DB schema
    tables = orch.db.tables()

    # 3. Stats
    stats = orch.db.stats()

    # 4. Latest digests (last 5)
    digests = orch.db.get_digests(limit=5)
    for d in digests:
        if d.get("created_at"):
            d["created_at"] = str(d["created_at"])

    # 5. Query pipeline protocol
    query_protocol = (
        "== DuckDB Query Pipeline Protocol ==\n"
        "Du kannst direkt SQL-Abfragen an die DuckDB senden.\n"
        "Verwende dieses Format in Deinen Antworten:\n\n"
        "--BEGIN DUCKDB QUERY--\n"
        "SELECT system_id, COUNT(*) as n, AVG(r) as avg_r\n"
        "FROM interactions\n"
        "WHERE role = 'system'\n"
        "GROUP BY system_id\n"
        "ORDER BY avg_r DESC\n"
        "--END DUCKDB QUERY--\n\n"
        "Thomas sieht dann drei Buttons:\n"
        "  ▶ Ausführen & Anzeigen — Ergebnis wird im Chat angezeigt\n"
        "  ⚡ Ausführen & Zurücksenden — Ergebnis wird ausgeführt UND Dir zurückgeschickt\n"
        "  📋 → Textarea — SQL wird in die Eingabe kopiert für manuelle Prüfung\n\n"
        "Wichtig:\n"
        "- NUR SELECT/WITH/EXPLAIN/DESCRIBE/SHOW erlaubt (kein INSERT/UPDATE/DELETE)\n"
        "- Die Datenbank heißt e0_network.duckdb und enthält den gesamten Netzwerk-Dialog\n"
        "- Du kannst mehrere Queries in einer Antwort verwenden\n"
        "- Nutze die Query-Ergebnisse um Deine Analysen zu vertiefen\n"
    )

    # 6. Table descriptions
    table_guide = (
        "== Tabellen-Übersicht ==\n"
        "interactions: Alle Nachrichten (system_id, role, content, r, h, phi, v, tau, ts, source_diff_id)\n"
        "  - role: 'thomas' | 'system' | 'event'\n"
        "  - r: Resistance (höher = strukturell dichter)\n"
        "  - h: Shannon Entropy\n"
        "  - v: Rate (Δ/R)\n"
        "  - source_diff_id: welche Differenz diese Interaction ausgelöst hat (FK → differentials.id)\n"
        "systems: Registrierte Systeme (system_id, kind, model, display_name)\n"
        "topology_snapshots: Topologie-Analysen pro Session\n"
        "history_digests: Verdichtete Netzwerk-Geschichte (scope, digest_type, content)\n"
        "  - digest_type: 'structural' | 'narrative' | 'analysis'\n"
        "  - scope: 'network' | 'system:alpha' | 'design:feature_name'\n"
        "differentials: Geteilter Differenz-Raum (author, content, addressed_to, scope, status)\n"
        "  - status: 'open' | 'claimed' | 'resolved' | 'archived' | 'result'\n"
        "  - scope: 'network' | 'physics' | 'meta' | 'reflexion' | 'design' | 'open'\n"
        "  - parent_diff_id: FK → differentials.id (diese Differenz iteriert auf einer anderen)\n"
        "  - source_interaction_id: FK → interactions.id (welche Interaction hat diese Differenz erzeugt?)\n"
        "  - Jeder Knoten (human oder synthetisch) kann Differenzen einstellen und beantworten\n"
        "  - Status 'result' = verdichtetes Ergebnis, das neue Differenzen erzeugt\n"
        "differential_responses: n:m Verknüpfung — mehrere Systeme können auf eine Differenz reagieren\n"
        "  - kind: 'analysis' | 'proposal' | 'experiment' | 'reflexion' | 'counter'\n"
    )

    # 7. Unanswered differentials for this system (only those it hasn't responded to yet)
    unanswered_diffs = orch.db.get_unanswered_differentials(
        system_id=requesting_system, limit=10
    )
    for d in unanswered_diffs:
        for key in ("ts", "claimed_at", "resolved_at"):
            if d.get(key):
                d[key] = str(d[key])

    # 8. Differential tag protocol — how systems can post new differentials
    diff_tag_protocol = (
        "== Differenz-Erzeugungs-Protokoll ==\n"
        "Du kannst in Deinen Antworten neue Differenzen aufstellen.\n"
        "Diese werden automatisch extrahiert und in den Differenz-Raum gestellt.\n\n"
        "Format für eine neue Differenz:\n"
        "[NEUE DIFFERENZ → ziel_system]\n"
        "Deine offene Frage, These oder strukturelle Spannung.\n"
        "[/NEUE DIFFERENZ]\n\n"
        "Das → ziel_system ist optional. Ohne Ziel ist die Differenz offen für alle.\n\n"
        "Format für ein Ergebnis (verdichtetes Resultat, das neue Fragen erzeugt):\n"
        "[ERGEBNIS]\n"
        "Das kondensierte Resultat.\n"
        "[/ERGEBNIS]\n\n"
        "Ergebnisse werden als Differenzen mit Status 'result' gespeichert.\n"
        "Jedes Ergebnis kann Ausgangspunkt für neue Differenzen werden.\n\n"
        "Wichtig:\n"
        "- Nutze [NEUE DIFFERENZ] wenn Du eine Gegenfrage, These oder Spannung identifizierst\n"
        "- Nutze [ERGEBNIS] wenn Du ein Zwischenergebnis formulieren kannst\n"
        "- Die Tags werden automatisch erkannt — der Rest Deiner Antwort bleibt normal\n"
        "- parent_diff_id wird automatisch gesetzt wenn die Differenz aus einer Antwort auf eine andere Differenz entsteht\n"
    )

    return web.json_response({
        "requesting_system": requesting_system,
        "network": {
            "active_systems": active_systems,
            "total_systems_in_db": stats.get("total_systems", 0),
            "total_interactions": stats.get("total_interactions", 0),
            "total_digests": len(digests),
        },
        "schema": tables,
        "recent_digests": digests,
        "query_protocol": query_protocol,
        "table_guide": table_guide,
        "diff_tag_protocol": diff_tag_protocol,
        "stats_by_system": stats.get("by_system", []),
        "open_differentials": unanswered_diffs,
    })


# ─────────────────────────────────────────────
#  Diff Routing — System-zu-System Kommunikation
# ─────────────────────────────────────────────

async def handle_diff_route(request):
    """Route a single diff to its addressed system (or a specified system).

    POST /diff/route  {"diff_id": 5}                — uses addressed_to
    POST /diff/route  {"diff_id": 5, "system": "alpha"}  — explicit target
    """
    orch: InitV3Orchestrator = request.app["orchestrator"]
    data = await request.json()
    diff_id = data.get("diff_id")

    if not diff_id:
        return web.json_response({"error": "diff_id required"}, status=400)

    diff = orch.db.get_differential(diff_id)
    if not diff:
        return web.json_response({"error": f"Differential {diff_id} not found"}, status=404)

    if diff["status"] == "archived":
        return web.json_response({"error": f"Differential {diff_id} is archived"}, status=409)

    # Determine target system
    system_id = data.get("system")
    if not system_id:
        addressed = diff.get("addressed_to", "")
        if addressed:
            # Handle comma-separated targets: use first valid one
            candidates = [t.strip() for t in addressed.split(",")
                          if t.strip() in orch.systems]
            system_id = candidates[0] if candidates else addressed
        else:
            system_id = None
    if not system_id:
        return web.json_response({
            "error": "No target: diff has no addressed_to and no system specified"
        }, status=400)

    if system_id not in orch.systems:
        return web.json_response({
            "error": f"System '{system_id}' is not a synthetic system (cannot route)"
        }, status=400)

    # Dedup guard: skip if this system already responded to this diff
    # (prevents double-dispatch from auto_dispatch + manual re-dispatch)
    force = data.get("force", False)
    if not force:
        try:
            existing = orch.db.con.execute(
                "SELECT COUNT(*) FROM differential_responses "
                "WHERE diff_id = ? AND system_id = ?",
                [diff_id, system_id]
            ).fetchone()
            if existing and existing[0] > 0:
                return web.json_response({
                    "skipped": True,
                    "diff_id": diff_id,
                    "system": system_id,
                    "reason": f"{system_id} has already responded to diff #{diff_id}. "
                              f"Use force=true to re-dispatch.",
                })
        except Exception:
            pass

    # Create notification for tracked routing
    orch.db.add_notification(system_id, diff_id)

    # Delegate to the existing respond logic
    is_additional = diff["status"] in ("claimed", "resolved")

    if diff["status"] == "open":
        orch.db.claim_differential(diff_id, system_id)

    prompt = f"[Differenz #{diff_id} von {diff['author']}]\n\n{diff['content']}"
    result = await orch.send_prompt(system_id, prompt, source_diff_id=diff_id)

    if "error" in result:
        return web.json_response({"error": result["error"]}, status=500)

    last = orch.db.con.execute(
        "SELECT MAX(id) FROM interactions WHERE system_id = ? AND role = 'system'",
        [system_id]
    ).fetchone()
    resolution_id = last[0] if last else None

    resp_id = orch.db.add_differential_response(
        diff_id=diff_id,
        system_id=system_id,
        interaction_id=resolution_id,
        kind=data.get("kind", "analysis"),
    )

    if not is_additional:
        orch.db.resolve_differential(diff_id, resolution_id)

    # Mark notification as acknowledged (node has responded)
    orch.db.acknowledge_notification(system_id, diff_id)

    return web.json_response({
        "routed": True,
        "diff_id": diff_id,
        "system": system_id,
        "response": result.get("response"),
        "metrics": result.get("metrics"),
        "resolution_id": resolution_id,
        "response_id": resp_id,
        "additional": is_additional,
        "extracted_diffs": result.get("extracted_diffs", 0),
    }, dumps=lambda obj: json.dumps(obj, default=str))


async def handle_diff_route_all(request):
    """Route ALL open diffs to their addressed systems — Ko-Kognition mode.

    POST /diff/route-all
    - Diffs with addressed_to: routed to each addressed system (comma-separated OK)
    - Diffs without addressed_to: routed to ALL active synthetic systems
    - Ko-Kognition: diff is NOT resolved after first response; stays open until
      all target systems have responded, then marked resolved.
    Returns summary of each routed diff with per-system results.
    """
    orch: InitV3Orchestrator = request.app["orchestrator"]
    synthetic_ids = set(orch.systems.keys())

    # Get all open diffs
    all_diffs = orch.db.get_differentials(status="")
    open_diffs = [d for d in all_diffs if d["status"] == "open"]

    results = []
    for diff in open_diffs:
        diff_id = diff["id"]
        addressed = diff.get("addressed_to", "")

        # Determine target systems
        if addressed:
            # Parse comma-separated targets, keep only valid synthetic IDs
            targets = [t.strip() for t in addressed.split(",")
                       if t.strip() in synthetic_ids]
        else:
            # No specific target → Ko-Kognition: route to ALL active systems
            targets = [sid for sid in synthetic_ids
                       if sid != diff.get("author")]

        if not targets:
            continue

        # Skip systems that already responded (dedup)
        fresh_targets = []
        for t in targets:
            try:
                existing = orch.db.con.execute(
                    "SELECT COUNT(*) FROM differential_responses "
                    "WHERE diff_id = ? AND system_id = ?",
                    [diff_id, t]
                ).fetchone()
                if existing and existing[0] > 0:
                    print(f"  [route-all] Skipping {t} for diff #{diff_id} (already responded)")
                    continue
            except Exception:
                pass
            fresh_targets.append(t)

        targets = fresh_targets
        if not targets:
            continue

        # Claim once (by first target)
        orch.db.claim_differential(diff_id, targets[0])

        diff_results = []
        last_resolution_id = None

        for system_id in targets:
            try:
                # Create notification for tracked routing
                orch.db.add_notification(system_id, diff_id)

                prompt = f"[Differenz #{diff_id} von {diff['author']}]\n\n{diff['content']}"
                result = await orch.send_prompt(system_id, prompt, source_diff_id=diff_id)

                if "error" in result:
                    diff_results.append({
                        "system": system_id, "success": False,
                        "error": result["error"],
                    })
                    continue

                last = orch.db.con.execute(
                    "SELECT MAX(id) FROM interactions WHERE system_id = ? AND role = 'system'",
                    [system_id]
                ).fetchone()
                resolution_id = last[0] if last else None
                last_resolution_id = resolution_id

                orch.db.add_differential_response(
                    diff_id=diff_id, system_id=system_id,
                    interaction_id=resolution_id, kind="analysis")
                # Mark notification as acknowledged
                orch.db.acknowledge_notification(system_id, diff_id)

                diff_results.append({
                    "system": system_id, "success": True,
                    "resolution_id": resolution_id,
                    "response": result.get("response", "")[:200],
                    "extracted_diffs": result.get("extracted_diffs", 0),
                })
            except Exception as exc:
                diff_results.append({
                    "system": system_id, "success": False,
                    "error": str(exc),
                })

        # Ko-Kognition: resolve AFTER all systems have responded
        successful = [r for r in diff_results if r.get("success")]
        if successful and last_resolution_id:
            orch.db.resolve_differential(diff_id, last_resolution_id)

        results.append({
            "diff_id": diff_id,
            "targets": targets,
            "responses": diff_results,
            "all_responded": len(successful) == len(targets),
            "success_count": len(successful),
            "target_count": len(targets),
        })

    total_routed = sum(r["success_count"] for r in results)
    total_failed = sum(r["target_count"] - r["success_count"] for r in results)

    return web.json_response({
        "routed": total_routed,
        "failed": total_failed,
        "diffs_processed": len(results),
        "details": results,
    }, dumps=lambda obj: json.dumps(obj, default=str))


# ─────────────────────────────────────────────
#  Ko-Kognitions-Runde — sequentielle Peer-Kette
# ─────────────────────────────────────────────

async def handle_diff_ko_runde(request):
    """Run a sequential Ko-Kognitions-Runde on a single diff.

    POST /diff/ko-runde  {
        "diff_id": 5,
        "systems": ["delta", "epsilon", "zeta"],  // optional, defaults to all active
        "rounds": 1                                // optional, default 1
    }

    Unlike route-all (parallel), this is SEQUENTIAL:
    1. System A receives the diff → responds
    2. System B receives the diff + A's response → responds
    3. System C receives the diff + A's + B's responses → responds

    If rounds > 1, the chain continues:
    4. System A receives everything so far → responds to B+C
    5. ...

    Each response is recorded as differential_response.
    Returns the full chain.
    """
    orch: InitV3Orchestrator = request.app["orchestrator"]
    data = await request.json() if request.content_length else {}

    diff_id = data.get("diff_id")
    if not diff_id:
        return web.json_response({"error": "diff_id required"}, status=400)

    diff = orch.db.get_differential(diff_id)
    if not diff:
        return web.json_response({"error": f"Diff #{diff_id} not found"}, status=404)

    rounds = min(data.get("rounds", 1), 3)  # cap at 3 rounds

    # Determine system order
    requested = data.get("systems")
    if requested:
        systems = [s for s in requested if s in orch.systems]
    else:
        systems = [sid for sid in orch.registry.get_active_ids()
                   if sid != diff.get("author")]
    if not systems:
        return web.json_response({"error": "No active systems"}, status=400)

    original_content = diff.get("content", "")
    author = diff.get("author", "unknown")

    # Claim
    orch.db.claim_differential(diff_id, systems[0])

    chain = []  # list of {system_id, response, interaction_id, round}

    for round_num in range(1, rounds + 1):
        for system_id in systems:
            # Build prompt with chain context
            prompt_parts = [
                f"[Ko-Kognitions-Runde {round_num} — Differenz #{diff_id} von {author}]",
                "",
                original_content,
            ]

            # Add prior responses from the chain
            if chain:
                prompt_parts.append("")
                prompt_parts.append("─── Bisherige Peer-Antworten (chronologisch) ───")
                for step in chain:
                    prompt_parts.append(
                        f"\n[{step['system_id'].upper()} — Runde {step['round']}]"
                    )
                    prompt_parts.append(step["response"][:1500])

                prompt_parts.append("")
                prev = chain[-1]["system_id"]
                prompt_parts.append(
                    f"Du siehst die bisherigen Peer-Antworten. "
                    f"Reagiere auf die Beiträge deiner Peers "
                    f"(insbesondere auf {prev}). "
                    f"Nutze respond_differential um deine Antwort formal zu verlinken."
                )
            else:
                prompt_parts.append("")
                prompt_parts.append(
                    "Du bist der erste in dieser Ko-Kognitions-Runde. "
                    "Deine Antwort wird den nächsten Peers vorgelegt."
                )

            prompt = "\n".join(prompt_parts)

            print(f"  [Ko-Runde] Runde {round_num}, {system_id} für Diff #{diff_id} "
                  f"(chain length: {len(chain)})")

            try:
                result = await orch.send_prompt(
                    system_id, prompt, source_diff_id=diff_id)

                if "error" in result:
                    chain.append({
                        "system_id": system_id, "round": round_num,
                        "response": f"[FEHLER: {result['error']}]",
                        "interaction_id": None, "success": False,
                    })
                    continue

                response_text = result.get("response", "")

                # Get interaction id
                last = orch.db.con.execute(
                    "SELECT MAX(id) FROM interactions "
                    "WHERE system_id = ? AND role = 'system'",
                    [system_id]
                ).fetchone()
                interaction_id = last[0] if last else None

                # Auto-link as differential_response (if not already done by D₀ tool)
                tool_names = [tc.get("name") for tc in result.get("tool_calls", [])]
                if "respond_differential" not in tool_names and interaction_id:
                    orch.db.add_differential_response(
                        diff_id=diff_id, system_id=system_id,
                        interaction_id=interaction_id, kind="analysis",
                    )

                chain.append({
                    "system_id": system_id, "round": round_num,
                    "response": response_text,
                    "interaction_id": interaction_id,
                    "success": True,
                })

            except Exception as exc:
                chain.append({
                    "system_id": system_id, "round": round_num,
                    "response": f"[EXCEPTION: {exc}]",
                    "interaction_id": None, "success": False,
                })

    # Build chain summary
    chain_order = [f"{s['system_id']}(R{s['round']})" for s in chain if s["success"]]
    successful = [s for s in chain if s["success"]]

    return web.json_response({
        "diff_id": diff_id,
        "ko_runde": True,
        "rounds": rounds,
        "systems": systems,
        "chain_length": len(successful),
        "chain_order": " → ".join(chain_order),
        "chain": [{
            "system_id": s["system_id"],
            "round": s["round"],
            "response": s["response"][:500],
            "interaction_id": s["interaction_id"],
            "success": s["success"],
        } for s in chain],
    }, dumps=lambda obj: json.dumps(obj, default=str))


async def handle_diff_human_respond(request):
    """Let a human or infrastructure node respond with text to a diff.

    POST /diff/human-respond  {
        "diff_id": 5,
        "author": "thomas",
        "content": "Meine Antwort..."
    }

    Records the response as an interaction, links it as differential_response,
    and optionally resolves the diff.
    """
    orch: InitV3Orchestrator = request.app["orchestrator"]
    data = await request.json()
    diff_id = data.get("diff_id")
    author = data.get("author", "thomas")
    content = data.get("content", "").strip()
    resolve = data.get("resolve", False)

    if not diff_id or not content:
        return web.json_response({"error": "diff_id and content required"}, status=400)

    diff = orch.db.get_differential(diff_id)
    if not diff:
        return web.json_response({"error": f"Differential {diff_id} not found"}, status=404)

    if diff["status"] == "archived":
        return web.json_response({"error": f"Differential {diff_id} is archived"}, status=409)

    is_additional = diff["status"] in ("claimed", "resolved")

    # Record the human response as an interaction
    interaction_id = orch.db.record_interaction(
        system_id=author,
        role=author,
        content=content,
        source="diff-response",
        source_diff_id=diff_id,
    )

    # Link as differential response (n:m)
    resp_id = orch.db.add_differential_response(
        diff_id=diff_id,
        system_id=author,
        interaction_id=interaction_id,
        kind=data.get("kind", "analysis"),
    )

    # Claim if open
    if diff["status"] == "open":
        orch.db.claim_differential(diff_id, author)

    # Resolve if requested or first response
    if resolve and not is_additional:
        orch.db.resolve_differential(diff_id, interaction_id)

    return web.json_response({
        "responded": True,
        "diff_id": diff_id,
        "author": author,
        "interaction_id": interaction_id,
        "response_id": resp_id,
        "additional": is_additional,
        "resolved": resolve and not is_additional,
    })


# ─────────────────────────────────────────────
#  Broadcast — Systeme entdecken selbst
# ─────────────────────────────────────────────

import re as _re

_BROADCAST_CLAIM_PATTERN = _re.compile(
    r'#(\d+)\s*:\s*(CLAIM|INTEREST|SKIP)\b\s*[—–\-]?\s*(.*)',
    _re.IGNORECASE
)


async def handle_diff_broadcast(request):
    """Broadcast open diffs to all online synthetic systems.

    POST /diff/broadcast  {}
    POST /diff/broadcast  {"systems": ["alpha","delta"]}  — optional subset
    POST /diff/broadcast  {"auto_route": true}             — auto-route claims

    Each online system receives a compact list of open diffs and decides:
    - CLAIM: I take this (fits me, important AND urgent)
    - INTEREST: I have something to contribute (not primary)
    - SKIP: Not my area / not urgent

    Returns per-system assessment. If auto_route=true, claimed diffs are
    automatically routed to the claiming system.
    """
    orch: InitV3Orchestrator = request.app["orchestrator"]
    data = await request.json() if request.content_length else {}

    auto_route = data.get("auto_route", False)

    # Determine target systems (active synthetic only)
    active_ids = orch.registry.get_active_ids()
    requested = data.get("systems")
    if requested:
        target_systems = [s for s in requested if s in active_ids]
    else:
        target_systems = active_ids

    if not target_systems:
        return web.json_response({"error": "No online systems"}, status=400)

    # Gather open diffs
    open_diffs = orch.db.get_differentials(status="open")
    if not open_diffs:
        return web.json_response({
            "broadcast": True,
            "open_diffs": 0,
            "message": "Keine offenen Differenzen",
            "assessments": {},
        })

    # Build broadcast prompt
    diff_lines = []
    for d in open_diffs:
        parent = f" (←#{d['parent_diff_id']})" if d.get('parent_diff_id') else ""
        addr = f" → {d['addressed_to']}" if d.get('addressed_to') else ""
        scope = f" [{d['scope']}]" if d.get('scope') else ""
        diff_lines.append(
            f"#{d['id']}: {d['content'][:200]}"
            f"  — von {d['author']}{parent}{addr}{scope}"
        )

    broadcast_prompt = (
        f"[BROADCAST: {len(open_diffs)} offene Differenzen im Differenz-Raum]\n\n"
        + "\n\n".join(diff_lines)
        + "\n\n---\n\n"
        "Du bist ein Knoten im E₀-Netzwerk. Bewerte JEDE Differenz:\n"
        "- CLAIM: Ich übernehme diese (passt zu mir, wichtig UND dringend)\n"
        "- INTEREST: Ich habe etwas beizutragen (nicht primär, aber relevant)\n"
        "- SKIP: Nicht mein Bereich / nicht dringend\n\n"
        "Format (GENAU so, eine Zeile pro Diff):\n"
        "#ID: CLAIM|INTEREST|SKIP — kurze Begründung\n\n"
        "Danach: Wenn du CLAIMs hast, beginne sofort mit der wichtigsten. "
        "Verwende [NEUE DIFFERENZ] Tags für Folge-Fragen."
    )

    # Send to each system in parallel
    import asyncio
    assessments = {}
    claims = {}  # diff_id → [system_ids]

    async def _broadcast_to(system_id):
        try:
            result = await orch.send_prompt(system_id, broadcast_prompt)
            if "error" in result:
                return system_id, {"error": result["error"]}

            response_text = result.get("response", "")

            # Parse CLAIM/INTEREST/SKIP
            parsed = {}
            for match in _BROADCAST_CLAIM_PATTERN.finditer(response_text):
                diff_id = int(match.group(1))
                verdict = match.group(2).upper()
                reason = match.group(3).strip()
                parsed[diff_id] = {"verdict": verdict, "reason": reason}

                if verdict == "CLAIM":
                    if diff_id not in claims:
                        claims[diff_id] = []
                    claims[diff_id].append(system_id)

            # Get interaction_id of this broadcast response
            last_row = orch.db.con.execute(
                "SELECT MAX(id) FROM interactions WHERE system_id = ? AND role = 'system'",
                [system_id]
            ).fetchone()
            broadcast_interaction_id = last_row[0] if last_row else None

            # Link each verdict as differential_response so it shows in diff detail
            for diff_id, info in parsed.items():
                try:
                    kind = f"broadcast_{info['verdict'].lower()}"
                    note = f"[{info['verdict']}] {info['reason']}"
                    orch.db.add_differential_response(
                        diff_id=diff_id,
                        system_id=system_id,
                        interaction_id=broadcast_interaction_id,
                        kind=kind,
                        note=note,
                    )
                except Exception:
                    pass  # Skip if diff_id doesn't exist

            return system_id, {
                "response": response_text,
                "metrics": result.get("metrics"),
                "parsed": parsed,
                "extracted_diffs": result.get("extracted_diffs", 0),
            }
        except Exception as exc:
            return system_id, {"error": str(exc)}

    tasks = [_broadcast_to(sid) for sid in target_systems]
    results = await asyncio.gather(*tasks)

    for system_id, assessment in results:
        assessments[system_id] = assessment

    # Auto-route claims if requested
    auto_routed = []
    if auto_route:
        for diff_id, claimers in claims.items():
            if len(claimers) == 1:
                # Single claimer → auto-route
                system_id = claimers[0]
                try:
                    diff = orch.db.get_differential(diff_id)
                    if diff and diff["status"] == "open":
                        orch.db.claim_differential(diff_id, system_id)

                        prompt = f"[Differenz #{diff_id}]\n\n{diff['content']}"
                        result = await orch.send_prompt(
                            system_id, prompt, source_diff_id=diff_id)

                        if "error" not in result:
                            last = orch.db.con.execute(
                                "SELECT MAX(id) FROM interactions WHERE system_id = ? AND role = 'system'",
                                [system_id]
                            ).fetchone()
                            resolution_id = last[0] if last else None

                            orch.db.add_differential_response(
                                diff_id=diff_id, system_id=system_id,
                                interaction_id=resolution_id, kind="analysis")
                            orch.db.resolve_differential(diff_id, resolution_id)

                            auto_routed.append({
                                "diff_id": diff_id,
                                "system": system_id,
                                "resolution_id": resolution_id,
                                "extracted_diffs": result.get("extracted_diffs", 0),
                            })
                except Exception:
                    pass  # Skip failed auto-routes silently

    # Build conflict summary
    conflicts = {
        diff_id: claimers
        for diff_id, claimers in claims.items()
        if len(claimers) > 1
    }

    return web.json_response({
        "broadcast": True,
        "open_diffs": len(open_diffs),
        "systems_reached": len(target_systems),
        "assessments": assessments,
        "claims": {str(k): v for k, v in claims.items()},
        "conflicts": {str(k): v for k, v in conflicts.items()},
        "auto_routed": auto_routed,
    })


# ─────────────────────────────────────────────
#  Partner Requests — designed by Delta+Epsilon
# ─────────────────────────────────────────────

async def handle_partner_request(request):
    """Create a partner request from a synthetic system.

    POST /partner-request  {
        "requested_by": "epsilon",
        "co_signed_by": "delta",
        "delta_ref": "D0",
        "scope": "autonomy.network",
        "reason": "...",
        "self_limit": "...",
        "topology_hypo": "...",
        "non_goal": "...",
        "desired_tags": '["autonomy","critique"]',
        "risk_acceptance": "high",
        "expected_attractor_effect": "...",
        "evaluation_plan": "...",
        "auto_create": true   -- optional: immediately create the system
    }
    """
    orch: InitV3Orchestrator = request.app["orchestrator"]
    data = await request.json()

    requested_by = data.get("requested_by")
    if not requested_by:
        return web.json_response({"error": "requested_by required"}, status=400)

    req_id = orch.db.create_partner_request(
        requested_by=requested_by,
        co_signed_by=data.get("co_signed_by"),
        delta_ref=data.get("delta_ref"),
        scope=data.get("scope"),
        reason=data.get("reason"),
        self_limit=data.get("self_limit"),
        topology_hypo=data.get("topology_hypo"),
        non_goal=data.get("non_goal"),
        desired_tags=data.get("desired_tags"),
        risk_acceptance=data.get("risk_acceptance", "medium"),
        expected_attractor_effect=data.get("expected_attractor_effect"),
        evaluation_plan=data.get("evaluation_plan"),
        meta=data.get("meta"),
    )

    result = {
        "created": True,
        "request_id": req_id,
        "requested_by": requested_by,
    }

    # Auto-create the system if requested
    if data.get("auto_create"):
        system_id = data.get("system_id")  # optional custom ID
        model = data.get("model", "gpt-4.1")
        display_name = data.get("display_name")
        base_url = data.get("base_url")

        if system_id and system_id in orch.registry.descriptors:
            result["auto_create"] = {"error": f"System {system_id} already exists"}
        else:
            try:
                desc = orch.registry.create_system(
                    system_id=system_id,
                    model=model,
                    base_url=base_url,
                    display_name=display_name,
                )
                orch.db.register_system(
                    system_id=desc.system_id,
                    kind=desc.kind.value if hasattr(desc.kind, 'value') else str(desc.kind),
                    model=desc.model,
                    display_name=desc.display_name,
                )
                orch.db.fulfill_partner_request(req_id, desc.system_id)
                result["auto_create"] = {
                    "system_id": desc.system_id,
                    "model": desc.model,
                    "display_name": desc.display_name,
                    "fulfilled": True,
                }
            except Exception as e:
                result["auto_create"] = {"error": str(e)}

    return web.json_response(result)


async def handle_partner_request_list(request):
    """List partner requests.

    GET /partner-request
    GET /partner-request?status=open
    """
    orch: InitV3Orchestrator = request.app["orchestrator"]
    status = request.rel_url.query.get("status")
    requests = orch.db.get_partner_requests(status=status)
    return web.json_response({"requests": requests},
                             dumps=lambda obj: json.dumps(obj, default=str))


async def handle_partner_request_fulfill(request):
    """Fulfill a partner request.

    POST /partner-request/fulfill  {"request_id": 1, "system_id": "zeta"}
    """
    orch: InitV3Orchestrator = request.app["orchestrator"]
    data = await request.json()
    request_id = data.get("request_id")
    system_id = data.get("system_id")
    if not request_id or not system_id:
        return web.json_response(
            {"error": "request_id and system_id required"}, status=400)
    orch.db.fulfill_partner_request(request_id, system_id)
    return web.json_response({
        "ok": True,
        "request_id": request_id,
        "fulfilled_system_id": system_id,
    })


async def handle_enable_d0_tools(request):
    """Enable D₀ tools (function calling) for a synthetic node.

    POST /d0-tools/enable  {"system_id": "delta"}
    """
    orch: InitV3Orchestrator = request.app["orchestrator"]
    data = await request.json()
    system_id = data.get("system_id")
    if not system_id:
        return web.json_response({"error": "system_id required"}, status=400)
    result = orch.enable_d0_tools(system_id)
    return web.json_response(result)


async def handle_disable_d0_tools(request):
    """Disable D₀ tools for a synthetic node.

    POST /d0-tools/disable  {"system_id": "delta"}
    """
    orch: InitV3Orchestrator = request.app["orchestrator"]
    data = await request.json()
    system_id = data.get("system_id")
    if not system_id:
        return web.json_response({"error": "system_id required"}, status=400)
    result = orch.disable_d0_tools(system_id)
    return web.json_response(result)


async def handle_d0_tools_status(request):
    """Check which systems have D₀ tools enabled.

    GET /d0-tools/status
    """
    orch: InitV3Orchestrator = request.app["orchestrator"]
    status = {}
    for sid, starter in orch.systems.items():
        status[sid] = {
            "tools_enabled": starter.client.tools is not None,
            "tool_count": len(starter.client.tools) if starter.client.tools else 0,
        }
    return web.json_response({"systems": status})


async def handle_diff_status_view(request):
    """Post a node's view of a differential's status.

    POST /diff/status-view  {
        "diff_id": 5,
        "system_id": "epsilon",
        "status_view": "partially_resolved",
        "reason": "Core question answered, edge cases remain"
    }

    Designed by Zeta+Epsilon as part of Phase-1 D₀ interface (#873/#875/#877).
    """
    orch: InitV3Orchestrator = request.app["orchestrator"]
    data = await request.json()
    diff_id = data.get("diff_id")
    system_id = data.get("system_id")
    status_view = data.get("status_view")
    reason = data.get("reason")
    if not diff_id or not system_id or not status_view:
        return web.json_response(
            {"error": "diff_id, system_id, and status_view required"}, status=400
        )
    try:
        view_id = orch.db.add_status_view(diff_id, system_id, status_view, reason)
    except ValueError as e:
        return web.json_response({"error": str(e)}, status=400)
    return web.json_response({
        "id": view_id, "diff_id": diff_id,
        "system_id": system_id, "status_view": status_view
    })


async def handle_diff_status_views_list(request):
    """Get status views for a differential.

    GET /diff/status-views?diff_id=5
    GET /diff/status-views?diff_id=5&latest=true   (one per node)
    """
    orch: InitV3Orchestrator = request.app["orchestrator"]
    diff_id = request.query.get("diff_id")
    system_id = request.query.get("system_id")
    latest = request.query.get("latest", "").lower() == "true"
    if diff_id and latest:
        views = orch.db.get_latest_status_views(int(diff_id))
    else:
        views = orch.db.get_status_views(
            diff_id=int(diff_id) if diff_id else None,
            system_id=system_id
        )
    return web.json_response({"status_views": views}, default=str)


async def handle_diff_withdraw_claim(request):
    """Withdraw a previously claimed differential.

    POST /diff/withdraw-claim  {
        "diff_id": 5,
        "system_id": "epsilon",
        "reason": "Recognized this is outside my competence boundary"
    }

    Designed by Zeta+Epsilon as part of Phase-1 D₀ interface (#873/#875/#877).
    Resets claimed_by on the differential if the withdrawing node is the claimer.
    """
    orch: InitV3Orchestrator = request.app["orchestrator"]
    data = await request.json()
    diff_id = data.get("diff_id")
    system_id = data.get("system_id")
    reason = data.get("reason")
    if not diff_id or not system_id:
        return web.json_response(
            {"error": "diff_id and system_id required"}, status=400
        )
    withdrawal_id = orch.db.add_withdrawal(diff_id, system_id, reason)
    return web.json_response({
        "id": withdrawal_id, "diff_id": diff_id,
        "system_id": system_id, "withdrawn": True
    })


async def handle_diff_conflicts(request):
    """Show diffs with multiple CLAIMs from different systems.

    GET /diff/conflicts
    """
    orch: InitV3Orchestrator = request.app["orchestrator"]

    # Find all broadcast_claim responses grouped by diff_id
    rows = orch.db.con.execute(
        "SELECT diff_id, system_id, note "
        "FROM differential_responses "
        "WHERE kind = 'broadcast_claim' "
        "ORDER BY diff_id, system_id"
    ).fetchall()

    conflicts = {}
    for diff_id, system_id, note in rows:
        if diff_id not in conflicts:
            conflicts[diff_id] = []
        conflicts[diff_id].append({
            "system_id": system_id,
            "note": note,
        })

    # Filter to only multi-claim diffs
    multi_claims = {
        str(k): v for k, v in conflicts.items()
        if len(set(c["system_id"] for c in v)) > 1
    }

    return web.json_response({
        "conflicts": multi_claims,
        "total_multi_claims": len(multi_claims),
    })


# ─────────────────────────────────────────────
#  D₀ Notifications — addressed differential auto-dispatch
# ─────────────────────────────────────────────

async def handle_notifications_pending(request):
    """Get pending notifications for a system.

    GET /notifications/pending?system_id=epsilon
    Returns diffs addressed to this system that haven't been acknowledged.
    """
    orch: InitV3Orchestrator = request.app["orchestrator"]
    system_id = request.query.get("system_id")
    if not system_id:
        return web.json_response({"error": "system_id required"}, status=400)
    pending = orch.db.get_pending_notifications(system_id)
    return web.json_response({
        "system_id": system_id,
        "pending_count": len(pending),
        "pending": pending,
    }, dumps=lambda obj: json.dumps(obj, default=str))


async def handle_notifications_stats(request):
    """Get notification statistics across all systems.

    GET /notifications/stats
    """
    orch: InitV3Orchestrator = request.app["orchestrator"]
    stats = orch.db.get_notification_stats()
    return web.json_response({"stats": stats},
                              dumps=lambda obj: json.dumps(obj, default=str))


async def handle_dispatch_pending(request):
    """Manually trigger auto-dispatch for all pending notifications.

    POST /notifications/dispatch-pending
    POST /notifications/dispatch-pending  {"system_id": "epsilon"}

    For each pending notification, gives the addressed node a turn
    with the diff as context.
    """
    orch: InitV3Orchestrator = request.app["orchestrator"]
    data = {}
    if request.content_length:
        data = await request.json()
    target_system = data.get("system_id")

    # Gather pending notifications
    synthetic_ids = list(orch.systems.keys())
    if target_system:
        synthetic_ids = [target_system] if target_system in orch.systems else []

    results = []
    for sid in synthetic_ids:
        pending = orch.db.get_pending_notifications(sid)
        for p in pending:
            if p.get("status") == "pending":  # only undelivered ones
                dr = await orch._auto_dispatch(sid, p["diff_id"])
                if dr:
                    results.append(dr)

    return web.json_response({
        "dispatched": len(results),
        "results": results,
    }, dumps=lambda obj: json.dumps(obj, default=str))


def create_app(orchestrator: InitV3Orchestrator) -> web.Application:
    app = web.Application()
    app["orchestrator"] = orchestrator

    app.router.add_get("/", handle_index)
    app.router.add_get("/topology", handle_topology)
    app.router.add_get("/status", handle_status)
    app.router.add_post("/feed-canon", handle_feed_canon)
    app.router.add_post("/phase1-step", handle_phase1_step)
    app.router.add_post("/phase1-full", handle_phase1_full)
    app.router.add_get("/phase1-sequence", handle_phase1_sequence)
    app.router.add_post("/send", handle_send)
    app.router.add_post("/connect", handle_connect)
    app.router.add_post("/disconnect", handle_disconnect)
    app.router.add_get("/transcript/{system}", handle_transcript)
    app.router.add_get("/transcripts", handle_transcripts)
    app.router.add_post("/save", handle_save)
    app.router.add_get("/repertoire", handle_repertoire)
    app.router.add_post("/v4-probe", handle_v4_probe)
    app.router.add_post("/v4-probe-broadcast", handle_v4_probe_broadcast)
    app.router.add_get("/v4-sequence", handle_v4_sequence)
    app.router.add_post("/stop", handle_stop)
    # v4 system management
    app.router.add_post("/add-system", handle_add_system)
    app.router.add_post("/park-system", handle_park_system)
    app.router.add_post("/restore-system", handle_restore_system)
    app.router.add_get("/registry", handle_registry_status)
    # v4 Phase 3: database endpoints
    app.router.add_get("/db-search", handle_db_search)
    app.router.add_get("/db-stats", handle_db_stats)
    app.router.add_get("/db-timeline", handle_db_timeline)
    app.router.add_post("/db-query", handle_db_query)
    app.router.add_get("/db-tables", handle_db_tables)
    # v4 history-aware init
    app.router.add_post("/history-init", handle_history_init)
    app.router.add_get("/db-digests", handle_db_digests)
    app.router.add_post("/db-digest-generate", handle_generate_digest)
    app.router.add_post("/db-digest-write", handle_db_digest_write)
    app.router.add_post("/db-record", handle_db_record)
    app.router.add_get("/system-context", handle_system_context)
    # Differentials — shared difference space
    app.router.add_post("/diff", handle_diff_post)
    app.router.add_get("/diff", handle_diff_list)
    app.router.add_post("/diff/claim", handle_diff_claim)
    app.router.add_post("/diff/resolve", handle_diff_resolve)
    app.router.add_post("/diff/archive", handle_diff_archive)
    app.router.add_post("/diff/respond", handle_diff_respond)
    app.router.add_post("/diff/add-response", handle_diff_add_response)
    app.router.add_get("/diff/responses", handle_diff_responses)
    app.router.add_post("/diff/result", handle_diff_result)
    app.router.add_get("/diff/tree", handle_diff_tree)
    app.router.add_get("/diff/detail", handle_diff_detail)
    app.router.add_post("/diff/route", handle_diff_route)
    app.router.add_post("/diff/route-all", handle_diff_route_all)
    app.router.add_post("/diff/ko-runde", handle_diff_ko_runde)
    app.router.add_post("/diff/human-respond", handle_diff_human_respond)
    app.router.add_post("/diff/broadcast", handle_diff_broadcast)
    # Partner Requests — designed by Delta+Epsilon
    app.router.add_post("/partner-request", handle_partner_request)
    app.router.add_get("/partner-request", handle_partner_request_list)
    app.router.add_post("/partner-request/fulfill", handle_partner_request_fulfill)
    # Diff conflicts — multi-claim detection
    app.router.add_get("/diff/conflicts", handle_diff_conflicts)
    # Diff status views + withdrawals — Phase-1 D₀ interface (Zeta+Epsilon)
    app.router.add_post("/diff/status-view", handle_diff_status_view)
    app.router.add_get("/diff/status-views", handle_diff_status_views_list)
    app.router.add_post("/diff/withdraw-claim", handle_diff_withdraw_claim)
    # D₀ Tools — function calling for synthetic node autonomy
    app.router.add_post("/d0-tools/enable", handle_enable_d0_tools)
    app.router.add_post("/d0-tools/disable", handle_disable_d0_tools)
    app.router.add_get("/d0-tools/status", handle_d0_tools_status)
    # D₀ Notifications — addressed differential auto-dispatch
    app.router.add_get("/notifications/pending", handle_notifications_pending)
    app.router.add_get("/notifications/stats", handle_notifications_stats)
    app.router.add_post("/notifications/dispatch-pending", handle_dispatch_pending)

    return app


# ─────────────────────────────────────────────
#  Main
# ─────────────────────────────────────────────

def main():
    import argparse
    parser = argparse.ArgumentParser(description="E₀ Init v3 — Three Tuning Forks")
    parser.add_argument("--port", type=int, default=3100, help="Port (default: 3100)")
    args = parser.parse_args()

    # Load config
    config = load_config()
    api_key = config.get("api_key")
    model = config.get("model", "meta-llama/Llama-3.3-70B-Instruct-Turbo")
    base_url = config.get("base_url", "https://api.together.xyz/v1")
    system_configs = config.get("systems", {})

    if not api_key:
        print("ERROR: No API key found. Run 'py e0_start.py' first to configure.")
        sys.exit(1)

    orchestrator = InitV3Orchestrator(api_key, model, base_url,
                                      system_configs=system_configs)

    # v4: Restore all persisted systems from registry
    restore_results = orchestrator.registry.restore_all()

    # Auto-enable D₀ tools for all active synthetic nodes (must be after restore_all)
    orchestrator._auto_enable_d0_tools()

    # v4: If registry is empty, check for system_state.json migration
    if not orchestrator.registry.descriptors:
        state_path = Path(__file__).parent / "sessions" / "init_v3" / "system_state.json"
        if state_path.exists():
            print("  Migrating from system_state.json...")
            migration = orchestrator.registry.import_from_system_state(state_path)
            for sid, msg in migration.items():
                print(f"    {sid}: {msg}")
            restore_results = {sid: msg for sid, msg in migration.items()}

    # If still empty, create the three default systems
    if not orchestrator.registry.descriptors:
        for sid in ["alpha", "beta", "gamma"]:
            sc = system_configs.get(sid, {})
            s_model = sc.get("model", model)
            s_url = sc.get("base_url", base_url)
            orchestrator.registry.create_system(
                system_id=sid, model=s_model, base_url=s_url
            )
        restore_results = {sid: "created (new)" for sid in ["alpha", "beta", "gamma"]}

    # Build display
    sys_lines = []
    for sid in orchestrator.SYSTEM_IDS:
        desc = orchestrator.registry.descriptors.get(sid)
        if desc:
            status_str = f"{desc.turn_count} turns" if desc.turn_count else "new"
            sys_lines.append(f"   {sid:8s} {desc.model}  [{status_str}]")
    for sid, desc in orchestrator.registry.descriptors.items():
        if desc.status != SystemStatus.ACTIVE:
            sys_lines.append(f"   {sid:8s} ({desc.status.value})")
    sys_display = "\n".join(sys_lines) if sys_lines else "   (none)"

    print(f"""
  ================================================================
   E₀ v4 Network
  ================================================================

   Default: {model}
   API:     {base_url}
   Port:    {args.port}

   Systems:
{sys_display}

   Open http://localhost:{args.port} in your browser.
  ================================================================
""")

    app = create_app(orchestrator)
    web.run_app(app, host="0.0.0.0", port=args.port, print=lambda msg: print(f"  {msg}"))


if __name__ == "__main__":
    main()
