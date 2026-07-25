"""
structural_geometry — runnable demo.

    cd lean && python -m structural_geometry.demo

Three scenes, each printing one thing the package claims:

  1. A field splits into progress and swirl, and the split is exact.
  2. Loops and dead ends cancel themselves in the amplitude sum.
  3. The override gate refuses a low-margin call -- on purpose.
"""

from __future__ import annotations

from . import (
    NavField,
    circulation_ratio,
    curvature_map,
    holonomy,
    influence_map,
    interference_analysis,
    orthogonality_residual,
    phase_regime,
    potential_map,
    v_grad,
    v_rot,
)


def _rule(title: str) -> None:
    print()
    print("=" * 68)
    print(title)
    print("=" * 68)


# ──────────────────────────────────────────────────────────────────
# Scene 1 — how much of a navigation field is wasted motion?
# ──────────────────────────────────────────────────────────────────

def scene_decomposition() -> None:
    _rule("1. Helmholtz split — progress vs. swirl")

    def ring_with_exit(exit_cost: float) -> NavField:
        f = NavField()
        for a, b in (("N", "E"), ("E", "S"), ("S", "W"), ("W", "N")):
            f.add_edge(a, b, cost=0.5)
        f.add_edge("N", "OUT", cost=exit_cost)
        return f

    print(f"  {'exit cost':>10}  {'circulation':>12}  {'orthogonality':>14}")
    print(f"  {'-' * 10}  {'-' * 12}  {'-' * 14}")
    for exit_cost in (0.1, 0.5, 1.5, 4.0):
        f = ring_with_exit(exit_cost)
        print(
            f"  {exit_cost:>10.1f}  {circulation_ratio(f):>12.4f}"
            f"  {orthogonality_residual(f):>14.2e}"
        )

    print()
    print("  A cheap exit drains the ring: most of the field is progress.")
    print("  An expensive exit leaves agents orbiting: the field is mostly swirl.")
    print("  circulation_ratio measures that before a single agent moves.")

    f = ring_with_exit(4.0)
    print()
    print(f"  holonomy(N→E→S→W→N) = {holonomy(f, ['N','E','S','W','N']):+.6f}")
    print("  Non-zero holonomy is what gives paths a phase to interfere with.")

    tree = NavField()
    tree.add_edge("A", "B", cost=0.4)
    tree.add_edge("A", "C", cost=0.7)
    tree.add_edge("B", "D", cost=0.2)
    print()
    print(f"  A tree has no cycles → circulation_ratio = {circulation_ratio(tree):.1e}")
    print("  (exactly zero, not approximately — gradients span the whole edge space)")


# ──────────────────────────────────────────────────────────────────
# Scene 2 — interference kills loops without loop detection
# ──────────────────────────────────────────────────────────────────

def scene_interference() -> None:
    _rule("2. Amplitude interference — and the regime it needs")

    def loop_field(weight: float) -> NavField:
        """Two routes to Z, plus a return leg that makes the field circulate."""
        f = NavField()
        f.add_edge("A", "P", cost=0.30, weight=weight)
        f.add_edge("P", "Z", cost=0.30, weight=weight)
        f.add_edge("A", "Q", cost=0.30, weight=weight)
        f.add_edge("Q", "Z", cost=0.30, weight=weight)
        f.add_edge("P", "Q", cost=0.25, weight=weight)
        f.add_edge("Z", "A", cost=0.35, weight=weight)   # closes the loop
        return f

    paths = [["A", "P", "Z"], ["A", "Q", "Z"], ["A", "P", "Q", "Z"]]

    print("  Same topology, same costs. Only the field's scale (weight) changes.")
    print()
    print(f"  {'weight':>7} {'phase gap':>10} {'spread':>9} {'regime':>13} {'factor':>9}")
    print(f"  {'-' * 7} {'-' * 10} {'-' * 9} {'-' * 13} {'-' * 9}")
    for w in (0.2, 1.0, 3.0, 10.0):
        f = loop_field(w)
        rep = interference_analysis(f, paths)
        reg = phase_regime(f, horizon=3)
        print(
            f"  {w:>7.1f} {reg['phase_gap']:>10.4f} {rep['phase_spread']:>9.4f}"
            f" {reg['regime']:>13} {rep['interference_factor']:>9.4f}"
        )

    print()
    print("  factor > 1  constructive — amplitudes reinforce")
    print("  factor < 1  destructive  — amplitudes cancel")
    print()
    print("  What this table actually shows, without varnish:")
    print()
    print("  In the 'gradient' regime the phase gap is far below π, every")
    print("  amplitude points essentially the same way, and the ranking is")
    print("  driven by exp(−cost) alone. Phase contributes nothing.")
    print()
    print("  In the 'interfering' regime phase modulates the total — the")
    print("  factor falls from 2.96 to 2.24 — but it stays constructive.")
    print("  This is the useful operating range, and the effect is a")
    print("  correction, not a reversal.")
    print()
    print("  Outright cancellation (factor < 1) only appears once the gap")
    print("  passes 2π — and there the ranking is no longer stable in weight,")
    print("  which is what 'wrapped' warns about. So: cancellation is real,")
    print("  and it is NOT something to chase by turning weight up. Check")
    print("  phase_regime() and stay in range.")

    f = loop_field(10.0)
    rep = interference_analysis(f, paths)
    print()
    print("  Detail at weight=10 (wrapped — shown to make the effect visible):")
    print(f"    {'path':<20} {'cost':>7} {'phase°':>10} {'|Ψ|':>8}")
    print(f"    {'-' * 20} {'-' * 7} {'-' * 10} {'-' * 8}")
    for a in rep["paths"]:
        print(
            f"    {a['path']:<20} {a['cost']:>7.3f} {a['phase_deg']:>10.2f}"
            f" {a['magnitude']:>8.4f}"
        )
    print(f"    Σ|Ψ|² = {rep['sum_intensities']:.6f}   "
          f"|ΣΨ|² = {rep['total_intensity']:.6f}")
    print("    The detour A→P→Q→Z has swung ~223° away from the two direct")
    print("    routes, so it subtracts instead of adding. Nothing in this")
    print("    package detects loops — the geometry did that on its own.")


# ──────────────────────────────────────────────────────────────────
# Scene 3 — the influence map, and when not to trust it
# ──────────────────────────────────────────────────────────────────

def scene_influence_map() -> None:
    _rule("3. Influence map — two rankings and a validated gate")

    f = NavField()
    f.add_edge("A", "C", cost=0.10)     # cheapest step...
    f.add_edge("C", "A", cost=0.10)     # ...into a pocket
    f.add_edge("C", "D", cost=0.15)
    f.add_edge("D", "C", cost=0.15)
    f.add_edge("A", "B", cost=0.50)     # expensive step...
    f.add_edge("B", "GOAL", cost=0.10)  # ...that actually arrives
    f.add_edge("B", "H", cost=0.30)
    f.add_edge("H", "GOAL", cost=0.10)

    rep = influence_map(f, "A", horizon=3)
    print(rep.summary())

    print()
    print(f"  greedy (cheapest edge)      → {rep.greedy}")
    print(f"  best   (forward support)    → {rep.best}")
    print(f"  confidence (P₁ − P₂)        = {rep.confidence:.4f}")
    print(f"  should_override()           = {rep.should_override()}")
    print(f"  decide()                    → {rep.decide()}")
    print()
    print("  Interference is right here — B is the route that arrives.")
    print("  The gate still declines: the margin is below the validated 0.85.")
    print("  In the parent framework's 1000-tick congestion study, overriding")
    print("  on every disagreement scored WORSE than never overriding at all.")
    print("  Acting on weak margins is the failure mode, not the feature.")

    print()
    print("  Raise the goal route's payoff and the margin follows:")
    f.set_cost("A", "B", 0.12)
    rep2 = influence_map(f, "A", horizon=3)
    print(
        f"    cost(A→B) 0.50 → 0.12 :  best={rep2.best}"
        f"  confidence={rep2.confidence:.4f}"
        f"  override={rep2.should_override()}"
    )


def main() -> None:
    scene_decomposition()
    scene_interference()
    scene_influence_map()
    print()


if __name__ == "__main__":
    main()
