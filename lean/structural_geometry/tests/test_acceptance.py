"""
Acceptance tests G1-G10 for structural_geometry.

Each test pins a property the package claims in its documentation.
If one of these fails, a documented claim is false.

Run:  cd lean && python -m pytest structural_geometry/tests/ -v
"""

from __future__ import annotations

import math

import pytest
from structural_geometry import (
    NavField,
    circulation_ratio,
    curvature_map,
    divergence,
    edge_curvature,
    enumerate_continuations,
    helmholtz,
    holonomy,
    influence_map,
    interference_analysis,
    omega,
    orthogonality_residual,
    path_intensity,
    potential_map,
    psi,
    theta,
    v_grad,
    v_rot,
)
from structural_geometry.linalg import solve_cg

# ── fixtures ────────────────────────────────────────────────────────

def tree_field() -> NavField:
    """Directed tree: edge space dimension == gradient space dimension."""
    f = NavField()
    f.add_edge("A", "B", cost=0.4)
    f.add_edge("A", "C", cost=0.7)
    f.add_edge("B", "D", cost=0.2)
    f.add_edge("C", "E", cost=0.9)
    return f


def cycle_field() -> NavField:
    """Uniform directed 3-cycle: divergence-free, pure circulation."""
    f = NavField()
    f.add_edge("A", "B", cost=0.5)
    f.add_edge("B", "C", cost=0.5)
    f.add_edge("C", "A", cost=0.5)
    return f


def grid_field(n: int = 5) -> NavField:
    """4-connected n x n grid, bidirectional, cost rising toward the far corner."""
    f = NavField()
    for r in range(n):
        for c in range(n):
            for dr, dc in ((1, 0), (0, 1)):
                nr, nc = r + dr, c + dc
                if nr < n and nc < n:
                    a, b = f"R{r}C{c}", f"R{nr}C{nc}"
                    f.add_edge(a, b, cost=0.1 + 0.05 * (nr + nc))
                    f.add_edge(b, a, cost=0.1 + 0.05 * (r + c))
    return f


def loop_trap_field() -> NavField:
    """Cheap edge leads into a pocket; expensive edge leads to the goal.

    The pocket is given its own branch so that both candidates have a
    comparable number of continuations -- otherwise the intensity gap
    would be an artefact of path count, which is exactly what
    ``path_imbalance`` exists to catch.
    """
    f = NavField()
    f.add_edge("A", "C", cost=0.10)   # cheapest single step
    f.add_edge("C", "A", cost=0.10)   # ...but it only comes back
    f.add_edge("C", "D", cost=0.15)
    f.add_edge("D", "C", cost=0.15)
    f.add_edge("A", "B", cost=0.50)
    f.add_edge("B", "GOAL", cost=0.10)
    f.add_edge("B", "H", cost=0.30)
    f.add_edge("H", "GOAL", cost=0.10)
    return f


# ── G1: the decomposition is orthogonal ─────────────────────────────

@pytest.mark.parametrize(
    "builder", [tree_field, cycle_field, grid_field, loop_trap_field]
)
def test_G1_orthogonality(builder):
    """<v_grad, v_rot>_E == 0 up to solver tolerance, on every topology."""
    assert orthogonality_residual(builder()) < 1e-8


def test_G1b_divergence_free_remainder():
    """div(v_rot) == 0 at every node -- the defining property of the split."""
    f = grid_field(4)
    phi = potential_map(f)
    for node in sorted(f.nodes):
        out = sum(
            f.flow(node, y) - (phi[node] - phi[y]) for y in f.neighbors(node)
        )
        inn = sum(
            f.flow(y, node) - (phi[y] - phi[node]) for y in f.predecessors(node)
        )
        assert abs(out - inn) < 1e-8, f"v_rot not divergence-free at {node}"


# ── G2: the two endpoints of circulation_ratio ──────────────────────

def test_G2_tree_is_pure_gradient():
    """A tree has no cycles, so every flow on it is a pure gradient."""
    f = tree_field()
    assert circulation_ratio(f) < 1e-10
    for e in f.edges:
        assert abs(v_rot(f, e.source, e.target)) < 1e-10


def test_G2b_uniform_cycle_is_pure_circulation():
    """A divergence-free loop has no gradient part at all."""
    f = cycle_field()
    for node in sorted(f.nodes):
        assert abs(divergence(f, node)) < 1e-12
    assert circulation_ratio(f) > 1.0 - 1e-10
    for e in f.edges:
        assert abs(v_grad(f, e.source, e.target)) < 1e-10


def test_G2c_grid_is_mixed():
    """A real navigation graph sits strictly between the two endpoints."""
    ratio = circulation_ratio(grid_field(5))
    assert 0.0 < ratio < 1.0


# ── G3: disconnected graphs are solved per component ────────────────

def test_G3_disconnected_components():
    """Each component gets its own pinned solve; no cross-contamination."""
    f = NavField()
    f.add_edge("A", "B", cost=0.3)
    f.add_edge("B", "C", cost=0.3)
    f.add_edge("X", "Y", cost=0.9)
    f.add_node("LONE")

    assert f.components() == [["A", "B", "C"], ["LONE"], ["X", "Y"]]
    assert orthogonality_residual(f) < 1e-8
    assert potential_map(f)["LONE"] == 0.0
    # Both components are trees -> no circulation anywhere.
    assert circulation_ratio(f) < 1e-10


# ── G4: connection, antisymmetry, holonomy ──────────────────────────

def test_G4_antisymmetry():
    """omega(u,v) == -omega(v,u), including where the reverse edge is absent."""
    f = grid_field(4)
    for e in f.edges:
        assert omega(f, e.source, e.target) == pytest.approx(
            -omega(f, e.target, e.source), abs=1e-12
        )
    g = cycle_field()  # one-way edges only
    assert omega(g, "A", "B") == pytest.approx(-omega(g, "B", "A"), abs=1e-12)


def test_G4b_tree_has_no_phase():
    """No circulation -> no connection -> every path phase is zero."""
    f = tree_field()
    assert theta(f, ["A", "B", "D"]) == pytest.approx(0.0, abs=1e-10)


def test_G4c_cycle_has_holonomy():
    """A closed lap around a circulating region accumulates net phase."""
    f = cycle_field()
    h = holonomy(f, ["A", "B", "C", "A"])
    assert abs(h) > 1e-6
    # Each one-way edge carries half the circulation.
    assert omega(f, "A", "B") == pytest.approx(0.5 * f.flow("A", "B"), abs=1e-10)


def test_G4d_holonomy_rejects_open_paths():
    """Open paths raise rather than silently returning a non-holonomy."""
    with pytest.raises(ValueError, match="closed path"):
        holonomy(cycle_field(), ["A", "B", "C"])


def test_G4e_curvature_flat_without_triangles():
    """No triangle through the edge -> curvature 0 -> damping 1."""
    f = tree_field()
    assert edge_curvature(f, "A", "B") == 0.0
    assert all(v == 0.0 for v in curvature_map(f).values())


# ── G5: amplitudes ──────────────────────────────────────────────────

def test_G5_impossible_path_contributes_nothing():
    """A path with a missing hop is exactly zero, not a large penalty."""
    f = tree_field()
    assert psi(f, ["A", "B", "E"]) == 0j
    assert path_intensity(f, ["A", "B", "E"]) == 0.0


def test_G5b_single_path_has_no_interference():
    """|Psi(p)|^2 == exp(-2 cost) regardless of phase."""
    f = grid_field(4)
    p = ["R0C0", "R0C1", "R1C1"]
    assert path_intensity(f, p) == pytest.approx(
        math.exp(-2 * f.path_cost(p)), rel=1e-12
    )


def test_G5c_phaseless_family_is_constructive():
    """Zero phase everywhere -> all amplitudes real positive -> factor > 1."""
    f = tree_field()
    rep = interference_analysis(f, [["A", "B"], ["A", "B", "D"]])
    assert rep["interference_factor"] > 1.0


def test_G5d_phase_changes_the_total():
    """With holonomy present, the interfering total departs from the naive sum."""
    f = grid_field(5)
    paths, _ = enumerate_continuations(f, "R0C0", 3, geometry="simple")
    rep = interference_analysis(f, paths)
    naive = sum(path_intensity(f, p) for p in paths)
    assert rep["sum_intensities"] == pytest.approx(naive, rel=1e-12)
    assert rep["total_intensity"] != pytest.approx(naive, rel=1e-6)


def test_G5e_phase_regime_tracks_weight():
    """The phase regime is set by the field's scale, and says so."""
    from structural_geometry import phase_regime

    def ring(w: float) -> NavField:
        f = NavField()
        f.add_edge("A", "P", cost=0.3, weight=w)
        f.add_edge("P", "Z", cost=0.3, weight=w)
        f.add_edge("A", "Q", cost=0.3, weight=w)
        f.add_edge("Q", "Z", cost=0.3, weight=w)
        f.add_edge("P", "Q", cost=0.25, weight=w)
        f.add_edge("Z", "A", cost=0.35, weight=w)
        return f

    gaps = [phase_regime(ring(w))["phase_gap"] for w in (0.2, 1.0, 3.0, 10.0)]
    assert gaps == sorted(gaps), "phase gap must grow monotonically with weight"
    assert phase_regime(ring(0.2))["regime"] == "gradient"
    assert phase_regime(ring(1.0))["regime"] == "interfering"
    assert phase_regime(ring(10.0))["regime"] == "wrapped"
    assert phase_regime(ring(1.0))["basis"] == "curvature"


def test_G5f_cancellation_needs_phase_spread():
    """Destructive interference is a regime, not a default. Both directions verified."""
    def ring(w: float) -> NavField:
        f = NavField()
        f.add_edge("A", "P", cost=0.3, weight=w)
        f.add_edge("P", "Z", cost=0.3, weight=w)
        f.add_edge("A", "Q", cost=0.3, weight=w)
        f.add_edge("Q", "Z", cost=0.3, weight=w)
        f.add_edge("P", "Q", cost=0.25, weight=w)
        f.add_edge("Z", "A", cost=0.35, weight=w)
        return f

    paths = [["A", "P", "Z"], ["A", "Q", "Z"], ["A", "P", "Q", "Z"]]
    low = interference_analysis(ring(0.2), paths)
    high = interference_analysis(ring(10.0), paths)

    assert low["phase_spread"] < 0.1 * math.pi
    assert low["interference_factor"] > 1.0          # constructive
    assert high["phase_spread"] > math.pi
    assert high["interference_factor"] < 1.0         # destructive


def test_G5g_regime_falls_back_without_triangles():
    """No triangles -> curvature is uninformative -> the fallback is declared."""
    from structural_geometry import phase_regime

    reg = phase_regime(tree_field())
    assert reg["basis"] == "omega"
    assert reg["regime"] == "gradient"


# ── G6: the influence map ───────────────────────────────────────────

def test_G6_interference_sees_past_the_cheap_loop():
    """Greedy takes the cheapest edge into a pocket; interference does not."""
    f = loop_trap_field()
    rep = influence_map(f, "A", horizon=3)
    assert rep.greedy == "C"
    assert rep.best == "B"
    assert rep.disagrees


def test_G6b_probabilities_normalise():
    f = grid_field(5)
    rep = influence_map(f, "R1C1", horizon=3)
    assert sum(a.probability for a in rep.actions) == pytest.approx(1.0, abs=1e-12)
    assert 0.0 <= rep.confidence <= 1.0
    assert rep.path_imbalance >= 1.0


def test_G6c_geometries_differ():
    """'simple' suppresses the loop inflation that 'prefix' admits."""
    f = loop_trap_field()
    simple, _ = enumerate_continuations(f, "A", 4, geometry="simple")
    prefix, _ = enumerate_continuations(f, "A", 4, geometry="prefix")
    assert len(prefix) > len(simple)
    assert all(len(set(p)) == len(p) for p in simple)


def test_G6d_goal_reaching_keeps_only_arrivals():
    f = loop_trap_field()
    paths, _ = enumerate_continuations(
        f, "A", 4, geometry="goal_reaching", goals={"GOAL"}
    )
    assert paths, "expected at least one goal-reaching path"
    assert all(p[-1] == "GOAL" for p in paths)


def test_G6e_unknown_geometry_rejected():
    with pytest.raises(ValueError, match="unknown geometry"):
        enumerate_continuations(tree_field(), "A", 2, geometry="spiral")


# ── G7: the override gate ───────────────────────────────────────────

def test_G7_gate_blocks_low_confidence():
    """Disagreement alone is not enough -- the validated gate needs a margin."""
    f = loop_trap_field()
    rep = influence_map(f, "A", horizon=3)
    assert rep.disagrees
    assert rep.should_override(min_confidence=0.0) is True
    assert rep.should_override(min_confidence=1.01) is False


def test_G7b_gate_blocks_path_imbalance():
    """A ranking driven by sheer path count is refused, however confident."""
    f = loop_trap_field()
    rep = influence_map(f, "A", horizon=3)
    assert rep.should_override(min_confidence=0.0, max_imbalance=0.5) is False


def test_G7c_default_gate_is_conservative():
    """The shipped defaults refuse a merely-plausible override.

    In this trap the interference view is right, but its margin is small.
    The validated gate declines anyway -- that asymmetry is the finding it
    encodes, not a shortcoming.
    """
    rep = influence_map(loop_trap_field(), "A", horizon=3)
    assert rep.confidence < 0.85
    assert rep.should_override() is False
    assert rep.decide() == rep.greedy


def test_G7d_decide_follows_gate():
    f = loop_trap_field()
    rep = influence_map(f, "A", horizon=3)
    assert rep.decide(min_confidence=1.01) == rep.greedy
    assert rep.decide(min_confidence=0.0) == rep.best


def test_G7e_truncation_is_reported():
    """Dense branching hits the cap and says so rather than silently sampling."""
    f = NavField()
    for i in range(6):
        for j in range(6):
            if i != j:
                f.add_edge(f"N{i}", f"N{j}", cost=0.2)
    rep = influence_map(f, "N0", horizon=5, geometry="prefix", max_paths=50)
    assert rep.truncated is True


# ── G8: solvers agree ───────────────────────────────────────────────

def test_G8_cg_matches_cholesky(monkeypatch):
    """Sparse conjugate gradients reproduces the exact dense solve."""
    f = grid_field(5)
    dense = potential_map(f)

    monkeypatch.setattr(helmholtz, "DENSE_THRESHOLD", 0)
    monkeypatch.setattr(helmholtz, "factorized", None)
    g = grid_field(5)
    sparse = potential_map(g)

    for node in dense:
        assert sparse[node] == pytest.approx(dense[node], abs=1e-6)


def test_G8b_sparse_direct_matches_cholesky(monkeypatch):
    """The cached SciPy factorization solves the same reduced Laplacian."""
    if helmholtz.factorized is None:
        pytest.skip("SciPy is not installed")
    dense = potential_map(grid_field(5))

    monkeypatch.setattr(helmholtz, "DENSE_THRESHOLD", 0)
    direct = potential_map(grid_field(5))

    for node in dense:
        assert direct[node] == pytest.approx(dense[node], abs=1e-10)


def test_G8c_cg_warm_start_matches_cold_solution():
    """A previous solution changes convergence work, not the solved system."""

    def matvec(values):
        return [
            4.0 * values[0] - values[1],
            -values[0] + 3.0 * values[1],
        ]

    rhs = [1.0, 2.0]
    cold = solve_cg(matvec, rhs)
    warm = solve_cg(matvec, rhs, x0=[cold[0] + 0.1, cold[1] - 0.1])
    assert warm == pytest.approx(cold, abs=1e-12)


# ── G9: determinism and persistence ─────────────────────────────────

def test_G9_deterministic():
    """Identical input -> byte-identical output. No RNG, no dict-order leak."""
    a = influence_map(grid_field(5), "R2C2", horizon=3).summary()
    b = influence_map(grid_field(5), "R2C2", horizon=3).summary()
    assert a == b


def test_G9b_roundtrip():
    f = grid_field(4)
    g = NavField.from_dict(f.to_dict())
    assert g.to_dict() == f.to_dict()
    assert potential_map(g) == pytest.approx(potential_map(f))


def test_G9c_cost_update_invalidates_cache():
    """The hot path -- changing a cost must change the geometry, not a stale copy."""
    f = loop_trap_field()

    before = influence_map(f, "A", horizon=3)
    i_before = next(a.intensity for a in before.actions if a.action == "B")
    assert before.best == "B"

    f.set_cost("A", "B", 5.0)          # the route to GOAL becomes expensive

    after = influence_map(f, "A", horizon=3)
    i_after = next(a.intensity for a in after.actions if a.action == "B")
    assert i_after < i_before / 10.0
    assert after.best == "C"


def test_G9d_cost_update_preserves_topology_revision():
    """Cost changes retain reusable topology data; edge changes do not."""
    f = loop_trap_field()
    topology_token = f.topology_token

    f.set_cost("A", "B", 0.6)
    assert f.topology_token == topology_token

    f.add_edge("GOAL", "A", cost=0.5)
    assert f.topology_token > topology_token


# ── G10: input validation ───────────────────────────────────────────

def test_G10_rejects_bad_input():
    f = NavField()
    with pytest.raises(ValueError):
        f.add_edge("A", "B", cost=-1.0)
    with pytest.raises(ValueError):
        f.add_edge("A", "B", cost=math.inf)
    with pytest.raises(ValueError):
        f.add_edge("A", "B", weight=-0.5)
    f.add_edge("A", "B", cost=0.1)
    with pytest.raises(KeyError):
        f.set_cost("B", "A", 0.2)
    with pytest.raises(ValueError):
        influence_map(f, "A", horizon=0)


def test_G10b_missing_edge_semantics():
    """Absent edge: flow 0, cost inf, v_rot None -- three distinct answers."""
    f = tree_field()
    assert f.flow("D", "A") == 0.0
    assert math.isinf(f.cost("D", "A"))
    assert v_rot(f, "D", "A") is None
    assert math.isinf(f.path_cost(["A", "B", "A"]))
