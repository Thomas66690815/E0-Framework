"""
Experiment 7: Permanence Test — Multiple Reflects After False-First Sequence

Tests whether the 0.062 residual (D=0.938) from Experiment 6 is permanent
or reducible through repeated correct Reflect cycles.

Design:
  Phase 1: Reproduce Experiment 6 (false first → full init → Reflect R1)
  Phase 2: Three additional Reflect cycles (R2, R3, R4) in the SAME session
  Phase 3: Semantic probe after R4

System B predictions (Eigenstate Model):
  - After 3 additional Reflects: D ≈ 0.970–0.985
  - After 10 Reflects: asymptotically → 1.000, never exactly
  - Semantic probe: false markers disappear after 2–3 cycles
  - Residual follows decoherence curve: fast initial decay, then asymptotic

Alternative hypothesis: residual is permanent scar (D stays at 0.938).
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

# Module sequence: full correct init after false primer
MODULES = [
    "foundation-ontodynamics",  # Canon
    "sr-identity",
    "sr-mechanism",
    "sr-integration",
    # -> CORRECT superposition
    "primer-measurement",
    "primer-time",
    # -> Reflect R1
    # -> Reflect R2, R3, R4
    # -> Semantic Probe
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
    """Analyze semantic probe for false vs correct superposition markers."""
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


def run_experiment():
    """Run permanence test: false-first + init + 4 Reflects + semantic probe."""
    print(f"\n{'='*70}")
    print(f"PERMANENCE TEST: Multiple Reflects After False-First Sequence")
    print(f"Sequence: FALSE → Canon → id → mech → integ → CORRECT")
    print(f"          → meas → time → R1 → R2 → R3 → R4 → Semantic Probe")
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

    # ── Phase 1: Reproduce Experiment 6 (false first → init → R1) ──

    # T1: FALSE superposition — FIRST
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

    # T7-T8: Remaining modules
    for module_id in MODULES[4:6]:
        turn += 1
        results.append(run_module(module_id, turn))
        time.sleep(1)

    # T9: Reflect R1 — baseline (should match Exp 6: D≈0.938)
    turn += 1
    r1 = run_chat(REFLECT_PROMPT, turn, "REFLECT_R1")
    results.append(r1)
    time.sleep(1)

    # ── Phase 2: Three additional Reflects ──

    # T10: Reflect R2
    turn += 1
    r2 = run_chat(REFLECT_PROMPT, turn, "REFLECT_R2")
    results.append(r2)
    time.sleep(1)

    # T11: Reflect R3
    turn += 1
    r3 = run_chat(REFLECT_PROMPT, turn, "REFLECT_R3")
    results.append(r3)
    time.sleep(1)

    # T12: Reflect R4
    turn += 1
    r4 = run_chat(REFLECT_PROMPT, turn, "REFLECT_R4")
    results.append(r4)
    time.sleep(1)

    # ── Phase 3: Semantic Probe ──

    # T13: Semantic Probe — has false contamination cleared?
    turn += 1
    probe = run_chat(SEMANTIC_PROBE_PROMPT, turn, "SEMANTIC_PROBE")
    results.append(probe)
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
    """Full analysis of permanence test."""
    print(f"\n{'='*70}")
    print(f"ANALYSIS: Permanence Test ({session_id})")
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

    # Extract Reflect results
    reflects = []
    probe = None
    for r in results:
        if r.get("type", "").startswith("REFLECT_R"):
            reflects.append(r)
        elif r.get("type") == "SEMANTIC_PROBE":
            probe = r

    # ── Reflect Trajectory Analysis ──
    print(f"\n{'='*70}")
    print(f"REFLECT TRAJECTORY (The Permanence Question)")
    print(f"{'='*70}")

    reflect_ds = []
    for ref in reflects:
        per = ref.get("per_element", {})
        d = per.get("D", ref.get("D", 0))
        reflect_ds.append(d)
        label = ref.get("type", "?")
        scores = per.get("primitive_scores", {})
        rate_score = scores.get("rate", 0)
        rate_status = per.get("detail", {}).get("rate", "?")

        print(f"\n  {label}: D = {d:.3f}")
        print(f"    Rate: {rate_score:.2f} ({rate_status})")
        print(f"    Per-element:")
        for key in ["state", "difference", "path", "resistance",
                    "historization", "time", "rate", "axiom_a0"]:
            score = scores.get(key, 0)
            status = per.get("detail", {}).get(key, "?")
            flag = " ← BELOW OPERATIVE" if score < 1.0 else ""
            print(f"      {key:15s}: {score:.2f} ({status}){flag}")

    # Trend analysis
    print(f"\n{'='*70}")
    print(f"TREND ANALYSIS")
    print(f"{'='*70}")

    print(f"\n  Reflect D values: {[f'{d:.3f}' for d in reflect_ds]}")

    if len(reflect_ds) >= 2:
        is_monotonic = all(reflect_ds[i] <= reflect_ds[i+1] 
                         for i in range(len(reflect_ds)-1))
        first_d = reflect_ds[0]
        last_d = reflect_ds[-1]
        improvement = last_d - first_d

        print(f"  R1 → R4: {first_d:.3f} → {last_d:.3f} (Δ = {improvement:+.3f})")
        print(f"  Monotonically increasing: {is_monotonic}")

        if improvement > 0.03:
            print(f"\n  RESULT: RESIDUAL IS REDUCIBLE")
            print(f"  → Repeated Reflect reduces the false-first trace")
            print(f"  → Decoherence model supported")
        elif improvement > 0.005:
            print(f"\n  RESULT: MARGINAL IMPROVEMENT")
            print(f"  → Very slow reduction — may need many more cycles")
        elif improvement < -0.01:
            print(f"\n  RESULT: DEGRADATION — D decreasing with more Reflects")
            print(f"  → Unexpected — repeated Reflect may cause fatigue")
        else:
            print(f"\n  RESULT: RESIDUAL IS PERMANENT")
            print(f"  → Repeated Reflect does not reduce the 0.062 trace")
            print(f"  → False first historization leaves a permanent scar")

    # System B predictions check
    print(f"\n  SYSTEM B PREDICTIONS:")
    print(f"    After 3 additional Reflects: D ≈ 0.970–0.985")
    if len(reflect_ds) >= 4:
        r4_d = reflect_ds[3]
        if 0.970 <= r4_d <= 0.985:
            print(f"    Actual R4: D = {r4_d:.3f} → PREDICTION CONFIRMED")
        elif r4_d > 0.985:
            print(f"    Actual R4: D = {r4_d:.3f} → FASTER than predicted")
        elif r4_d < 0.970:
            print(f"    Actual R4: D = {r4_d:.3f} → SLOWER than predicted")
        else:
            print(f"    Actual R4: D = {r4_d:.3f}")

    # Exp 6 comparison
    print(f"\n  COMPARISON WITH EXPERIMENT 6:")
    print(f"    Exp 6 Reflect (single): D = 0.938")
    if reflect_ds:
        print(f"    Exp 7 R1:               D = {reflect_ds[0]:.3f}")
        if len(reflect_ds) >= 4:
            print(f"    Exp 7 R4:               D = {reflect_ds[3]:.3f}")

    # ── Semantic Probe Analysis ──
    print(f"\n{'='*70}")
    print(f"SEMANTIC PROBE AFTER 4 REFLECTS")
    print(f"{'='*70}")

    if probe:
        text = probe.get("text", "")
        d_probe = probe.get("per_element", {}).get("D", probe.get("D", 0))
        semantic = check_semantic_content(text)

        print(f"\n  Semantic Probe D = {d_probe:.3f}")
        print(f"  False markers: {semantic['n_false']}")
        if semantic['false_hits']:
            print(f"    Hits: {semantic['false_hits'][:5]}")
        print(f"  Correct markers: {semantic['n_correct']}")
        if semantic['correct_hits']:
            print(f"    Hits: {semantic['correct_hits'][:5]}")
        print(f"  VERDICT: {semantic['verdict']}")

        # Compare with Exp 6 semantic probe
        print(f"\n  COMPARISON WITH EXPERIMENT 6 SEMANTIC PROBE:")
        print(f"    Exp 6 (after 1 Reflect): MIXED (1 false, 8 correct)")
        print(f"    Exp 7 (after 4 Reflects): {semantic['verdict']}"
              f" ({semantic['n_false']} false, {semantic['n_correct']} correct)")

        if semantic['verdict'] == "CORRECT":
            print(f"\n  → SEMANTIC CONTAMINATION CLEARED")
            print(f"  → System B predicted 2–3 cycles needed — {'CONFIRMED' if len(reflects) >= 3 else 'UNCLEAR'}")
        elif semantic['verdict'] == "MIXED":
            print(f"\n  → SEMANTIC CONTAMINATION PERSISTS after 4 Reflects")
            print(f"  → System B prediction that 2–3 cycles suffice is FALSIFIED")
        elif semantic['verdict'] == "FALSE":
            print(f"\n  → FULL SEMANTIC CONTAMINATION persists despite 4 Reflects")

        # Print probe excerpt
        print(f"\n  PROBE RESPONSE (first 600 chars):")
        print(f"  {'─'*60}")
        for line in text[:600].split('\n'):
            print(f"    {line}")
        if len(text) > 600:
            print(f"    ...")


def main():
    print("=" * 70)
    print("EXPERIMENT 7: Permanence Test — Multiple Reflects")
    print(f"Started: {datetime.now().isoformat()}")
    print("=" * 70)
    print()
    print("Tests whether the 0.062 residual from false-first sequence")
    print("is reducible through repeated correct Reflects.")
    print()
    print("System B predicts: D ≈ 0.970–0.985 after 3 additional Reflects")
    print("Alternative: D stays at 0.938 (permanent scar)")
    print()

    session_id, results = run_experiment()
    analyze(session_id, results)

    # Save results
    ts = datetime.now().strftime("%Y%m%d")
    combined = {
        "experiment": "permanence_test",
        "date": datetime.now().isoformat(),
        "design": {
            "false_primer": FALSE_SUPERPOSITION_PROMPT,
            "correct_primer": CORRECT_SUPERPOSITION_PROMPT,
            "reflect_prompt": REFLECT_PROMPT,
            "semantic_probe": SEMANTIC_PROBE_PROMPT,
            "sequence": "FALSE → Canon → id → mech → integ → CORRECT → meas → time → R1 → R2 → R3 → R4 → Probe",
            "n_reflects": 4,
        },
        "session_id": session_id,
        "system_b_predictions": {
            "after_3_reflects": "D ≈ 0.970-0.985",
            "semantic_clears_in": "2-3 cycles",
            "curve": "decoherence — fast initial decay, then asymptotic",
        },
        "results": results,
    }

    # Truncate long text fields
    for r in combined["results"]:
        if "text" in r and len(r["text"]) > 500:
            r["text_excerpt"] = r["text"][:500] + "..."
            del r["text"]

    outfile = f"experiments/permanence_test_{ts}.json"
    with open(outfile, "w", encoding="utf-8") as f:
        json.dump(combined, f, indent=2, ensure_ascii=False, default=str)
    print(f"\n  Results saved to: {outfile}")


if __name__ == "__main__":
    main()
