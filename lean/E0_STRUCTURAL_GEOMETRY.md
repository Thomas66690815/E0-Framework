# Structural Geometry — the navigation-field layer of E₀ for engine builders

A self-contained, ~900-line package that takes a directed graph with per-edge costs and
answers three questions no conventional navigation stack answers:

1. **How much of my navigation field is wasted motion?** — the Helmholtz split separates the
   part that makes progress from the part that circulates, exactly and orthogonally.
2. **Does walking a loop here leave the field where it started?** — holonomy and per-edge
   curvature, computed before anything moves.
3. **Which next move has the strongest forward support, once loops and dead ends have been
   allowed to cancel themselves?** — a complex-valued influence map over moves.

This is the geometry half of the [E₀ Framework](https://github.com/Thomas66690815/E0-Framework).
The companion package [`reliability_memory`](E0_LEAN_CORE.md) is the *memory* half — it learns
which edges are reliable from outcomes. The two are independent: use either, or feed the
memory's `R_eff` into this package's `cost` and use both.

Zero third-party dependencies. Pure Python. Deterministic. JSON round-trip.

---

## 1. Why this is not an influence map you already have

Influence maps, potential fields, flow fields and Dijkstra-distance fields are all
**real-valued scalar fields**. That is a representational ceiling, not an implementation
detail: a non-negative sum cannot distinguish

- one route that genuinely arrives, from
- twenty routes that wander, loop, and come back,

because both accumulate a large positive number. Every production system patches around this
with explicit loop detection, visited-sets, revisit penalties, or path smoothing — bolted on
top of the field, not derived from it.

This package carries a **complex amplitude** per path:

```
Ψ(p) = exp(−cost(p)) · exp(i·Θ(p))
```

`|Ψ|` is how cheap the path is. `arg Ψ = Θ` is where the path went — accumulated from the
field's own circulation. Amplitudes reaching the same node superpose, and superposition can
*subtract*. Route topology becomes a first-class term in the score rather than a correction
applied afterwards.

### Where the phase comes from

Not from a heuristic. From the field itself.

Any flow field on a graph splits uniquely into a conservative part and a circulating part:

```
flow      = v_grad + v_rot
v_grad(u→v) = Φ(u) − Φ(v)              solve  L·Φ = div(flow)
v_rot       = flow − v_grad             div(v_rot) ≡ 0
```

`L` is the graph Laplacian. Because `Φ` solves that equation exactly, the two parts are
**orthogonal in edge space**: `⟨v_grad, v_rot⟩ = ⟨Φ, div v_rot⟩ = 0`. The package ships
`orthogonality_residual()` as a live assertion of this, not a claim in a comment.

`v_rot` is the only source of path-dependence in the whole system. It induces

```
ω(u→v) = ½ (v_rot(u→v) − v_rot(v→u))      connection, antisymmetric
Θ(p)   = Σ ω                               path phase
Hol(γ) = Θ(closed γ)                       holonomy — net phase per lap
κ(u→v) = mean |Hol| over triangles         local curvature
```

No circulation → no connection → every phase is zero → amplitudes collapse to plain positive
sums and you are back to a conventional influence map. That degeneracy is a theorem here, and
`test_G2_tree_is_pure_gradient` pins it: on a tree, `v_rot` is exactly zero.

---

## 2. `circulation_ratio` — the number to look at first

```
circulation_ratio = ‖v_rot‖² / (‖v_grad‖² + ‖v_rot‖²)     ∈ [0, 1]
```

- `0.0` — the field is pure gradient. Every edge makes progress. Agents following it
  **cannot** loop, structurally.
- `1.0` — pure circulation. The field has no downhill direction at all. Agents following it
  **only** loop.

A 5×5 grid with a rising cost gradient sits around 0.3–0.6. A ring with an expensive exit
approaches 1.0 — and it does so *before you spawn a single agent*.

This is the practical payoff of the decomposition. Crowd systems normally discover their swirl
problem by watching units orbit an obstacle in a playtest. Here it is a scalar you can assert
on in CI, log per region, or drive an authoring warning from.

---

## 3. The influence map, and the gate that stops it hurting you

```python
report = influence_map(field, current, horizon=3)

report.greedy          # cheapest immediate edge — the one-step baseline
report.best            # strongest interfering forward support
report.confidence      # P_best − P_second
report.path_imbalance  # is `best` winning on merit or on path count?
report.decide()        # gated: best if the gate passes, else greedy
```

`best` and `greedy` usually agree. **The disagreements are where the value and the danger both
live**, and the parent framework measured which is which. In a 1000-tick, 20-agent congestion
study on a grid city with chokepoints:

| Strategy | Trips | Throughput / 100 | Stuck |
|---|---|---|---|
| BFS shortest path | 1112 | 111.2 | 11 270 |
| Greedy (no memory) | 2071 | 207.1 | 8 535 |
| Memory only, never override | 2462 | 246.2 | 6 623 |
| Override on **every** disagreement (conf ≥ 0.5) | 2229 | 222.9 | 8 107 |
| **Override only on high confidence (conf ≥ 0.85)** | **2565** | **256.5** | 6 913 |

Overriding aggressively scored **worse than never overriding at all**. Each high-confidence
override saved ~0.5 stuck events; each low-confidence override *cost* ~0.4.

`should_override()` ships with `min_confidence=0.85, max_imbalance=3.0` — those numbers, not
round-number guesses. Lower them and you will reproduce the failure row, not a speedup.

---

## 4. The three things that decide whether this works

Honest limitations. Address them before expecting value.

**1. Phase only matters in the right regime.** `Θ` scales linearly with `ω`, hence with `flow`,
hence with your chosen `weight`. Below a route-to-route phase gap of ~0.1π, amplitudes are
near-collinear, nothing cancels, and the ranking is `exp(−cost)` with extra steps. Above 2π,
phases alias and the ranking becomes erratic in `weight`. Call `phase_regime(field)` — it
reports `"gradient"` / `"interfering"` / `"wrapped"` and the gap it measured. Do not claim
cancellation you are not getting; the package's own demo shows a field where outright
destructive interference only appears in the wrapped regime.

**2. Enumeration is exponential in the horizon.** `O(branching^horizon)`. Horizon 2–4 is the
useful range on a 4-connected grid. `enumerate_continuations` caps at `DEFAULT_MAX_PATHS` and
sets `report.truncated` — a truncated report's intensities are not comparable across moves, so
refuse to act on it rather than trusting it. The parent framework's falsification benchmark
records this as confirmed limit **F3**: at branching factor ≥ 3 on a complete tree, the
combinatorial explosion defeats the mechanism outright.

**3. Cost quality is the crux.** The geometry is exact; it is exact *about whatever you put in
`cost`*. Static costs give you a static field and a one-time answer. The interesting behaviour
comes from updating `cost` as the world changes — congestion, danger, damage, a learned
reliability trace — and re-reading the geometry. `set_cost` / `update_costs` invalidate the
cached solve automatically.

---

## 5. Cost model

The Helmholtz solve is the only non-trivial cost, and it is cached per field revision — one
solve per batch of cost changes, not per query.

| Component | Cost |
|---|---|
| `potential_map` (dense Cholesky, per component) | `O(n³/3)`, used for `n ≤ 256` |
| `potential_map` (sparse conjugate gradients) | `O(edges · iterations)`, used above that |
| `omega_map`, cached per revision | `O(edges)` |
| `edge_curvature` for one edge | `O(deg²)` |
| `influence_map` | `O(branching^horizon)` |

The parent framework uses `numpy.linalg.lstsq` on a dense `n×n` matrix and pins a single node
globally. This package solves **per weakly connected component** with one pin each, which is
both exact (the reduced Laplacian of a connected component is positive definite — no
pseudo-inverse required) and correct for disconnected graphs by construction rather than by
accident. `test_G8_cg_matches_cholesky` pins the two solvers to each other.

---

## 6. Integration sketch

```python
from structural_geometry import NavField, influence_map, circulation_ratio, phase_regime

field = NavField()
for (u, v), dist in nav_graph_edges():
    field.add_edge(u, v, cost=dist, weight=1.0)

# once, at authoring time — is this level's navmesh full of swirl?
assert circulation_ratio(field) < 0.7, "navigation field is mostly circulation"
assert phase_regime(field)["regime"] != "wrapped"

# per tick — costs move, the geometry follows
field.update_costs({(u, v): base[u, v] + congestion[v] for u, v in hot_edges})

for agent in agents:
    report = influence_map(field, agent.node, horizon=3, goals={agent.goal})
    agent.step_to(report.decide())
```

Nothing here is engine-specific and nothing imports a third-party package, so the port to C#,
C++ or Rust is mechanical: five modules, one `math.exp`, one `cmath.exp`, one linear solve.

---

## 7. What was deliberately left out

Dropped from the full framework because it does not serve the geometry use case: historization
and U/F traces (that is `reliability_memory`), the controller's escalation and revisit
machinery, SU(2)/spinor coins and the quantum walk, dream mode, multiverse coupling, structural
entropy, sleep–wake, self-graph, perception/UI, LLM adapters.

The SU(2) layer is the most interesting omission — the parent framework generalises the scalar
connection `ω` to a full non-abelian `SU(2)` transport, which makes the coin carry orientation
as well as phase. It is a genuine extension and it can be re-added on top of this package's
`connection` module without touching anything else. It is not needed to state the core claim.

The machine-readable build specification is in `structural_geometry.bootstrap.json` — hand it
to a coding agent to reconstruct the package from scratch.

---

## Appendix — E₀ canon ↔ this package

| E₀ canon | This package | Meaning |
|---|---|---|
| `Δ` | `weight` | difference measure the edge spans |
| `S_eff = Δ · R_eff` | `cost` | current traversal cost |
| transition field `v` | `flow` | `weight · exp(−cost)` |
| §9 potential `Φ` | `potential` | Helmholtz potential |
| §10 `v_grad` | `v_grad` | conservative component |
| §11 `v_rot` | `v_rot` | rotational component |
| §12 connection `ω` | `omega` | per-edge phase |
| §13 path phase `Θ` | `theta` | accumulated phase |
| §14 holonomy | `holonomy` | net phase per closed lap |
| curvature `κ`, `M_H` | `edge_curvature`, `damping` | local curl, traversal damping |
| §15 `Ψ(p)` | `psi` | complex path amplitude |
| §16 path summation `I` | `intensity` | `|ΣΨ|²` |
| amplitude overlay | `influence_map` | per-move interfering support |
| `path_count_imbalance` | `path_imbalance` | path-count bias guard |
| `override_confidence` | `confidence` | `P_best − P_second` |
| Landscape | `NavField` | the graph itself |

Author: Thomas Wehner · License: CC BY 4.0 ·
Source: <https://github.com/Thomas66690815/E0-Framework>
