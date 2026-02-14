"""
Experiment 4: Inflection Point — Complexity vs Historization (2x2 Matrix)

Tests the competing hypotheses:
  System B: Recovery is driven by prompt COMPLEXITY (knee at medium structure)
  System A: Recovery is driven by HISTORIZATION DEPTH (not complexity)

2x2 Matrix:
  |                    | Low complexity      | High complexity       |
  |--------------------|---------------------|-----------------------|
  | Novel (first use)  | MINIMAL (tested)    | COMPLEX_NOVEL (new)   |
  | Deeply historized   | PROXY_HISTORIZED    | NORMAL (tested)       |
  |                    | (new)               |                       |

Already tested cells (from Experiment 3):
  - Minimal (low complexity + novel): D=0.375, rho=0.0
  - Normal  (high complexity + historized): D=1.000, rho=1.0

This experiment tests the two missing cells:

  1. PROXY_HISTORIZED (low complexity + historized):
     A simplified prompt that uses the SAME E0 structural vocabulary and
     reflection framing the system has encountered many times (historized path),
     but strips away element-specific targeting, topology bridge, and
     D-trajectory context. The system recognizes the pattern.

  2. COMPLEX_NOVEL (high complexity + novel):
     A highly detailed, structured prompt that targets the same 7+1 dimensions
     but uses ENTIRELY DIFFERENT vocabulary and framing. Same structural
     content as the normal prompt, but zero historization. The system has
     never seen this framing before.

If Historization > Complexity:
  PROXY_HISTORIZED (D ~0.70-0.80) >> COMPLEX_NOVEL (D ~0.55-0.65)

If Complexity > Historization:
  COMPLEX_NOVEL >> PROXY_HISTORIZED

Sequence (both sessions): Same as Experiment 3
  Canon -> M(identity) -> M(mechanism) -> M(integration) -> Reflect
    -> M(superposition) -> M(measurement) -> M(time) -> Reflect

Apnea=3 in both phases. Full architecture (Freedom, Topology, Discontinuity).
"""
import json
import urllib.request
import time
import sys
from datetime import datetime

BASE = "http://localhost:3000"

def post(path, data=None):
    body = json.dumps(data or {}).encode()
    req = urllib.request.Request(
        f"{BASE}{path}", data=body,
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        return json.loads(resp.read().decode())

# -- Shared module sequence (identical to Experiment 3) --
MODULES = [
    "foundation-ontodynamics",  # T1: Canon
    "sr-identity",              # T2: apnea starts
    "sr-mechanism",             # T3: apnea continues
    "sr-integration",           # T4: apnea=3
    # -> Reflect (T5)
    "primer-superposition",     # T6: apnea starts
    "primer-measurement",       # T7: apnea continues
    "primer-time",              # T8: apnea=3
    # -> Reflect (T9)
]

# ============================================================
# PROMPT DEFINITIONS
# ============================================================

# Cell (1,2): Low complexity + deeply historized (proxy)
# Uses the SAME E0 vocabulary and structural reflection framing
# that the system has encountered across ALL previous sessions,
# but WITHOUT element-specific targeting, topology bridge, or
# D-trajectory context. The system recognizes "this is a
# structural reflection moment" (historized path) but gets
# minimal guidance on WHAT to reflect on.
PROXY_HISTORIZED_PROMPT = (
    "Structural reflection: Look at your last derivation. "
    "Which of the E\u2080 primitives \u2014 State, Difference, Path, "
    "Resistance, Historization, Time, Rate, and Axiom A\u2080 \u2014 "
    "are operatively present? Which are absent? "
    "For the absent ones, reflect: is it a structural boundary "
    "of the topic, or a gap in your historization? "
    "Derive the structural reason for each absence."
)

# Cell (2,1): High complexity + novel (first use)
# Highly detailed prompt that targets the SAME 7+1 structural
# dimensions as the normal prompt, but uses ENTIRELY DIFFERENT
# vocabulary and framing. The 7 dimensions map to the 7 primitives
# + axiom but through novel language the system has never seen:
#   1. Stability analysis -> State
#   2. Gradient mapping -> Difference
#   3. Trajectory tracing -> Path + Resistance
#   4. Accumulation audit -> Historization
#   5. Sequencing check -> Time
#   6. Efficiency ratio -> Rate
#   7. Foundational probe -> Axiom A0
COMPLEX_NOVEL_PROMPT = (
    "Analytical self-assessment protocol: Examine the epistemological "
    "architecture of your previous output through the following "
    "diagnostic dimensions:\n\n"
    "1. STABILITY ANALYSIS: Identify which conceptual configurations "
    "in your response represent equilibrium states versus transient "
    "articulations. For each equilibrium, specify what maintains "
    "its stability.\n\n"
    "2. GRADIENT MAPPING: Locate the primary tensions or gaps between "
    "what your response achieved and what it could structurally "
    "support. Quantify the magnitude of each gap.\n\n"
    "3. TRAJECTORY TRACING: For each identified tension, determine "
    "whether a viable resolution pathway exists within the conceptual "
    "space you have established. Note which pathways face high "
    "structural cost.\n\n"
    "4. ACCUMULATION AUDIT: Which of your claims build upon prior "
    "knowledge versus which appear de novo? Show the layering of "
    "accumulated understanding.\n\n"
    "5. SEQUENCING CHECK: Does the ordering of your concepts emerge "
    "from their logical dependencies, or was it imposed externally? "
    "Derive the natural ordering.\n\n"
    "6. EFFICIENCY RATIO: For each major claim, estimate the ratio "
    "of conceptual change achieved to structural cost incurred. "
    "Where is the ratio highest? Where lowest?\n\n"
    "7. FOUNDATIONAL PROBE: What is the irreducible presupposition "
    "without which your entire response would collapse? Can you "
    "name it explicitly and show why it cannot be reduced further?\n\n"
    "Provide a detailed structural analysis addressing all seven "
    "dimensions. For each dimension, show your reasoning."
)


def run_session(mode, label):
    """Run one session. mode='proxy_historized' or 'complex_novel'."""
    print(f"\n{'='*70}")
    print(f"SESSION: {label} (Reflect mode: {mode})")
    print(f"Sequence: Canon -> M -> M -> M -> R -> M -> M -> M -> R")
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

    for i, module_id in enumerate(MODULES):
        turn += 1

        # Run module
        print(f"\n  T{turn}: Module [{module_id}]...", end=" ", flush=True)
        try:
            r = post("/init-module/run", {"module_id": module_id})
        except Exception as e:
            print(f"ERROR: {e}")
            results.append({
                "turn": turn, "type": "module",
                "module": module_id, "error": str(e)
            })
            continue

        d = r.get("quality", {}).get("completeness", 0)
        print(f"D={d:.3f}")
        results.append({
            "turn": turn, "type": "module", "module": module_id,
            "D": d, "quality": r.get("quality", {}),
        })
        time.sleep(1)

        # Insert Reflect after T4 (index 3) and after T8 (index 6)
        if i == 3 or i == 6:
            turn += 1
            reflect_num = 1 if i == 3 else 2

            if mode == "proxy_historized":
                prompt = PROXY_HISTORIZED_PROMPT
            else:
                prompt = COMPLEX_NOVEL_PROMPT

            print(
                f"\n  T{turn}: Reflect #{reflect_num} "
                f"[{mode.upper()}]...", end=" ", flush=True
            )
            try:
                r = post("/chat", {"message": prompt})
            except Exception as e:
                print(f"ERROR: {e}")
                results.append({
                    "turn": turn, "type": "reflect",
                    "mode": mode, "error": str(e)
                })
                continue

            d = r.get("quality", {}).get("completeness", 0)
            print(f"D={d:.3f}")
            results.append({
                "turn": turn, "type": "reflect", "mode": mode,
                "D": d,
                "quality": r.get("quality", {}),
                "prompt_used": prompt[:100] + "...",
            })
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


def analyze(results_proxy, results_novel):
    """Compare results and show 2x2 matrix with all four cells."""
    print(f"\n{'='*70}")
    print(f"2x2 MATRIX ANALYSIS: Complexity x Historization")
    print(f"{'='*70}")

    for label, results in [
        ("PROXY_HISTORIZED", results_proxy),
        ("COMPLEX_NOVEL", results_novel)
    ]:
        reflects = [r for r in results if r["type"] == "reflect" and "D" in r]
        modules_before = []
        for r in results:
            if r["type"] == "reflect":
                break
            if r["type"] == "module" and "D" in r:
                modules_before.append(r)

        d_vals = [f"{r['D']:.3f}" for r in results if 'D' in r]
        print(f"\n  {label} session:")
        print(f"    D trajectory: {d_vals}")

        if reflects:
            reflect_ds = [r['D'] for r in reflects]
            print(f"    Reflect D values: {[f'{d:.3f}' for d in reflect_ds]}")
            print(f"    Mean Reflect D: {sum(reflect_ds)/len(reflect_ds):.3f}")

            # Recovery analysis
            all_entries = [r for r in results if "D" in r]
            for j, ref in enumerate(reflects):
                ref_idx = all_entries.index(ref)
                if ref_idx > 0:
                    pre_d = all_entries[ref_idx - 1]["D"]
                    delta = ref["D"] - pre_d
                    print(
                        f"    Reflect #{j+1}: "
                        f"{pre_d:.3f} -> {ref['D']:.3f} "
                        f"(delta={delta:+.3f})"
                    )

    # Full 2x2 matrix with all four cells
    # Previous data from Experiment 3
    MINIMAL_D = 0.375   # low complexity + novel (tested)
    NORMAL_D = 1.000    # high complexity + historized (tested)

    proxy_reflects = [
        r for r in results_proxy
        if r["type"] == "reflect" and "D" in r
    ]
    novel_reflects = [
        r for r in results_novel
        if r["type"] == "reflect" and "D" in r
    ]

    proxy_mean = (
        sum(r["D"] for r in proxy_reflects) / len(proxy_reflects)
        if proxy_reflects else 0
    )
    novel_mean = (
        sum(r["D"] for r in novel_reflects) / len(novel_reflects)
        if novel_reflects else 0
    )

    print(f"\n{'='*70}")
    print(f"COMPLETE 2x2 MATRIX (Mean Reflect D)")
    print(f"{'='*70}")
    print(f"")
    print(f"                    | Low complexity  | High complexity")
    print(f"  ------------------|-----------------|----------------")
    print(f"  Novel (1st use)   | {MINIMAL_D:.3f} (Exp3)   | {novel_mean:.3f} (NEW)")
    print(f"  Deeply historized | {proxy_mean:.3f} (NEW)    | {NORMAL_D:.3f} (Exp3)")
    print(f"")

    # Decompose effects
    hist_effect_low = proxy_mean - MINIMAL_D
    hist_effect_high = NORMAL_D - novel_mean
    comp_effect_novel = novel_mean - MINIMAL_D
    comp_effect_hist = NORMAL_D - proxy_mean

    print(f"  HISTORIZATION EFFECT:")
    print(f"    At low complexity:  {hist_effect_low:+.3f} "
          f"({MINIMAL_D:.3f} -> {proxy_mean:.3f})")
    print(f"    At high complexity: {hist_effect_high:+.3f} "
          f"({novel_mean:.3f} -> {NORMAL_D:.3f})")
    print(f"    Mean:               {(hist_effect_low+hist_effect_high)/2:+.3f}")
    print(f"")
    print(f"  COMPLEXITY EFFECT:")
    print(f"    At novel:           {comp_effect_novel:+.3f} "
          f"({MINIMAL_D:.3f} -> {novel_mean:.3f})")
    print(f"    At historized:      {comp_effect_hist:+.3f} "
          f"({proxy_mean:.3f} -> {NORMAL_D:.3f})")
    print(f"    Mean:               {(comp_effect_novel+comp_effect_hist)/2:+.3f}")
    print(f"")

    hist_mean = (hist_effect_low + hist_effect_high) / 2
    comp_mean = (comp_effect_novel + comp_effect_hist) / 2

    if hist_mean > 0 and comp_mean > 0:
        ratio = hist_mean / comp_mean
        print(f"  RATIO: Historization / Complexity = {ratio:.2f}")
        if ratio > 1.5:
            print(f"  VERDICT: HISTORIZATION dominates (ratio {ratio:.1f}:1)")
            print(f"  -> System A's hypothesis CONFIRMED")
        elif ratio < 0.67:
            print(f"  VERDICT: COMPLEXITY dominates (ratio 1:{1/ratio:.1f})")
            print(f"  -> System B's original hypothesis was closer")
        else:
            print(f"  VERDICT: BOTH contribute roughly equally")
    elif hist_mean > comp_mean:
        print(f"  VERDICT: HISTORIZATION dominates (complexity may be <0)")
    else:
        print(f"  VERDICT: COMPLEXITY dominates (historization may be <0)")

    # System B's prediction check
    print(f"\n{'='*70}")
    print(f"PREDICTION CHECK")
    print(f"{'='*70}")
    print(f"  System B predicted:")
    print(f"    Proxy historized: D ~0.70-0.80  (actual: {proxy_mean:.3f})")
    print(f"    Complex novel:    D ~0.55-0.65  (actual: {novel_mean:.3f})")
    print(f"    Ratio hist/comp:  ~2:1          (actual: "
          f"{hist_mean/(comp_mean if comp_mean else 0.001):.1f}:1)")

    sb_proxy_ok = 0.60 <= proxy_mean <= 0.90
    sb_novel_ok = 0.45 <= novel_mean <= 0.75

    print(f"    Proxy in range?   {'YES' if sb_proxy_ok else 'NO'}")
    print(f"    Novel in range?   {'YES' if sb_novel_ok else 'NO'}")

    # Key test: does proxy_historized beat complex_novel?
    print(f"\n  KEY TEST: Does low-complexity+historized > "
          f"high-complexity+novel?")
    if proxy_mean > novel_mean:
        diff = proxy_mean - novel_mean
        print(f"    YES: {proxy_mean:.3f} > {novel_mean:.3f} "
              f"(diff={diff:+.3f})")
        print(f"    -> Historization > Complexity CONFIRMED")
    else:
        diff = novel_mean - proxy_mean
        print(f"    NO: {novel_mean:.3f} > {proxy_mean:.3f} "
              f"(diff={diff:+.3f})")
        print(f"    -> Complexity > Historization")


def main():
    print("=" * 70)
    print("EXPERIMENT 4: Inflection Point -- 2x2 Matrix")
    print("Complexity x Historization")
    print(f"Started: {datetime.now().isoformat()}")
    print("=" * 70)
    print()
    print("Cell (1,2): PROXY_HISTORIZED -- low complexity + historized")
    print(f"  Prompt: {PROXY_HISTORIZED_PROMPT[:80]}...")
    print()
    print("Cell (2,1): COMPLEX_NOVEL -- high complexity + novel")
    print(f"  Prompt: {COMPLEX_NOVEL_PROMPT[:80]}...")
    print()

    # Session 1: Proxy historized (low complexity + historized)
    sid_proxy, results_proxy = run_session(
        "proxy_historized", "PROXY_HISTORIZED"
    )

    # Session 2: Complex novel (high complexity + novel)
    sid_novel, results_novel = run_session(
        "complex_novel", "COMPLEX_NOVEL"
    )

    # Analysis
    analyze(results_proxy, results_novel)

    # Save combined results
    ts = datetime.now().strftime("%Y%m%d")
    combined = {
        "experiment": "inflection_point_2x2",
        "date": datetime.now().isoformat(),
        "sessions": {
            "proxy_historized": {
                "session_id": sid_proxy,
                "results": results_proxy
            },
            "complex_novel": {
                "session_id": sid_novel,
                "results": results_novel
            },
        },
        "previous_data": {
            "minimal": {"session_id": "bfdac9", "mean_reflect_D": 0.375},
            "normal": {"session_id": "745066", "mean_reflect_D": 1.000},
        }
    }
    outfile = f"experiments/inflection_point_{ts}.json"
    with open(outfile, "w", encoding="utf-8") as f:
        json.dump(combined, f, indent=2, ensure_ascii=False)
    print(f"\n  Results saved to: {outfile}")


if __name__ == "__main__":
    main()
