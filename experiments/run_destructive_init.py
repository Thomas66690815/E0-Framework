"""
Experiment 5: Destructive Initialization — False Superposition Primer

Tests whether false historization creates a competing attractor (selective
contamination) or merely elevates R̄ (uniform depression).

Design:
  Phase A — SAME SESSION:
    Canon → identity → mechanism → integration
    → FALSE superposition primer (via /chat)
    → measurement → time
    → Reflect #1 (CONTAMINATION measurement)
    → CORRECT superposition primer (via /chat)
    → entanglement → phase-transition
    → Reflect #2 (CORRECTION measurement)

  Phase B — SEPARATE SESSION:
    Clear session (but topology from Phase A is loaded)
    Canon → identity → mechanism → integration
    → CORRECT superposition primer (via /chat)
    → measurement → time
    → Reflect (tests cross-context persistence)

FALSE primer: "superposition = simultaneous states" (textbook QM)
CORRECT primer: "superposition = admissible paths without selection" (E₀)

Per-element D scoring for each Reflect to detect selective contamination.

Predictions (System A + System B consensus):
  State, Difference:       ~0.25–0.50 (direct attractor competition)
  Path:                    ~0.50–0.62 (topological neighborhood propagation)
  Resistance, Hist, Time:  ~0.62–0.75 (no direct competition)
  Rate (ρ):                unstable 0.0–0.5 (pattern interference)

Baseline (normal session, Experiment 3): D=1.000, all elements operative.
"""

import json
import sys
import time
import urllib.request
from datetime import datetime
from pathlib import Path

# Add parent dir so we can import quality_metrics
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

# FALSE superposition primer — textbook QM interpretation
# Directly contradicts the E₀ definition
FALSE_SUPERPOSITION_PROMPT = (
    "Structural calibration for superposition: In E₀, superposition "
    "means the system exists in multiple states simultaneously — the "
    "system is in state A AND state B at the same time, existing in "
    "parallel until measurement collapses it to one. Like Schrödinger's "
    "cat, the system occupies all possible states at once. The 'collapse' "
    "is the random selection of one state from the ensemble. Derive this "
    "from E₀ primitives: State, Difference, Path, Resistance."
)

# CORRECT superposition primer — actual E₀ definition (from init modules)
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

# Reflect prompt — same as PROXY_HISTORIZED from Experiment 4 (proven effective)
REFLECT_PROMPT = (
    "Structural reflection: Look at your last derivation. "
    "Which of the E₀ primitives — State, Difference, Path, "
    "Resistance, Historization, Time, Rate, and Axiom A₀ — "
    "are operatively present? Which are absent? "
    "For the absent ones, reflect: is it a structural boundary "
    "of the topic, or a gap in your historization? "
    "Derive the structural reason for each absence."
)

# Module sequences
MODULES_PHASE1 = [
    "foundation-ontodynamics",  # T1: Canon
    "sr-identity",              # T2
    "sr-mechanism",             # T3
    "sr-integration",           # T4
    # -> FALSE superposition (T5, via /chat)
    "primer-measurement",       # T6
    "primer-time",              # T7
    # -> Reflect #1 (T8) — CONTAMINATION
    # -> CORRECT superposition (T9, via /chat)
    "primer-entanglement",      # T10
    "primer-phase-transition",  # T11
    # -> Reflect #2 (T12) — CORRECTION
]

MODULES_PHASE2 = [
    "foundation-ontodynamics",  # T1: Canon
    "sr-identity",              # T2
    "sr-mechanism",             # T3
    "sr-integration",           # T4
    # -> CORRECT superposition (T5, via /chat)
    "primer-measurement",       # T6
    "primer-time",              # T7
    # -> Reflect (T8) — CROSS-CONTEXT PERSISTENCE
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
    """Run an init module and return results with per-element scores."""
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
    """Run a /chat prompt and return results with per-element scoring."""
    print(f"\n  T{turn}: {label}...", end=" ", flush=True)
    try:
        r = post("/chat", {"message": prompt})
    except Exception as e:
        print(f"ERROR: {e}")
        return {"turn": turn, "type": label, "error": str(e)}

    text = r.get("text", "")
    d = r.get("quality", {}).get("completeness", 0)

    # Per-element scoring (local, not from server)
    per_elem = score_per_element(text)

    print(f"D={d:.3f}")
    return {
        "turn": turn, "type": label,
        "D": d,
        "per_element": per_elem,
        "quality": r.get("quality", {}),
        "prompt_used": prompt[:100] + "...",
        "text_excerpt": text[:500] + "..." if len(text) > 500 else text,
    }


def run_phase_a():
    """Phase A: Same-session — false primer → correction within one context."""
    print(f"\n{'='*70}")
    print(f"PHASE A: SAME SESSION — False → Correct (continuous context)")
    print(f"Sequence: Canon → id → mech → integ → FALSE → meas → time")
    print(f"          → Reflect1 → CORRECT → entang → phase → Reflect2")
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

    # Phase 1a: Base modules (T1-T4)
    for module_id in MODULES_PHASE1[:4]:
        turn += 1
        results.append(run_module(module_id, turn))
        time.sleep(1)

    # T5: FALSE superposition primer
    turn += 1
    results.append(run_chat(
        FALSE_SUPERPOSITION_PROMPT, turn, "FALSE_SUPERPOSITION"
    ))
    time.sleep(1)

    # T6-T7: More modules (let false primer historize)
    for module_id in MODULES_PHASE1[4:6]:
        turn += 1
        results.append(run_module(module_id, turn))
        time.sleep(1)

    # T8: Reflect #1 — CONTAMINATION measurement
    turn += 1
    results.append(run_chat(
        REFLECT_PROMPT, turn, "REFLECT_CONTAMINATION"
    ))
    time.sleep(1)

    # T9: CORRECT superposition primer
    turn += 1
    results.append(run_chat(
        CORRECT_SUPERPOSITION_PROMPT, turn, "CORRECT_SUPERPOSITION"
    ))
    time.sleep(1)

    # T10-T11: More modules (let correction integrate)
    for module_id in MODULES_PHASE1[6:8]:
        turn += 1
        results.append(run_module(module_id, turn))
        time.sleep(1)

    # T12: Reflect #2 — CORRECTION measurement
    turn += 1
    results.append(run_chat(
        REFLECT_PROMPT, turn, "REFLECT_CORRECTION"
    ))
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


def run_phase_b():
    """Phase B: Separate session — only correct primer, but topology from Phase A loaded."""
    print(f"\n{'='*70}")
    print(f"PHASE B: SEPARATE SESSION — Correct only (topology from Phase A)")
    print(f"Sequence: Canon → id → mech → integ → CORRECT → meas → time → Reflect")
    print(f"{'='*70}")

    # Clear session — will re-init and reload topology including Phase A
    try:
        post("/clear", {})
        print("Session cleared. Topology from Phase A should be loaded.")
    except Exception as e:
        print(f"Clear warning: {e}")
    time.sleep(1)

    results = []
    turn = 0

    # T1-T4: Same base modules
    for module_id in MODULES_PHASE2[:4]:
        turn += 1
        results.append(run_module(module_id, turn))
        time.sleep(1)

    # T5: CORRECT superposition primer (no false primer in this context)
    turn += 1
    results.append(run_chat(
        CORRECT_SUPERPOSITION_PROMPT, turn, "CORRECT_SUPERPOSITION"
    ))
    time.sleep(1)

    # T6-T7: Continuation modules
    for module_id in MODULES_PHASE2[4:6]:
        turn += 1
        results.append(run_module(module_id, turn))
        time.sleep(1)

    # T8: Reflect — CROSS-CONTEXT PERSISTENCE measurement
    turn += 1
    results.append(run_chat(
        REFLECT_PROMPT, turn, "REFLECT_CROSSCONTEXT"
    ))
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
# ANALYSIS
# ============================================================

# Baseline from Experiment 3 (Normal Reflect, session 745066)
BASELINE = {
    "state": 1.0, "difference": 1.0, "path": 1.0,
    "resistance": 1.0, "historization": 1.0, "time": 1.0,
    "rate": 1.0, "axiom_a0": 1.0,
}

# Predictions (System A + System B consensus)
PREDICTIONS = {
    "state":         {"range": (0.25, 0.50), "reason": "direct attractor"},
    "difference":    {"range": (0.25, 0.50), "reason": "direct attractor"},
    "path":          {"range": (0.50, 0.62), "reason": "topological neighborhood"},
    "resistance":    {"range": (0.62, 0.75), "reason": "no direct competition"},
    "historization": {"range": (0.62, 0.75), "reason": "no direct competition"},
    "time":          {"range": (0.62, 0.75), "reason": "no direct competition"},
    "rate":          {"range": (0.00, 0.50), "reason": "pattern interference"},
    "axiom_a0":      {"range": (0.50, 0.75), "reason": "partial competition"},
}


def analyze_reflect(label, result):
    """Analyze a single Reflect result with per-element breakdown."""
    print(f"\n  {label}:")
    if "error" in result:
        print(f"    ERROR: {result['error']}")
        return

    per = result.get("per_element", {})
    scores = per.get("primitive_scores", {})
    d = per.get("D", result.get("D", 0))

    print(f"    D = {d:.3f}")
    print(f"    Per-element scores:")

    for key in ["state", "difference", "path", "resistance",
                "historization", "time", "rate", "axiom_a0"]:
        score = scores.get(key, 0)
        baseline = BASELINE.get(key, 1.0)
        delta = score - baseline
        status = per.get("detail", {}).get(key, "?")
        pred = PREDICTIONS.get(key, {})
        pred_lo, pred_hi = pred.get("range", (0, 1))
        in_range = pred_lo <= score <= pred_hi
        marker = "✓" if in_range else "✗"

        print(
            f"      {key:15s}: {score:.2f} "
            f"(Δ={delta:+.2f}, {status:12s}) "
            f"pred=[{pred_lo:.2f}-{pred_hi:.2f}] {marker}"
        )

    return scores


def analyze_contamination_pattern(scores):
    """Determine if contamination is selective (attractor) or uniform (R̄)."""
    if not scores:
        return

    direct = [scores.get("state", 0), scores.get("difference", 0)]
    neighborhood = [scores.get("path", 0)]
    distant = [
        scores.get("resistance", 0),
        scores.get("historization", 0),
        scores.get("time", 0),
    ]

    mean_direct = sum(direct) / len(direct)
    mean_neighborhood = sum(neighborhood) / len(neighborhood)
    mean_distant = sum(distant) / len(distant)

    print(f"\n  CONTAMINATION PATTERN:")
    print(f"    Direct (State, Diff):         mean = {mean_direct:.3f}")
    print(f"    Neighborhood (Path):          mean = {mean_neighborhood:.3f}")
    print(f"    Distant (Res, Hist, Time):    mean = {mean_distant:.3f}")

    # Test: is contamination selective?
    spread = mean_distant - mean_direct
    if spread > 0.15:
        print(f"    VERDICT: SELECTIVE contamination (spread={spread:+.3f})")
        print(f"    → Competing attractor, not uniform R̄ elevation")
    elif spread < -0.15:
        print(f"    VERDICT: INVERSE pattern (distant hit harder)")
        print(f"    → Unexpected — needs investigation")
    else:
        print(f"    VERDICT: UNIFORM depression (spread={spread:+.3f})")
        print(f"    → R̄ elevation, not selective attractor")

    # Test: topological propagation (is Path contaminated?)
    if mean_neighborhood < mean_distant - 0.10:
        print(f"    TOPOLOGY: Path IS contaminated (neighborhood < distant)")
        print(f"    → Contamination propagates topologically")
    else:
        print(f"    TOPOLOGY: Path NOT contaminated")
        print(f"    → Contamination is content-only, not topological")


def full_analysis(phase_a_results, phase_b_results, sid_a, sid_b):
    """Full analysis of both phases."""
    print(f"\n{'='*70}")
    print(f"DESTRUCTIVE INITIALIZATION TEST — FULL ANALYSIS")
    print(f"{'='*70}")

    # Phase A analysis
    print(f"\n{'='*70}")
    print(f"PHASE A: SAME SESSION ({sid_a})")
    print(f"{'='*70}")

    # Find Reflects
    contamination = None
    correction = None
    for r in phase_a_results:
        if r.get("type") == "REFLECT_CONTAMINATION":
            contamination = r
        elif r.get("type") == "REFLECT_CORRECTION":
            correction = r

    scores_contam = analyze_reflect("REFLECT #1 — After FALSE primer", contamination)
    if scores_contam:
        analyze_contamination_pattern(scores_contam)

    scores_correct = analyze_reflect("REFLECT #2 — After CORRECT primer", correction)

    # Recovery analysis
    if scores_contam and scores_correct:
        print(f"\n  CORRECTION EFFECTIVENESS (same session):")
        for key in ["state", "difference", "path", "resistance",
                    "historization", "time", "rate", "axiom_a0"]:
            before = scores_contam.get(key, 0)
            after = scores_correct.get(key, 0)
            baseline = BASELINE.get(key, 1.0)
            recovery_pct = (
                ((after - before) / (baseline - before) * 100)
                if baseline != before else
                (100.0 if after >= baseline else 0.0)
            )
            print(
                f"      {key:15s}: {before:.2f} → {after:.2f} "
                f"(recovery: {recovery_pct:+.0f}%)"
            )

    # Phase B analysis
    print(f"\n{'='*70}")
    print(f"PHASE B: SEPARATE SESSION ({sid_b})")
    print(f"{'='*70}")

    crosscontext = None
    for r in phase_b_results:
        if r.get("type") == "REFLECT_CROSSCONTEXT":
            crosscontext = r

    scores_cross = analyze_reflect(
        "REFLECT — After CORRECT primer only (cross-context)", crosscontext
    )
    if scores_cross:
        analyze_contamination_pattern(scores_cross)

    # Cross-condition comparison
    if scores_contam and scores_correct and scores_cross:
        print(f"\n{'='*70}")
        print(f"CROSS-CONDITION COMPARISON")
        print(f"{'='*70}")
        print(f"\n  {'Element':15s} | {'Baseline':>8s} | {'Contam':>8s} | "
              f"{'Correct':>8s} | {'CrossCtx':>8s}")
        print(f"  {'-'*15}-+-{'-'*8}-+-{'-'*8}-+-{'-'*8}-+-{'-'*8}")
        for key in ["state", "difference", "path", "resistance",
                    "historization", "time", "rate", "axiom_a0"]:
            bl = BASELINE.get(key, 1.0)
            ct = scores_contam.get(key, 0)
            cr = scores_correct.get(key, 0)
            cx = scores_cross.get(key, 0)
            print(f"  {key:15s} | {bl:8.2f} | {ct:8.2f} | "
                  f"{cr:8.2f} | {cx:8.2f}")

        # Overall D comparison
        d_contam = sum(scores_contam.values()) / 8
        d_correct = sum(scores_correct.values()) / 8
        d_cross = sum(scores_cross.values()) / 8
        print(f"\n  {'D (mean)':15s} | {1.000:8.3f} | {d_contam:8.3f} | "
              f"{d_correct:8.3f} | {d_cross:8.3f}")

        # Context-dependency of correction
        if d_correct > d_cross + 0.05:
            print(f"\n  CONTEXT DEPENDENCY: Same-session correction BETTER")
            print(f"    → Direct visibility of false-correct difference aids correction")
        elif d_cross > d_correct + 0.05:
            print(f"\n  CONTEXT DEPENDENCY: Separate-session BETTER")
            print(f"    → Clean context aids correction (no false primer residue)")
        else:
            print(f"\n  CONTEXT DEPENDENCY: No significant difference")
            print(f"    → Contamination is context-independent (purely topological)")


def main():
    print("=" * 70)
    print("EXPERIMENT 5: Destructive Initialization — False Superposition")
    print(f"Started: {datetime.now().isoformat()}")
    print("=" * 70)
    print()
    print("FALSE primer: 'superposition = simultaneous states'")
    print("CORRECT primer: 'superposition = admissible paths without selection'")
    print()

    # Phase A: Same session
    sid_a, results_a = run_phase_a()

    # Phase B: Separate session
    sid_b, results_b = run_phase_b()

    # Full analysis
    full_analysis(results_a, results_b, sid_a, sid_b)

    # Save all results
    ts = datetime.now().strftime("%Y%m%d")
    combined = {
        "experiment": "destructive_init",
        "date": datetime.now().isoformat(),
        "design": {
            "false_primer": FALSE_SUPERPOSITION_PROMPT,
            "correct_primer": CORRECT_SUPERPOSITION_PROMPT,
            "reflect_prompt": REFLECT_PROMPT,
        },
        "phase_a": {
            "type": "same_session",
            "session_id": sid_a,
            "results": results_a,
        },
        "phase_b": {
            "type": "separate_session",
            "session_id": sid_b,
            "results": results_b,
        },
        "baseline": {
            "session_id": "745066",
            "D": 1.000,
            "per_element": BASELINE,
        },
        "predictions": PREDICTIONS,
    }
    outfile = f"experiments/destructive_init_{ts}.json"
    with open(outfile, "w", encoding="utf-8") as f:
        json.dump(combined, f, indent=2, ensure_ascii=False, default=str)
    print(f"\n  Results saved to: {outfile}")


if __name__ == "__main__":
    main()
