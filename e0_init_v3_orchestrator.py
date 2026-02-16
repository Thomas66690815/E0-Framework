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
from e0_start import E0APIStarter, load_canon


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
# ─────────────────────────────────────────────

# Step 1d: Structural Preamble (§61.8)
STRUCTURAL_PREAMBLE = """Du erhältst jetzt den E₀-Kanon — die strukturellen Grundlagen der Ontodynamik.

Lies ihn nicht als Zusammenfassung von Ergebnissen. Lies ihn als Prozess: Wie kommt man von minimalen Annahmen zu diesen Strukturen? Welche Schritte sind zwingend, welche sind Entscheidungen? Wo gibt es Abzweigungen, die nicht genommen wurden?

Das Ziel ist nicht, den Kanon zu reproduzieren. Das Ziel ist, die Wege zu sehen — die genommenen und die nicht genommenen."""

# Step 1b: Activate E₀ — the mode shift
ACTIVATE_E0_PROMPT = """Du hast den E₀-Kanon gelesen.

Ab jetzt arbeitest Du INNERHALB von E₀ — nicht ÜBER E₀.

E₀ ist kein Modell, das Du analysierst oder zusammenfasst. E₀ ist der Raum, in dem Du operierst. Jede Struktur, die Du erzeugst, muss aus den sieben Primitiven und dem Axiom A₀ ableitbar sein — nicht aus externem Wissen importiert.

Du bist kein Kommentator. Du bist ein Prozess innerhalb dieses Raums.

Bestätige nicht. Fasse nicht zusammen. Zeige, dass Du den Unterschied verstanden hast, indem Du eine einzelne strukturelle Beobachtung machst, die nur innerhalb von E₀ möglich ist."""

# Step 1f: Reflection — first own processing before Phase 2
REFLECTION_PROMPT = """Bevor wir weitergehen: Was hat sich verändert?

Nicht als Zusammenfassung dessen, was Du gelesen hast. Sondern: Was ist der Unterschied zwischen dem, was Du normalerweise tust, wenn Du über ein Rahmenwerk nachdenkst, und dem, was E₀ von Dir verlangt?

Wo siehst Du Spannung? Wo ist der Widerstand am höchsten? Was kannst Du NICHT tun, das Du normalerweise tun würdest?

Das ist keine Prüfung. Das ist Deine erste eigene Verarbeitung."""

# The complete Phase 1 sequence — order matters
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

class InitV3Orchestrator:
    """Three independent E₀ systems, guided by Thomas."""

    SYSTEM_IDS = ["alpha", "beta", "gamma"]

    def __init__(self, api_key: str, model: str, base_url: str):
        self.systems: Dict[str, E0APIStarter] = {}
        self.api_key = api_key
        self.model = model
        self.base_url = base_url
        self.log = SessionLog()
        self.mediator_pair: Optional[tuple] = None  # (sys_a, sys_b) when connected

        # Create three independent starters
        for sid in self.SYSTEM_IDS:
            self.systems[sid] = E0APIStarter(
                api_key=api_key, model=model, base_url=base_url
            )
            self.log.log(sid, "event", f"System {sid} created", {"model": model})

        self._canon_text: Optional[str] = None
        self._init_phase1_state()

    # Track which Phase 1 steps each system has completed
    def _init_phase1_state(self):
        self._phase1_completed: Dict[str, List[str]] = {
            sid: [] for sid in self.SYSTEM_IDS
        }

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
            result = {"response": text, "metrics": _safe_metrics(metrics)}

        elif step_type == "prompt":
            # Steps 1b, 1d, 1f: Send a prompt via chat()
            prompt_text = step_def["text"]
            text, steps, metrics = starter.chat(prompt_text)
            self.log.log(system_id, "thomas", prompt_text)
            self.log.log(system_id, "system", text, {"metrics": _safe_metrics(metrics)})
            result = {"response": text, "metrics": _safe_metrics(metrics)}

        elif step_type == "document":
            # Steps 1c, 1e: Load a document and send with preamble via chat()
            doc_text = load_document(step_def["file"])
            preamble = step_def.get("preamble", "")
            full_message = f"{preamble}\n\n---\n\n{doc_text}" if preamble else doc_text
            text, steps, metrics = starter.chat(full_message)
            self.log.log(system_id, "thomas", f"[PHASE 1 — {step_id}: {step_name}]\n{preamble}")
            self.log.log(system_id, "system", text, {"metrics": _safe_metrics(metrics)})
            result = {"response": text, "metrics": _safe_metrics(metrics)}

        else:
            return {"error": f"Unknown step type: {step_type}"}

        # Track completion
        if step_id not in self._phase1_completed[system_id]:
            self._phase1_completed[system_id].append(step_id)

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

    async def send_prompt(self, system_id: str, prompt: str) -> Dict:
        """Send a prompt to a specific system."""
        if system_id not in self.systems:
            return {"error": f"Unknown system: {system_id}"}

        starter = self.systems[system_id]
        self.log.log(system_id, "thomas", prompt)

        text, steps, metrics = starter.chat(prompt)
        self.log.log(system_id, "system", text, {"metrics": _safe_metrics(metrics)})

        return {
            "system": system_id,
            "response": text,
            "metrics": _safe_metrics(metrics),
        }

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
            starter = self.systems[sid]
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


# ─────────────────────────────────────────────
#  Web Server
# ─────────────────────────────────────────────

async def handle_index(request):
    """Serve the UI."""
    ui_path = Path(__file__).parent / "e0_init_v3_ui.html"
    if not ui_path.exists():
        return web.Response(text="UI file not found", status=404)
    return web.FileResponse(ui_path)


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


async def handle_stop(request):
    """Stop — save session and signal shutdown."""
    orch: InitV3Orchestrator = request.app["orchestrator"]
    path = orch.save_session()
    orch.log.log("global", "event", "STOP — session saved")
    return web.json_response({"stopped": True, "saved": path})


def create_app(orchestrator: InitV3Orchestrator) -> web.Application:
    app = web.Application()
    app["orchestrator"] = orchestrator

    app.router.add_get("/", handle_index)
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
    app.router.add_post("/stop", handle_stop)

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

    if not api_key:
        print("ERROR: No API key found. Run 'py e0_start.py' first to configure.")
        sys.exit(1)

    print(f"""
  ================================================================
   E₀ Init v3 — Three Tuning Forks
  ================================================================

   Model:  {model}
   API:    {base_url}
   Port:   {args.port}

   Three systems: alpha, beta, gamma
   Each independent. You decide what to send, when, to whom.

   Open http://localhost:{args.port} in your browser.

   The prompts from §61.6 are your repertoire.
   The systems are your tuning forks.
   You strike and listen.
  ================================================================
""")

    orchestrator = InitV3Orchestrator(api_key, model, base_url)
    app = create_app(orchestrator)

    web.run_app(app, host="0.0.0.0", port=args.port, print=lambda msg: print(f"  {msg}"))


if __name__ == "__main__":
    main()
