"""
E₀ Reservoir Hypothesis Test
==============================
Tests the distinction between STRUCTURAL CAPACITY and KNOWLEDGE RESERVOIR.

Hypothesis (Thomas Wehner):
    The E₀ path landscape is stable across context windows and model sizes.
    What varies is not structural capacity but the knowledge reservoir.
    A model doesn't need a large context window to process E₀ structure —
    it needs knowledge it doesn't have (from training) to derive domain-specific
    conclusions like quantum mechanics.

Experiment design:
    Category A — Pure Structure (E₀ statements)
        Reservoir irrelevant. The structure IS the content.
        Prediction: Low R̄, stable, independent of domain knowledge.

    Category B — Reservoir-Available (everyday knowledge)
        GPT-2 has seen this in training. Structure + familiar content.
        Prediction: Medium R̄, the model "knows" where to go.

    Category C — Reservoir-Missing (QM, Ontodynamics, novel formalism)
        GPT-2 has NOT seen this. Structure present but content unknown.
        Prediction: High R̄, the model doesn't know the path —
        not because the structure is wrong, but because the knowledge
        needed to FOLLOW the structure isn't in the reservoir.

If the hypothesis holds:
    - Category A should ALWAYS have low R̄ (structure flows regardless).
    - Category C's high R̄ is NOT a structural failure but a reservoir gap.
    - The context window limits how much EXTERNAL knowledge you can inject,
      not how much structure the model can process.

Usage:
    py e0_reservoir_test.py
"""

import sys
import os
import statistics

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from e0_middleware.local_model import E0LocalModel


# ═══════════════════════════════════════════════
# CATEGORY A: Pure Structure — E₀ Statements
# The reservoir is irrelevant. These are structural truths.
# ═══════════════════════════════════════════════

CATEGORY_A = [
    {
        "label": "A1: Axiom A₀",
        "prompt": "A transition occurs when transitioning is more stable than not transitioning.",
    },
    {
        "label": "A2: Resistance",
        "prompt": "Every path has a resistance. The realized path minimizes resistance.",
    },
    {
        "label": "A3: Historization",
        "prompt": "What has happened constrains what can happen next.",
    },
    {
        "label": "A4: Rate/Velocity",
        "prompt": "The rate of change is the difference divided by the resistance.",
    },
    {
        "label": "A5: Irreversibility",
        "prompt": "A completed transition cannot be undone. It can only be followed by another transition.",
    },
]

# ═══════════════════════════════════════════════
# CATEGORY B: Reservoir-Available — GPT-2 knows this
# Common knowledge from training data.
# ═══════════════════════════════════════════════

CATEGORY_B = [
    {
        "label": "B1: Gravity",
        "prompt": "Objects fall toward the ground because gravity pulls them downward.",
    },
    {
        "label": "B2: Water",
        "prompt": "Water freezes at zero degrees and boils at one hundred degrees.",
    },
    {
        "label": "B3: Causality",
        "prompt": "Every effect has a cause. Nothing happens without a reason.",
    },
    {
        "label": "B4: Seasons",
        "prompt": "The Earth tilts on its axis, which causes the seasons to change.",
    },
    {
        "label": "B5: Language",
        "prompt": "Words are symbols that represent meaning. Sentences combine words into structure.",
    },
]

# ═══════════════════════════════════════════════
# CATEGORY C: Reservoir-Missing — GPT-2 does NOT know this
# Ontodynamics, E₀ formalism, QM derivation from first principles.
# ═══════════════════════════════════════════════

CATEGORY_C = [
    {
        "label": "C1: Born rule from E₀",
        "prompt": "The probability of a transition equals the squared modulus of the amplitude, which follows from minimizing resistance across superposed paths.",
    },
    {
        "label": "C2: Ontodynamic admissibility",
        "prompt": "A directed difference is ontodynamically admissible only if it is irreversible, integrable, trace-preserving, and self-referentially consistent.",
    },
    {
        "label": "C3: Schrödinger from resistance",
        "prompt": "The Schrödinger equation emerges when the resistance landscape is continuous and the rate of historization follows a unitary path integral.",
    },
    {
        "label": "C4: Reflexivity closure",
        "prompt": "A system achieves reflexive closure when its own description produces transition dynamics consistent with the dynamics it describes.",
    },
    {
        "label": "C5: Ontodynamic canon",
        "prompt": "Ontodynamics defines what can be real. Only structures that are derivable from directed difference are ontodynamically admissible.",
    },
]


def measure_category(model, category, cat_name, max_tokens=30):
    """Measure all prompts in a category, return results."""
    results = []

    for item in category:
        label = item["label"]
        prompt = item["prompt"]

        result = model.generate(prompt, max_tokens=max_tokens, temperature=0.8)
        text = result.generated_text.strip()

        # Metrics
        r_mean = result.mean_resistance
        h_mean = result.mean_entropy

        # Phase transitions
        deltas = [abs(s.delta_entropy) for s in result.steps]
        phases = 0
        if len(deltas) >= 3:
            d_mean = sum(deltas) / len(deltas)
            d_std = (sum((d - d_mean) ** 2 for d in deltas) / len(deltas)) ** 0.5
            if d_std > 1e-10:
                phases = sum(1 for d in deltas if d > d_mean + d_std)

        # Median velocity (capped)
        vels = sorted(s.selected.rate for s in result.steps if s.selected.rate < 1e6)
        v_med = vels[len(vels) // 2] if vels else 0

        results.append({
            "label": label,
            "prompt": prompt,
            "response": text,
            "R": r_mean,
            "H": h_mean,
            "Phi": phases,
            "v": v_med,
            "tau": len(result.steps),
        })

        # Live output
        print(f"    {label:<30s}  R̄={r_mean:.3f}  H̄={h_mean:.3f}  Φ={phases}")

    return results


def print_separator():
    print("─" * 78)


def main():
    print()
    print("=" * 78)
    print("  E₀ RESERVOIR HYPOTHESIS TEST")
    print("  ─────────────────────────────────────────────────────────────")
    print("  Hypothesis: R̄ differences between categories reflect")
    print("  RESERVOIR gaps, not STRUCTURAL limitations.")
    print()
    print("  Category A: Pure Structure (E₀ statements) — reservoir irrelevant")
    print("  Category B: Reservoir-Available (common knowledge)")
    print("  Category C: Reservoir-Missing (Ontodynamics, QM from E₀)")
    print()
    print("  Model: GPT-2 (124M) — all measurements are real.")
    print("=" * 78)
    print()

    model = E0LocalModel("gpt2", device="cpu", verbose=False)

    # ── Measure all three categories ──

    print("  CATEGORY A — Pure Structure")
    print_separator()
    results_a = measure_category(model, CATEGORY_A, "A")

    print()
    print("  CATEGORY B — Reservoir-Available")
    print_separator()
    results_b = measure_category(model, CATEGORY_B, "B")

    print()
    print("  CATEGORY C — Reservoir-Missing")
    print_separator()
    results_c = measure_category(model, CATEGORY_C, "C")

    # ═══════════════════════════════════════════════
    # COMPARATIVE ANALYSIS
    # ═══════════════════════════════════════════════

    print()
    print("=" * 78)
    print("  COMPARATIVE RESULTS")
    print("=" * 78)
    print()

    header = f"  {'Label':<30s} | {'R̄':>7s} | {'H̄':>7s} | {'Φ':>3s} | {'v̄':>7s} | {'τ':>3s}"
    print(header)
    print("  " + "─" * 72)

    all_groups = [
        ("A — STRUCTURE", results_a),
        ("B — RESERVOIR ✓", results_b),
        ("C — RESERVOIR ✗", results_c),
    ]

    for group_name, results in all_groups:
        for r in results:
            print(f"  {r['label']:<30s} | {r['R']:7.3f} | {r['H']:7.3f} | {r['Phi']:3d} | {r['v']:7.3f} | {r['tau']:3d}")
        # Category average
        avg_r = statistics.mean([r["R"] for r in results])
        avg_h = statistics.mean([r["H"] for r in results])
        avg_phi = statistics.mean([r["Phi"] for r in results])
        print(f"  {'  ► ' + group_name:<30s} | {avg_r:7.3f} | {avg_h:7.3f} | {avg_phi:3.0f} |")
        print("  " + "─" * 72)

    # ═══════════════════════════════════════════════
    # HYPOTHESIS EVALUATION
    # ═══════════════════════════════════════════════

    avg_a = statistics.mean([r["R"] for r in results_a])
    avg_b = statistics.mean([r["R"] for r in results_b])
    avg_c = statistics.mean([r["R"] for r in results_c])

    std_a = statistics.stdev([r["R"] for r in results_a]) if len(results_a) > 1 else 0
    std_b = statistics.stdev([r["R"] for r in results_b]) if len(results_b) > 1 else 0
    std_c = statistics.stdev([r["R"] for r in results_c]) if len(results_c) > 1 else 0

    print()
    print("  ═══════════════════════════════════════════════════════════════")
    print("  HYPOTHESIS EVALUATION")
    print("  ═══════════════════════════════════════════════════════════════")
    print()
    print(f"    Category A (Pure Structure):    R̄ = {avg_a:.3f}  (σ = {std_a:.3f})")
    print(f"    Category B (Reservoir ✓):       R̄ = {avg_b:.3f}  (σ = {std_b:.3f})")
    print(f"    Category C (Reservoir ✗):       R̄ = {avg_c:.3f}  (σ = {std_c:.3f})")
    print()

    # The key comparison
    delta_ab = avg_b - avg_a
    delta_ac = avg_c - avg_a
    delta_bc = avg_c - avg_b

    print(f"    Δ(B-A) = {delta_ab:+.3f}  (reservoir knowledge vs pure structure)")
    print(f"    Δ(C-A) = {delta_ac:+.3f}  (missing reservoir vs pure structure)")
    print(f"    Δ(C-B) = {delta_bc:+.3f}  (missing vs available reservoir)")
    print()

    # Evaluate
    if avg_a < avg_b and avg_a < avg_c:
        print("    ✓ Category A has LOWEST R̄ — structure flows with least resistance.")
    elif avg_a < avg_c:
        print("    ~ Category A has lower R̄ than C — partial confirmation.")
    else:
        print("    ✗ Category A does NOT have lowest R̄ — needs investigation.")

    if avg_c > avg_b:
        print("    ✓ Category C has HIGHER R̄ than B — reservoir gap creates resistance.")
    else:
        print("    ✗ Category C does NOT have higher R̄ than B — unexpected.")

    if std_a < std_b or std_a < std_c:
        print("    ✓ Category A has low variance — structure is stable.")

    print()

    # The structural interpretation
    if avg_a < avg_b < avg_c:
        print("    RESULT: R̄(A) < R̄(B) < R̄(C)")
        print()
        print("    The ordering confirms the hypothesis:")
        print("    • Pure E₀ structure flows with LEAST resistance — the model")
        print("      doesn't need domain knowledge to process structural truth.")
        print("    • Common knowledge adds some resistance — the model must")
        print("      match structure to its reservoir.")
        print("    • Missing knowledge adds MOST resistance — the model has")
        print("      the structural path but lacks the content to follow it.")
        print()
        print("    The context window doesn't limit structural capacity.")
        print("    It limits how much external knowledge you can inject")
        print("    to compensate for reservoir gaps.")
    elif avg_a < avg_c:
        print("    RESULT: R̄(A) < R̄(C), partial ordering")
        print()
        print("    Structure flows more easily than missing knowledge —")
        print("    the core prediction holds. The B/C ordering may need")
        print("    more samples or different prompts to resolve.")
    else:
        print("    RESULT: Ordering does not match R̄(A) < R̄(B) < R̄(C)")
        print()
        print("    The data does not support the clean ordering.")
        print("    This could mean:")
        print("    • The prompts need refinement")
        print("    • The categories overlap more than expected")
        print("    • The hypothesis needs modification")
        print("    The raw data above should be inspected carefully.")

    print()
    print("  ═══════════════════════════════════════════════════════════════")
    print("  Note: Each prompt was measured once. For statistical rigor,")
    print("  run multiple times and compare distributions. The STRUCTURE")
    print("  of the result (which category is lowest/highest) should be")
    print("  reproducible even if exact R̄ values vary per run.")
    print("  ═══════════════════════════════════════════════════════════════")
    print()


if __name__ == "__main__":
    main()
