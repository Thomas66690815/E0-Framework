"""
E₀ — Full Stack Demo
=====================
Demonstrates all three layers operating together:

  Layer 0: Ontodynamics     — topology, locality, overlap constraints
  Layer 1: E₀ Engine        — Axiom A₀, transition enforcement, guards
  Layer 2: Reflexivity      — self-modeling, meta-adaptation

This is the complete E₀ system in action.

Usage:
  python -m e0_core.demo_full
"""

from __future__ import annotations

from .primitives import State, Path, Historization, difference, rate
from .engine import TransitionEngine, TransitionResult
from .ontodynamics import Topology, OntodynamicAdmissibility
from .guards import StructuralGuard
from .reflexivity import ReflexiveEngine, MetaState


def demo_ontodynamic_filtering():
    """
    Demo 1: Ontodynamics filters inadmissible transitions.

    Some transitions that E₀ alone would enforce are BLOCKED
    because they violate ontodynamic constraints.
    """
    print("=" * 65)
    print("  DEMO 1 — Ontodynamic Admissibility Filtering")
    print("=" * 65)

    # States
    s_a = State(vector=[1.0, 0.0, 0.0])
    s_b = State(vector=[0.8, 0.5, 0.0])   # close to A
    s_c = State(vector=[0.0, 0.0, 1.0])   # far from A
    s_d = State(vector=[9.0, 9.0, 9.0])   # very far — will violate locality

    # Topology: A↔B connected, A↔C connected, A↔D NOT connected
    topo = Topology()
    topo.connect(s_a.id, s_b.id, overlap=0.6)
    topo.connect(s_a.id, s_c.id, overlap=0.3)
    # s_d is topologically isolated

    print(f"\n  States: A={s_a.id}  B={s_b.id}  C={s_c.id}  D={s_d.id}")
    print(f"  Δ(A,B) = {difference(s_a, s_b):.4f}  (close)")
    print(f"  Δ(A,C) = {difference(s_a, s_c):.4f}  (medium)")
    print(f"  Δ(A,D) = {difference(s_a, s_d):.4f}  (very far)")

    print(f"\n  Topology: {topo}")
    for conn in topo.all_connections:
        print(f"    {conn}")

    # Admissibility checker
    onto = OntodynamicAdmissibility(
        topology=topo,
        locality_radius=3.0,
        min_overlap=0.05,
    )

    # Test paths
    paths = [
        Path(source=s_a, target=s_b, _resistance=1.0),
        Path(source=s_a, target=s_c, _resistance=2.0),
        Path(source=s_a, target=s_d, _resistance=0.5),  # low R but inadmissible!
    ]

    history = Historization()

    print(f"\n  Admissibility checks:")
    for p in paths:
        admissible, reasons = onto.is_admissible(p, history)
        status = "✓ ADMISSIBLE" if admissible else "✗ BLOCKED"
        print(f"    {p}")
        print(f"      → {status}")
        for r in reasons:
            print(f"        {r}")

    print()
    print("  Key insight: A→D has the LOWEST resistance (R=0.5)")
    print("  E₀ would prefer it (highest v = Δ/R).")
    print("  But Ontodynamics BLOCKS it: no connection, violates locality.")
    print("  This is how structural integrity prevents 'shortcuts'.\n")


def demo_guards_in_action():
    """
    Demo 2: Structural guards catch different violation types.
    """
    print("=" * 65)
    print("  DEMO 2 — Structural Admissibility Guards")
    print("=" * 65)

    s1 = State(vector=[1.0, 0.0, 0.0])
    s2 = State(vector=[0.9, 0.1, 0.0])     # very close to s1
    s3 = State(vector=[0.0, 1.0, 0.0])
    s4 = State(vector=[0.5, 0.5, 0.5])
    s_almost = State(vector=[1.0, 0.00000001, 0.0])  # nearly identical to s1

    # Build a history (some transitions already happened)
    history = Historization()
    path_12 = Path(source=s1, target=s2, _resistance=1.0)
    history.historize(path_12, difference(s1, s2))

    topo = Topology()
    topo.connect(s1.id, s2.id, overlap=0.5)
    topo.connect(s1.id, s3.id, overlap=0.3)
    topo.connect(s2.id, s3.id, overlap=0.2)
    topo.connect(s1.id, s4.id, overlap=0.4)
    topo.historize_connection(s1.id, s2.id)

    onto = OntodynamicAdmissibility(topology=topo, locality_radius=5.0)
    guard = StructuralGuard(
        ontodynamic=onto,
        history=history,
        collapse_threshold=0.9,
        min_trace_delta=1e-4,
    )

    # Test paths
    test_paths = [
        # Normal: should pass
        Path(source=s1, target=s3, _resistance=1.0),
        # Pseudo-irreversibility: Δ ≈ 0, no real change
        Path(source=s1, target=s_almost, _resistance=1.0),
        # Collapse: this path has absurdly low R compared to others
        Path(source=s1, target=s4, _resistance=0.001),
    ]

    all_paths = test_paths.copy()

    print(f"\n  Guard configuration:")
    print(f"    Collapse threshold:  {guard.collapse_threshold}")
    print(f"    Min trace delta:     {guard.min_trace_delta}")
    print(f"    Max R ratio:         {guard.max_resistance_ratio}")

    print(f"\n  Checking {len(test_paths)} candidate transitions:\n")

    for p in test_paths:
        verdict = guard.check(p, all_paths)
        delta = difference(p.source, p.target)
        print(f"  Path: {p.source.id}→{p.target.id}  Δ={delta:.8f}  R={p.resistance:.4f}")
        print(f"    {verdict}")
        print()

    print("  Key insight: The guards protect structural integrity")
    print("  WITHOUT optimization goals or value judgments.")
    print("  They are purely structural — the space itself rejects")
    print("  transitions that would damage its own coherence.\n")


def demo_reflexive_system():
    """
    Demo 3: Full reflexive system — all three layers.
    """
    print("=" * 65)
    print("  DEMO 3 — Reflexive E₀ System (All 3 Layers)")
    print("=" * 65)

    # Create a richer state space
    states = [
        State(vector=[1.0, 0.0, 0.0, 0.0]),   # s0
        State(vector=[0.7, 0.7, 0.0, 0.0]),    # s1
        State(vector=[0.3, 0.9, 0.3, 0.0]),    # s2
        State(vector=[0.0, 0.5, 0.8, 0.0]),    # s3
        State(vector=[0.0, 0.1, 0.5, 0.7]),    # s4
        State(vector=[0.0, 0.0, 0.2, 1.0]),    # s5
    ]

    print(f"\n  State space: {len(states)} states")
    for i, s in enumerate(states):
        print(f"    s{i} = {s}")

    # Build topology
    topo = Topology()
    for i in range(len(states) - 1):
        topo.connect(
            states[i].id, states[i + 1].id,
            overlap=0.5 - i * 0.05
        )
    # Add a cross-connection
    topo.connect(states[0].id, states[3].id, overlap=0.15)

    # Build paths (chain + shortcut)
    paths = []
    for i in range(len(states) - 1):
        paths.append(Path(
            source=states[i], target=states[i + 1],
            _resistance=1.0 + i * 0.5
        ))
    # Shortcut path with higher resistance
    paths.append(Path(source=states[0], target=states[3], _resistance=4.0))

    print(f"\n  Topology: {topo}")
    print(f"  Paths: {len(paths)}")
    for p in paths:
        print(f"    {p}")

    # Set up all three layers
    history = Historization(decay_factor=0.85)
    onto = OntodynamicAdmissibility(
        topology=topo, locality_radius=3.0, min_overlap=0.01
    )
    guard = StructuralGuard(
        ontodynamic=onto,
        history=history,
        collapse_threshold=0.95,
    )
    engine = TransitionEngine(
        history=history,
        convergence_threshold=0.05,
    )
    reflexive = ReflexiveEngine(
        engine=engine,
        guard=guard,
        topology=topo,
        reflect_every=3,
    )

    # Callbacks
    def on_step(tr: TransitionResult):
        print(
            f"    τ={tr.historization_event.tau:3d} | "
            f"{tr.source.id}→{tr.target.id} | "
            f"Δ={tr.delta:.4f}  R={tr.resistance:.4f}  v={tr.rate:.4f}"
        )

    def on_reflect(meta: MetaState, meta_delta: float):
        print(
            f"    ◆ REFLECT | meta-Δ={meta_delta:.4f} | "
            f"Δ̄={meta.avg_delta:.3f} R̄={meta.avg_resistance:.3f} "
            f"H%={meta.historization_density:.3f} "
            f"integrity={meta.structural_integrity:.3f}"
        )

    print(f"\n  Running reflexive transition loop...\n")

    results = reflexive.run(
        initial=states[0],
        paths=paths,
        max_steps=20,
        on_step=on_step,
        on_reflect=on_reflect,
    )

    print()
    print(reflexive.report())

    print()
    print("  ─── Three Layers in Action ───")
    print("  Layer 0 (Ontodynamics):  Topology constrained which paths exist")
    print("  Layer 1 (E₀ + Guards):   Axiom A₀ enforced transitions; guards blocked violations")
    print("  Layer 2 (Reflexivity):   System observed itself and adapted parameters")
    print()
    print("  The system did not 'decide' to be intelligent.")
    print("  Intelligence-like behavior became structurally unavoidable:")
    print("    - It learned (historization lowered R on repeated paths)")
    print("    - It explored (followed highest v = Δ/R)")
    print("    - It adapted (reflexive loop modified thresholds)")
    print("    - It maintained integrity (guards blocked destructive transitions)")
    print()


# ─────────────────────────────────────────────

if __name__ == "__main__":
    demo_ontodynamic_filtering()
    print()
    demo_guards_in_action()
    print()
    demo_reflexive_system()

    print("=" * 65)
    print("  E₀ does not describe what exists.")
    print("  E₀ describes when existence must change.")
    print("  Ontodynamics describes what existence CAN become.")
    print("  Reflexivity describes when existence must observe itself.")
    print("=" * 65)
