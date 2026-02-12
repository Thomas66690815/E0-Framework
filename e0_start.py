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
  py e0_start.py                    GPT-2 on CPU (always works)
  py e0_start.py --model X          Any HuggingFace model
  py e0_start.py --detail           Show token-level measurements
  py e0_start.py --lang de          German guidance (default: en)
"""

from __future__ import annotations

import argparse
import math
import os
import sys
import time
from typing import List, Tuple, Optional, Dict

# Suppress noisy HuggingFace progress bars and warnings
os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
os.environ.setdefault("TRANSFORMERS_VERBOSITY", "error")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from e0_middleware.instrumentation import E0Instrumenter, StepMeasurement


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
        "e0-canon-plain.txt"
    )
    if not os.path.exists(canon_path):
        print(f"  [ERROR] Canon not found: {canon_path}")
        print(f"  Make sure e0-canon-plain.txt is in the same directory as this script.")
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


# =============================================
#  The Main Flow
# =============================================

def run(model_name: str, device: str, lang: str, show_detail: bool):
    """Full initialization and chat flow."""
    g = GUIDANCE[lang]

    # Welcome
    print(g["welcome"])

    # Load canon
    canon = load_canon()

    # Load model
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

        print()


# =============================================
#  Entry Point
# =============================================

def main():
    parser = argparse.ArgumentParser(
        description="E0 Start -- practical initialization for humans",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  py e0_start.py                    GPT-2 on CPU (always works)
  py e0_start.py --model gpt2       Same as above, explicit
  py e0_start.py --model microsoft/phi-2    Larger model
  py e0_start.py --detail           Show token-level trace
  py e0_start.py --lang de          German guidance
        """,
    )
    parser.add_argument(
        "--model", type=str, default="gpt2",
        help="HuggingFace model name (default: gpt2)",
    )
    parser.add_argument(
        "--device", type=str, default="cpu",
        help="Device (default: cpu)",
    )
    parser.add_argument(
        "--detail", action="store_true",
        help="Show token-level E0 trace",
    )
    parser.add_argument(
        "--lang", type=str, default="en", choices=["en", "de"],
        help="Guidance language (default: en)",
    )

    args = parser.parse_args()
    run(args.model, args.device, args.lang, args.detail)


if __name__ == "__main__":
    main()
