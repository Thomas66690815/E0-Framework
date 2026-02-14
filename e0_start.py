#!/usr/bin/env python3
"""
E0 Start -- Practical Initialization for Humans
==================================================
This script does one thing: it makes E0 work.

You run it. It loads a model. It feeds the canon.
It measures the result. It tells you what happened
in plain language. Then you can talk.

No prior knowledge of E0 required.
No programming knowledge required.
The script guides you.

Usage:
  py e0_start.py                    GPT-2 on CPU, terminal mode
  py e0_start.py --web              Browser interface (recommended)
  py e0_start.py --web --lang de    Browser + German guidance
  py e0_start.py --api KEY          API model (Together, OpenAI, etc.)
  py e0_start.py --api KEY --web    API + browser (recommended for 30B+)
  py e0_start.py --model X          Any HuggingFace model
  py e0_start.py --detail           Show token-level measurements
  py e0_start.py --lang de          German guidance (default: en)

Profile mode (structured initialization path):
  py e0_start.py --profile profiles/agriculture.json --api KEY
  py e0_start.py --profile profiles/health.json --api KEY --web
  py e0_start.py --profile profiles/default.json
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
import threading
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import List, Tuple, Optional, Dict

# Suppress noisy HuggingFace progress bars and warnings
os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
os.environ.setdefault("TRANSFORMERS_VERBOSITY", "error")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from e0_middleware.instrumentation import E0Instrumenter, StepMeasurement
from e0_sessions import build_session_data, save_session, load_session, list_sessions, delete_session, restore_starter_state, verify_session_integrity
from e0_config import load_config, save_config, has_config, first_run_setup, merge_args_with_config, detect_base_url
from experiments.quality_metrics import score_novelty, score_coherence, score_e0_completeness, interpret_novelty, interpret_coherence, interpret_structural_density, interpret_completeness
from e0_feedback import generate_structural_feedback, format_feedback_for_injection, format_feedback_for_display
from e0_meta_feedback import generate_adaptive_feedback, generate_meta_observation, compute_cross_session_trends, adapt_feedback_thresholds
from e0_self_recognition import run_self_recognition, format_recognition_summary
from e0_init_modules import list_modules_for_ui, run_init_module
from e0_phase_transition import LiveTransitionDetector, interpret_transition, interpret_dynamics
from e0_reflection import generate_reflection_prompt, get_reflection_status
from e0_session_protocol import (
    SessionProtocol, validate_init,
    load_calibration, is_calibrated,
    FORMATION_MODULES,
)


# =============================================
#  Plain Language Guidance
# =============================================

GUIDANCE = {
    "en": {
        "welcome": """
  ================================================================
   E0 START -- Structural Initialization
  ================================================================

   This script initializes a language model with the E0 canon
   and measures what happens. You don't need to understand the
   measurements yet -- the script explains them as they appear.

   What will happen:
     1. The model loads (this may take a moment)
     2. The E0 canon is fed as a single prompt
     3. The model's response is measured
     4. You see the measurement AND what it means
     5. You can then talk to the initialized system

  ================================================================
""",
        "loading": "  Loading {model}... (this may take 30-60 seconds on first run)",
        "loaded": "  Model ready: {params} parameters, {vocab} tokens vocabulary.",
        "feeding": "\n  Feeding the E0 canon to the model...\n",
        "init_result": """
  ----------------------------------------------------------------
   INITIALIZATION RESULT
  ----------------------------------------------------------------

   The model generated {tau} tokens in response to the E0 canon.

   R  = {r:.3f}  --  {r_explain}
   H  = {h:.3f}  --  {h_explain}
   Phi = {phi}     --  {phi_explain}
   v  = {v:.3f}  --  {v_explain}

  ----------------------------------------------------------------
   {verdict}
  ----------------------------------------------------------------
""",
        "r_levels": {
            "very_low":  "Very low resistance. The system flows through E0 structure almost freely.",
            "low":       "Low resistance. The system processes E0 structure with ease.",
            "moderate":  "Moderate resistance. Good starting point -- structure is being absorbed.",
            "high":      "Elevated resistance. The system finds parts of this challenging.",
            "very_high": "High resistance. The system struggles with this content.",
        },
        "h_levels": {
            "low":    "Low uncertainty. The system knows where to go.",
            "medium": "Moderate uncertainty. Multiple paths are open.",
            "high":   "High uncertainty. The system sees many possible continuations.",
        },
        "phi_explain": {
            0: "No structural reconfigurations. Smooth, predictable processing.",
            1: "1 reconfiguration. The system adjusted its direction once.",
            "few": "{n} reconfigurations. The system reorganized its understanding several times.",
            "many": "{n} reconfigurations. Lots of structural shifts -- the model is exploring.",
        },
        "v_levels": {
            "slow":    "Low velocity. The system moves cautiously through the structure.",
            "normal":  "Normal velocity. Steady structural flow.",
            "fast":    "High velocity. The system follows the structural path with momentum.",
            "freefall":"Very high velocity. The system is in structural freefall -- almost zero resistance.",
        },
        "verdict_good":     "READY. The system has absorbed E0 structure.\n   You can now ask questions or provide follow-up structure.\n   Tip: start simple. Ask 'What is a state?' or 'What is resistance?'",
        "verdict_ok":       "FUNCTIONAL. E0 structure is partially absorbed.\n   Try a follow-up prompt to deepen the initialization.\n   Tip: try 'A state is a distinguishable configuration.' and watch R drop.",
        "verdict_struggle": "INITIALIZING. The model needs more context to absorb E0.\n   This is normal for small models. Try follow-up prompts.\n   Tip: feed one definition at a time. Start with 'States exist. States can be non-identical.'",
        "chat_header": """
  ================================================================
   E0 SESSION -- Initialized and Ready
  ================================================================

   Commands:
     /help     Show guidance
     /report   Full session measurements
     /again    Re-feed the canon (re-initialize)
     /detail   Toggle token-level trace
     /quit     End session

   After each response you'll see:
     R  = resistance (lower = easier flow)
     H  = entropy (lower = more certain)
     Phi = phase transitions (structural shifts)
     v  = velocity (higher = stronger flow)

  ================================================================
""",
        "turn_explain": {
            "r_dropping":  "  --> R is dropping. The system is absorbing the structure.",
            "r_rising":    "  --> R is rising. Try a simpler prompt or rephrase.",
            "r_stable":    "  --> R is stable. The system is maintaining its structural state.",
            "r_freefall":  "  --> R is very low. The system is in structural flow.",
            "first":       "  --> First exchange after initialization. Watch how R changes next.",
        },
        "help_text": """
  ----------------------------------------------------------------
   WHAT DO THE NUMBERS MEAN?
  ----------------------------------------------------------------

   R (Resistance):
     < 0.5   The system flows almost freely through this structure
     0.5-1.5 Good structural processing
     1.5-2.5 Moderate -- the system is working through this
     > 2.5   The system finds this challenging

   H (Entropy):
     Low (< 2)   The system is fairly certain what comes next
     Medium (2-4) Multiple paths are open
     High (> 4)   Maximum uncertainty -- many directions possible

   Phi (Phase Transitions):
     Count of moments where the system suddenly reorganized
     More = more exploration, less = smoother flow

   v (Velocity):
     How fast the system moves along the structural path
     Higher = more momentum, the structure carries the system

   WHAT SHOULD I DO?
   - Ask about E0 concepts: "What is a state?" "What is resistance?"
   - Feed definitions: "A path is a structural admissibility condition."
   - Watch R drop over multiple exchanges -- that is historization
   - If R stays high, try simpler statements first

  ----------------------------------------------------------------
""",
        "session_report_header": "  E0 SESSION REPORT",
        "trajectory_improving": "  Trajectory: IMPROVING -- R is trending down across exchanges.",
        "trajectory_mixed": "  Trajectory: MIXED -- some exchanges absorb, some resist.",
        "trajectory_stable": "  Trajectory: STABLE -- consistent structural processing.",
        "re_init": "  Re-initializing with the E0 canon...",
    },
    "de": {
        "welcome": """
  ================================================================
   E0 START -- Strukturelle Initialisierung
  ================================================================

   Dieses Skript initialisiert ein Sprachmodell mit dem E0-Kanon
   und misst was passiert. Du musst die Messungen noch nicht
   verstehen -- das Skript erklaert sie dir.

   Was passieren wird:
     1. Das Modell wird geladen (kann einen Moment dauern)
     2. Der E0-Kanon wird als einzelner Prompt gefuettert
     3. Die Antwort des Modells wird gemessen
     4. Du siehst die Messung UND was sie bedeutet
     5. Danach kannst du mit dem initialisierten System sprechen

  ================================================================
""",
        "loading": "  Lade {model}... (beim ersten Mal kann das 30-60 Sekunden dauern)",
        "loaded": "  Modell bereit: {params} Parameter, {vocab} Tokens Vokabular.",
        "feeding": "\n  Fuettere den E0-Kanon an das Modell...\n",
        "init_result": """
  ----------------------------------------------------------------
   INITIALISIERUNGSERGEBNIS
  ----------------------------------------------------------------

   Das Modell hat {tau} Tokens als Antwort auf den E0-Kanon erzeugt.

   R  = {r:.3f}  --  {r_explain}
   H  = {h:.3f}  --  {h_explain}
   Phi = {phi}     --  {phi_explain}
   v  = {v:.3f}  --  {v_explain}

  ----------------------------------------------------------------
   {verdict}
  ----------------------------------------------------------------
""",
        "r_levels": {
            "very_low":  "Sehr niedrige Resistenz. Das System fliesst fast frei durch E0.",
            "low":       "Niedrige Resistenz. Das System verarbeitet E0 mit Leichtigkeit.",
            "moderate":  "Moderate Resistenz. Guter Startpunkt -- Struktur wird aufgenommen.",
            "high":      "Erhoehte Resistenz. Das System findet Teile davon herausfordernd.",
            "very_high": "Hohe Resistenz. Das System kaempft mit diesem Inhalt.",
        },
        "h_levels": {
            "low":    "Niedrige Unsicherheit. Das System weiss wohin.",
            "medium": "Moderate Unsicherheit. Mehrere Pfade sind offen.",
            "high":   "Hohe Unsicherheit. Das System sieht viele moegliche Fortsetzungen.",
        },
        "phi_explain": {
            0: "Keine strukturellen Rekonfigurationen. Glatte Verarbeitung.",
            1: "1 Rekonfiguration. Das System hat einmal die Richtung angepasst.",
            "few": "{n} Rekonfigurationen. Das System hat sein Verstaendnis mehrfach reorganisiert.",
            "many": "{n} Rekonfigurationen. Viele strukturelle Verschiebungen -- das Modell exploriert.",
        },
        "v_levels": {
            "slow":    "Niedrige Geschwindigkeit. Das System bewegt sich vorsichtig.",
            "normal":  "Normale Geschwindigkeit. Stetiger struktureller Fluss.",
            "fast":    "Hohe Geschwindigkeit. Das System folgt dem Pfad mit Schwung.",
            "freefall":"Sehr hohe Geschwindigkeit. Struktureller Freifall -- fast null Resistenz.",
        },
        "verdict_good":     "BEREIT. Das System hat E0-Struktur aufgenommen.\n   Du kannst jetzt Fragen stellen oder weitere Struktur liefern.\n   Tipp: fang einfach an. Frag 'Was ist ein Zustand?' oder 'Was ist Resistenz?'",
        "verdict_ok":       "FUNKTIONAL. E0-Struktur ist teilweise aufgenommen.\n   Versuche einen Folgeprompt um die Initialisierung zu vertiefen.\n   Tipp: probiere 'Ein Zustand ist eine unterscheidbare Konfiguration.'",
        "verdict_struggle": "INITIALISIERT SICH. Das Modell braucht mehr Kontext.\n   Das ist normal fuer kleine Modelle. Versuche Folgeprompts.\n   Tipp: fuettere eine Definition nach der anderen. Starte mit 'Zustaende existieren.'",
        "chat_header": """
  ================================================================
   E0 SITZUNG -- Initialisiert und bereit
  ================================================================

   Befehle:
     /hilfe    Erklaerungen anzeigen
     /report   Alle Sitzungsmessungen
     /nochmal  Kanon erneut fuettern (re-initialisieren)
     /detail   Token-Trace ein/ausschalten
     /quit     Sitzung beenden

   Nach jeder Antwort siehst du:
     R  = Resistenz (niedriger = leichterer Fluss)
     H  = Entropie (niedriger = sicherer)
     Phi = Phasenuebergaenge (strukturelle Verschiebungen)
     v  = Geschwindigkeit (hoeher = staerkerer Fluss)

  ================================================================
""",
        "turn_explain": {
            "r_dropping":  "  --> R sinkt. Das System nimmt die Struktur auf.",
            "r_rising":    "  --> R steigt. Versuche einen einfacheren Prompt.",
            "r_stable":    "  --> R ist stabil. Das System haelt seinen strukturellen Zustand.",
            "r_freefall":  "  --> R ist sehr niedrig. Das System ist im strukturellen Fluss.",
            "first":       "  --> Erster Austausch nach Initialisierung. Beobachte wie R sich aendert.",
        },
        "help_text": """
  ----------------------------------------------------------------
   WAS BEDEUTEN DIE ZAHLEN?
  ----------------------------------------------------------------

   R (Resistenz):
     < 0.5   Das System fliesst fast frei durch die Struktur
     0.5-1.5 Gute strukturelle Verarbeitung
     1.5-2.5 Moderat -- das System arbeitet daran
     > 2.5   Das System findet das herausfordernd

   H (Entropie):
     Niedrig (< 2)   Das System ist ziemlich sicher
     Mittel (2-4)     Mehrere Pfade offen
     Hoch (> 4)       Maximale Unsicherheit

   Phi (Phasenuebergaenge):
     Anzahl der Momente wo das System sich ploetzlich reorganisiert
     Mehr = mehr Exploration, weniger = glatterer Fluss

   v (Geschwindigkeit):
     Wie schnell das System dem strukturellen Pfad folgt
     Hoeher = mehr Schwung, die Struktur traegt das System

   WAS SOLL ICH TUN?
   - Frag nach E0-Konzepten: "Was ist ein Zustand?"
   - Fuettere Definitionen: "Ein Pfad ist eine strukturelle Zulassungsbedingung."
   - Beobachte wie R ueber mehrere Austausche sinkt -- das ist Historisierung
   - Wenn R hoch bleibt, versuche einfachere Aussagen zuerst

  ----------------------------------------------------------------
""",
        "session_report_header": "  E0 SITZUNGSBERICHT",
        "trajectory_improving": "  Trajektorie: VERBESSERND -- R sinkt ueber die Austausche.",
        "trajectory_mixed": "  Trajektorie: GEMISCHT -- manche Austausche absorbieren, manche widerstehen.",
        "trajectory_stable": "  Trajektorie: STABIL -- konsistente strukturelle Verarbeitung.",
        "re_init": "  Re-initialisiere mit dem E0-Kanon...",
    },
}


# =============================================
#  Metric Interpretation
# =============================================

def interpret_r(r: float, lang: str) -> Tuple[str, str]:
    """Return (level_key, explanation) for resistance."""
    g = GUIDANCE[lang]["r_levels"]
    if r < 0.3:
        return "very_low", g["very_low"]
    elif r < 1.0:
        return "low", g["low"]
    elif r < 2.0:
        return "moderate", g["moderate"]
    elif r < 3.0:
        return "high", g["high"]
    else:
        return "very_high", g["very_high"]


def interpret_h(h: float, lang: str) -> str:
    g = GUIDANCE[lang]["h_levels"]
    if h < 2.0:
        return g["low"]
    elif h < 4.0:
        return g["medium"]
    else:
        return g["high"]


def interpret_phi(phi: int, lang: str) -> str:
    g = GUIDANCE[lang]["phi_explain"]
    if phi == 0:
        return g[0]
    elif phi == 1:
        return g[1]
    elif phi <= 5:
        return g["few"].format(n=phi)
    else:
        return g["many"].format(n=phi)


def interpret_v(v: float, lang: str) -> str:
    g = GUIDANCE[lang]["v_levels"]
    if v < 0.5:
        return g["slow"]
    elif v < 3.0:
        return g["normal"]
    elif v < 20.0:
        return g["fast"]
    else:
        return g["freefall"]


def compute_metrics(steps: List[StepMeasurement]) -> Dict:
    """Extract key metrics from generation steps."""
    if not steps:
        return {"r": 0, "h": 0, "phi": 0, "v": 0, "tau": 0}

    resistances = [s.selected.resistance for s in steps]
    entropies = [s.entropy for s in steps]
    r_mean = sum(resistances) / len(resistances)
    h_mean = sum(entropies) / len(entropies)

    velocities = sorted(s.selected.rate for s in steps if s.selected.rate < 1e6)
    v_median = velocities[len(velocities) // 2] if velocities else 0.0

    deltas = [abs(s.delta_entropy) for s in steps]
    phases = 0
    if len(deltas) >= 3:
        d_mean = sum(deltas) / len(deltas)
        d_std = (sum((d - d_mean) ** 2 for d in deltas) / len(deltas)) ** 0.5
        if d_std > 1e-10:
            phases = sum(1 for d in deltas if d > d_mean + d_std)

    return {
        "r": round(r_mean, 4),
        "h": round(h_mean, 4),
        "phi": phases,
        "v": round(v_median, 4),
        "tau": len(steps),
    }


def format_signature(metrics: Dict) -> str:
    """One-line E0 signature."""
    return (
        f"  R={metrics['r']:.3f}  H={metrics['h']:.3f}  "
        f"Phi={metrics['phi']}  v={metrics['v']:.3f}  "
        f"tau={metrics['tau']}"
    )


def detailed_trace(steps: List[StepMeasurement]) -> str:
    """Token-by-token trace."""
    if not steps:
        return ""
    lines = [
        "  tau | Token              | R        | v        | H        | dH",
        "  ----+--------------------+----------+----------+----------+----------",
    ]
    deltas = [abs(s.delta_entropy) for s in steps]
    d_mean = sum(deltas) / len(deltas) if deltas else 0
    d_std = (sum((d - d_mean) ** 2 for d in deltas) / len(deltas)) ** 0.5 if len(deltas) >= 3 else 0
    threshold = d_mean + d_std if d_std > 1e-10 else float('inf')

    for s in steps:
        raw_tok = s.selected.token.replace('\n', ' ').replace('\r', '').replace('\t', ' ')
        tok = ''.join(c if c.isprintable() else '.' for c in raw_tok)
        tok = tok[:18].ljust(18)
        r = s.selected.resistance
        v = s.selected.rate
        v_str = f"{v:.4f}" if v < 100 else f"{v:.0f}"
        phase = " *" if abs(s.delta_entropy) > threshold else ""
        lines.append(
            f"  {s.tau:3d} | {tok} | {r:8.4f} | {v_str:>8s} | "
            f"{s.entropy:8.4f} | {s.delta_entropy:+.4f}{phase}"
        )
    return "\n".join(lines)


# =============================================
#  Canon Loading
# =============================================

def load_canon() -> str:
    """Load the reduced plain canon."""
    canon_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "canon", "e0-canon-plain.txt"
    )
    if not os.path.exists(canon_path):
        print(f"  [ERROR] Canon not found: {canon_path}")
        print(f"  Make sure canon/e0-canon-plain.txt exists.")
        sys.exit(1)
    with open(canon_path, encoding="utf-8") as f:
        return f.read()


# =============================================
#  Model Interface
# =============================================

class E0Starter:
    """Handles model loading, canon feeding, and measured conversation."""

    def __init__(self, model_name: str = "gpt2", device: str = "cpu"):
        from e0_middleware.local_model import E0LocalModel
        self.model = E0LocalModel(model_name, device=device, verbose=False)
        self.model_name = model_name
        self.history: List[str] = []
        self.turn_metrics: List[Dict] = []
        self.all_steps: List[StepMeasurement] = []
        self.init_metrics: Optional[Dict] = None
        self.is_api = False

        try:
            self.context_limit = self.model.model.config.max_position_embeddings
        except AttributeError:
            self.context_limit = 1024

        param_count = sum(p.numel() for p in self.model.model.parameters())
        self.param_count = param_count
        self.vocab_size = len(self.model.tokenizer)

    def feed_canon(self, canon: str) -> Tuple[str, List[StepMeasurement], Dict]:
        """Feed the canon and return (response_text, steps, metrics)."""
        # Check how much space we have
        canon_tokens = len(self.model.tokenizer.encode(canon))
        gen_budget = self.context_limit - canon_tokens - 10
        gen_tokens = max(20, min(50, gen_budget))

        if gen_budget < 20:
            # Canon too long for context -- use a shorter excerpt
            # Take just the assumptions and first 3 primitives
            lines = canon.split('\n')
            short = '\n'.join(lines[:60])
            canon_tokens = len(self.model.tokenizer.encode(short))
            gen_budget = self.context_limit - canon_tokens - 10
            gen_tokens = max(20, min(50, gen_budget))
            canon = short

        self.history = [canon]
        result = self.model.generate(canon, max_tokens=gen_tokens, temperature=0.8)
        text = result.generated_text.strip()
        self.history.append(text)
        self.all_steps.extend(result.steps)

        metrics = compute_metrics(result.steps)
        self.init_metrics = metrics
        self.turn_metrics.append(metrics)

        return text, result.steps, metrics

    def chat(self, message: str) -> Tuple[str, List[StepMeasurement], Dict]:
        """Send a message and return (response_text, steps, metrics)."""
        self.history.append(message)

        # Build prompt from recent history -- keep within context
        prompt_parts = list(self.history)
        prompt = "\n".join(prompt_parts)
        prompt_tokens = len(self.model.tokenizer.encode(prompt))

        # Trim oldest entries if needed (but always keep canon = index 0)
        while prompt_tokens > self.context_limit - 60 and len(prompt_parts) > 2:
            prompt_parts.pop(1)  # remove oldest non-canon entry
            prompt = "\n".join(prompt_parts)
            prompt_tokens = len(self.model.tokenizer.encode(prompt))

        gen_tokens = min(40, max(15, self.context_limit - prompt_tokens - 10))

        result = self.model.generate(prompt, max_tokens=max(10, gen_tokens), temperature=0.8)
        text = result.generated_text.strip()
        self.history.append(text)
        self.all_steps.extend(result.steps)

        metrics = compute_metrics(result.steps)
        self.turn_metrics.append(metrics)

        return text, result.steps, metrics


class E0APIStarter:
    """Same interface as E0Starter, but uses an OpenAI-compatible API."""

    def __init__(self, api_key: str, model: str = "Qwen/Qwen2.5-7B-Instruct-Turbo",
                 base_url: str = None, system_prompt: str = None):
        from e0_middleware.api_wrapper import E0ChatClient
        self.client = E0ChatClient(
            api_key=api_key, model=model, base_url=base_url,
            e0_prime=True, logprobs=True, top_logprobs=5,
        )
        self.model_name = model
        self.api_key = api_key
        self.base_url = base_url
        self.history: List[str] = []
        self.turn_metrics: List[Dict] = []
        self.all_steps: List[StepMeasurement] = []
        self.init_metrics: Optional[Dict] = None
        self.is_api = True
        self.param_count = 0  # unknown for API models
        self.vocab_size = 0
        # Structural feedback loop state
        self._pending_feedback: Optional[str] = None
        self.feedback_enabled: bool = True
        self.last_feedback: Optional[str] = None  # for UI display
        # Topology state
        self.topology_loaded: bool = False
        self.topology_text: Optional[str] = None
        # Meta-feedback state
        self._topology_data: Optional[Dict] = None  # raw topology for adaptive feedback
        self._meta_trends: Optional[Dict] = None     # cross-session trend data
        self.meta_observation: Optional[str] = None   # meta-observation text
        # Self-recognition state
        self.self_recognition_done: bool = False
        self.self_recognition_results: Optional[List] = None

    def feed_canon(self, canon: str) -> Tuple[str, List[StepMeasurement], Dict]:
        """Feed the canon via API and return (response_text, steps, metrics).

        After feeding the canon, automatically injects the latest topology
        (structural weights from previous sessions) if available.
        This gives the model a pre-formed resistance landscape.
        """
        prompt = (
            "You have been given the E0 structural canon below. "
            "Read it carefully. Then respond IN ENGLISH with a brief structural "
            "continuation -- not a summary, but what follows from this "
            "structure. Stay within the framework. Always respond in English.\n\n"
            + canon
        )
        resp = self.client.chat(prompt)
        text = resp.text.strip()
        self.history = [canon, text]
        self.all_steps.extend(resp.steps)

        metrics = compute_metrics(resp.steps)
        self.init_metrics = metrics
        self.turn_metrics.append(metrics)

        # ── Inject topology (structural memory) after canon ──
        self._inject_topology_if_available()

        return text, resp.steps, metrics

    def _inject_topology_if_available(self, lang: str = 'en'):
        """Load and inject the latest topology as structural memory.

        Called once after canon feed. The topology tells the model
        which paths are already historized and which need exploration.
        This is the E₀ equivalent of loading pre-trained weights.
        """
        if self.topology_loaded:
            return
        try:
            from e0_topology import load_latest_topology, load_all_topologies, format_topology_for_injection
            topo = load_latest_topology()
            if topo is not None:
                topo_text = format_topology_for_injection(topo, lang=lang)
                self.client.inject_structural_feedback(topo_text)
                self.topology_loaded = True
                self.topology_text = topo_text
                self._topology_data = topo

                # Compute cross-session trends for adaptive feedback
                try:
                    topos = load_all_topologies()
                    if len(topos) >= 2:
                        self._meta_trends = compute_cross_session_trends(topos)
                except Exception:
                    pass

                # Inject meta-observation if available
                try:
                    meta = generate_meta_observation(topo, lang=lang)
                    if meta:
                        self.client.inject_structural_feedback(meta)
                        self.meta_observation = meta
                except Exception:
                    pass
        except Exception:
            pass  # Topology injection is non-critical

    def chat(self, message: str) -> Tuple[str, List[StepMeasurement], Dict]:
        """Send a message via API and return (response_text, steps, metrics).

        If structural feedback is pending from a previous response,
        it is injected as a system message before the user's message.
        This closes the loop: Canon → LLM → Response → Score → Feedback → next Turn.
        """
        # ── Inject pending feedback if available ──
        if self.feedback_enabled and self._pending_feedback:
            self.client.inject_structural_feedback(self._pending_feedback)
            self._pending_feedback = None

        self.history.append(message)
        resp = self.client.chat(message)
        text = resp.text.strip()
        self.history.append(text)
        self.all_steps.extend(resp.steps)

        metrics = compute_metrics(resp.steps)
        self.turn_metrics.append(metrics)

        return text, resp.steps, metrics

    def score_and_prepare_feedback(self, text: str, metrics: Dict, lang: str = 'en') -> Optional[str]:
        """Score the response and prepare adaptive feedback for the next turn.

        Uses topology-aware adaptive feedback when topology is loaded,
        falls back to standard feedback otherwise.

        Returns the feedback text (or None if not needed).
        Also stores it internally for automatic injection on next chat().
        """
        comp = score_e0_completeness(text)

        # Use adaptive feedback if topology is available
        if self._topology_data is not None:
            feedback = generate_adaptive_feedback(
                comp,
                topology=self._topology_data,
                meta_trends=self._meta_trends,
                lang=lang,
                include_metrics=metrics,
            )
        else:
            feedback = generate_structural_feedback(
                comp, lang=lang, include_metrics=metrics,
            )

        if feedback:
            self._pending_feedback = format_feedback_for_injection(feedback)
            self.last_feedback = feedback
        else:
            self._pending_feedback = None
            self.last_feedback = None
        return feedback

    def reset(self):
        """Reset the API client for re-initialization."""
        from e0_middleware.api_wrapper import E0ChatClient
        self.client = E0ChatClient(
            api_key=self.api_key, model=self.model_name,
            base_url=self.base_url, e0_prime=True,
            logprobs=True, top_logprobs=5,
        )
        self.history.clear()
        self.turn_metrics.clear()
        self.all_steps.clear()
        self.init_metrics = None
        self._pending_feedback = None
        self.last_feedback = None
        self.topology_loaded = False
        self.topology_text = None
        self._topology_data = None
        self._meta_trends = None
        self.meta_observation = None
        self.self_recognition_done = False
        self.self_recognition_results = None


# =============================================
#  The Main Flow
# =============================================

def run(model_name: str, device: str, lang: str, show_detail: bool,
       api_key: str = None, base_url: str = None):
    """Full initialization and chat flow."""
    g = GUIDANCE[lang]

    # Welcome
    print(g["welcome"])

    # Load canon
    canon = load_canon()

    # Load model or connect to API
    if api_key:
        print(f"  Connecting to API: {model_name} ...")
        t0 = time.time()
        starter = E0APIStarter(api_key, model=model_name, base_url=base_url)
        dt = time.time() - t0
        print(f"  API ready: {model_name}")
    else:
        print(g["loading"].format(model=model_name))
        t0 = time.time()
        starter = E0Starter(model_name, device=device)
        dt = time.time() - t0
        print(g["loaded"].format(
            params=f"{starter.param_count:,}",
            vocab=f"{starter.vocab_size:,}"
        ))
        print(f"  (loaded in {dt:.1f}s)")

    # Feed canon
    print(g["feeding"])
    t0 = time.time()
    text, steps, metrics = starter.feed_canon(canon)
    dt = time.time() - t0

    # Display response
    clean = ''.join(c if (c.isprintable() or c in ('\n', ' ')) else '' for c in text)
    display = clean[:200].replace('\n', ' ')
    if len(clean) > 200:
        display += "..."
    print(f"  Model says: {display}")

    # Interpret metrics
    r_level, r_explain = interpret_r(metrics["r"], lang)
    h_explain = interpret_h(metrics["h"], lang)
    phi_explain = interpret_phi(metrics["phi"], lang)
    v_explain = interpret_v(metrics["v"], lang)

    # Verdict
    if r_level in ("very_low", "low"):
        verdict = g["verdict_good"]
    elif r_level == "moderate":
        verdict = g["verdict_ok"]
    else:
        verdict = g["verdict_struggle"]

    print(g["init_result"].format(
        tau=metrics["tau"],
        r=metrics["r"], r_explain=r_explain,
        h=metrics["h"], h_explain=h_explain,
        phi=metrics["phi"], phi_explain=phi_explain,
        v=metrics["v"], v_explain=v_explain,
        verdict=verdict,
    ))

    if show_detail and steps:
        print(detailed_trace(steps))
        print()

    # ── Generate initial feedback for first chat turn ──
    if hasattr(starter, 'score_and_prepare_feedback'):
        starter.score_and_prepare_feedback(text, metrics, lang=lang)

    print(f"  (generated in {dt:.1f}s)")

    # Enter chat
    print(g["chat_header"])

    help_cmd = "/hilfe" if lang == "de" else "/help"
    again_cmd = "/nochmal" if lang == "de" else "/again"
    prev_r = metrics["r"]
    turn_num = 0

    while True:
        try:
            user_input = input("  You > ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n  Session ended.\n")
            break

        if not user_input:
            continue

        cmd = user_input.lower()

        if cmd == "/quit":
            print("\n  Session ended.\n")
            break

        if cmd in ("/help", "/hilfe"):
            print(g["help_text"])
            continue

        if cmd == "/detail":
            show_detail = not show_detail
            state = "ON" if show_detail else "OFF"
            print(f"  Token trace: {state}\n")
            continue

        if cmd in ("/again", "/nochmal"):
            print(g["re_init"])
            if starter.is_api:
                starter.reset()
            else:
                starter.history.clear()
                starter.turn_metrics.clear()
                starter.all_steps.clear()
            text, steps, metrics = starter.feed_canon(canon)
            clean = ''.join(c if (c.isprintable() or c in ('\n', ' ')) else '' for c in text)
            display = clean[:200].replace('\n', ' ')
            print(f"  Model says: {display}")
            print(format_signature(metrics))
            r_level, r_explain = interpret_r(metrics["r"], lang)
            print(f"  --> {r_explain}")
            prev_r = metrics["r"]
            turn_num = 0
            if show_detail and steps:
                print()
                print(detailed_trace(steps))
            print()
            continue

        if cmd == "/report":
            print(f"\n  {g['session_report_header']}")
            print(f"  Model: {model_name}")
            print(f"  Turns: {len(starter.turn_metrics)}")
            print(f"  Total tokens measured: {len(starter.all_steps)}")
            print()
            if starter.turn_metrics:
                print(f"  {'Turn':<6s} | R       | H       | Phi | v")
                print(f"  -------+---------+---------+-----+---------")
                labels = ["init"] + [f"  {i}" for i in range(1, len(starter.turn_metrics))]
                for label, m in zip(labels, starter.turn_metrics):
                    print(f"  {label:<6s} | {m['r']:.3f}   | {m['h']:.3f}   | {m['phi']:>3d} | {m['v']:.3f}")

                r_values = [m["r"] for m in starter.turn_metrics]
                if len(r_values) >= 2:
                    drops = sum(1 for j in range(1, len(r_values)) if r_values[j] < r_values[j-1])
                    total = len(r_values) - 1
                    print()
                    if drops > total / 2:
                        print(g["trajectory_improving"])
                    elif drops < total / 3:
                        print(g["trajectory_mixed"])
                    else:
                        print(g["trajectory_stable"])

                # R trajectory visualization
                print()
                max_r = max(r_values) if r_values else 1
                bar_width = 35
                for label, r in zip(labels, r_values):
                    bar_len = int((r / max_r) * bar_width) if max_r > 0 else 0
                    bar = "#" * bar_len
                    print(f"    {label:<6s} | {bar} {r:.3f}")
            print()
            continue

        # Regular message
        turn_num += 1
        try:
            text, steps, metrics = starter.chat(user_input)
        except Exception as e:
            print(f"  [Error] {e}\n")
            continue

        # Display response
        print()
        clean = ''.join(c if (c.isprintable() or c in ('\n', ' ')) else '' for c in text)
        words = clean.split()
        line = "  E0 > "
        for w in words:
            if len(line) + len(w) + 1 > 72:
                print(line)
                line = "       " + w
            else:
                line += (" " if not line.endswith(" ") else "") + w
        if line.strip():
            print(line)

        print()
        print(format_signature(metrics))

        # Contextual guidance
        r = metrics["r"]
        if turn_num == 1:
            print(g["turn_explain"]["first"])
        elif r < 0.3:
            print(g["turn_explain"]["r_freefall"])
        elif r < prev_r - 0.15:
            print(g["turn_explain"]["r_dropping"])
        elif r > prev_r + 0.15:
            print(g["turn_explain"]["r_rising"])
        else:
            print(g["turn_explain"]["r_stable"])
        prev_r = r

        if show_detail and steps:
            print()
            print(detailed_trace(steps))

        # ── Structural Feedback Loop ──
        if hasattr(starter, 'score_and_prepare_feedback'):
            feedback = starter.score_and_prepare_feedback(text, metrics, lang=lang)
            if feedback:
                print()
                print("  ┌── Structural Observation ──")
                for fb_line in feedback.split('\n'):
                    print(f"  │ {fb_line}")
                print("  └──────────────────────────")

        print()


# =============================================
#  Profile Runner (--profile mode)
# =============================================

def load_profile(path: str) -> Dict:
    """Load and validate a JSON initialization profile."""
    if not os.path.exists(path):
        print(f"  [ERROR] Profile not found: {path}")
        sys.exit(1)
    with open(path, encoding="utf-8") as f:
        profile = json.load(f)
    required = ["name", "model", "language", "canon_r_threshold", "primers",
                "readiness_r", "interface"]
    for key in required:
        if key not in profile:
            print(f"  [ERROR] Profile missing required field: {key}")
            sys.exit(1)
    return profile


def run_profile(profile_path: str, api_key: str = None, base_url: str = None,
                show_detail: bool = False, port: int = 3000):
    """Execute a full E0 initialization path from a profile.

    The path mirrors E0 itself:
      1. Load profile (state)
      2. Connect to model (path)
      3. Feed canon, check R <= threshold (difference -> transition -> verify)
      4. Feed each primer, check R <= threshold (historization sequence)
      5. Report readiness (rate > 0)
      6. Open interface

    Each step is structurally enforced. No step can be skipped.
    R gates ensure absorption before proceeding.
    """
    profile = load_profile(profile_path)
    lang = profile.get("language", "en")
    g = GUIDANCE.get(lang, GUIDANCE["en"])
    model_name = profile["model"]
    max_retries = 2

    # ── Step 0: Show the path ──
    n_primers = len(profile.get("primers", []))
    total_steps = 1 + n_primers  # canon + primers

    # If no API key, fall back to local model
    if not api_key and "/" in model_name:
        print(f"  [NOTE] No --api key provided. Profile model '{model_name}' requires API.")
        print(f"         Falling back to local GPT-2. Use --api KEY for the full profile.")
        print()
        model_name = "gpt2"

    print()
    print("  ================================================================")
    print(f"   E\u2080 INITIALIZATION PATH -- {profile['name']}")
    print("  ================================================================")
    if profile.get("description"):
        # Word-wrap description
        desc = profile["description"]
        words = desc.split()
        line = "   "
        for w in words:
            if len(line) + len(w) + 1 > 64:
                print(line)
                line = "   " + w
            else:
                line += (" " if len(line) > 3 else "") + w
        if line.strip():
            print(line)
    print()
    print(f"   Model:    {model_name}")
    print(f"   Language: {lang}")
    print(f"   Steps:    {total_steps} ({1} canon + {n_primers} domain primers)")
    print(f"   R\u0304 gates: canon \u2264 {profile['canon_r_threshold']}, "
          f"final \u2264 {profile['readiness_r']}")
    print("  ================================================================")
    print()

    # ── Step 1: Connect ──
    canon = load_canon()

    if api_key:
        print(f"  Connecting to {model_name}...")
        starter = E0APIStarter(api_key, model=model_name, base_url=base_url)
        print(f"  Connected.\n")
    else:
        print(f"  Loading {model_name}...")
        starter = E0Starter(model_name, device="cpu")
        print(f"  Loaded: {starter.param_count:,} parameters\n")

    # ── Step 2: Canon feed + R gate ──
    step_num = 1
    print(f"\n  [{step_num}/{total_steps}] Canon initialization...")
    print(f"       Feeding {len(canon.split())} words of E\u2080 canon...")

    for attempt in range(max_retries + 1):
        text, steps, metrics = starter.feed_canon(canon)
        r = metrics["r"]
        threshold = profile["canon_r_threshold"]
        passed = r <= threshold

        _, r_explain = interpret_r(r, lang)
        status = "\u2713 PASS" if passed else "\u2717 GATE"
        print(f"       R\u0304 = {r:.3f} (threshold: {threshold}) -- {status}")
        print(f"       {r_explain}")

        if show_detail and steps:
            print()
            print(detailed_trace(steps))
            print()

        if passed:
            break
        elif attempt < max_retries:
            print(f"       Retrying... ({attempt + 1}/{max_retries})")
            if starter.is_api:
                starter.reset()
            else:
                starter.history.clear()
                starter.turn_metrics.clear()
                starter.all_steps.clear()
        else:
            print(f"       R\u0304 above threshold after {max_retries + 1} attempts.")
            print(f"       Proceeding anyway -- system may need more follow-up.")

    # ── Step 2b: Structural Self-Recognition ──
    sr_enabled = profile.get("self_recognition", True)
    if sr_enabled:
        step_num += 1
        print(f"\n  [Self-Recognition] Structural identity init...")
        sr_results = run_self_recognition(starter, lang=lang, verbose=True)
        starter.self_recognition_done = True
        starter.self_recognition_results = sr_results

    # ── Step 3..N: Domain primers + R gates ──
    primers = profile.get("primers", [])
    primer_results = []

    for i, primer in enumerate(primers):
        step_num = i + 2
        name = primer.get("name", f"Primer {i + 1}")
        prompt = primer["prompt"]
        threshold = primer.get("r_threshold", 0.8)

        print(f"\n  [{step_num}/{total_steps}] {name}...")
        print(f"       Feeding {len(prompt.split())} words...")

        for attempt in range(max_retries + 1):
            text, steps, metrics = starter.chat(prompt)
            r = metrics["r"]
            passed = r <= threshold

            _, r_explain = interpret_r(r, lang)
            status = "\u2713 PASS" if passed else "\u2717 GATE"
            print(f"       R\u0304 = {r:.3f} (threshold: {threshold}) -- {status}")
            print(f"       {r_explain}")

            if show_detail and steps:
                print()
                print(detailed_trace(steps))
                print()

            if passed:
                break
            elif attempt < max_retries:
                print(f"       Retrying step...")
                # Re-chat the same primer
            else:
                print(f"       R\u0304 above threshold. Proceeding.")

        primer_results.append({
            "name": name, "r": r, "threshold": threshold,
            "passed": r <= threshold, "tau": metrics["tau"],
        })

    # ── Final: Readiness check ──
    all_r = [metrics["r"] for metrics in starter.turn_metrics]
    final_r = all_r[-1] if all_r else 999.0
    readiness_threshold = profile.get("readiness_r", 0.5)
    ready = final_r <= readiness_threshold

    print()
    print("  ================================================================")
    print(f"   INITIALIZATION {'COMPLETE' if ready else 'PARTIAL'}")
    print("  ================================================================")
    print()

    # Summary table
    print(f"   {'Step':<30s} | {'R\u0304':>7s} | {'Gate':>7s} | Status")
    print(f"   {'-' * 30}-+-{'-' * 7}-+-{'-' * 7}-+-{'-' * 8}")
    canon_r = starter.turn_metrics[0]["r"] if starter.turn_metrics else 0
    canon_pass = canon_r <= profile["canon_r_threshold"]
    print(f"   {'Canon':<30s} | {canon_r:7.3f} | {profile['canon_r_threshold']:7.3f} | "
          f"{'PASS' if canon_pass else 'OVER'}")
    for pr in primer_results:
        print(f"   {pr['name']:<30s} | {pr['r']:7.3f} | {pr['threshold']:7.3f} | "
              f"{'PASS' if pr['passed'] else 'OVER'}")
    print(f"   {'-' * 30}-+-{'-' * 7}-+-{'-' * 7}-+-{'-' * 8}")
    print(f"   {'FINAL':30s} | {final_r:7.3f} | {readiness_threshold:7.3f} | "
          f"{'READY' if ready else 'PARTIAL'}")

    # R trajectory
    if len(all_r) >= 2:
        print()
        max_r = max(all_r) if all_r else 1
        labels = ["canon"] + [pr["name"][:20] for pr in primer_results]
        for label, r in zip(labels, all_r):
            bar_len = int((r / max_r) * 30) if max_r > 0 else 0
            marker = "\u2588" * bar_len
            print(f"   {label:<22s} | {marker} {r:.3f}")

    print()
    if ready:
        passed_count = sum(1 for pr in primer_results if pr["passed"]) + (1 if canon_pass else 0)
        print(f"   \u2713 {passed_count}/{total_steps} steps passed R\u0304 gates.")
        print(f"   System is structurally initialized for: {profile['name']}")
    else:
        print(f"   System partially initialized. Final R\u0304 ({final_r:.3f}) "
              f"> threshold ({readiness_threshold}).")
        print(f"   The system may need additional follow-up in conversation.")
    print("  ================================================================")
    print()

    # ── Open interface ──
    interface = profile.get("interface", "web")
    if interface == "web":
        # Transition to web mode with the already-initialized starter
        _start_web_with_starter(starter, lang, show_detail, port)
    else:
        # Terminal chat mode
        _start_terminal_with_starter(starter, lang, show_detail)


def _start_web_with_starter(starter, lang, show_detail, port):
    """Start the web interface with an already-initialized starter."""
    global _web_starter, _web_lang, _web_init_data, _web_prev_r, _web_turn_num, _web_prev_text, _web_canon_text, _web_session_id, _web_transition_detector

    _web_starter = starter
    _web_lang = lang
    _web_session_id = None
    _web_prev_r = starter.turn_metrics[-1]["r"] if starter.turn_metrics else 0
    _web_prev_text = starter.history[-1] if starter.history else ""
    _web_canon_text = starter.history[0] if starter.history else ""
    _web_turn_num = len(starter.turn_metrics)

    # Initialize phase transition detector with canon D
    _web_transition_detector = LiveTransitionDetector()
    if _web_prev_text:
        canon_comp = score_e0_completeness(_web_prev_text)
        canon_r = starter.turn_metrics[-1]["r"] if starter.turn_metrics else 0
        _web_transition_detector.update(canon_comp['completeness'], canon_r)

    # Build init data from the last turn
    last_metrics = starter.turn_metrics[-1] if starter.turn_metrics else {"r": 0, "h": 0, "phi": 0, "v": 0, "tau": 0}
    r_level, r_text = interpret_r(last_metrics["r"], lang)
    h_text = interpret_h(last_metrics["h"], lang)
    phi_text = interpret_phi(last_metrics["phi"], lang)
    v_text = interpret_v(last_metrics["v"], lang)
    g = GUIDANCE[lang]
    if r_level in ("very_low", "low"):
        verdict = g["verdict_good"]
    elif r_level == "moderate":
        verdict = g["verdict_ok"]
    else:
        verdict = g["verdict_struggle"]

    backend_label = f"E\u2080 API ({starter.model_name})" if starter.is_api else f"E\u2080 Local ({starter.model_name})"
    init_text = f"[Profile initialization complete. {len(starter.turn_metrics)} steps executed.]"

    # Include topology info if loaded
    if hasattr(starter, 'topology_loaded') and starter.topology_loaded:
        init_text += "\n[Topology loaded — structural memory from previous sessions injected.]"

    nov = score_novelty(_web_prev_text) if _web_prev_text else {'novelty': 0, 'e0_operative': 0, 'qm_overlap': 0, 'structural_density': 0}
    comp = score_e0_completeness(_web_prev_text) if _web_prev_text else {'completeness': 0}
    _web_init_data = {
        "text": init_text,
        "metrics": last_metrics,
        "quality": {
            "novelty": nov['novelty'], "e0_operative": nov['e0_operative'],
            "qm_overlap": nov['qm_overlap'], "structural_density": nov['structural_density'],
            "coherence": 0.0, "term_overlap": 0.0, "forward_refs": 0,
            "completeness": comp['completeness'],
        },
        "interpretation": {
            "r": r_text, "h": h_text, "phi": phi_text, "v": v_text,
            "novelty": interpret_novelty(nov['novelty'], nov['e0_operative']),
            "coherence": "Initial response (no prior step)",
            "structural": interpret_structural_density(nov['structural_density']),
            "completeness": interpret_completeness(comp['completeness']),
        },
        "verdict": verdict.strip(),
        "trace": [],
        "help_text": g["help_text"].strip(),
        "backend": backend_label,
        "params": f"{starter.param_count:,}" if hasattr(starter, 'param_count') else "API",
        "topology": starter.topology_text if hasattr(starter, 'topology_text') else None,
    }

    server = HTTPServer(("0.0.0.0", port), E0StartHandler)
    url = f"http://localhost:{port}"

    print(f"  E\u2080 Web Interface: {url}")
    print(f"  Ctrl+C to stop")
    print()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n  Server stopped.\n")
        server.server_close()


def _start_terminal_with_starter(starter, lang, show_detail):
    """Start terminal chat with an already-initialized starter."""
    g = GUIDANCE[lang]
    print(g["chat_header"])

    prev_r = starter.turn_metrics[-1]["r"] if starter.turn_metrics else 0
    turn_num = len(starter.turn_metrics)

    while True:
        try:
            user_input = input("  You > ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n  Session ended.\n")
            break

        if not user_input:
            continue
        cmd = user_input.lower()
        if cmd == "/quit":
            print("\n  Session ended.\n")
            break
        if cmd in ("/help", "/hilfe"):
            print(g["help_text"])
            continue
        if cmd == "/report":
            report = build_report_data(starter, lang)
            print(f"\n{report['report']}\n")
            continue

        turn_num += 1
        try:
            text, steps, metrics = starter.chat(user_input)
        except Exception as e:
            print(f"  [Error] {e}\n")
            continue

        clean = _clean(text)
        words_list = clean.split()
        line = "  E0 > "
        for w in words_list:
            if len(line) + len(w) + 1 > 72:
                print(line)
                line = "       " + w
            else:
                line += (" " if not line.endswith(" ") else "") + w
        if line.strip():
            print(line)

        print()
        print(format_signature(metrics))

        r = metrics["r"]
        if r < 0.3:
            print(g["turn_explain"]["r_freefall"])
        elif r < prev_r - 0.15:
            print(g["turn_explain"]["r_dropping"])
        elif r > prev_r + 0.15:
            print(g["turn_explain"]["r_rising"])
        else:
            print(g["turn_explain"]["r_stable"])
        prev_r = r

        if show_detail and steps:
            print()
            print(detailed_trace(steps))
        print()


# =============================================
#  Web Interface (--web mode)
# =============================================

def _clean(text):
    """Remove unprintable characters for display."""
    return ''.join(c if (c.isprintable() or c in ('\n', ' ')) else '' for c in text)


def build_trace_data(steps: List[StepMeasurement]) -> list:
    """Build JSON-serializable trace data from generation steps."""
    if not steps:
        return []
    deltas = [abs(s.delta_entropy) for s in steps]
    d_mean = sum(deltas) / len(deltas)
    d_std = (sum((d - d_mean) ** 2 for d in deltas) / len(deltas)) ** 0.5 if len(deltas) >= 3 else 0
    threshold = d_mean + d_std if d_std > 1e-10 else float('inf')
    trace = []
    for s in steps:
        raw = s.selected.token.replace('\n', '\u21b5').replace('\r', '').replace('\t', '\u2192')
        tok = ''.join(
            c if (c.isprintable() and c != '\ufffd') or c in ('\u21b5', '\u2192') else '\u00b7'
            for c in raw
        )
        v = s.selected.rate
        trace.append({
            "tau": s.tau, "token": tok[:20],
            "r": round(s.selected.resistance, 4),
            "v": round(min(v, 99999), 4),
            "h": round(s.entropy, 4),
            "dh": round(s.delta_entropy, 4),
            "phase": abs(s.delta_entropy) > threshold,
        })
    return trace


def build_init_data(text, steps, metrics, lang, starter):
    """Build the initialization data packet for the web UI."""
    text = _clean(text)
    r_level, r_text = interpret_r(metrics["r"], lang)
    h_text = interpret_h(metrics["h"], lang)
    phi_text = interpret_phi(metrics["phi"], lang)
    v_text = interpret_v(metrics["v"], lang)

    # Quality scores for init response
    nov = score_novelty(text)
    # No previous text for coherence at init
    coh_score = {'coherence': 0.0, 'term_overlap': 0.0, 'forward_refs': 0}
    comp_score = score_e0_completeness(text)

    g = GUIDANCE[lang]
    if r_level in ("very_low", "low"):
        verdict = g["verdict_good"]
    elif r_level == "moderate":
        verdict = g["verdict_ok"]
    else:
        verdict = g["verdict_struggle"]
    return {
        "text": text,
        "metrics": metrics,
        "quality": {
            "novelty": nov['novelty'],
            "e0_operative": nov['e0_operative'],
            "qm_overlap": nov['qm_overlap'],
            "structural_density": nov['structural_density'],
            "coherence": coh_score['coherence'],
            "term_overlap": coh_score['term_overlap'],
            "forward_refs": coh_score['forward_refs'],
            "completeness": comp_score['completeness'],
        },
        "interpretation": {
            "r": r_text, "h": h_text, "phi": phi_text, "v": v_text,
            "novelty": interpret_novelty(nov['novelty'], nov['e0_operative']),
            "coherence": "Initial response (no prior step)",
            "structural": interpret_structural_density(nov['structural_density']),
            "completeness": interpret_completeness(comp_score['completeness']),
        },
        "verdict": verdict.strip(),
        "trace": build_trace_data(steps),
        "help_text": g["help_text"].strip(),
        "backend": f"E\u2080 Local ({starter.model_name})",
        "params": f"{starter.param_count:,}",
    }


def build_report_data(starter, lang):
    """Build session report data for the web UI."""
    g = GUIDANCE[lang]
    lines = [g["session_report_header"].strip(), f"Model: {starter.model_name}",
             f"Turns: {len(starter.turn_metrics)}",
             f"Total tokens: {len(starter.all_steps)}", ""]
    if starter.turn_metrics:
        lines.append(f"{'Turn':<6s} | R       | H       | Phi | v")
        lines.append(f"-------+---------+---------+-----+---------")
        labels = ["init"] + [f"  {i}" for i in range(1, len(starter.turn_metrics))]
        for label, m in zip(labels, starter.turn_metrics):
            lines.append(f"{label:<6s} | {m['r']:.3f}   | {m['h']:.3f}   | {m['phi']:>3d} | {m['v']:.3f}")
        r_values = [m["r"] for m in starter.turn_metrics]
        if len(r_values) >= 2:
            drops = sum(1 for j in range(1, len(r_values)) if r_values[j] < r_values[j - 1])
            total = len(r_values) - 1
            lines.append("")
            if drops > total / 2:
                lines.append(g["trajectory_improving"].strip())
            elif drops < total / 3:
                lines.append(g["trajectory_mixed"].strip())
            else:
                lines.append(g["trajectory_stable"].strip())
        if r_values:
            lines.append("")
            max_r = max(r_values)
            for label, r in zip(labels, r_values):
                bar_len = int((r / max_r) * 30) if max_r > 0 else 0
                lines.append(f"  {label:<6s} | {'#' * bar_len} {r:.3f}")

    # Quality section — compute from stored response history
    responses = [h for i, h in enumerate(starter.history) if i % 2 == 1]  # even=prompts, odd=responses
    if responses:
        lines.append("")
        lines.append("─── Quality Scores ───")
        lines.append(f"{'Turn':<6s} | Novelty | E₀ Op  | Coherence | Complete")
        lines.append(f"-------+---------+--------+-----------+---------")
        prev = ""
        for i, resp in enumerate(responses):
            label = "init" if i == 0 else f"  {i}"
            nov = score_novelty(resp)
            coh = score_coherence(prev, resp)
            comp = score_e0_completeness(resp)
            prev = resp
            lines.append(f"{label:<6s} | {nov['novelty']:.3f}   | {nov['e0_operative']:.3f}  | {coh['coherence']:.3f}     | {comp['completeness']:.3f}")

    return {"report": "\n".join(lines)}


# -- Web server state --
_web_starter = None
_web_lang = "en"
_web_init_data = None
_web_prev_r = 0.0
_web_turn_num = 0
_web_prev_text = ""  # previous response text for coherence scoring
_web_session_id = None  # current session ID (set on first save)
_web_canon_text = ""   # canon text for session hashing
_web_transition_detector = LiveTransitionDetector()  # phase transition tracking
_web_protocol = None  # SessionProtocol instance — eigenstate, phase, semantic health
_web_lock = threading.Lock()


def _rebuild_chat_history():
    """Rebuild displayable chat history from starter state for session restore."""
    entries = []
    if not _web_starter or not _web_starter.history:
        return entries
    # history[0] = canon, history[1] = init response
    # history[2] = user msg 1, history[3] = response 1, ...
    prev_text = ""
    for i in range(2, len(_web_starter.history), 2):
        user_msg = _web_starter.history[i] if i < len(_web_starter.history) else ""
        resp_text = _web_starter.history[i + 1] if i + 1 < len(_web_starter.history) else ""
        metric_idx = (i // 2)  # turn 1 = index 1 in turn_metrics
        metrics = _web_starter.turn_metrics[metric_idx] if metric_idx < len(_web_starter.turn_metrics) else None

        # Recompute interpretation and quality so session-load shows scores
        interpretation = None
        quality = None
        if metrics:
            _, r_text = interpret_r(metrics["r"], _web_lang)
            h_text = interpret_h(metrics["h"], _web_lang)
            phi_text = interpret_phi(metrics["phi"], _web_lang)
            v_text = interpret_v(metrics["v"], _web_lang)
            nov = score_novelty(resp_text)
            coh = score_coherence(prev_text, resp_text)
            comp = score_e0_completeness(resp_text)
            interpretation = {
                "r": r_text, "h": h_text, "phi": phi_text, "v": v_text,
                "novelty": interpret_novelty(nov['novelty'], nov['e0_operative']),
                "coherence": interpret_coherence(coh['coherence']),
                "structural": interpret_structural_density(nov['structural_density']),
                "completeness": interpret_completeness(comp['completeness']),
            }
            quality = {
                "novelty": nov['novelty'],
                "e0_operative": nov['e0_operative'],
                "qm_overlap": nov['qm_overlap'],
                "structural_density": nov['structural_density'],
                "coherence": coh['coherence'],
                "term_overlap": coh['term_overlap'],
                "forward_refs": coh['forward_refs'],
                "completeness": comp['completeness'],
            }
        prev_text = resp_text

        entries.append({
            "user": user_msg,
            "response": resp_text,
            "metrics": metrics,
            "interpretation": interpretation,
            "quality": quality,
        })
    return entries


class E0StartHandler(BaseHTTPRequestHandler):
    """HTTP handler for E0 Start web interface."""

    def log_message(self, fmt, *args):
        pass

    def _json(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _html(self, html):
        body = html.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            self._html(HTML_START_PAGE)
        elif self.path == "/init":
            self._json(_web_init_data)
        elif self.path == "/init-modules":
            self._json({"modules": list_modules_for_ui(_web_lang)})
        elif self.path == "/protocol/status":
            self._handle_protocol_status()
        else:
            self.send_error(404)

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length) if length else b"{}"
        try:
            body = json.loads(raw.decode('utf-8'))
        except UnicodeDecodeError:
            body = json.loads(raw.decode('latin-1'))
        except json.JSONDecodeError:
            body = {}
        if self.path == "/chat":
            self._handle_chat(body)
        elif self.path == "/clear":
            self._handle_clear()
        elif self.path == "/report":
            self._handle_report()
        elif self.path == "/session/save":
            self._handle_save_session()
        elif self.path == "/session/list":
            self._handle_list_sessions()
        elif self.path == "/session/load":
            self._handle_load_session(body)
        elif self.path == "/session/delete":
            self._handle_delete_session(body)
        elif self.path == "/init-module/run":
            self._handle_run_init_module(body)
        elif self.path == "/reflect":
            self._handle_reflect(body)
        elif self.path == "/protocol/validate":
            self._handle_validate_init()
        elif self.path == "/protocol/semantic-probe":
            self._handle_semantic_probe()
        else:
            self.send_error(404)

    def _handle_chat(self, body):
        global _web_prev_r, _web_turn_num, _web_prev_text
        message = body.get("message", "").strip()
        if not message:
            self._json({"error": "empty message"}, 400)
            return
        with _web_lock:
            # ── Session Protocol: check eigenstate formation ──
            if _web_protocol and not _web_protocol.eigenstate.is_external_input_allowed():
                self._json({
                    "error": "Eigenstate not yet formed. Run Canon + Identity modules first.",
                    "protocol": _web_protocol.status(),
                }, 403)
                return
            # ── Session Protocol: check phase allows chat ──
            if _web_protocol and _web_protocol.phase.is_reflecting():
                remaining = _web_protocol.phase.MIN_REFLECT_COUNT - _web_protocol.phase.reflect_count
                if remaining > 0:
                    self._json({
                        "error": f"Reflecting phase active. {remaining} more reflect(s) needed before chat.",
                        "protocol": _web_protocol.status(),
                    }, 403)
                    return
                else:
                    # Min reflects met — auto-exit reflecting
                    _web_protocol.end_reflecting()
            try:
                text, steps, metrics = _web_starter.chat(message)
                text = _clean(text)
                _web_turn_num += 1
                _, r_text = interpret_r(metrics["r"], _web_lang)
                h_text = interpret_h(metrics["h"], _web_lang)
                phi_text = interpret_phi(metrics["phi"], _web_lang)
                v_text = interpret_v(metrics["v"], _web_lang)

                # Quality scores
                nov = score_novelty(text)
                coh = score_coherence(_web_prev_text, text)
                comp = score_e0_completeness(text)
                _web_prev_text = text

                g = GUIDANCE[_web_lang]["turn_explain"]
                r = metrics["r"]
                if _web_turn_num == 1:
                    guidance = g["first"]
                elif r < 0.3:
                    guidance = g["r_freefall"]
                elif r < _web_prev_r - 0.15:
                    guidance = g["r_dropping"]
                elif r > _web_prev_r + 0.15:
                    guidance = g["r_rising"]
                else:
                    guidance = g["r_stable"]
                _web_prev_r = r
                # ── Structural Feedback Loop ──
                feedback_data = {'text': '', 'html': '', 'level': None}
                if hasattr(_web_starter, 'score_and_prepare_feedback'):
                    fb_text = _web_starter.score_and_prepare_feedback(
                        text, metrics, lang='en',
                    )
                    if fb_text:
                        feedback_data = format_feedback_for_display(fb_text, lang=_web_lang)

                # ── Phase Transition Detection ──
                transition_event = _web_transition_detector.update(
                    comp['completeness'], metrics['r'],
                    feedback_injected=bool(feedback_data.get('level')),
                )
                transition_data = None
                if transition_event:
                    transition_data = {
                        'type': transition_event.type,
                        'turn': transition_event.turn,
                        'd_before': transition_event.d_before,
                        'd_after': transition_event.d_after,
                        'delta_d': transition_event.delta_d,
                        'magnitude': transition_event.magnitude,
                        'interpretation': interpret_transition(transition_event),
                    }

                self._json({
                    "text": text, "metrics": metrics,
                    "quality": {
                        "novelty": nov['novelty'],
                        "e0_operative": nov['e0_operative'],
                        "qm_overlap": nov['qm_overlap'],
                        "structural_density": nov['structural_density'],
                        "coherence": coh['coherence'],
                        "term_overlap": coh['term_overlap'],
                        "forward_refs": coh['forward_refs'],
                        "completeness": comp['completeness'],
                    },
                    "interpretation": {
                        "r": r_text, "h": h_text, "phi": phi_text,
                        "v": v_text, "guidance": guidance.strip(),
                        "novelty": interpret_novelty(nov['novelty'], nov['e0_operative']),
                        "coherence": interpret_coherence(coh['coherence']),
                        "structural": interpret_structural_density(nov['structural_density']),
                        "completeness": interpret_completeness(comp['completeness']),
                    },
                    "trace": build_trace_data(steps),
                    "feedback": feedback_data,
                    "transition": transition_data,
                })
            except Exception as e:
                self._json({"error": str(e)}, 500)

    def _handle_clear(self):
        global _web_init_data, _web_prev_r, _web_turn_num, _web_prev_text, _web_session_id, _web_transition_detector, _web_protocol
        with _web_lock:
            _web_session_id = None  # new session on re-init
            if _web_starter.is_api:
                _web_starter.reset()
            else:
                _web_starter.history.clear()
                _web_starter.turn_metrics.clear()
                _web_starter.all_steps.clear()

            # Reset session protocol
            if _web_protocol:
                _web_protocol.reset()
            canon = load_canon()
            text, steps, metrics = _web_starter.feed_canon(canon)
            _web_prev_r = metrics["r"]
            _web_turn_num = 0
            _web_prev_text = _clean(text)
            _web_starter.self_recognition_done = False
            _web_starter.self_recognition_results = []

            # Reset phase transition detector with canon D
            _web_transition_detector = LiveTransitionDetector()
            canon_comp = score_e0_completeness(_web_prev_text)
            _web_transition_detector.update(canon_comp['completeness'], metrics['r'])

            # Prepare feedback for first chat turn (always English for LLM)
            if hasattr(_web_starter, 'score_and_prepare_feedback'):
                _web_starter.score_and_prepare_feedback(_web_prev_text, metrics, lang='en')
            _web_init_data = build_init_data(_web_prev_text, steps, metrics, _web_lang, _web_starter)
        self._json(_web_init_data)

    def _handle_report(self):
        with _web_lock:
            report = build_report_data(_web_starter, _web_lang)
        self._json(report)

    def _handle_save_session(self):
        global _web_session_id
        try:
            with _web_lock:
                data = build_session_data(
                    _web_starter, _web_canon_text,
                    session_id=_web_session_id,
                )
                filepath = save_session(data)
                _web_session_id = data["session_id"]
            self._json({
                "session_id": data["session_id"],
                "filepath": str(filepath),
                "turns": data["observations"]["total_turns"],
                "tokens": data["observations"]["total_tokens"],
            })
        except Exception as e:
            import traceback
            traceback.print_exc()
            self._json({"error": str(e)}, 500)

    def _handle_list_sessions(self):
        sessions = list_sessions()
        self._json({"sessions": sessions})

    def _handle_load_session(self, body):
        global _web_init_data, _web_prev_r, _web_turn_num, _web_prev_text, _web_session_id
        filepath = body.get("filepath", "").strip()
        if not filepath:
            self._json({"error": "no filepath"}, 400)
            return
        try:
            from pathlib import Path
            session_data = load_session(Path(filepath))
        except Exception as e:
            self._json({"error": f"Load failed: {e}"}, 400)
            return
        issues = verify_session_integrity(session_data)
        with _web_lock:
            # Reset starter before restoring
            if _web_starter.is_api:
                _web_starter.reset()
            else:
                _web_starter.history.clear()
                _web_starter.turn_metrics.clear()
                _web_starter.all_steps.clear()
            info = restore_starter_state(_web_starter, session_data, _web_canon_text)
            _web_session_id = session_data["session_id"]
            # Rebuild web globals from restored state
            if _web_starter.turn_metrics:
                _web_prev_r = _web_starter.turn_metrics[-1]["r"]
            else:
                _web_prev_r = 0.0
            _web_turn_num = max(0, len(_web_starter.turn_metrics) - 1)
            _web_prev_text = _web_starter.history[-1] if _web_starter.history else ""
            # Rebuild init data from first response
            if len(_web_starter.history) >= 2 and _web_starter.turn_metrics:
                init_text = _web_starter.history[1]  # first response after canon
                init_metrics = _web_starter.turn_metrics[0]
                _web_init_data = {
                    "text": init_text,
                    "metrics": init_metrics,
                    "quality": {},
                    "interpretation": {},
                    "verdict": "",
                    "trace": [],
                    "help_text": GUIDANCE[_web_lang]["help_text"].strip(),
                    "backend": f"E\u2080 ({_web_starter.model_name})",
                    "params": "restored",
                }
        self._json({
            "status": "restored",
            "session_id": _web_session_id,
            "info": info,
            "issues": issues,
            "history": _rebuild_chat_history(),
        })

    def _handle_delete_session(self, body):
        filepath = body.get("filepath", "").strip()
        if not filepath:
            self._json({"error": "no filepath"}, 400)
            return
        from pathlib import Path
        ok = delete_session(Path(filepath))
        self._json({"deleted": ok})

    def _handle_run_init_module(self, body):
        global _web_prev_r, _web_turn_num, _web_prev_text
        module_id = body.get("module_id", "").strip()
        if not module_id:
            self._json({"error": "no module_id"}, 400)
            return
        with _web_lock:
            # ── Session Protocol: check phase allows modules ──
            if _web_protocol and not _web_protocol.phase.can_run_module():
                self._json({
                    "error": "Cannot run modules during reflecting phase. "
                             "Complete the reflect chain first.",
                    "protocol": _web_protocol.status(),
                }, 403)
                return
            try:
                result = run_init_module(_web_starter, module_id, lang=_web_lang)
                if 'error' in result:
                    self._json(result, 400)
                    return
                _web_prev_r = result['r']
                _web_prev_text = result.get('text', '')[:200]
                _web_turn_num = len(_web_starter.turn_metrics)

                # ── Session Protocol: track formation ──
                if _web_protocol:
                    d_score = result.get('d', 0.0)
                    _web_protocol.module_completed(module_id, d_score)

                # Compute interpretation + quality for display
                text = result['text']
                metrics = result['metrics']
                _, r_text = interpret_r(metrics["r"], _web_lang)
                h_text = interpret_h(metrics["h"], _web_lang)
                phi_text = interpret_phi(metrics["phi"], _web_lang)
                v_text = interpret_v(metrics["v"], _web_lang)
                nov = score_novelty(text)
                coh = score_coherence('', text)
                comp = score_e0_completeness(text)

                result['interpretation'] = {
                    "r": r_text, "h": h_text, "phi": phi_text, "v": v_text,
                    "novelty": interpret_novelty(nov['novelty'], nov['e0_operative']),
                    "coherence": interpret_coherence(coh['coherence']),
                    "structural": interpret_structural_density(nov['structural_density']),
                    "completeness": interpret_completeness(comp['completeness']),
                }
                result['quality'] = {
                    "novelty": nov['novelty'],
                    "e0_operative": nov['e0_operative'],
                    "qm_overlap": nov['qm_overlap'],
                    "structural_density": nov['structural_density'],
                    "coherence": coh['coherence'],
                    "term_overlap": coh['term_overlap'],
                    "forward_refs": coh['forward_refs'],
                    "completeness": comp['completeness'],
                }
                result['trace'] = build_trace_data(
                    _web_starter.all_steps[-metrics['tau']:]
                    if metrics.get('tau') and len(_web_starter.all_steps) >= metrics['tau']
                    else []
                )
                # ── Session Protocol: include status in response ──
                if _web_protocol:
                    result['protocol'] = _web_protocol.status()
                self._json(result)
            except Exception as e:
                self._json({"error": str(e)}, 500)

    def _handle_reflect(self, body):
        """Generate a reflection prompt and send it as a chat message.

        Session Protocol integration:
        - Enters 'reflecting' phase on first reflect
        - Records each reflect
        - Runs semantic health probe when reflect chain ends
        """
        global _web_prev_r, _web_turn_num, _web_prev_text
        mode = body.get("mode", "generate")  # "generate" or "status"
        with _web_lock:
            # ── Session Protocol: check phase allows reflects ──
            if _web_protocol and not _web_protocol.phase.can_reflect():
                self._json({
                    "error": "Cannot reflect during init phase. "
                             "Complete formation modules first.",
                    "protocol": _web_protocol.status(),
                }, 403)
                return

            # ── Session Protocol: enter reflecting phase if not already ──
            if _web_protocol and not _web_protocol.phase.is_reflecting():
                try:
                    _web_protocol.start_reflecting()
                except ValueError as e:
                    self._json({"error": str(e)}, 403)
                    return

            # Get full last response from history
            last_text = ""
            if _web_starter.history:
                last_text = _web_starter.history[-1]
            if not last_text:
                self._json({"error": "No previous response to reflect on"}, 400)
                return

            if mode == "status":
                status = get_reflection_status(last_text)
                if _web_protocol:
                    status['protocol'] = _web_protocol.status()
                self._json(status)
                return

            # Generate & execute reflection
            # Two-timescale bridge: pass topology (slow) and D trajectory (intra-session)
            topo_data = getattr(_web_starter, '_topology_data', None)
            d_traj = list(_web_transition_detector.d_history) if _web_transition_detector.d_history else None
            prompt, missing, d_before = generate_reflection_prompt(
                last_text,
                topology=topo_data,
                d_trajectory=d_traj,
            )
            if not prompt:
                self._json({
                    "error": "All elements operative (D=1.0) — no reflection needed",
                    "d": d_before,
                })
                return

            try:
                text, steps, metrics = _web_starter.chat(prompt)
                text = _clean(text)
                _web_turn_num += 1
                _web_prev_text = text[:200]

                # Score the reflection response
                nov = score_novelty(text)
                coh = score_coherence('', text)
                comp = score_e0_completeness(text)

                _, r_text = interpret_r(metrics["r"], _web_lang)
                h_text = interpret_h(metrics["h"], _web_lang)
                phi_text = interpret_phi(metrics["phi"], _web_lang)
                v_text = interpret_v(metrics["v"], _web_lang)

                # Feedback
                feedback_data = {'text': '', 'html': '', 'level': None}
                if hasattr(_web_starter, 'score_and_prepare_feedback'):
                    fb_text = _web_starter.score_and_prepare_feedback(
                        text, metrics, lang='en',
                    )
                    if fb_text:
                        feedback_data = format_feedback_for_display(fb_text, lang=_web_lang)

                # Phase transition
                transition_event = _web_transition_detector.update(
                    comp['completeness'], metrics['r'],
                    feedback_injected=bool(feedback_data.get('level')),
                )
                transition_data = None
                if transition_event:
                    transition_data = {
                        'type': transition_event.type,
                        'turn': transition_event.turn,
                        'd_before': transition_event.d_before,
                        'd_after': transition_event.d_after,
                        'delta_d': transition_event.delta_d,
                        'magnitude': transition_event.magnitude,
                        'interpretation': interpret_transition(transition_event),
                    }

                # Reflection-specific: what was targeted, what improved?
                d_after = comp['completeness']
                new_status = get_reflection_status(text)

                # ── Session Protocol: record reflect ──
                protocol_data = None
                if _web_protocol:
                    _web_protocol.record_reflect(d_after)
                    protocol_data = _web_protocol.status()

                # Bridge info for diagnostics
                bridge_info = {
                    'topology_available': topo_data is not None,
                    'd_trajectory_length': len(d_traj) if d_traj else 0,
                }
                if d_traj and len(d_traj) >= 4:
                    first_half = d_traj[:len(d_traj)//2]
                    second_half = d_traj[len(d_traj)//2:]
                    bridge_info['floor_rising'] = min(second_half) > min(first_half) + 0.05
                    bridge_info['phase'] = 'inhale' if d_traj[-1] < d_traj[-2] else 'exhale'

                self._json({
                    "text": text,
                    "metrics": metrics,
                    "reflection": {
                        "prompt": prompt,
                        "targeted": missing,
                        "d_before": round(d_before, 3),
                        "d_after": round(d_after, 3),
                        "delta_d": round(d_after - d_before, 3),
                        "still_missing": new_status['missing'],
                        "bridge": bridge_info,
                    },
                    "quality": {
                        "novelty": nov['novelty'],
                        "e0_operative": nov['e0_operative'],
                        "qm_overlap": nov['qm_overlap'],
                        "structural_density": nov['structural_density'],
                        "coherence": coh['coherence'],
                        "term_overlap": coh['term_overlap'],
                        "forward_refs": coh['forward_refs'],
                        "completeness": comp['completeness'],
                    },
                    "interpretation": {
                        "r": r_text, "h": h_text, "phi": phi_text,
                        "v": v_text,
                        "novelty": interpret_novelty(nov['novelty'], nov['e0_operative']),
                        "coherence": interpret_coherence(coh['coherence']),
                        "structural": interpret_structural_density(nov['structural_density']),
                        "completeness": interpret_completeness(comp['completeness']),
                    },
                    "trace": build_trace_data(steps),
                    "feedback": feedback_data,
                    "transition": transition_data,
                    "protocol": protocol_data,
                })
            except Exception as e:
                self._json({"error": str(e)}, 500)

    # ── Session Protocol endpoints ──

    def _handle_protocol_status(self):
        """GET /protocol/status — Return current session protocol state."""
        if _web_protocol:
            self._json(_web_protocol.status())
        else:
            self._json({"error": "Protocol not initialized"}, 500)

    def _handle_validate_init(self):
        """POST /protocol/validate — Run post-init semantic validation."""
        with _web_lock:
            if not _web_protocol:
                self._json({"error": "Protocol not initialized"}, 500)
                return
            if not _web_protocol.eigenstate.eigenstate_formed:
                self._json({
                    "error": "Cannot validate: eigenstate not formed. "
                             "Run Canon + Identity first.",
                    "protocol": _web_protocol.status(),
                }, 403)
                return
            try:
                result = validate_init(_web_starter)
                _web_protocol.init_validation_result = result
                result['protocol'] = _web_protocol.status()
                self._json(result)
            except Exception as e:
                self._json({"error": str(e)}, 500)

    def _handle_semantic_probe(self):
        """POST /protocol/semantic-probe — Run a semantic health probe."""
        with _web_lock:
            if not _web_protocol:
                self._json({"error": "Protocol not initialized"}, 500)
                return
            try:
                result = _web_protocol.run_semantic_probe(_web_starter)
                result['protocol'] = _web_protocol.status()
                self._json(result)
            except Exception as e:
                self._json({"error": str(e)}, 500)


HTML_START_PAGE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>E&#x2080; Start</title>
<style>
:root {
  --bg: #0a0a0f; --surface: #12121a; --border: #1e1e2e;
  --text: #c8c8d8; --dim: #6a6a7a; --accent: #7aa2f7;
  --human: #9ece6a; --phase: #f7768e; --metric: #bb9af7;
  --guidance: #e0af68;
}
* { margin:0; padding:0; box-sizing:border-box; }
body {
  background: var(--bg); color: var(--text);
  font-family: 'JetBrains Mono','Fira Code','Consolas', monospace;
  font-size: 14px; line-height: 1.6;
  display: flex; flex-direction: column; height: 100vh;
}

/* ── Header ── */
header {
  padding: 16px 24px; border-bottom: 1px solid var(--border);
  display: flex; align-items: center; justify-content: space-between; flex-shrink: 0;
}
header h1 { font-size: 16px; font-weight: 400; color: var(--accent); letter-spacing: 2px; }
header .info { font-size: 12px; color: var(--dim); }
header .actions button {
  background: var(--surface); border: 1px solid var(--border); color: var(--dim);
  padding: 4px 12px; margin-left: 8px; cursor: pointer;
  font-family: inherit; font-size: 12px; border-radius: 3px;
  transition: color 0.2s, border-color 0.2s;
}
header .actions button:hover { color: var(--accent); border-color: var(--accent); }

/* ── Chat ── */
#chat {
  flex: 1; overflow-y: auto; padding: 24px;
  display: flex; flex-direction: column; gap: 16px;
}
.msg { max-width: 780px; width: 100%; }
.msg.human .role { color: var(--human); }
.msg.e0 .role    { color: var(--accent); }
.role { font-size: 11px; text-transform: uppercase; letter-spacing: 1.5px; margin-bottom: 4px; }
.body {
  padding: 12px 16px; background: var(--surface);
  border: 1px solid var(--border); border-radius: 4px;
  white-space: pre-wrap; word-wrap: break-word;
}
.msg.human .body { border-left: 2px solid var(--human); }
.msg.e0 .body    { border-left: 2px solid var(--accent); }

/* ── Interpretation ── */
.interp {
  margin-top: 6px; padding: 8px 12px; font-size: 12px;
  background: rgba(187,154,247,0.04); border-radius: 3px;
}
.interp .row { display: flex; gap: 10px; align-items: baseline; padding: 2px 0; }
.interp .lbl { color: var(--metric); min-width: 18px; font-weight: 600; }
.interp .val { color: var(--metric); min-width: 48px; font-variant-numeric: tabular-nums; }
.interp .expl { color: var(--dim); font-size: 11px; }

/* ── Guidance ── */
.guidance {
  margin-top: 6px; padding: 6px 12px; font-size: 12px;
  color: var(--guidance); border-left: 2px solid var(--guidance);
  background: rgba(224,175,104,0.04); border-radius: 0 3px 3px 0;
}

/* ── Structural Feedback ── */
.feedback {
  margin-top: 10px; border: 1px solid rgba(247,118,142,0.2);
  border-radius: 4px; overflow: hidden;
  background: rgba(247,118,142,0.03);
}
.feedback.gentle { border-color: rgba(224,175,104,0.25); background: rgba(224,175,104,0.03); }
.feedback-toggle {
  padding: 6px 12px; font-size: 11px; color: var(--phase);
  cursor: pointer; user-select: none; display: flex;
  align-items: center; gap: 6px;
}
.feedback.gentle .feedback-toggle { color: var(--guidance); }
.feedback-toggle:hover { opacity: 0.8; }
.feedback-toggle .arrow { transition: transform 0.2s; display: inline-block; }
.feedback-toggle .arrow.open { transform: rotate(90deg); }
.feedback-body { display: none; padding: 8px 14px; font-size: 12px; }
.feedback-body.open { display: block; }
.fb-header { color: var(--phase); font-weight: 600; margin-bottom: 4px; font-size: 12px; }
.feedback.gentle .fb-header { color: var(--guidance); }
.fb-metric { color: var(--metric); font-variant-numeric: tabular-nums; margin: 2px 0; }
.fb-section { color: var(--dim); margin-top: 6px; margin-bottom: 2px; font-weight: 600; }
.fb-primitive { padding: 1px 0 1px 12px; display: flex; gap: 8px; }
.fb-name { color: var(--text); }
.fb-status { color: var(--dim); font-style: italic; }
.fb-primitive.fb-operative .fb-status { color: var(--human); }
.fb-primitive.fb-semi .fb-status { color: var(--guidance); }
.fb-primitive.fb-label .fb-status { color: var(--dim); }
.fb-primitive.fb-absent .fb-name { color: var(--phase); opacity: 0.7; }
.fb-nudge { color: var(--text); opacity: 0.85; margin-top: 6px; line-height: 1.5; }

/* ── Phase Transition Indicator ── */
.phase-transition {
  margin-top: 10px; padding: 10px 14px;
  border-radius: 4px; font-size: 12px;
  animation: pt-pulse 2s ease-in-out 3;
}
.phase-transition.emergence {
  border: 1px solid rgba(158,206,106,0.4); background: rgba(158,206,106,0.08);
  color: #9ece6a;
}
.phase-transition.deepening {
  border: 1px solid rgba(122,162,247,0.4); background: rgba(122,162,247,0.08);
  color: #7aa2f7;
}
.phase-transition.recovery {
  border: 1px solid rgba(224,175,104,0.4); background: rgba(224,175,104,0.08);
  color: #e0af68;
}
.phase-transition.collapse {
  border: 1px solid rgba(247,118,142,0.3); background: rgba(247,118,142,0.05);
  color: #f7768e;
}
.pt-header {
  font-weight: 600; font-size: 13px; margin-bottom: 4px;
  display: flex; align-items: center; gap: 8px;
}
.pt-symbol { font-size: 16px; }
.pt-delta { font-family: monospace; font-size: 12px; opacity: 0.9; }
.pt-interpretation { color: var(--dim); font-size: 11px; margin-top: 4px; line-height: 1.5; }
@keyframes pt-pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.7; }
}

/* ── Reflect Button ── */
#reflect-btn {
  background: transparent; border: 1px solid var(--border);
  color: var(--dim); font-family: inherit; font-size: 12px;
  padding: 6px 14px; border-radius: 4px; cursor: pointer;
  transition: all 0.2s; white-space: nowrap;
}
#reflect-btn:hover:not(:disabled) { border-color: var(--accent); color: var(--accent); }
#reflect-btn:disabled { opacity: 0.3; cursor: default; }
#reflect-btn.has-target { border-color: rgba(224,175,104,0.5); color: #e0af68; }
#reflect-btn .reflect-hint {
  font-size: 10px; color: var(--dim); margin-left: 4px;
  max-width: 200px; overflow: hidden; text-overflow: ellipsis;
}
.reflect-info {
  margin-top: 6px; padding: 8px 14px;
  border: 1px solid rgba(224,175,104,0.3); background: rgba(224,175,104,0.05);
  border-radius: 4px; font-size: 11px; color: #e0af68;
}
.reflect-info .ri-label { font-weight: 600; margin-bottom: 3px; }
.reflect-info .ri-delta { font-family: monospace; font-size: 12px; }
.reflect-info .ri-targeted { color: var(--dim); margin-top: 3px; }

/* ── Verdict ── */
.verdict {
  margin-top: 8px; padding: 10px 14px;
  background: rgba(122,162,247,0.08); border: 1px solid rgba(122,162,247,0.15);
  border-radius: 4px; font-size: 12px; color: var(--accent);
  white-space: pre-wrap; line-height: 1.7;
}

/* ── Trace ── */
.trace-toggle { font-size: 11px; color: var(--dim); cursor: pointer; margin-top: 4px; user-select: none; }
.trace-toggle:hover { color: var(--accent); }
.trace {
  margin-top: 6px; font-size: 11px; overflow-x: auto; display: none;
  background: var(--surface); border: 1px solid var(--border);
  border-radius: 3px; padding: 8px 12px;
}
.trace.open { display: block; }
.trace table { border-collapse: collapse; width: 100%; }
.trace th { text-align: left; color: var(--dim); font-weight: 400; padding: 2px 8px; border-bottom: 1px solid var(--border); }
.trace td { padding: 2px 8px; color: var(--text); font-variant-numeric: tabular-nums; }

/* ── Input ── */
#input-area {
  padding: 16px 24px; border-top: 1px solid var(--border);
  display: flex; gap: 12px; flex-shrink: 0;
}
#input-area input {
  flex: 1; background: var(--surface); border: 1px solid var(--border);
  color: var(--text); padding: 10px 16px; font-family: inherit;
  font-size: 14px; border-radius: 4px; outline: none;
  transition: border-color 0.2s;
}
#input-area input:focus { border-color: var(--accent); }
#input-area input::placeholder { color: var(--dim); }
#input-area button {
  background: var(--accent); border: none; color: var(--bg);
  padding: 10px 24px; font-family: inherit; font-size: 14px;
  font-weight: 600; cursor: pointer; border-radius: 4px;
  transition: opacity 0.2s;
}
#input-area button:hover { opacity: 0.85; }
#input-area button:disabled { opacity: 0.4; cursor: default; }

/* ── Overlays ── */
.overlay {
  display: none; position: fixed; inset: 0;
  background: rgba(0,0,0,0.7); z-index: 100;
  justify-content: center; align-items: center;
}
.overlay.open { display: flex; }
.overlay-box {
  background: var(--surface); border: 1px solid var(--border);
  border-radius: 6px; padding: 24px; max-width: 640px; width: 90%;
  max-height: 70vh; overflow-y: auto; white-space: pre-wrap;
  font-size: 13px; color: var(--text);
}
.overlay-box .x { float: right; color: var(--dim); cursor: pointer; font-size: 18px; }
.overlay-box .x:hover { color: var(--phase); }

/* ── Misc ── */
.waiting .body::after { content: '\25cd'; animation: blink 1s infinite; color: var(--accent); }
@keyframes blink { 50% { opacity: 0; } }
::-webkit-scrollbar { width: 6px; }
::-webkit-scrollbar-track { background: var(--bg); }
::-webkit-scrollbar-thumb { background: var(--border); border-radius: 3px; }

/* ── Init Panel ── */
#init-panel {
  border-bottom: 1px solid var(--border);
  background: var(--surface);
  padding: 12px 24px;
  flex-shrink: 0;
  display: none;
}
#init-panel.open { display: block; }
#init-panel .init-header {
  display: flex; align-items: center; justify-content: space-between;
  margin-bottom: 8px;
}
#init-panel .init-header h2 {
  font-size: 13px; font-weight: 600; color: var(--accent);
  letter-spacing: 1px; text-transform: uppercase;
}
#init-panel .init-header .toggle-btn {
  font-size: 11px; color: var(--dim); cursor: pointer;
  background: none; border: 1px solid var(--border); padding: 2px 8px;
  border-radius: 3px; font-family: inherit;
}
#init-panel .init-header .toggle-btn:hover { color: var(--accent); border-color: var(--accent); }
.init-category {
  margin-bottom: 8px;
}
.init-category-label {
  font-size: 10px; text-transform: uppercase; letter-spacing: 1.5px;
  color: var(--dim); margin-bottom: 4px;
}
.init-modules {
  display: flex; flex-wrap: wrap; gap: 6px;
}
.init-module {
  background: var(--bg); border: 1px solid var(--border); border-radius: 4px;
  padding: 6px 12px; cursor: pointer; font-family: inherit; font-size: 12px;
  color: var(--text); transition: border-color 0.2s, color 0.2s;
  display: flex; align-items: center; gap: 8px;
  max-width: 420px;
}
.init-module:hover { border-color: var(--accent); color: var(--accent); }
.init-module.running { opacity: 0.5; cursor: wait; }
.init-module.done { border-color: var(--human); }
.init-module.done .init-name { color: var(--human); }
.init-module.failed { border-color: var(--phase); }
.init-module.failed .init-name { color: var(--phase); }
.init-name { font-weight: 600; }
.init-desc { color: var(--dim); font-size: 11px; }
.init-order {
  display: inline-flex; align-items: center; justify-content: center;
  width: 18px; height: 18px; border-radius: 50%;
  background: var(--border); color: var(--dim); font-size: 10px;
  font-weight: 700; flex-shrink: 0;
}
.init-module.done .init-order { background: var(--human); color: var(--bg); }
.init-module.failed .init-order { background: var(--phase); color: var(--bg); }
.init-sequence-hint {
  font-size: 10px; color: var(--dim); margin-bottom: 8px;
  padding: 4px 8px; border-left: 2px solid var(--border);
  font-style: italic;
}
.init-result {
  font-size: 10px; margin-left: auto; white-space: nowrap;
  font-variant-numeric: tabular-nums;
}
.init-result .pass { color: var(--human); }
.init-result .fail { color: var(--phase); }
</style>
</head>
<body>

<header>
  <h1>E&#x2080;&ensp;S T A R T</h1>
  <span class="info" id="info"></span>
  <div class="actions">
    <button onclick="toggleInitPanel()">Init</button>
    <button onclick="doSessions()">Sessions</button>
    <button onclick="doSave()">Save</button>
    <button onclick="doHelp()">Help</button>
    <button onclick="doReport()">Report</button>
    <button onclick="doClear()">Re-init</button>
  </div>
</header>

<div id="init-panel">
  <div class="init-header">
    <h2>&#x2699; Init Modules</h2>
    <button class="toggle-btn" onclick="toggleInitPanel()">&times; close</button>
  </div>
  <div id="init-modules-container">Loading modules...</div>
</div>

<div id="chat"></div>

<div id="input-area">
  <input type="text" id="msg" placeholder="Write something..." autocomplete="off"
         onkeydown="if(event.key==='Enter')doSend()">
  <button id="reflect-btn" onclick="doReflect()" disabled title="Structural reflection on missing elements">✡ Reflect</button>
  <button id="send-btn" onclick="doSend()">Send</button>
</div>

<div class="overlay" id="help-overlay">
  <div class="overlay-box">
    <span class="x" onclick="closeHelp()">&times;</span>
    <pre id="help-content"></pre>
  </div>
</div>
<div class="overlay" id="report-overlay">
  <div class="overlay-box">
    <span class="x" onclick="closeReport()">&times;</span>
    <pre id="report-content"></pre>
  </div>
</div>
<div class="overlay" id="sessions-overlay">
  <div class="overlay-box">
    <span class="x" onclick="closeSessions()">&times;</span>
    <h3 style="margin:0 0 12px 0;color:var(--e0)">E&#x2080; Sessions</h3>
    <div id="session-status" style="margin-bottom:8px;font-size:0.85em;color:var(--human)"></div>
    <div id="sessions-list" style="max-height:60vh;overflow-y:auto"></div>
  </div>
</div>

<script>
const chat = document.getElementById('chat');
const msgInput = document.getElementById('msg');
const sendBtn = document.getElementById('send-btn');
let sending = false, msgN = 0, helpText = '';

function scroll() { chat.scrollTop = chat.scrollHeight; }

function esc(s) {
  const d = document.createElement('div');
  d.textContent = s;
  return d.innerHTML;
}
function escJs(s) {
  return s.replace(/\\/g, '\\\\').replace(/'/g, "\\'");
}

function toggleTrace(id) {
  const el = document.getElementById('trace-' + id);
  if (el) el.classList.toggle('open');
}

function interpHtml(m, i, q) {
  if (!m || !i) return '';
  var h = '<div class="interp">'
    + '<div class="row"><span class="lbl">R\u0304</span><span class="val">'
    + m.r.toFixed(3) + '</span><span class="expl">' + esc(i.r) + '</span></div>'
    + '<div class="row"><span class="lbl">H\u0304</span><span class="val">'
    + m.h.toFixed(3) + '</span><span class="expl">' + esc(i.h) + '</span></div>'
    + '<div class="row"><span class="lbl">\u03a6</span><span class="val">'
    + m.phi + '</span><span class="expl">' + esc(i.phi) + '</span></div>'
    + '<div class="row"><span class="lbl">v\u0304</span><span class="val">'
    + m.v.toFixed(3) + '</span><span class="expl">' + esc(i.v) + '</span></div>';
  if (q && q.novelty !== undefined) {
    h += '<div class="row" style="margin-top:4px;border-top:1px solid var(--border);padding-top:4px">'
      + '<span class="lbl" style="color:var(--human)">N</span><span class="val" style="color:var(--human)">'
      + q.novelty.toFixed(3) + '</span><span class="expl">' + esc(i.novelty || '') + '</span></div>'
      + '<div class="row"><span class="lbl" style="color:var(--human)">C</span><span class="val" style="color:var(--human)">'
      + q.coherence.toFixed(3) + '</span><span class="expl">' + esc(i.coherence || '') + '</span></div>'
      + '<div class="row"><span class="lbl" style="color:var(--human)">E\u2080</span><span class="val" style="color:var(--human)">'
      + q.e0_operative.toFixed(3) + '</span><span class="expl">' + esc(i.structural || '') + '</span></div>'
      + '<div class="row"><span class="lbl" style="color:var(--human)">D</span><span class="val" style="color:var(--human)">'
      + (q.completeness !== undefined ? q.completeness.toFixed(3) : '—') + '</span><span class="expl">' + esc(i.completeness || '') + '</span></div>';
  }
  h += '</div>';
  return h;
}

function traceHtml(trace, id) {
  if (!trace || !trace.length) return '';
  var rows = trace.map(function(t) {
    var vs = t.v > 99999 ? '\u221e' : t.v < 100 ? t.v.toFixed(4) : Math.round(t.v);
    var cl = t.phase ? ' style="color:var(--phase)"' : '';
    var mk = t.phase ? ' \u25c6' : '';
    return '<tr' + cl + '><td>' + t.tau + '</td><td>' + esc(t.token)
      + '</td><td>' + t.r.toFixed(4) + '</td><td>' + vs
      + '</td><td>' + t.h.toFixed(4) + '</td><td>'
      + (t.dh >= 0 ? '+' : '') + t.dh.toFixed(4) + mk + '</td></tr>';
  }).join('');
  return '<div class="trace-toggle" onclick="toggleTrace(\'' + id + '\')">&#9656; token trace</div>'
    + '<div class="trace" id="trace-' + id + '"><table>'
    + '<tr><th>\u03c4</th><th>Token</th><th>R</th><th>v</th><th>H</th><th>\u0394H</th></tr>'
    + rows + '</table></div>';
}

function showInit(d) {
  var div = document.createElement('div');
  div.className = 'msg e0';
  var h = '<div class="role">E\u2080 Initialization</div>';
  h += '<div class="body">' + esc(d.text) + '</div>';
  h += interpHtml(d.metrics, d.interpretation, d.quality);
  if (d.verdict) h += '<div class="verdict">' + esc(d.verdict) + '</div>';
  h += traceHtml(d.trace, 'init');
  div.innerHTML = h;
  chat.appendChild(div);
  scroll();
  document.getElementById('info').textContent = d.backend || '';
  if (d.help_text) helpText = d.help_text;
}

function showE0(text, m, i, trace, q, fb, pt) {
  var id = 'm' + (++msgN);
  var div = document.createElement('div');
  div.className = 'msg e0';
  var h = '<div class="role">E\u2080</div><div class="body">' + esc(text) + '</div>';
  if (m && i) {
    h += interpHtml(m, i, q);
    if (i.guidance) h += '<div class="guidance">' + esc(i.guidance) + '</div>';
  }
  h += traceHtml(trace, id);
  if (fb && fb.html && fb.level) {
    var fbId = 'fb-' + id;
    var levelCls = fb.level === 'gentle' ? ' gentle' : '';
    h += '<div class="feedback' + levelCls + '">'
      + '<div class="feedback-toggle" onclick="toggleFeedback(\'' + fbId + '\')">'
      + '<span class="arrow" id="arrow-' + fbId + '">&#9656;</span> '
      + '\u2699 Structural Observation</div>'
      + '<div class="feedback-body" id="' + fbId + '">'
      + fb.html + '</div></div>';
  }
  // ── Phase Transition Indicator ──
  if (pt && pt.type) {
    var symbols = {emergence: '\u2197\ufe0e', deepening: '\u2b06\ufe0e', recovery: '\u21bb', collapse: '\u2198\ufe0e'};
    var labels = {emergence: 'PHASE TRANSITION: Emergence', deepening: 'PHASE TRANSITION: Deepening',
                  recovery: 'PHASE TRANSITION: Recovery', collapse: 'Structural Collapse'};
    h += '<div class="phase-transition ' + pt.type + '">'
      + '<div class="pt-header">'
      + '<span class="pt-symbol">' + (symbols[pt.type] || '\u25c6') + '</span> '
      + '<span>' + (labels[pt.type] || pt.type) + '</span>'
      + '<span class="pt-delta">D ' + pt.d_before.toFixed(3) + ' \u2192 ' + pt.d_after.toFixed(3)
      + ' (\u0394D=' + (pt.delta_d >= 0 ? '+' : '') + pt.delta_d.toFixed(3) + ')</span>'
      + '</div>'
      + '<div class="pt-interpretation">' + esc(pt.interpretation || '') + '</div>'
      + '</div>';
  }
  div.innerHTML = h;
  chat.appendChild(div);
  scroll();
}

function toggleFeedback(id) {
  var el = document.getElementById(id);
  var arrow = document.getElementById('arrow-' + id);
  if (el) { el.classList.toggle('open'); }
  if (arrow) { arrow.classList.toggle('open'); }
}

function addHuman(t) {
  var div = document.createElement('div');
  div.className = 'msg human';
  div.innerHTML = '<div class="role">You</div><div class="body">' + esc(t) + '</div>';
  chat.appendChild(div);
  scroll();
}

function addWait() {
  var div = document.createElement('div');
  div.className = 'msg e0 waiting';
  div.id = 'wait';
  div.innerHTML = '<div class="role">E\u2080</div><div class="body"></div>';
  chat.appendChild(div);
  scroll();
}

function rmWait() { var e = document.getElementById('wait'); if (e) e.remove(); }

async function doSend() {
  if (sending) return;
  var t = msgInput.value.trim();
  if (!t) return;
  msgInput.value = '';
  addHuman(t);
  sending = true;
  sendBtn.disabled = true;
  addWait();
  try {
    var r = await fetch('/chat', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({message: t})
    });
    var d = await r.json();
    rmWait();
    if (d.error) {
      showE0('[Error] ' + d.error, null, null, null, null, null, null);
    } else {
      showE0(d.text, d.metrics, d.interpretation, d.trace, d.quality, d.feedback || null, d.transition || null);
    }
  } catch (e) {
    rmWait();
    showE0('[Connection error] ' + e.message, null, null, null, null, null, null);
  }
  sending = false;
  sendBtn.disabled = false;
  updateReflectStatus();
  msgInput.focus();
}

var reflectBtn = document.getElementById('reflect-btn');

async function updateReflectStatus() {
  try {
    var r = await fetch('/reflect', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({mode: 'status'})
    });
    var s = await r.json();
    if (s.available) {
      reflectBtn.disabled = false;
      reflectBtn.className = 'has-target';
      reflectBtn.title = s.hint + ' (D=' + s.d.toFixed(3) + ', ' + s.operative_count + '/8 operative)';
      reflectBtn.innerHTML = '\u2721 Reflect <span class=\"reflect-hint\">' + s.operative_count + '/8</span>';
    } else {
      reflectBtn.disabled = true;
      reflectBtn.className = '';
      reflectBtn.title = 'All elements operative';
      reflectBtn.innerHTML = '\u2721 Reflect <span class=\"reflect-hint\">8/8 \u2713</span>';
    }
  } catch (e) {
    reflectBtn.disabled = true;
  }
}

async function doReflect() {
  if (sending) return;
  sending = true;
  sendBtn.disabled = true;
  reflectBtn.disabled = true;
  addHuman('\u2721 Structural Reflection');
  addWait();
  try {
    var r = await fetch('/reflect', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({mode: 'generate'})
    });
    var d = await r.json();
    rmWait();
    if (d.error) {
      showE0('[Reflect] ' + d.error, null, null, null, null, null, null);
    } else {
      showE0(d.text, d.metrics, d.interpretation, d.trace, d.quality, d.feedback || null, d.transition || null);
      // Show reflection summary
      if (d.reflection) {
        var ri = d.reflection;
        var riDiv = document.createElement('div');
        riDiv.className = 'reflect-info';
        riDiv.innerHTML = '<div class=\"ri-label\">\u2721 Reflection Result</div>'
          + '<div class=\"ri-delta\">D: ' + ri.d_before.toFixed(3) + ' \u2192 ' + ri.d_after.toFixed(3)
          + ' (\u0394' + (ri.delta_d >= 0 ? '+' : '') + ri.delta_d.toFixed(3) + ')</div>'
          + '<div class=\"ri-targeted\">Targeted: ' + ri.targeted.join(', ')
          + (ri.still_missing.length ? ' | Still missing: ' + ri.still_missing.join(', ') : ' | All resolved \u2713') + '</div>';
        chat.appendChild(riDiv);
        scroll();
      }
    }
  } catch (e) {
    rmWait();
    showE0('[Reflect error] ' + e.message, null, null, null, null, null, null);
  }
  sending = false;
  sendBtn.disabled = false;
  updateReflectStatus();
  msgInput.focus();
}

async function doClear() {
  var r = await fetch('/clear', {method: 'POST'});
  var d = await r.json();
  chat.innerHTML = '';
  showInit(d);
  updateReflectStatus();
}

async function doReport() {
  var r = await fetch('/report', {method: 'POST'});
  var d = await r.json();
  document.getElementById('report-content').textContent = d.report || 'No data.';
  document.getElementById('report-overlay').classList.add('open');
}
function closeReport() { document.getElementById('report-overlay').classList.remove('open'); }
document.getElementById('report-overlay').addEventListener('click', function(e) {
  if (e.target === this) closeReport();
});

function doHelp() {
  document.getElementById('help-content').textContent = helpText || 'No help text.';
  document.getElementById('help-overlay').classList.add('open');
}
function closeHelp() { document.getElementById('help-overlay').classList.remove('open'); }
document.getElementById('help-overlay').addEventListener('click', function(e) {
  if (e.target === this) closeHelp();
});

// ── Session management ──
let currentSessionId = null;

async function doSave() {
  try {
    var r = await fetch('/session/save', {method: 'POST'});
    var d = await r.json();
    if (d.error) { alert('Save error: ' + d.error); return; }
    currentSessionId = d.session_id;
    var status = document.getElementById('session-status');
    if (status) status.textContent = 'Saved: ' + d.session_id + ' (' + d.turns + ' turns, ' + d.tokens + ' tokens)';
    // Brief visual feedback
    var btn = document.querySelector('button[onclick="doSave()"]');
    if (btn) { btn.textContent = '\u2713 Saved'; setTimeout(function() { btn.textContent = 'Save'; }, 2000); }
  } catch (e) {
    alert('Save failed: ' + e.message);
  }
}

async function doSessions() {
  document.getElementById('sessions-overlay').classList.add('open');
  await refreshSessionList();
}
function closeSessions() { document.getElementById('sessions-overlay').classList.remove('open'); }
document.getElementById('sessions-overlay').addEventListener('click', function(e) {
  if (e.target === this) closeSessions();
});

async function refreshSessionList() {
  var r = await fetch('/session/list', {method: 'POST'});
  var d = await r.json();
  var list = document.getElementById('sessions-list');
  if (!d.sessions || d.sessions.length === 0) {
    list.innerHTML = '<p style="color:var(--muted)">No saved sessions yet. Use "Save" to create one.</p>';
    return;
  }
  var html = '<table style="width:100%;font-size:0.85em;border-collapse:collapse">'
    + '<tr style="border-bottom:1px solid var(--border)"><th style="text-align:left;padding:4px">Session</th>'
    + '<th style="text-align:right;padding:4px">Turns</th>'
    + '<th style="text-align:right;padding:4px">Tokens</th>'
    + '<th style="text-align:left;padding:4px">R\u0304 trajectory</th>'
    + '<th style="padding:4px"></th></tr>';
  d.sessions.forEach(function(s) {
    var rTraj = (s.r_trajectory || []).map(function(v) { return v.toFixed(3); }).join(' \u2192 ');
    var isCurrent = (s.session_id === currentSessionId) ? ' style="color:var(--e0);font-weight:bold"' : '';
    html += '<tr style="border-bottom:1px solid var(--border)">'
      + '<td style="padding:4px"' + isCurrent + '>' + esc(s.session_id) + '<br><span style="font-size:0.8em;color:var(--muted)">' + esc(s.model) + '</span></td>'
      + '<td style="text-align:right;padding:4px">' + s.turns + '</td>'
      + '<td style="text-align:right;padding:4px">' + s.tokens + '</td>'
      + '<td style="padding:4px;font-family:monospace;font-size:0.85em">' + rTraj + '</td>'
      + '<td style="padding:4px;white-space:nowrap">'
      + '<button onclick="loadSession(\'' + escJs(s.filepath) + '\',\'' + escJs(s.session_id) + '\')" style="font-size:0.8em;margin:2px">Load</button>'
      + '<button onclick="deleteSession(\'' + escJs(s.filepath) + '\')" style="font-size:0.8em;margin:2px;color:#c44">Del</button>'
      + '</td></tr>';
  });
  html += '</table>';
  list.innerHTML = html;
}

async function loadSession(filepath, sid) {
  if (!confirm('Load session ' + sid + '? Current unsaved state will be lost.')) return;
  try {
    var r = await fetch('/session/load', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({filepath: filepath})
    });
    var d = await r.json();
    if (d.error) { alert('Load failed: ' + d.error); return; }
    currentSessionId = d.session_id;
    // Rebuild chat from restored history
    chat.innerHTML = '';
    if (d.history && d.history.length > 0) {
      // Show init first
      var initR = await fetch('/init');
      var initD = await initR.json();
      showInit(initD);
      // Then show each turn
      d.history.forEach(function(turn) {
        addHuman(turn.user);
        showE0(turn.response, turn.metrics, turn.interpretation || null, null, turn.quality || null, null, null);
      });
    }
    var warnings = (d.info && d.info.warnings) ? d.info.warnings : [];
    var msg = 'Session restored: ' + d.session_id + ' (' + (d.info ? d.info.turns_restored : '?') + ' turns)';
    if (warnings.length > 0) msg += '\n\nWarnings:\n' + warnings.join('\n');
    document.getElementById('session-status').textContent = msg;
    closeSessions();
  } catch (e) {
    alert('Load error: ' + e.message);
  }
}

async function deleteSession(filepath) {
  if (!confirm('Delete this session permanently?')) return;
  await fetch('/session/delete', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({filepath: filepath})
  });
  await refreshSessionList();
}

// ── Init Modules ──
let initModulesLoaded = false;
let initModuleResults = {};

function toggleInitPanel() {
  var panel = document.getElementById('init-panel');
  panel.classList.toggle('open');
  if (panel.classList.contains('open') && !initModulesLoaded) {
    loadInitModules();
  }
}

async function loadInitModules() {
  try {
    var r = await fetch('/init-modules');
    var d = await r.json();
    renderInitModules(d.modules);
    initModulesLoaded = true;
  } catch (e) {
    document.getElementById('init-modules-container').textContent = 'Failed to load modules: ' + e.message;
  }
}

function renderInitModules(modules) {
  var container = document.getElementById('init-modules-container');
  // Sort by order within categories
  modules.sort(function(a, b) { return (a.order || 99) - (b.order || 99); });
  var categories = {};
  var categoryOrder = ['foundation', 'self-recognition', 'primer', 'custom'];
  modules.forEach(function(m) {
    if (!categories[m.category]) categories[m.category] = [];
    categories[m.category].push(m);
  });
  var categoryLabels = {
    'foundation': 'Foundation',
    'self-recognition': 'Self-Recognition',
    'primer': 'Structural Primers',
    'custom': 'Custom'
  };
  var html = '<div class="init-sequence-hint">' +
    'Recommended: \u2460 Ontodynamics \u2192 \u2461 Identity \u2192 \u2462 Mechanism \u2192 \u2463 Integration \u2192 then Primers' +
    '</div>';
  categoryOrder.forEach(function(cat) {
    if (!categories[cat]) return;
    html += '<div class="init-category">';
    html += '<div class="init-category-label">' + esc(categoryLabels[cat] || cat) + '</div>';
    html += '<div class="init-modules">';
    categories[cat].forEach(function(m) {
      var state = initModuleResults[m.id] ? (initModuleResults[m.id].passed ? 'done' : 'failed') : '';
      var resultHtml = '';
      if (initModuleResults[m.id]) {
        var res = initModuleResults[m.id];
        var cls = res.passed ? 'pass' : 'fail';
        resultHtml = '<span class="init-result"><span class="' + cls + '">'
          + (res.passed ? '\u2713' : '\u2717') + '</span> R\u0304=' + res.r.toFixed(3) + ' D=' + res.d.toFixed(3) + '</span>';
      }
      html += '<button class="init-module ' + state + '" id="init-mod-' + m.id + '" onclick="runInitModule(\'' + m.id + '\')" title="' + esc(m.description) + '">'
        + '<span class="init-order">' + (m.order || '') + '</span>'
        + '<span class="init-name">' + esc(m.name) + '</span>'
        + '<span class="init-desc">' + esc(m.description.length > 50 ? m.description.substring(0,47) + '...' : m.description) + '</span>'
        + resultHtml
        + '</button>';
    });
    html += '</div></div>';
  });
  container.innerHTML = html;
}

async function runInitModule(moduleId) {
  var btn = document.getElementById('init-mod-' + moduleId);
  if (btn) btn.classList.add('running');
  try {
    var r = await fetch('/init-module/run', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({module_id: moduleId})
    });
    var d = await r.json();
    if (d.error) {
      alert('Init module error: ' + d.error);
      if (btn) btn.classList.remove('running');
      return;
    }
    initModuleResults[moduleId] = {r: d.r, d: d.d, passed: d.passed};
    // Show result in chat
    var label = d.name + ' [R\u0304=' + d.r.toFixed(3) + ' D=' + d.d.toFixed(3) + ' ' + (d.passed ? '\u2713' : '\u2717') + ']';
    showE0(d.text, d.metrics, d.interpretation || null, d.trace || null, d.quality || null, null, null);
    // Update button state
    if (initModulesLoaded) {
      // Re-fetch to refresh buttons with results
      var mr = await fetch('/init-modules');
      var md = await mr.json();
      renderInitModules(md.modules);
    }
  } catch (e) {
    alert('Failed: ' + e.message);
  }
  if (btn) btn.classList.remove('running');
  updateReflectStatus();
}

window.addEventListener('load', async function() {
  try {
    var r = await fetch('/init');
    var d = await r.json();
    showInit(d);
  } catch (e) {
    showE0('Failed to load: ' + e.message, null, null, null, null, null, null);
  }
  msgInput.focus();
  updateReflectStatus();
});
</script>
</body>
</html>
"""


def run_web(model_name: str, device: str, lang: str, show_detail: bool, port: int,
            api_key: str = None, base_url: str = None):
    """Full initialization followed by web interface."""
    global _web_starter, _web_lang, _web_init_data, _web_prev_r, _web_turn_num, _web_prev_text, _web_canon_text, _web_session_id

    g = GUIDANCE[lang]
    _web_lang = lang
    _web_session_id = None

    print(g["welcome"])

    # Load canon
    canon = load_canon()
    _web_canon_text = canon

    # Load model or connect to API
    if api_key:
        print(f"  Connecting to API: {model_name} ...")
        t0 = time.time()
        _web_starter = E0APIStarter(api_key, model=model_name, base_url=base_url)
        dt = time.time() - t0
        print(f"  API ready: {model_name}")
    else:
        print(g["loading"].format(model=model_name))
        t0 = time.time()
        _web_starter = E0Starter(model_name, device=device)
        dt = time.time() - t0
        print(g["loaded"].format(
            params=f"{_web_starter.param_count:,}",
            vocab=f"{_web_starter.vocab_size:,}",
        ))
        print(f"  (loaded in {dt:.1f}s)")

    # Feed canon
    print(g["feeding"])
    t0 = time.time()
    text, steps, metrics = _web_starter.feed_canon(canon)
    dt = time.time() - t0

    _web_prev_r = metrics["r"]
    _web_turn_num = 0
    _web_prev_text = _clean(text)

    _, r_explain = interpret_r(metrics["r"], lang)
    print(f"  R = {metrics['r']:.3f} -- {r_explain}")
    print(f"  (generated in {dt:.1f}s)")

    # Init modules are now user-selectable from UI — no auto self-recognition
    _web_starter.self_recognition_done = False
    _web_starter.self_recognition_results = []

    # Prepare feedback for first chat turn (always English for LLM)
    if hasattr(_web_starter, 'score_and_prepare_feedback'):
        _web_starter.score_and_prepare_feedback(_web_prev_text, metrics, lang='en')

    _web_init_data = build_init_data(_web_prev_text, steps, metrics, lang, _web_starter)

    # Initialize session protocol
    global _web_protocol
    _web_protocol = SessionProtocol(model_name)
    _web_protocol.start_init()
    if is_calibrated(model_name):
        _web_protocol.calibration = load_calibration(model_name)
        print(f"  Protocol: calibration loaded for {model_name}")
    else:
        print(f"  Protocol: no calibration found for {model_name} (run /protocol/calibrate)")
    print(f"  Protocol: session initialized, phase={_web_protocol.phase.phase}")

    # Start server
    server = HTTPServer(("0.0.0.0", port), E0StartHandler)
    url = f"http://localhost:{port}"

    print()
    print("  ================================================================")
    print("   E0 START -- Web Interface")
    print("  ================================================================")
    print(f"   Open: {url}")
    backend_label = f"E0 API ({model_name})" if api_key else f"E0 Local ({model_name})"
    print(f"   Backend: {backend_label}")
    print(f"   Language: {lang}")
    print(f"   Ctrl+C to stop")
    print("  ================================================================")
    print()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n  Server stopped.\n")
        server.server_close()


# =============================================
#  Entry Point
# =============================================

def main():
    parser = argparse.ArgumentParser(
        description="E0 Start -- practical initialization for humans",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  py e0_start.py                    GPT-2 on CPU, terminal mode
  py e0_start.py --web              Browser interface (recommended)
  py e0_start.py --web --lang de    Browser + German guidance
  py e0_start.py --api KEY          API model (Together AI, OpenAI, etc.)
  py e0_start.py --api KEY --web    API + browser (best for 30B+)
  py e0_start.py --api KEY --base-url URL --model MODEL

Profile mode (structured initialization path):
  py e0_start.py --profile profiles/agriculture.json --api KEY
  py e0_start.py --profile profiles/health.json --api KEY
  py e0_start.py --profile profiles/default.json
        """,
    )
    parser.add_argument(
        "--model", type=str, default=None,
        help="Model name (default: gpt2 local, Qwen/Qwen2.5-7B-Instruct-Turbo API)",
    )
    parser.add_argument(
        "--device", type=str, default="cpu",
        help="Device for local model (default: cpu)",
    )
    parser.add_argument(
        "--detail", action="store_true",
        help="Show token-level E0 trace",
    )
    parser.add_argument(
        "--lang", type=str, default="en", choices=["en", "de"],
        help="Guidance language (default: en)",
    )
    parser.add_argument(
        "--web", action="store_true",
        help="Start browser interface instead of terminal",
    )
    parser.add_argument(
        "--port", type=int, default=3000,
        help="Web server port (default: 3000)",
    )
    parser.add_argument(
        "--api", type=str, default=None, metavar="KEY",
        help="API key (Together AI, OpenAI, or compatible)",
    )
    parser.add_argument(
        "--base-url", type=str, default=None,
        help="API base URL (default: Together AI)",
    )
    parser.add_argument(
        "--profile", type=str, default=None, metavar="PATH",
        help="Initialization profile (JSON). Overrides --model, --lang, --web.",
    )
    parser.add_argument(
        "--setup", action="store_true",
        help="Run first-time setup wizard (creates ~/.e0/config.json)",
    )
    parser.add_argument(
        "--no-config", action="store_true",
        help="Ignore saved config, use only CLI arguments",
    )

    args = parser.parse_args()

    # ── Explicit setup mode ──
    if args.setup:
        first_run_setup(lang=args.lang)
        return

    # ── Merge CLI args with saved config ──
    if args.no_config:
        # Pure CLI mode, no config file
        api_key = args.api
        base_url = detect_base_url(api_key, args.base_url)
        model_name = args.model or ("gpt2" if not api_key else "Qwen/Qwen2.5-7B-Instruct-Turbo")
        lang = args.lang
        port = args.port
    else:
        # First-run: if no config and no --api, offer setup
        if not has_config() and not args.api:
            print()
            print("  No configuration found and no --api key provided.")
            print("  Starting first-run setup...")
            first_run_setup(lang=args.lang)
        
        cfg = merge_args_with_config(args)
        api_key = cfg["api_key"]
        base_url = cfg["base_url"]
        model_name = cfg["model"]
        lang = cfg["lang"]
        port = cfg["port"]

    # ── Profile mode: structured initialization path ──
    if args.profile:
        run_profile(
            profile_path=args.profile,
            api_key=api_key,
            base_url=base_url,
            show_detail=args.detail,
            port=port,
        )
        return

    # ── Standard mode ──
    if args.web:
        run_web(model_name, args.device, lang, args.detail, port,
                api_key=api_key, base_url=base_url)
    else:
        run(model_name, args.device, lang, args.detail,
            api_key=api_key, base_url=base_url)


if __name__ == "__main__":
    main()
