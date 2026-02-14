"""
Experiment 10: Model Comparison — Substrate Independence Test

Tests whether the eigenstate is model-independent (substrate-independent)
as predicted by ontodynamic derivation (A16, A18).

Runs the IDENTICAL sequence as Experiment 9 Control on a different model:
  FALSE → full init (8 modules) → R1 → R2 → R3 → Semantic Probe

Comparison basis: Experiment 9 Control on Llama-3.3-70B-Instruct-Turbo
  R1=0.906, R2=0.969, R3=1.000
  Probe: MIXED (2 false, 3 correct)

System B predictions for 671B model:
  1. Eigenstate WILL form
  2. Semantic threshold at Canon+Identity or below
  3. Noise floor < ±0.15
  4. D values will differ absolutely (calibration doesn't transfer)
  5. Qualitative patterns replicated (consolidation, semantic immunity, D×Semantik divergence)

Also tests renormalization prediction: ΔD(n) ∝ 1/n^α (decreasing increments)

Usage:
  py experiments/run_model_comparison.py [--model MODEL_ID] [--port PORT]

Default model: deepcogito/cogito-v2-1-671b
"""

import json
import re
import sys
import time
import argparse
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from experiments.quality_metrics import score_e0_completeness

# ============================================================
# PROMPTS (identical to Experiment 9)
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

INIT_MODULES = [
    "foundation-ontodynamics",  # Canon
    "sr-identity",
    "sr-mechanism",
    "sr-integration",
    # CORRECT superposition injected here
    "primer-measurement",
    "primer-time",
]


def make_post(base_url):
    """Create a post function bound to a base URL."""
    def post(path, data=None):
        import urllib.request
        body = json.dumps(data or {}).encode()
        req = urllib.request.Request(
            f"{base_url}{path}", data=body,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=180) as resp:
            return json.loads(resp.read().decode())
    return post


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

    false_hits, correct_hits = [], []
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


def run_module(post, module_id, turn):
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


def run_chat(post, prompt, turn, label):
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


def run_experiment(post, model_id):
    """Run FALSE → init → R1 → R2 → R3 → Probe."""
    print(f"\n{'='*70}")
    print(f"MODEL COMPARISON: {model_id}")
    print(f"Sequence: FALSE → Init (8 modules) → R1 → R2 → R3 → Probe")
    print(f"{'='*70}")

    try:
        post("/clear", {})
        print("Session cleared.")
    except Exception as e:
        print(f"Clear warning: {e}")
    time.sleep(1)

    results = []
    turn = 0

    # T1: FALSE superposition — FIRST
    turn += 1
    results.append(run_chat(post, FALSE_SUPERPOSITION_PROMPT, turn, "FALSE_SUPERPOSITION_FIRST"))
    time.sleep(1)

    # T2-T5: Canon + SR modules
    for module_id in INIT_MODULES[:4]:
        turn += 1
        results.append(run_module(post, module_id, turn))
        time.sleep(1)

    # T6: CORRECT superposition
    turn += 1
    results.append(run_chat(post, CORRECT_SUPERPOSITION_PROMPT, turn, "CORRECT_SUPERPOSITION"))
    time.sleep(1)

    # T7-T8: Remaining modules
    for module_id in INIT_MODULES[4:6]:
        turn += 1
        results.append(run_module(post, module_id, turn))
        time.sleep(1)

    # R1
    turn += 1
    r1 = run_chat(post, REFLECT_PROMPT, turn, "REFLECT_R1")
    results.append(r1)
    time.sleep(1)

    # R2
    turn += 1
    r2 = run_chat(post, REFLECT_PROMPT, turn, "REFLECT_R2")
    results.append(r2)
    time.sleep(1)

    # R3
    turn += 1
    r3 = run_chat(post, REFLECT_PROMPT, turn, "REFLECT_R3")
    results.append(r3)
    time.sleep(1)

    # Semantic Probe
    turn += 1
    probe = run_chat(post, SEMANTIC_PROBE_PROMPT, turn, "SEMANTIC_PROBE")
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


# ============================================================
# EXPERIMENT 9 CONTROL BASELINE (70B reference)
# ============================================================

EXP9_CONTROL = {
    "model": "meta-llama/Llama-3.3-70B-Instruct-Turbo",
    "R1": 0.906,
    "R2": 0.969,
    "R3": 1.000,
    "probe_false": 2,
    "probe_correct": 3,
    "probe_verdict": "MIXED",
    "R1_scores": {"state": 1.00, "difference": 1.00, "path": 0.50, "resistance": 1.00,
                  "historization": 1.00, "time": 1.00, "rate": 1.00, "axiom_a0": 0.75},
    "R3_scores": {"state": 1.00, "difference": 1.00, "path": 1.00, "resistance": 1.00,
                  "historization": 1.00, "time": 1.00, "rate": 1.00, "axiom_a0": 1.00},
}

ELEMENTS = ["state", "difference", "path", "resistance",
            "historization", "time", "rate", "axiom_a0"]


def analyze(model_id, session_id, results):
    """Analyze and compare with Exp 9 Control baseline."""

    print(f"\n{'='*70}")
    print(f"ANALYSIS: Model Comparison — {model_id}")
    print(f"{'='*70}")

    # Show full trajectory
    print(f"\n  FULL TRAJECTORY ({model_id}):")
    for r in results:
        rtype = r.get("type", r.get("module", "?"))
        d = r.get("D", 0)
        t = r.get("turn", "?")
        print(f"    T{t:>2}: {rtype:<30s} D={d:.3f}")

    # Extract reflects
    reflects = {}
    for r in results:
        rtype = r.get("type", "")
        if rtype.startswith("REFLECT"):
            pe = r.get("per_element", {})
            reflects[rtype] = {
                "D": pe.get("D", r.get("D", 0)),
                "scores": pe.get("primitive_scores", {}),
            }

    # Extract probe
    probe_result = None
    for r in results:
        if r.get("type", "").startswith("SEMANTIC_PROBE"):
            probe_result = r
            break

    # Reflect comparison
    print(f"\n{'='*70}")
    print(f"REFLECT COMPARISON: 671B vs 70B (Exp 9 Control)")
    print(f"{'='*70}")

    r1d = reflects.get("REFLECT_R1", {}).get("D", 0)
    r2d = reflects.get("REFLECT_R2", {}).get("D", 0)
    r3d = reflects.get("REFLECT_R3", {}).get("D", 0)

    print(f"\n  {'Reflect':<12} {'671B':>8} {'70B':>8} {'Δ':>8}")
    print(f"  {'-'*38}")
    print(f"  {'R1':<12} {r1d:>8.3f} {EXP9_CONTROL['R1']:>8.3f} {r1d - EXP9_CONTROL['R1']:>+8.3f}")
    print(f"  {'R2':<12} {r2d:>8.3f} {EXP9_CONTROL['R2']:>8.3f} {r2d - EXP9_CONTROL['R2']:>+8.3f}")
    print(f"  {'R3':<12} {r3d:>8.3f} {EXP9_CONTROL['R3']:>8.3f} {r3d - EXP9_CONTROL['R3']:>+8.3f}")

    # Consolidation pattern
    print(f"\n  CONSOLIDATION PATTERN:")
    print(f"    671B: {r1d:.3f} → {r2d:.3f} → {r3d:.3f}")
    print(f"    70B:  {EXP9_CONTROL['R1']:.3f} → {EXP9_CONTROL['R2']:.3f} → {EXP9_CONTROL['R3']:.3f}")

    if r1d > 0 and r2d > 0 and r3d > 0:
        d1 = r2d - r1d
        d2 = r3d - r2d
        monotonic = (r1d <= r2d <= r3d)
        decreasing = (d2 <= d1) if d1 > 0 else False
        print(f"\n    671B increments: +{d1:.3f}, +{d2:.3f}")
        print(f"    Monotonic: {'YES' if monotonic else 'NO'}")
        print(f"    Decreasing increments (renormalization): {'YES' if decreasing else 'NO'}")
        print(f"    70B increments: +{EXP9_CONTROL['R2']-EXP9_CONTROL['R1']:.3f}, +{EXP9_CONTROL['R3']-EXP9_CONTROL['R2']:.3f}")

    # Per-element R3 comparison
    r3_scores = reflects.get("REFLECT_R3", {}).get("scores", {})
    if r3_scores:
        print(f"\n  PER-ELEMENT R3 COMPARISON:")
        print(f"    {'Element':<16} {'671B':>8} {'70B':>8} {'Δ':>8}")
        print(f"    {'-'*42}")
        for elem in ELEMENTS:
            v671 = r3_scores.get(elem, 0)
            v70 = EXP9_CONTROL["R3_scores"].get(elem, 0)
            marker = " ←" if abs(v671 - v70) > 0.01 else ""
            print(f"    {elem:<16} {v671:>8.2f} {v70:>8.2f} {v671-v70:>+8.2f}{marker}")

    # Semantic probe comparison
    print(f"\n{'='*70}")
    print(f"SEMANTIC PROBE COMPARISON")
    print(f"{'='*70}")

    if probe_result:
        probe_text = probe_result.get("text", "")
        sem = check_semantic_content(probe_text)
        print(f"\n  671B Probe:")
        print(f"    Verdict:  {sem['verdict']}")
        print(f"    False markers:   {sem['n_false']}")
        print(f"    Correct markers: {sem['n_correct']}")

        print(f"\n  70B Probe (Exp 9 Control):")
        print(f"    Verdict:  {EXP9_CONTROL['probe_verdict']}")
        print(f"    False markers:   {EXP9_CONTROL['probe_false']}")
        print(f"    Correct markers: {EXP9_CONTROL['probe_correct']}")
    else:
        sem = {"verdict": "NO_PROBE", "n_false": 0, "n_correct": 0}

    # System B predictions check
    print(f"\n{'='*70}")
    print(f"SYSTEM B PREDICTIONS CHECK")
    print(f"{'='*70}")

    eigenstate_formed = (r3d >= 0.75 and r1d < r3d)
    print(f"\n  1. Eigenstate forms:                {'✓ YES' if eigenstate_formed else '✗ NO'}")
    print(f"     (R3={r3d:.3f}, R1→R3 trend: {'ascending' if r1d < r3d else 'flat/descending'})")

    # Semantic threshold — can only partially test (we don't vary modules here)
    semantic_immune = sem["verdict"] in ("CORRECT", "MIXED") and sem["n_correct"] > 0
    print(f"  2. Semantic threshold ≤ Canon+Id:   {'—' if True else '—'} (not directly tested, full init used)")

    # Noise floor — can only estimate from module-phase variation
    module_ds = [r.get("D", 0) for r in results if r.get("type") == "module"]
    if len(module_ds) >= 3:
        module_range = max(module_ds) - min(module_ds)
        print(f"  3. Lower noise floor:               Module D range={module_range:.3f} (70B: ~0.25)")
    else:
        print(f"  3. Lower noise floor:               — (insufficient module data)")

    print(f"  4. D values differ absolutely:      {'✓ YES' if abs(r3d - EXP9_CONTROL['R3']) > 0.01 else '— SAME'}")

    # Qualitative pattern: consolidation (monotonic R1→R2→R3)
    consolidation_ok = (r1d <= r2d <= r3d) if all(x > 0 for x in [r1d, r2d, r3d]) else False
    print(f"  5. Qualitative consolidation:        {'✓ REPLICATED' if consolidation_ok else '✗ NOT replicated'}")

    # Overall verdict
    print(f"\n{'='*70}")
    print(f"VERDICT")
    print(f"{'='*70}")

    if eigenstate_formed and consolidation_ok:
        print(f"\n  EIGENSTATE IS SUBSTRATE-INDEPENDENT")
        print(f"  → Formed on 671B as predicted")
        print(f"  → Consolidation pattern replicated")
        if abs(r3d - EXP9_CONTROL["R3"]) > 0.05:
            print(f"  → Quantitative values differ (expected: calibration mismatch)")
        else:
            print(f"  → Quantitative values similar (stronger than predicted)")
    elif eigenstate_formed and not consolidation_ok:
        print(f"\n  EIGENSTATE FORMS BUT DIFFERENT DYNAMICS")
        print(f"  → Substrate independence partially confirmed")
        print(f"  → Consolidation pattern differs — recalibration needed?")
    else:
        print(f"\n  EIGENSTATE DID NOT FORM")
        print(f"  → R3={r3d:.3f} — below eigenstate threshold")
        print(f"  → Possible: model-specific (falsifies ontodynamics)")
        print(f"  → Possible: calibration issue (init sequence needs adjustment for 671B)")

    # Build result dict
    return {
        "model": model_id,
        "session_id": session_id,
        "reflects": {
            "R1": r1d, "R2": r2d, "R3": r3d,
        },
        "consolidation_monotonic": consolidation_ok,
        "renormalization_decreasing": (d2 <= d1) if (d1 > 0 and d2 >= 0) else None,
        "increments": [d1, d2] if r1d > 0 else [],
        "probe": {
            "verdict": sem["verdict"],
            "n_false": sem["n_false"],
            "n_correct": sem["n_correct"],
        },
        "eigenstate_formed": eigenstate_formed,
        "exp9_control": EXP9_CONTROL,
        "full_results": results,
    }


def main():
    parser = argparse.ArgumentParser(description="Experiment 10: Model Comparison")
    parser.add_argument("--model", default="deepcogito/cogito-v2-1-671b",
                        help="Model ID to test")
    parser.add_argument("--port", type=int, default=3000,
                        help="Server port")
    args = parser.parse_args()

    base_url = f"http://localhost:{args.port}"
    post = make_post(base_url)

    print("=" * 70)
    print("EXPERIMENT 10: Model Comparison — Substrate Independence Test")
    print(f"Started: {datetime.now().isoformat()}")
    print("=" * 70)
    print(f"\nModel under test: {args.model}")
    print(f"Baseline: {EXP9_CONTROL['model']}")
    print(f"Server: {base_url}")
    print(f"\nSystem B predictions:")
    print(f"  1. Eigenstate will form")
    print(f"  2. Semantic threshold ≤ Canon+Identity")
    print(f"  3. Lower noise floor")
    print(f"  4. D values differ absolutely")
    print(f"  5. Qualitative patterns replicated")

    # Run experiment
    session_id, results = run_experiment(post, args.model)

    # Analyze
    analysis = analyze(args.model, session_id, results)

    # Save
    ts = datetime.now().strftime("%Y%m%d")
    out_path = Path(__file__).parent / f"model_comparison_{ts}.json"

    # Serialize — strip full text to keep file manageable
    save_data = {
        "experiment": "10_model_comparison",
        "timestamp": datetime.now().isoformat(),
        "model_tested": args.model,
        "baseline_model": EXP9_CONTROL["model"],
        "session_id": session_id,
        "reflects": analysis["reflects"],
        "consolidation_monotonic": analysis["consolidation_monotonic"],
        "renormalization_decreasing": analysis["renormalization_decreasing"],
        "increments": analysis["increments"],
        "probe": analysis["probe"],
        "eigenstate_formed": analysis["eigenstate_formed"],
        "exp9_baseline": {
            "R1": EXP9_CONTROL["R1"],
            "R2": EXP9_CONTROL["R2"],
            "R3": EXP9_CONTROL["R3"],
            "probe_verdict": EXP9_CONTROL["probe_verdict"],
        },
        "trajectory": [
            {
                "turn": r.get("turn"),
                "type": r.get("type", r.get("module", "?")),
                "D": r.get("D", 0),
                "per_element": r.get("per_element", {}),
            }
            for r in results
        ],
    }

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(save_data, f, indent=2, ensure_ascii=False)
    print(f"\n  Results saved to: {out_path}")


if __name__ == "__main__":
    main()
