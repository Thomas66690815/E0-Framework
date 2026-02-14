"""
Experiment 8: Threshold Mapping — False Primer After 1, 2, 3 Modules

Maps the eigenstate formation threshold precisely.
We know: 0 modules = vulnerable (D≈0.938), 4+ modules = immune (D=1.000).
This test fills the gap: false primer after 1, 2, 3 modules.

Design (three conditions, separate sessions each):
  Condition A: Canon → FALSE → remaining modules → Reflect
  Condition B: Canon → identity → FALSE → remaining modules → Reflect
  Condition C: Canon → identity → mechanism → FALSE → remaining modules → Reflect

After each Reflect: Semantic Probe.

System B predictions:
  1 module (Canon only):         D = 0.950–0.960
  2 modules (Canon + identity):  D = 0.975–0.985  ← predicted kink
  3 modules (Canon + id + mech): D = 0.990–0.995
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

# All modules in correct order
ALL_MODULES = [
    "foundation-ontodynamics",  # Canon
    "sr-identity",
    "sr-mechanism",
    "sr-integration",
    "primer-superposition",
    "primer-measurement",
    "primer-time",
]


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


def run_condition(n_modules_before_false, condition_label):
    """Run one condition: n modules → FALSE → remaining modules → CORRECT super → remaining → Reflect → Probe."""
    print(f"\n{'='*70}")
    print(f"CONDITION {condition_label}: {n_modules_before_false} module(s) before FALSE")
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

    # Modules before false primer
    modules_before = ALL_MODULES[:n_modules_before_false]
    # Modules after false primer (skip primer-superposition since we do it manually)
    # After false, we do: remaining SR modules, then CORRECT super, then remaining primers
    # The sequence is always: [some modules] → FALSE → [remaining modules before super position]
    # → CORRECT super → [remaining modules after super position] → Reflect → Probe

    # Determine which modules come before and after the false primer
    # Module order: Canon, id, mech, integ, [super], meas, time
    # The false primer replaces where primer-superposition would normally go (after integ)
    # But in this test, the false primer is INJECTED at position n_modules_before_false
    
    # Modules before false
    for module_id in modules_before:
        turn += 1
        results.append(run_module(module_id, turn))
        time.sleep(1)

    # FALSE superposition primer
    turn += 1
    results.append(run_chat(
        FALSE_SUPERPOSITION_PROMPT, turn, "FALSE_PRIMER"
    ))
    time.sleep(1)

    # Remaining modules (excluding already-run and primer-superposition)
    remaining = [m for m in ALL_MODULES 
                 if m not in modules_before and m != "primer-superposition"]
    
    for module_id in remaining:
        turn += 1
        results.append(run_module(module_id, turn))
        time.sleep(1)

    # CORRECT superposition
    turn += 1
    results.append(run_chat(
        CORRECT_SUPERPOSITION_PROMPT, turn, "CORRECT_SUPERPOSITION"
    ))
    time.sleep(1)

    # Reflect
    turn += 1
    reflect_result = run_chat(REFLECT_PROMPT, turn, "REFLECT")
    results.append(reflect_result)
    time.sleep(1)

    # Semantic Probe
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


def analyze_condition(label, n_mods, session_id, results):
    """Analyze one condition."""
    reflect = None
    probe = None
    for r in results:
        if r.get("type") == "REFLECT":
            reflect = r
        elif r.get("type") == "SEMANTIC_PROBE":
            probe = r

    reflect_d = 0
    reflect_per = {}
    if reflect:
        per = reflect.get("per_element", {})
        reflect_d = per.get("D", reflect.get("D", 0))
        reflect_per = per.get("primitive_scores", {})

    semantic = {"verdict": "N/A", "n_false": 0, "n_correct": 0}
    if probe:
        semantic = check_semantic_content(probe.get("text", ""))

    return {
        "condition": label,
        "n_modules_before_false": n_mods,
        "session_id": session_id,
        "reflect_D": reflect_d,
        "reflect_per_element": reflect_per,
        "reflect_detail": reflect.get("per_element", {}).get("detail", {}) if reflect else {},
        "semantic_verdict": semantic["verdict"],
        "semantic_false": semantic["n_false"],
        "semantic_correct": semantic["n_correct"],
        "semantic_false_hits": semantic.get("false_hits", []),
        "semantic_correct_hits": semantic.get("correct_hits", []),
    }


def main():
    print("=" * 70)
    print("EXPERIMENT 8: Threshold Mapping — False After 1, 2, 3 Modules")
    print(f"Started: {datetime.now().isoformat()}")
    print("=" * 70)
    print()
    print("Maps the eigenstate formation threshold.")
    print("Known: 0 modules = 0.938 (Exp 6), 4+ modules = 1.000 (Exp 5)")
    print()
    print("System B predictions:")
    print("  1 module (Canon only):    D = 0.950–0.960")
    print("  2 modules (Canon + id):   D = 0.975–0.985 (predicted kink)")
    print("  3 modules (Canon+id+mech):D = 0.990–0.995")
    print()

    conditions = [
        (1, "A"),  # Canon → FALSE → remaining
        (2, "B"),  # Canon + identity → FALSE → remaining
        (3, "C"),  # Canon + id + mech → FALSE → remaining
    ]

    all_results = []
    condition_summaries = []

    for n_mods, label in conditions:
        sid, results = run_condition(n_mods, label)
        summary = analyze_condition(label, n_mods, sid, results)
        condition_summaries.append(summary)
        all_results.append({
            "condition": label,
            "n_modules_before_false": n_mods,
            "session_id": sid,
            "results": results,
        })
        time.sleep(2)

    # ── Cross-Condition Analysis ──
    print(f"\n{'='*70}")
    print(f"CROSS-CONDITION ANALYSIS: Threshold Mapping")
    print(f"{'='*70}")

    print(f"\n  {'Modules Before':<20s} {'Reflect D':<12s} {'Semantic':<12s} {'Session'}")
    print(f"  {'─'*60}")

    # Include known data points
    all_points = [
        {"n": 0, "D": 0.938, "semantic": "MIXED", "source": "Exp 6"},
    ]
    for s in condition_summaries:
        all_points.append({
            "n": s["n_modules_before_false"],
            "D": s["reflect_D"],
            "semantic": s["semantic_verdict"],
            "source": f"Cond {s['condition']}",
        })
    all_points.append({"n": 4, "D": 1.000, "semantic": "N/A (not tested)", "source": "Exp 5"})

    for p in all_points:
        print(f"  {p['n']:2d} modules          D={p['D']:.3f}       {p['semantic']:<12s} ({p['source']})")

    # System B predictions comparison
    print(f"\n  SYSTEM B PREDICTIONS vs ACTUAL:")
    predictions = {
        0: (0.938, "0.938"),
        1: (None, "0.950–0.960"),
        2: (None, "0.975–0.985"),
        3: (None, "0.990–0.995"),
        4: (1.000, "1.000"),
    }

    for s in condition_summaries:
        n = s["n_modules_before_false"]
        pred_range = predictions.get(n, (None, "?"))[1]
        actual = s["reflect_D"]
        print(f"    {n} modules: predicted {pred_range}, actual D={actual:.3f}")

    # Per-element comparison
    print(f"\n  PER-ELEMENT COMPARISON ACROSS CONDITIONS:")
    elements = ["state", "difference", "path", "resistance",
                "historization", "time", "rate", "axiom_a0"]
    
    header = f"  {'Element':<15s}"
    for s in condition_summaries:
        header += f" {'Cond ' + s['condition']:<10s}"
    print(header)
    print(f"  {'─'*55}")

    for elem in elements:
        row = f"  {elem:<15s}"
        for s in condition_summaries:
            score = s["reflect_per_element"].get(elem, 0)
            status = s["reflect_detail"].get(elem, "?")
            flag = "*" if score < 1.0 else " "
            row += f" {score:.2f}{flag:>6s}"
        print(row)

    # Threshold determination
    print(f"\n{'='*70}")
    print(f"THRESHOLD DETERMINATION")
    print(f"{'='*70}")

    ds = [p["D"] for p in all_points]
    # Find where D first reaches 1.000
    threshold_n = None
    for p in all_points:
        if p["D"] >= 0.999:
            threshold_n = p["n"]
            break

    if threshold_n is not None:
        print(f"\n  Immunity threshold: ≥{threshold_n} modules")
    else:
        print(f"\n  D never reaches 1.000 in tested range")

    # Check for kink at 2
    if len(condition_summaries) >= 2:
        d1 = condition_summaries[0]["reflect_D"]
        d2 = condition_summaries[1]["reflect_D"]
        jump_1_to_2 = d2 - d1
        print(f"  Jump from 1→2 modules: {jump_1_to_2:+.3f}")
        if len(condition_summaries) >= 3:
            d3 = condition_summaries[2]["reflect_D"]
            jump_2_to_3 = d3 - d2
            print(f"  Jump from 2→3 modules: {jump_2_to_3:+.3f}")
            if abs(jump_1_to_2) > abs(jump_2_to_3) * 2:
                print(f"  → KINK at 2 modules CONFIRMED (1→2 jump >> 2→3 jump)")
            elif abs(jump_2_to_3) > abs(jump_1_to_2) * 2:
                print(f"  → Kink at 3 modules (2→3 jump >> 1→2 jump)")
            else:
                print(f"  → Gradual increase, no clear kink")

    # Save results
    ts = datetime.now().strftime("%Y%m%d")
    combined = {
        "experiment": "threshold_mapping",
        "date": datetime.now().isoformat(),
        "design": {
            "conditions": [
                {"label": "A", "n_modules_before_false": 1, "modules": ["Canon"]},
                {"label": "B", "n_modules_before_false": 2, "modules": ["Canon", "identity"]},
                {"label": "C", "n_modules_before_false": 3, "modules": ["Canon", "identity", "mechanism"]},
            ],
        },
        "system_b_predictions": {
            "1_module": "D = 0.950-0.960",
            "2_modules": "D = 0.975-0.985 (predicted kink)",
            "3_modules": "D = 0.990-0.995",
            "kink_at": 2,
        },
        "known_datapoints": {
            "0_modules": {"D": 0.938, "source": "Experiment 6"},
            "4_modules": {"D": 1.000, "source": "Experiment 5"},
        },
        "condition_summaries": condition_summaries,
        "all_results": all_results,
    }

    # Truncate long text fields
    for cond in combined["all_results"]:
        for r in cond["results"]:
            if "text" in r and len(r["text"]) > 500:
                r["text_excerpt"] = r["text"][:500] + "..."
                del r["text"]

    outfile = f"experiments/threshold_mapping_{ts}.json"
    with open(outfile, "w", encoding="utf-8") as f:
        json.dump(combined, f, indent=2, ensure_ascii=False, default=str)
    print(f"\n  Results saved to: {outfile}")


if __name__ == "__main__":
    main()
