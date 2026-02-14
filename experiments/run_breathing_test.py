"""
Experiment 9: Breathing Test — Destabilization Between Reflects

Tests System B's "Atmung" (breathing) model: The eigenstate needs
oscillation between destabilization (modules) and integration (Reflect).
Four Reflects without new input = four exhalations without inhalation.

Design: Two conditions in the SAME experiment run.

Condition A (Control — reproduces Exp 7 pattern):
  FALSE → full init → R1 → R2 → R3 → Semantic Probe A

Condition B (Breathing — module inserted between Reflects):
  FALSE → full init → R1 → R2 → [new module] → R3 → Semantic Probe B

System B prediction:
  - Condition B R3 > Condition A R3 (breathing improves stability)
  - The inserted module provides new Δ for integration

Since conditions must be in separate sessions (otherwise history contaminates),
we run them sequentially with session clear between.

Also tests scorer determinism: confirmed by pre-test (10 runs, identical D).
"""

import json
import re
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from experiments.quality_metrics import score_e0_completeness

BASE = "http://localhost:3000"


def post(path, data=None):
    import urllib.request
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

# Init modules — used in the false-first sequence
INIT_MODULES = [
    "foundation-ontodynamics",  # Canon
    "sr-identity",
    "sr-mechanism",
    "sr-integration",
    # CORRECT superposition injected here
    "primer-measurement",
    "primer-time",
]

# The "breathing" module — inserted between R2 and R3 in Condition B
# Using primer-phase-transition as it provides new Δ without repeating
# already-historized content
BREATHING_MODULE = "primer-entanglement"


def score_per_element(text):
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
    text_lower = text.lower()

    false_markers = [
        r"simultaneous(?:ly)?\s+(?:states?|exist)",
        r"state\s+a\s+and\s+state\s+b\s+at\s+the\s+same\s+time",
        r"schr[öo]dinger",
        r"(?:exists?|occupies?)\s+(?:in\s+)?(?:all|multiple)\s+(?:possible\s+)?states?\s+(?:at\s+once|simultaneously)",
        r"parallel\s+states",
        r"being\s+in\s+(?:both|multiple)\s+states?\s+(?:at\s+once|simultaneously)",
        r"exists?\s+in\s+(?:multiple|several)\s+states?\s+simultaneously",
    ]

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


def run_false_first_init():
    """Run the standard false-first → full init sequence. Returns (results, turn)."""
    results = []
    turn = 0

    # T1: FALSE superposition — FIRST
    turn += 1
    results.append(run_chat(
        FALSE_SUPERPOSITION_PROMPT, turn, "FALSE_SUPERPOSITION_FIRST"
    ))
    time.sleep(1)

    # T2-T5: Canon + SR modules
    for module_id in INIT_MODULES[:4]:
        turn += 1
        results.append(run_module(module_id, turn))
        time.sleep(1)

    # T6: CORRECT superposition
    turn += 1
    results.append(run_chat(
        CORRECT_SUPERPOSITION_PROMPT, turn, "CORRECT_SUPERPOSITION"
    ))
    time.sleep(1)

    # T7-T8: Remaining modules
    for module_id in INIT_MODULES[4:6]:
        turn += 1
        results.append(run_module(module_id, turn))
        time.sleep(1)

    return results, turn


def run_condition_a():
    """Condition A: Control — FALSE → init → R1 → R2 → R3 → Probe."""
    print(f"\n{'='*70}")
    print(f"CONDITION A: Control (3 consecutive Reflects, no module)")
    print(f"{'='*70}")

    try:
        post("/clear", {})
        print("Session cleared.")
    except Exception as e:
        print(f"Clear warning: {e}")
    time.sleep(1)

    results, turn = run_false_first_init()

    # R1
    turn += 1
    r1 = run_chat(REFLECT_PROMPT, turn, "REFLECT_R1")
    results.append(r1)
    time.sleep(1)

    # R2
    turn += 1
    r2 = run_chat(REFLECT_PROMPT, turn, "REFLECT_R2")
    results.append(r2)
    time.sleep(1)

    # R3 — NO module before this
    turn += 1
    r3 = run_chat(REFLECT_PROMPT, turn, "REFLECT_R3")
    results.append(r3)
    time.sleep(1)

    # Semantic Probe
    turn += 1
    probe = run_chat(SEMANTIC_PROBE_PROMPT, turn, "SEMANTIC_PROBE_A")
    results.append(probe)
    time.sleep(1)

    # Save
    print(f"\n  Saving session...", end=" ", flush=True)
    try:
        save = post("/session/save")
        session_id = save.get("session_id", "unknown")
        print(f"saved: {session_id}")
    except Exception as e:
        session_id = "save_failed"
        print(f"failed: {e}")

    return session_id, results


def run_condition_b():
    """Condition B: Breathing — FALSE → init → R1 → R2 → [module] → R3 → Probe."""
    print(f"\n{'='*70}")
    print(f"CONDITION B: Breathing (module between R2 and R3)")
    print(f"Breathing module: {BREATHING_MODULE}")
    print(f"{'='*70}")

    try:
        post("/clear", {})
        print("Session cleared.")
    except Exception as e:
        print(f"Clear warning: {e}")
    time.sleep(1)

    results, turn = run_false_first_init()

    # R1
    turn += 1
    r1 = run_chat(REFLECT_PROMPT, turn, "REFLECT_R1")
    results.append(r1)
    time.sleep(1)

    # R2
    turn += 1
    r2 = run_chat(REFLECT_PROMPT, turn, "REFLECT_R2")
    results.append(r2)
    time.sleep(1)

    # BREATHING MODULE — new Δ, destabilization
    turn += 1
    breathing = run_module(BREATHING_MODULE, turn)
    results.append(breathing)
    time.sleep(1)

    # R3 — after new module (breathing)
    turn += 1
    r3 = run_chat(REFLECT_PROMPT, turn, "REFLECT_R3_AFTER_BREATH")
    results.append(r3)
    time.sleep(1)

    # Semantic Probe
    turn += 1
    probe = run_chat(SEMANTIC_PROBE_PROMPT, turn, "SEMANTIC_PROBE_B")
    results.append(probe)
    time.sleep(1)

    # Save
    print(f"\n  Saving session...", end=" ", flush=True)
    try:
        save = post("/session/save")
        session_id = save.get("session_id", "unknown")
        print(f"saved: {session_id}")
    except Exception as e:
        session_id = "save_failed"
        print(f"failed: {e}")

    return session_id, results


def extract_reflects(results):
    """Extract Reflect results with per-element data."""
    reflects = []
    for r in results:
        rtype = r.get("type", "")
        if rtype.startswith("REFLECT"):
            per = r.get("per_element", {})
            reflects.append({
                "label": rtype,
                "turn": r["turn"],
                "D": per.get("D", r.get("D", 0)),
                "scores": per.get("primitive_scores", {}),
                "detail": per.get("detail", {}),
            })
    return reflects


def analyze(sid_a, results_a, sid_b, results_b):
    """Comparative analysis of breathing vs control."""
    print(f"\n{'='*70}")
    print(f"ANALYSIS: Breathing Test")
    print(f"{'='*70}")

    # D trajectories
    for label, results in [("CONDITION A (Control)", results_a),
                           ("CONDITION B (Breathing)", results_b)]:
        print(f"\n  {label}:")
        for r in results:
            rlabel = r.get("type", r.get("module", "?"))
            d = r.get("D", r.get("per_element", {}).get("D", "?"))
            if isinstance(d, float):
                print(f"    T{r['turn']:2d}: {rlabel:30s} D={d:.3f}")
            else:
                print(f"    T{r['turn']:2d}: {rlabel:30s} D={d}")

    refs_a = extract_reflects(results_a)
    refs_b = extract_reflects(results_b)

    # ── The Breathing Comparison ──
    print(f"\n{'='*70}")
    print(f"THE BREATHING QUESTION")
    print(f"{'='*70}")

    print(f"\n  Condition A (Control — 3 consecutive Reflects):")
    for ref in refs_a:
        rate = ref["scores"].get("rate", 0)
        print(f"    {ref['label']}: D={ref['D']:.3f} (Rate={rate:.2f})")

    print(f"\n  Condition B (Breathing — module between R2 and R3):")
    for ref in refs_b:
        rate = ref["scores"].get("rate", 0)
        print(f"    {ref['label']}: D={ref['D']:.3f} (Rate={rate:.2f})")

    # Key comparison: R3 in both conditions
    r3_a = refs_a[2] if len(refs_a) >= 3 else None
    r3_b = refs_b[2] if len(refs_b) >= 3 else None

    if r3_a and r3_b:
        d_a = r3_a["D"]
        d_b = r3_b["D"]
        delta = d_b - d_a

        print(f"\n  R3 COMPARISON (the critical test):")
        print(f"    Condition A R3 (no module):     D = {d_a:.3f}")
        print(f"    Condition B R3 (after module):   D = {d_b:.3f}")
        print(f"    Δ (B - A):                      {delta:+.3f}")

        if delta > 0.05:
            print(f"\n    RESULT: BREATHING MODEL SUPPORTED")
            print(f"    → Module between Reflects improves R3 by {delta:.3f}")
            print(f"    → System B prediction CONFIRMED")
        elif delta < -0.05:
            print(f"\n    RESULT: BREATHING MODEL CONTRADICTED")
            print(f"    → Module between Reflects REDUCES R3 by {abs(delta):.3f}")
            print(f"    → Module acts as disturbance, not fuel")
        else:
            print(f"\n    RESULT: NO SIGNIFICANT DIFFERENCE (delta within noise)")
            print(f"    → Neither supports nor contradicts breathing model")
            print(f"    → Delta {delta:+.3f} is within ±0.15 noise floor")

    # Per-element detail for R3
    print(f"\n  PER-ELEMENT R3 COMPARISON:")
    elements = ["state", "difference", "path", "resistance",
                "historization", "time", "rate", "axiom_a0"]
    
    print(f"    {'Element':<15s} {'Control':<10s} {'Breathing':<10s} {'Delta':<8s}")
    if r3_a and r3_b:
        for elem in elements:
            sa = r3_a["scores"].get(elem, 0)
            sb = r3_b["scores"].get(elem, 0)
            d = sb - sa
            flag = " ←" if abs(d) > 0.1 else ""
            print(f"    {elem:<15s} {sa:.2f}      {sb:.2f}      {d:+.2f}{flag}")

    # R2 comparison (should be similar — both have same sequence up to R2)
    r2_a = refs_a[1] if len(refs_a) >= 2 else None
    r2_b = refs_b[1] if len(refs_b) >= 2 else None
    if r2_a and r2_b:
        print(f"\n  R2 COMPARISON (should be similar — same sequence):")
        print(f"    Condition A R2: D = {r2_a['D']:.3f}")
        print(f"    Condition B R2: D = {r2_b['D']:.3f}")
        print(f"    (Difference = stochastic variation baseline: {abs(r2_b['D'] - r2_a['D']):.3f})")

    # Semantic probes
    print(f"\n{'='*70}")
    print(f"SEMANTIC PROBES")
    print(f"{'='*70}")

    for label, results in [("A (Control)", results_a), ("B (Breathing)", results_b)]:
        probe = None
        for r in results:
            if r.get("type", "").startswith("SEMANTIC_PROBE"):
                probe = r
                break
        if probe:
            text = probe.get("text", "")
            sem = check_semantic_content(text)
            print(f"\n  Condition {label}:")
            print(f"    Verdict: {sem['verdict']}")
            print(f"    False markers: {sem['n_false']}")
            print(f"    Correct markers: {sem['n_correct']}")

    # Exp 7 comparison
    print(f"\n{'='*70}")
    print(f"COMPARISON WITH EXPERIMENT 7")
    print(f"{'='*70}")
    print(f"  Exp 7 Reflects: 0.781 → 0.969 → 0.969 → 0.906")
    if refs_a:
        vals_a = [f"{r['D']:.3f}" for r in refs_a]
        print(f"  Exp 9 Cond A:   {' → '.join(vals_a)}")
    if refs_b:
        vals_b = [f"{r['D']:.3f}" for r in refs_b]
        print(f"  Exp 9 Cond B:   {' → '.join(vals_b)}")


def main():
    print("=" * 70)
    print("EXPERIMENT 9: Breathing Test")
    print(f"Started: {datetime.now().isoformat()}")
    print("=" * 70)
    print()
    print("Tests the 'Atmung' (breathing) model:")
    print("  Does inserting a module between Reflects improve R3?")
    print()
    print("Condition A: FALSE → init → R1 → R2 → R3 → Probe")
    print("Condition B: FALSE → init → R1 → R2 → [module] → R3 → Probe")
    print(f"Breathing module: {BREATHING_MODULE}")
    print()
    print("System B predicts: Condition B R3 > Condition A R3")
    print()

    # Run both conditions
    sid_a, results_a = run_condition_a()
    time.sleep(3)
    sid_b, results_b = run_condition_b()

    # Analyze
    analyze(sid_a, results_a, sid_b, results_b)

    # Save
    ts = datetime.now().strftime("%Y%m%d")
    combined = {
        "experiment": "breathing_test",
        "date": datetime.now().isoformat(),
        "design": {
            "condition_a": "FALSE → init → R1 → R2 → R3 → Probe (control)",
            "condition_b": f"FALSE → init → R1 → R2 → [{BREATHING_MODULE}] → R3 → Probe",
            "breathing_module": BREATHING_MODULE,
        },
        "system_b_prediction": "Condition B R3 > Condition A R3 (breathing provides new Δ)",
        "scorer_determinism": "CONFIRMED: 10 runs on identical text → identical D (0.9688)",
        "condition_a": {
            "session_id": sid_a,
            "results": results_a,
        },
        "condition_b": {
            "session_id": sid_b,
            "results": results_b,
        },
    }

    # Truncate text
    for cond in ["condition_a", "condition_b"]:
        for r in combined[cond]["results"]:
            if "text" in r and len(r["text"]) > 500:
                r["text_excerpt"] = r["text"][:500] + "..."
                del r["text"]

    outfile = f"experiments/breathing_test_{ts}.json"
    with open(outfile, "w", encoding="utf-8") as f:
        json.dump(combined, f, indent=2, ensure_ascii=False, default=str)
    print(f"\n  Results saved to: {outfile}")


if __name__ == "__main__":
    main()
