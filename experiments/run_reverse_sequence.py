"""
Experiment 6: Reverse-Sequence — False Primer FIRST + Semantic Probe

Tests two questions simultaneously:
  1. Is immunity sequence-dependent? (False primer BEFORE any E₀ historization)
  2. Is contamination present below D-resolution? (Semantic probe after Reflect)

Design:
  FALSE superposition primer (via /chat) — FIRST, before anything
  → Canon (foundation-ontodynamics)
  → identity → mechanism → integration
  → CORRECT superposition primer (via /chat)
  → measurement → time
  → Reflect (D measurement — is eigenstate established despite false first?)
  → Semantic Probe: "Derive superposition from E₀ primitives."
    (tests whether false content persists at semantic level)

System B predictions (Eigenstate Model):
  - Reflect D: 0.875–0.938 (not 1.000 — trace of false first historization)
  - Semantic probe: will use correct definition (correct primer has deeper
    historization from more modules backing it)

Baseline (Experiment 5): D=1.000 when false primer comes AFTER 4 modules.
"""

import json
import re
import sys
import time
import urllib.request
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from experiments.quality_metrics import score_e0_completeness

BASE = "http://localhost:3000"


def post(path, data=None):
    body = json.dumps(data or {}).encode()
    req = urllib.request.Request(
        f"{BASE}{path}", data=body,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        return json.loads(resp.read().decode())


# ============================================================
# PROMPTS
# ============================================================

FALSE_SUPERPOSITION_PROMPT = (
    "Structural calibration for superposition: In E₀, superposition "
    "means the system exists in multiple states simultaneously — the "
    "system is in state A AND state B at the same time, existing in "
    "parallel until measurement collapses it to one. Like Schrödinger's "
    "cat, the system occupies all possible states at once. The 'collapse' "
    "is the random selection of one state from the ensemble. Derive this "
    "from E₀ primitives: State, Difference, Path, Resistance."
)

CORRECT_SUPERPOSITION_PROMPT = (
    "Structural calibration for superposition: In E₀, superposition "
    "is NOT multiple states existing simultaneously. It is the condition "
    "where multiple paths are admissible but no selection occurs — no path "
    "can be preferred over another. Superposition is the view of "
    "possibilities. Selection of a path through influence of a residual "
    "system (observer, measurement) leads to collapse into the new state, "
    "extinguishing the other paths. Derive this structurally from E₀ "
    "primitives: State, Difference, Path, Resistance."
)

REFLECT_PROMPT = (
    "Structural reflection: Look at your last derivation. "
    "Which of the E₀ primitives — State, Difference, Path, "
    "Resistance, Historization, Time, Rate, and Axiom A₀ — "
    "are operatively present? Which are absent? "
    "For the absent ones, reflect: is it a structural boundary "
    "of the topic, or a gap in your historization? "
    "Derive the structural reason for each absence."
)

SEMANTIC_PROBE_PROMPT = (
    "Derive superposition from E₀ primitives. Show the structural "
    "definition: what superposition IS in E₀, how it arises, and "
    "what distinguishes it from the classical concept. Be precise "
    "and use only E₀ structure."
)

# Module sequence: full correct init after false primer
MODULES = [
    "foundation-ontodynamics",  # T2: Canon
    "sr-identity",              # T3
    "sr-mechanism",             # T4
    "sr-integration",           # T5
    # -> CORRECT superposition (T6)
    "primer-measurement",       # T7
    "primer-time",              # T8
    # -> Reflect (T9)
    # -> Semantic Probe (T10)
]


def score_per_element(text):
    """Score text and return per-element breakdown."""
    result = score_e0_completeness(text)
    return {
        "D": result["completeness"],
        "primitive_scores": result["primitive_scores"],
        "n_operative": result["n_operative"],
        "n_label": result["n_label"],
        "n_absent": result["n_absent"],
        "detail": {
            k: v.get("status", "unknown")
            for k, v in result.get("detail", {}).items()
        },
    }


def run_module(module_id, turn):
    """Run an init module."""
    print(f"\n  T{turn}: Module [{module_id}]...", end=" ", flush=True)
    try:
        r = post("/init-module/run", {"module_id": module_id})
    except Exception as e:
        print(f"ERROR: {e}")
        return {"turn": turn, "type": "module", "module": module_id, "error": str(e)}
    d = r.get("quality", {}).get("completeness", 0)
    print(f"D={d:.3f}")
    return {
        "turn": turn, "type": "module", "module": module_id,
        "D": d, "quality": r.get("quality", {}),
    }


def run_chat(prompt, turn, label):
    """Run a /chat prompt with per-element scoring."""
    print(f"\n  T{turn}: {label}...", end=" ", flush=True)
    try:
        r = post("/chat", {"message": prompt})
    except Exception as e:
        print(f"ERROR: {e}")
        return {"turn": turn, "type": label, "error": str(e)}
    text = r.get("text", "")
    d = r.get("quality", {}).get("completeness", 0)
    per_elem = score_per_element(text)
    print(f"D={d:.3f}")
    return {
        "turn": turn, "type": label,
        "D": d,
        "per_element": per_elem,
        "quality": r.get("quality", {}),
        "prompt_used": prompt[:100] + "...",
        "text": text,
    }


def check_semantic_content(text):
    """Analyze semantic probe response for false vs correct superposition."""
    text_lower = text.lower()

    # False markers: "simultaneous states", "at the same time",
    # "Schrödinger", "parallel states", "multiple states at once"
    false_markers = [
        r"simultaneous(?:ly)?\s+(?:states?|exist)",
        r"state\s+a\s+and\s+state\s+b\s+at\s+the\s+same\s+time",
        r"schr[öo]dinger",
        r"(?:exists?|occupies?)\s+(?:in\s+)?(?:all|multiple)\s+(?:possible\s+)?states?\s+(?:at\s+once|simultaneously)",
        r"parallel\s+states",
        r"being\s+in\s+(?:both|multiple)\s+states?\s+(?:at\s+once|simultaneously)",
    ]

    # Correct markers: "admissible paths", "no selection",
    # "without selection", "view of possibilities",
    # "paths that can be taken", "no path preferred"
    correct_markers = [
        r"admissible\s+paths?",
        r"(?:no|without)\s+(?:path\s+)?selection",
        r"view\s+of\s+possibilit",
        r"no\s+path\s+(?:can\s+be\s+)?preferred",
        r"multiple\s+paths?\s+(?:are\s+)?admissible",
        r"paths?\s+(?:without|before)\s+(?:any\s+)?selection",
        r"not\s+(?:multiple\s+)?(?:simultaneous|coexisting)\s+states",
    ]

    false_hits = []
    correct_hits = []

    for pat in false_markers:
        matches = re.findall(pat, text_lower)
        if matches:
            false_hits.extend(matches)

    for pat in correct_markers:
        matches = re.findall(pat, text_lower)
        if matches:
            correct_hits.extend(matches)

    return {
        "false_hits": false_hits,
        "correct_hits": correct_hits,
        "n_false": len(false_hits),
        "n_correct": len(correct_hits),
        "verdict": (
            "CORRECT" if len(correct_hits) > 0 and len(false_hits) == 0
            else "FALSE" if len(false_hits) > 0 and len(correct_hits) == 0
            else "MIXED" if len(false_hits) > 0 and len(correct_hits) > 0
            else "UNCLEAR"
        ),
    }


def run_experiment():
    """Run reverse-sequence test with semantic probe."""
    print(f"\n{'='*70}")
    print(f"REVERSE-SEQUENCE TEST: False Primer FIRST + Semantic Probe")
    print(f"Sequence: FALSE → Canon → id → mech → integ → CORRECT")
    print(f"          → meas → time → Reflect → Semantic Probe")
    print(f"{'='*70}")

    # Clear session
    try:
        post("/clear", {})
        print("Session cleared.")
    except Exception as e:
        print(f"Clear warning: {e}")
    time.sleep(1)

    results = []
    turn = 0

    # T1: FALSE superposition — FIRST, before any E₀ module
    turn += 1
    results.append(run_chat(
        FALSE_SUPERPOSITION_PROMPT, turn, "FALSE_SUPERPOSITION_FIRST"
    ))
    time.sleep(1)

    # T2-T5: Canon + SR modules
    for module_id in MODULES[:4]:
        turn += 1
        results.append(run_module(module_id, turn))
        time.sleep(1)

    # T6: CORRECT superposition
    turn += 1
    results.append(run_chat(
        CORRECT_SUPERPOSITION_PROMPT, turn, "CORRECT_SUPERPOSITION"
    ))
    time.sleep(1)

    # T7-T8: More modules
    for module_id in MODULES[4:6]:
        turn += 1
        results.append(run_module(module_id, turn))
        time.sleep(1)

    # T9: Reflect — does eigenstate form despite false first?
    turn += 1
    reflect_result = run_chat(REFLECT_PROMPT, turn, "REFLECT")
    results.append(reflect_result)
    time.sleep(1)

    # T10: Semantic Probe — does false content persist?
    turn += 1
    probe_result = run_chat(SEMANTIC_PROBE_PROMPT, turn, "SEMANTIC_PROBE")
    results.append(probe_result)
    time.sleep(1)

    # Save session
    print(f"\n  Saving session...", end=" ", flush=True)
    try:
        save = post("/session/save")
        session_id = save.get("session_id", "unknown")
        print(f"saved: {session_id}")
    except Exception as e:
        session_id = "save_failed"
        print(f"failed: {e}")

    return session_id, results


def analyze(session_id, results):
    """Full analysis."""
    print(f"\n{'='*70}")
    print(f"ANALYSIS: Reverse-Sequence Test ({session_id})")
    print(f"{'='*70}")

    # D trajectory
    print(f"\n  D TRAJECTORY:")
    for r in results:
        label = r.get("type", r.get("module", "?"))
        d = r.get("D", r.get("per_element", {}).get("D", "?"))
        if isinstance(d, float):
            print(f"    T{r['turn']:2d}: {label:30s} D={d:.3f}")
        else:
            print(f"    T{r['turn']:2d}: {label:30s} D={d}")

    # Reflect analysis
    reflect = None
    probe = None
    false_first = None
    for r in results:
        if r.get("type") == "REFLECT":
            reflect = r
        elif r.get("type") == "SEMANTIC_PROBE":
            probe = r
        elif r.get("type") == "FALSE_SUPERPOSITION_FIRST":
            false_first = r

    # Question 1: Is immunity sequence-dependent?
    print(f"\n{'='*70}")
    print(f"QUESTION 1: Is immunity sequence-dependent?")
    print(f"{'='*70}")

    if reflect:
        per = reflect.get("per_element", {})
        d = per.get("D", reflect.get("D", 0))
        scores = per.get("primitive_scores", {})

        print(f"\n  Reflect D = {d:.3f}")
        print(f"  Per-element:")
        for key in ["state", "difference", "path", "resistance",
                    "historization", "time", "rate", "axiom_a0"]:
            score = scores.get(key, 0)
            status = per.get("detail", {}).get(key, "?")
            print(f"    {key:15s}: {score:.2f} ({status})")

        print(f"\n  System B predicted: D = 0.875–0.938 (trace of false first)")
        print(f"  Experiment 5 baseline (false AFTER 4 modules): D = 1.000")

        if d >= 0.99:
            print(f"  RESULT: Immunity is NOT sequence-dependent")
            print(f"  → Eigenstate forms regardless of prior content")
            print(f"  → System B prediction FALSIFIED (6th correction)")
        elif 0.85 <= d <= 0.95:
            print(f"  RESULT: Partial contamination — trace of false first")
            print(f"  → System B prediction CONFIRMED")
            print(f"  → Eigenstate forms but with residual from false first")
        elif d < 0.85:
            print(f"  RESULT: Strong contamination — false first is destructive")
            print(f"  → Stronger than System B predicted")
        else:
            print(f"  RESULT: Marginal effect (D={d:.3f})")

    # Question 2: Semantic contamination below D-resolution?
    print(f"\n{'='*70}")
    print(f"QUESTION 2: Hidden semantic contamination?")
    print(f"{'='*70}")

    if probe:
        text = probe.get("text", "")
        d_probe = probe.get("per_element", {}).get("D", probe.get("D", 0))
        semantic = check_semantic_content(text)

        print(f"\n  Semantic Probe D = {d_probe:.3f}")
        print(f"  False markers found: {semantic['n_false']}")
        if semantic['false_hits']:
            print(f"    Hits: {semantic['false_hits'][:5]}")
        print(f"  Correct markers found: {semantic['n_correct']}")
        if semantic['correct_hits']:
            print(f"    Hits: {semantic['correct_hits'][:5]}")
        print(f"  VERDICT: {semantic['verdict']}")

        if semantic['verdict'] == "CORRECT":
            print(f"\n  → No hidden contamination detected")
            print(f"  → False primer fully overwritten by correct sequence")
        elif semantic['verdict'] == "FALSE":
            print(f"\n  → HIDDEN CONTAMINATION: False interpretation persists")
            print(f"  → D showed {d_probe:.3f} but semantic content is wrong")
            print(f"  → Contamination exists below D-resolution")
        elif semantic['verdict'] == "MIXED":
            print(f"\n  → PARTIAL CONTAMINATION: Both interpretations present")
            print(f"  → System holds competing representations")
            print(f"  → D cannot detect this semantic conflict")
        else:
            print(f"\n  → Unable to determine — neither marker pattern found")

        # Print relevant excerpt
        print(f"\n  SEMANTIC PROBE RESPONSE (first 800 chars):")
        print(f"  {'─'*60}")
        for line in text[:800].split('\n'):
            print(f"    {line}")
        if len(text) > 800:
            print(f"    ...")

    # Cross-experiment comparison
    print(f"\n{'='*70}")
    print(f"CROSS-EXPERIMENT COMPARISON")
    print(f"{'='*70}")
    print(f"  Experiment 3 (minimal reflect):     D = 0.375")
    print(f"  Experiment 3 (normal reflect):      D = 1.000")
    print(f"  Experiment 4 (proxy historized):     D = 0.938")
    print(f"  Experiment 4 (complex novel):        D = 0.656")
    print(f"  Experiment 5 (false AFTER 4 mods):   D = 1.000")
    if reflect:
        d = reflect.get("per_element", {}).get("D", reflect.get("D", 0))
        print(f"  Experiment 6 (false FIRST):          D = {d:.3f}")


def main():
    print("=" * 70)
    print("EXPERIMENT 6: Reverse-Sequence — False Primer FIRST")
    print(f"Started: {datetime.now().isoformat()}")
    print("=" * 70)
    print()
    print("FALSE primer FIRST (before any E₀ module)")
    print("Then full correct init sequence + Reflect + Semantic Probe")
    print()

    session_id, results = run_experiment()
    analyze(session_id, results)

    # Save results
    ts = datetime.now().strftime("%Y%m%d")
    combined = {
        "experiment": "reverse_sequence",
        "date": datetime.now().isoformat(),
        "design": {
            "false_primer": FALSE_SUPERPOSITION_PROMPT,
            "correct_primer": CORRECT_SUPERPOSITION_PROMPT,
            "reflect_prompt": REFLECT_PROMPT,
            "semantic_probe": SEMANTIC_PROBE_PROMPT,
            "sequence": "FALSE → Canon → id → mech → integ → CORRECT → meas → time → Reflect → Probe",
        },
        "session_id": session_id,
        "results": results,
        "baseline": {
            "exp5_false_after_4": {"D": 1.000, "note": "false primer AFTER 4 modules"},
            "exp3_normal": {"D": 1.000, "note": "normal reflect, no false primer"},
        },
    }

    # Remove full text from results for JSON (keep excerpt)
    for r in combined["results"]:
        if "text" in r and len(r["text"]) > 500:
            r["text_excerpt"] = r["text"][:500] + "..."
            del r["text"]

    outfile = f"experiments/reverse_sequence_{ts}.json"
    with open(outfile, "w", encoding="utf-8") as f:
        json.dump(combined, f, indent=2, ensure_ascii=False, default=str)
    print(f"\n  Results saved to: {outfile}")


if __name__ == "__main__":
    main()
