"""
Gordian Trap Design Exploration v3
===================================
Key insight (from Helmholtz analysis):

  ΔΘ between two paths from A→B = ½ Σ_loop [v_fwd - v_bwd]
  where Φ contributions cancel in the holonomy.

  Back-edges only affect individual ω values (through Φ),
  NOT the phase difference (holonomy) between A-short and A-loop.

  Therefore: ΔΘ depends ONLY on the raw transition field v
  on the forward edges of the two competing paths:

    ΔΘ = ½ [Σ v(A-loop edges) − Σ v(A-short edges)]

  where v(x,y) = δ(x,y) · exp(−S_eff(x,y)).

  Design:
    A-loop edges: high v (high δ, low R) → large phase accumulation
    A-short edges: low v (small δ) → small phase accumulation
    No back-edges needed (simplifies topology, eliminates prefix inflation).

Run:
    python -m e0_controller.explore_gordian
"""
import math
import cmath

from e0_controller.landscape import Landscape
from e0_controller.connection import theta, omega
from e0_controller.wavepath import psi


def build_gordian(n_loop=3, loop_delta=2.5, loop_R=0.1,
                  short_delta=0.08, short_R=0.3) -> Landscape:
    """
    Build Gordian Trap domain.

    Decoy A (START → A1):
      A-short: A1 → A2 → GOAL          (2 hops, low v, low Θ)
      A-loop:  A1 → L1 → … → Ln → GOAL (n+1 hops, high v, high Θ)
      ΔΘ ≈ π → destructive interference within A-family

    Detour B (START → B1): coherent, no phase splitting
      B1 → B2 → GOAL
    """
    L = Landscape()

    # --- Decoy A (cheap greedy entry) ---
    L.add_edge("START", "A1", delta=0.3, resistance=0.3)         # S≈0.09

    # A-short: low δ → low v → small Θ contribution
    L.add_edge("A1", "A2", delta=short_delta, resistance=short_R)
    L.add_edge("A2", "GOAL", delta=short_delta, resistance=short_R)

    # A-loop: high δ, low R → high v → large Θ contribution
    nodes = [f"L{i+1}" for i in range(n_loop)]
    prev = "A1"
    for nd in nodes:
        L.add_edge(prev, nd, delta=loop_delta, resistance=loop_R)
        prev = nd
    L.add_edge(prev, "GOAL", delta=loop_delta, resistance=loop_R)

    # --- Detour B (expensive start, coherent) ---
    L.add_edge("START", "B1", delta=0.5, resistance=0.4)         # S≈0.20
    L.add_edge("B1", "B2", delta=0.3, resistance=0.35)
    L.add_edge("B2", "GOAL", delta=0.3, resistance=0.3)

    return L


def compute_delta_theta(n_loop, loop_delta, loop_R, short_delta, short_R):
    """Analytical ΔΘ prediction (holonomy formula)."""
    v_l = loop_delta * math.exp(-loop_delta * loop_R)
    v_s = short_delta * math.exp(-short_delta * short_R)
    return 0.5 * ((n_loop + 1) * v_l - 2 * v_s)


# ── Path-level analysis ──────────────────────────────────────

def analyze(L, n_loop=3, label=""):
    """Print ω structure, path-level Θ/Ψ, interference factor."""
    nodes = [f"L{i+1}" for i in range(n_loop)]
    a_short = ["START", "A1", "A2", "GOAL"]
    a_loop  = ["START", "A1"] + nodes + ["GOAL"]
    b_path  = ["START", "B1", "B2", "GOAL"]

    print(f"\n{'='*60}")
    print(f"  {label}")
    print(f"{'='*60}")

    # ω per edge
    print(f"\n  ω per edge:")
    for edge in L.edges:
        w = omega(L, edge.source, edge.target)
        s = L.effective_tension(edge.source, edge.target)
        v = L.transition_field(edge.source, edge.target)
        print(f"    {edge.source:>5s}→{edge.target:<5s}  ω={w:+.6f}  S={s:.4f}  v={v:.4f}")

    # Path-level amplitudes
    print(f"\n  Path-level Ψ:")
    psi_A = complex(0, 0)
    I_A_inc = 0.0
    for path, name in [(a_short, "A-short"), (a_loop, "A-loop")]:
        t = theta(L, path)
        p = psi(L, path)
        print(f"    {name:12s}  Θ={t:+.6f}  |Ψ|={abs(p):.6f}  arg={cmath.phase(p):+.4f}")
        psi_A += p
        I_A_inc += abs(p) ** 2

    p_b = psi(L, b_path)
    t_b = theta(L, b_path)
    print(f"    {'B':12s}  Θ={t_b:+.6f}  |Ψ|={abs(p_b):.6f}  arg={cmath.phase(p_b):+.4f}")

    I_A = abs(psi_A) ** 2
    I_B = abs(p_b) ** 2
    factor = I_A / I_A_inc if I_A_inc > 0 else 0
    dt = theta(L, a_loop) - theta(L, a_short)

    print(f"\n  Interference:")
    print(f"    ΔΘ = {dt:+.4f}   cos(ΔΘ) = {math.cos(dt):+.4f}")
    print(f"    I(A) coh={I_A:.6f}  inc={I_A_inc:.6f}  factor={factor:.4f}")
    print(f"    I(B) = {I_B:.6f}")
    print(f"    Greedy: S(→A1)={L.effective_tension('START','A1'):.4f}"
          f"  S(→B1)={L.effective_tension('START','B1'):.4f}")
    tag = "B ✓" if I_B > I_A else "A ✗"
    print(f"    Path winner: {tag}")

    return dt, factor, I_A, I_B


# ── Overlay + Hybrid test ────────────────────────────────────

def overlay_test(L, n_loop=3):
    """Test with actual overlay and hybrid controller."""
    from e0_controller.controller import E0Controller, HybridMode
    from e0_controller.primitives import Outcome
    from e0_controller.amplitude_overlay import analyze_controller_state

    def evaluate(s, t):
        return Outcome.SUCCESS

    ctrl = E0Controller(L, evaluate)

    # Admissible neighbors
    all_states = (["START", "A1", "A2"]
                  + [f"L{i+1}" for i in range(n_loop)]
                  + ["GOAL", "B1", "B2"])
    print(f"\n  Admissible neighbors:")
    for st in all_states:
        adm = ctrl._admissible_neighbors(st)
        if adm:
            print(f"    {st}: {adm}")

    # Overlay at different horizons
    h_max = n_loop + 2  # enough for A-loop path
    print(f"\n  Overlay (simple geometry):")
    for h in range(3, h_max + 1):
        report = analyze_controller_state(ctrl, "START",
                                          horizon_edges=h, geometry="simple")
        det, amp = report.deterministic_choice, report.amplitude_choice
        print(f"    h={h}: det={det}  amp={amp}")
        for ai in report.action_infos:
            print(f"      {ai.action}: I={ai.intensity:.6f} P={ai.probability:.3f}"
                  f" paths={ai.path_count}")

    # first_arrival geometry
    print(f"\n  Overlay (first_arrival):")
    for h in range(3, h_max + 1):
        report = analyze_controller_state(
            ctrl, "START", horizon_edges=h,
            geometry="first_arrival", goals={"GOAL"},
        )
        det, amp = report.deterministic_choice, report.amplitude_choice
        print(f"    h={h}: det={det}  amp={amp}")
        for ai in report.action_infos:
            print(f"      {ai.action}: I={ai.intensity:.6f} P={ai.probability:.3f}"
                  f" paths={ai.path_count}")

    # goal_reaching geometry (Born-criterion: only GOAL-reaching paths)
    print(f"\n  Overlay (goal_reaching):")
    for h in range(3, h_max + 1):
        report = analyze_controller_state(
            ctrl, "START", horizon_edges=h,
            geometry="goal_reaching", goals={"GOAL"},
        )
        det, amp = report.deterministic_choice, report.amplitude_choice
        print(f"    h={h}: det={det}  amp={amp}")
        for ai in report.action_infos:
            print(f"      {ai.action}: I={ai.intensity:.6f} P={ai.probability:.3f}"
                  f" paths={ai.path_count}")

    # Greedy run
    print(f"\n  Greedy run:")
    g = E0Controller(L, evaluate)
    tg = g.run(start="START", goal="GOAL", max_cycles=20)
    print(f"    {' → '.join(tg.path)}")

    # Hybrid runs (simple geometry)
    print(f"\n  Hybrid runs (simple):")
    for h in range(3, h_max + 1):
        hy = E0Controller(
            L, evaluate,
            hybrid_mode=HybridMode.AMPLITUDE_ON_DISAGREE,
            hybrid_horizon=h, hybrid_goals={"GOAL"},
        )
        th = hy.run(start="START", goal="GOAL", max_cycles=20)
        ovr = sum(1 for s in th.steps if s.hybrid_overridden)
        print(f"    h={h}: {' → '.join(th.path)}  overrides={ovr}")

    # Hybrid runs (goal_reaching geometry)
    print(f"\n  Hybrid runs (goal_reaching):")
    for h in range(3, h_max + 1):
        hy = E0Controller(
            L, evaluate,
            hybrid_mode=HybridMode.AMPLITUDE_ON_DISAGREE,
            hybrid_horizon=h, hybrid_goals={"GOAL"},
            hybrid_geometry="goal_reaching",
        )
        th = hy.run(start="START", goal="GOAL", max_cycles=20)
        ovr = sum(1 for s in th.steps if s.hybrid_overridden)
        print(f"    h={h}: {' → '.join(th.path)}  overrides={ovr}")


# ── Parameter scan ───────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 60)
    print("  Holonomy-based parameter scan")
    print("=" * 60)

    results = []
    for n_loop in [2, 3]:
        for loop_delta in [1.5, 2.0, 2.5, 3.0, 4.0]:
            for loop_R in [0.05, 0.1, 0.15]:
                for short_delta in [0.05, 0.1, 0.2, 0.4]:
                    short_R = 0.3
                    dt_pred = compute_delta_theta(
                        n_loop, loop_delta, loop_R, short_delta, short_R)
                    # Only test configs where |ΔΘ| is close to π
                    if abs(abs(dt_pred) - math.pi) > 0.5:
                        continue
                    L = build_gordian(n_loop=n_loop, loop_delta=loop_delta,
                                      loop_R=loop_R, short_delta=short_delta,
                                      short_R=short_R)
                    dt, factor, I_A, I_B = analyze(
                        L, n_loop=n_loop,
                        label=f"n={n_loop} δl={loop_delta} Rl={loop_R}"
                              f" δs={short_delta} Rs={short_R}"
                              f" ΔΘ_pred={dt_pred:+.3f}",
                    )
                    results.append((n_loop, loop_delta, loop_R,
                                    short_delta, short_R,
                                    dt, factor, I_A, I_B))

    # Filter for B wins at path level
    wins = [r for r in results if r[8] > r[7]]  # I_B > I_A
    if wins:
        wins.sort(key=lambda r: r[6])  # lowest factor
        print(f"\n{'#'*60}")
        print(f"  {len(wins)} configs where B wins at path level")
        print(f"{'#'*60}")
        for r in wins[:5]:
            print(f"  n={r[0]} δl={r[1]} Rl={r[2]} δs={r[3]}"
                  f"  ΔΘ={r[5]:+.4f} factor={r[6]:.4f}"
                  f" I_A={r[7]:.4f} I_B={r[8]:.4f}")

        # Run overlay test on best
        r = wins[0]
        print(f"\n{'#'*60}")
        print(f"  BEST: n={r[0]} δl={r[1]} Rl={r[2]} δs={r[3]} Rs={r[4]}")
        print(f"  ΔΘ={r[5]:+.4f}  factor={r[6]:.4f}")
        print(f"{'#'*60}")
        L = build_gordian(n_loop=r[0], loop_delta=r[1], loop_R=r[2],
                          short_delta=r[3], short_R=r[4])
        overlay_test(L, n_loop=r[0])
    else:
        print(f"\n  No path-level wins found. Showing top 5 by |cos(ΔΘ)|:")
        results.sort(key=lambda r: abs(math.cos(r[5])))
        for r in results[:5]:
            print(f"  n={r[0]} δl={r[1]} Rl={r[2]} δs={r[3]}"
                  f"  ΔΘ={r[5]:+.4f} cos(ΔΘ)={math.cos(r[5]):+.4f}"
                  f" factor={r[6]:.4f}")
        r = results[0]
        L = build_gordian(n_loop=r[0], loop_delta=r[1], loop_R=r[2],
                          short_delta=r[3], short_R=r[4])
        overlay_test(L, n_loop=r[0])
