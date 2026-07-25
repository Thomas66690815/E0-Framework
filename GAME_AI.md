# E₀ for game and simulation developers

This document is a translation layer. E₀ was built as a structural reasoning framework and its
documentation uses that vocabulary. If you arrived here from pathfinding, crowd simulation or
agent AI, most of what is in this repository already has a name in your field — and a few
things do not, which is the interesting part.

Nothing here is new code. It is the same framework, described in the terms you would use to
decide whether to spend an afternoon on it.

---

## The one-paragraph version

E₀ is a navigation-and-decision layer for directed graphs where **edge costs change and nobody
has a reliable heuristic**. Agents learn edge costs from their own successes and failures at
runtime, with no training phase, no model, no GPU and no reward function. On top of that sits
a lookahead that scores moves by *complex-valued* path superposition rather than by summing
scalars — so routes that loop or dead-end are suppressed by the geometry instead of by
loop-detection code. It is deterministic, JSON-serialisable, and the interesting parts are
available as a dependency-free ~1150-line package you can port to C# in a day.

---

## Vocabulary map

| E₀ term | Your term | Notes |
|---|---|---|
| Landscape | Navigation graph / navmesh graph | Nodes and directed edges. Not tied to geometry — states can be anything. |
| Δ (difference) | Edge length / difficulty | Static per-edge weight. |
| R₀ (base resistance) | Base traversal cost | Terrain, road class, danger. |
| δ_H (historization delta) | Learned cost correction | Grows on failure, shrinks on success. |
| R_eff = R₀ + δ_H | Dynamic edge cost | What the agent actually plans against. |
| S_eff = Δ · R_eff | Edge cost | The thing being minimised. |
| Historization / Inscription | Runtime learning | Per-edge success/failure traces with decay. |
| Transition field v | Flow field | `Δ · exp(−S_eff)` per edge. |
| v_grad / v_rot | *(no standard term)* | Progress component vs. swirl component. See below. |
| Amplitude overlay | Influence map | But complex-valued — see below. |
| Communities (LPA on R_eff) | HPA\* clusters / navmesh regions | Derived from traversal, not authored. |
| Emergent locality | AI LOD / attention radius | Shrinks as the agent learns. |
| Structural entropy + sleep–wake | Memory budget + idle-time GC | Bounded persistent memory. |
| Shared historization | Faction / squad knowledge | One flag: solo memory or hive memory. |
| Self-graph | AI director monitoring itself | The system historises its own components. |
| NoveltyGate (multiverse) | Anti-stagnation director | "Consensus without novelty = failure." |
| Outcome SUCCESS/FAILURE | Did the move work? | Blocked, killed, path invalid — your call. |
| Escalation | Stuck handling | Dead end, filtered, exhausted, overloaded. |
| DifferenzPort | Input adapter | Sensor, player, LLM, script — one protocol. |

---

## The four things that are genuinely not standard

Everything above has an equivalent in shipped middleware. These four do not.

### 1. The navigation field is split into progress and swirl

Flow fields are treated as one opaque vector field. They are not one thing. Any flow field on
a graph decomposes **uniquely and orthogonally** into a conservative part and a circulating
part:

```
flow      = v_grad + v_rot
v_grad(u→v) = Φ(u) − Φ(v)          where  L·Φ = div(flow)     (graph Laplacian)
v_rot       = flow − v_grad         and    div(v_rot) ≡ 0
```

`v_grad` is the part that makes progress. `v_rot` is the part that makes crowds orbit
obstacles, units circle each other, and paths loop. It is the classic crowd-navigation failure
mode, and here it is a **number you can read per edge before spawning a single agent**:

```python
circulation_ratio(field)   # 0.0 = pure progress, 1.0 = pure swirl
```

A tree returns exactly `0.0` — with no cycles, gradients span the whole edge space, so agents
following the field structurally *cannot* loop. A ring with an expensive exit approaches `1.0`.
A 5×5 grid with a cost gradient sits around 0.3–0.6.

Practical use: assert on it in CI, log it per region, drive an authoring warning from it. You
normally discover a swirl problem by watching units orbit a pillar in a playtest.

Entry points: [`e0_controller/potential.py`](e0_controller/potential.py),
[`lean/structural_geometry/helmholtz.py`](lean/structural_geometry/helmholtz.py).

### 2. The influence map is complex-valued

Influence maps, potential fields and Dijkstra-distance fields are all real-valued scalar
fields. That is a representational ceiling: a non-negative sum cannot distinguish *one route
that arrives* from *twenty routes that wander and come back*, because both produce a large
number. Every production system patches around this with visited-sets, revisit penalties or
path smoothing bolted on afterwards.

E₀ carries a complex amplitude per path:

```
Ψ(p) = exp(−cost(p)) · exp(i·Θ(p))
```

`|Ψ|` is how cheap the path is. `arg Ψ = Θ` is *where it went*, accumulated from the field's own
circulation — the `v_rot` from point 1. Amplitudes reaching the same node superpose, and
superposition can subtract. Route topology becomes a term in the score rather than a
correction applied to it.

**Be precise about the size of the effect.** This is a regime, not a magic trick. Below a
route-to-route phase gap of ~0.1π nothing meaningfully cancels and the ranking is
`exp(−cost)` with extra steps. Cancellation needs a gap approaching π. The package ships
`phase_regime(field)` which reports `"gradient"` / `"interfering"` / `"wrapped"` so you can
check rather than assume. The gap scales linearly with your chosen edge weight, so the regime
is a modelling choice you control.

Entry points: [`e0_controller/wavepath.py`](e0_controller/wavepath.py),
[`e0_controller/amplitude_overlay.py`](e0_controller/amplitude_overlay.py),
[`lean/structural_geometry/amplitude.py`](lean/structural_geometry/amplitude.py).

### 3. Exploration self-tunes without an epsilon schedule

[`quantum_walk_historized.py`](e0_controller/quantum_walk_historized.py) gates its own
randomness on how well-established an edge is:

```
conviction(e)       = (m / (m + μ)) · |q(e)|      m = evidence, q = direction
quantum_strength(e) = 1 − conviction(e)
```

On unfamiliar or contested edges the walk is stochastic and exploratory. On edges it has
confirmed repeatedly it collapses toward deterministic. There is no epsilon decay, no
temperature schedule, no curve for a designer to author.

In gameplay terms this is emergent **familiarity**: an NPC is erratic in territory it does not
know and routine in its home ground, and the transition is a consequence of its own history
rather than a tuned parameter. There is no shipped middleware that does this.

### 4. Knowing when *not* to use the clever path

This is the part most worth stealing even if you take nothing else.

In a 1000-tick congestion study with 20 agents on a grid city with capacity-1 chokepoints:

| Strategy | Trips | Throughput / 100 | Stuck |
|---|---|---|---|
| BFS shortest path | 1112 | 111.2 | 11 270 |
| Greedy (no memory) | 2071 | 207.1 | 8 535 |
| Memory, never overrides | 2462 | 246.2 | 6 623 |
| **Overrides on every disagreement** | **2229** | **222.9** | **8 107** |
| Overrides only above 0.85 confidence | **2565** | **256.5** | 6 913 |

The lookahead is right often enough to be worth having and wrong often enough that acting on
it indiscriminately made things **worse than not having it**. Each high-confidence override
saved ~0.5 stuck events; each low-confidence override cost ~0.4.

`InfluenceReport.should_override()` ships with those measured thresholds
(`min_confidence=0.85`, `max_imbalance=3.0`) as defaults. This is the generalisable lesson:
a smarter planner needs a confidence gate, not just a better score.

Full report including the failure cases: [C185](docs/research/C185_TRAFFIC_VALIDATION_REPORT_v1.md).

---

## What the benchmarks actually show

### Congestion: 2.3× the throughput of precomputed shortest paths

The table above. The mechanism is not subtle — BFS routes every agent through the same
chokepoint, and per-agent memory does not. If your game has ever gridlocked a unit column in a
doorway, this is that problem.

### Navigation without a map

`py -3 -m e0_controller.benchmark_gridworld` — 5×5 grids with walls, dead-end lures and trap
loops:

| Domain | A\* (has the map) | Naive greedy | E₀ (learns by failing) |
|---|---|---|---|
| Detour wall | 8 steps | 0 % success | 100 %, 16 steps |
| Dead-end lure | 8 steps | 0 % success | 100 %, 10 steps |
| Trap loop | 8 steps | 0 % success | 100 %, 8 steps |

A\* is given the topology and is optimal. E₀ is not given it and still arrives, at 1–2×
optimal, by inscribing its own failures. The use case is not "replace A\*" — it is *the cases
where you cannot run A\* because you do not have the cost function A\* would need*.

### Dynamic environments

Falsification target **F2**: the executor changes mid-run — the route that worked is blocked,
a new one opens. E₀ adapts fully (100 % goal rate), no ossification. That is destructible
terrain, doors that lock, player-built walls, a bridge that collapses. A\* replans from
scratch each time; E₀ retains what it learned about everything else.

---

## Where it does not work

Stated plainly, because you will find these anyway.

**Dense branching (F3).** Complete tree with branching factor ≥ 3: path enumeration grows as
`O(b^h)` and the advantage disappears. Both E₀ and greedy fail. Keep `branching^horizon`
tractable; horizon 2–4 on a 4-connected grid is the working range. The lean package caps
enumeration and flags truncation rather than silently sampling.

**Non-adjacent dependencies (F4).** If success on edge C depends on having traversed edge A
three steps earlier, E₀ learns to avoid the trap but cannot learn the required sequence.
Credit assignment is edge-local. Trajectory historization (C277–C283) narrows this but does
not close it. If your mechanic is "pull lever, then door opens", model the lever state as part
of the node identity.

**Stale memory in dynamic chokepoints.** In the two-bridge river city, learned congestion costs
outlive the congestion: agents drift sideways to avoid a bridge that is now free, and E₀ greedy
falls 29 % *below* memoryless greedy. Memoryless retrying beats memorial avoidance when the
world changes faster than the memory decays. Use decaying costs, and read the honest write-up
before assuming memory is free.

**Single agent, static costs.** A\* is better and cheaper. E₀'s sweet spot is many agents on a
shared graph with chokepoints and time-varying costs.

**Frame budget is unmeasured.** The complexity is documented below, but nobody has profiled
this inside a game loop. Treat the per-tick cost as something to measure, not as a claim.

| Operation | Complexity |
|---|---|
| One controller step (greedy + inscription) | `O(out-degree)` |
| Helmholtz solve, cached per cost-batch | `O(n³/3)` dense, `O(edges · iters)` sparse |
| Influence map | `O(branching^horizon)` |
| Community detection (LPA) | `O(edges · iterations)` |

---

## Ideas this maps onto, ranked by how little work they need

**Congestion-aware unit movement.** Directly the benchmarked case. Feed intersection occupancy
into `cost`, give each unit its own historization, gate the overlay at 0.85.

**Automatic hierarchical pathfinding regions.** [`community.py`](e0_controller/community.py)
runs label propagation on the `R_eff` matrix — deterministic, no dependencies — and derives
clusters from where agents actually go rather than from authored region markup.

**Faction knowledge as a gameplay mechanic.** [`test_shared_historization.py`](e0_controller/test_shared_historization.py)
(C189): one flag switches between every NPC learning alone and the whole faction knowing
instantly when a scout dies. That is a design lever, not a config option — it changes how the
player experiences enemy intelligence.

**NPC memory that does not grow forever.** [`structural_entropy.py`](e0_controller/structural_entropy.py)
plus [`sleep_wake.py`](e0_controller/sleep_wake.py): pruning during idle phases, bounded
footprint. Persistent-world NPC memory is normally either unbounded or hand-capped.

**An AI director with a stated objective.** [`multiverse.py`](e0_controller/multiverse.py)'s
NoveltyGate treats *consensus without structural novelty* as failure, which pushes coupled
systems away from stagnation. [`self_graph.py`](e0_controller/self_graph.py) lets the system
historise its own components and deactivate the ones that measurably hurt.

**Opponent AI with a drifting style.** [`chess_e0.py`](e0_controller/chess_e0.py) plays by
navigating *strategic dimensions* (material, king safety, centre control, activity, pawn
structure, development) rather than a move tree — it picks which dimension to optimise, then
selects deterministically within it, and learns which dimension transitions pay off.
[`chess_team.py`](e0_controller/chess_team.py) runs three such agents sharing knowledge through
a coupling router. Cheap at runtime, and the resulting opponent has something a search-based
engine does not: a recognisable disposition that changes with experience.

---

## Getting started in fifteen minutes

The lean geometry package has no dependencies and no framework to learn:

```bash
cd lean && python -m structural_geometry.demo
```

Three scenes: the field decomposition, the interference regimes, and the influence map with
its gate. Every printed claim matches the printed numbers — including the one showing that
outright destructive interference only appears in the regime the tool warns about.

Then watch the congestion case play out — two topologies, three strategies, side by side:

```bash
py -3 -m e0_controller.demo_traffic_visual
```

That writes a self-contained HTML page with no dependencies. It shows the uniform grid where
E₀ roughly doubles BFS throughput **and** the river city where E₀ loses, because a demo that
only shows its wins is not worth your time.

And the map-free navigation benchmark:

```bash
py -3 -m e0_controller.benchmark_gridworld
```

If you want to read code rather than run it, the geometry chain is four files:
[`potential.py`](e0_controller/potential.py) →
[`connection.py`](e0_controller/connection.py) →
[`wavepath.py`](e0_controller/wavepath.py) →
[`amplitude_overlay.py`](e0_controller/amplitude_overlay.py).

Porting target: [`lean/structural_geometry/`](lean/structural_geometry) is ~1150 lines of pure
Python with one `math.exp`, one `cmath.exp` and one linear solve. The port to C#, C++ or Rust
is mechanical.

---

## Related work, honestly

E₀'s interference layer is not without precedent. **Projective Simulation** (Briegel et al.)
models deliberation as a random walk on an episodic memory graph and has an explicit
quantisation route through quantum walks. **D\* Lite** and **Planning with Experience Graphs**
cover incremental replanning and episode-derived reuse. **History-dependent transition costs**
(Cowlagi & Tsiotras) solve shortest paths when edge costs depend on prior path history.

What has no prior art, as far as this project's own literature review found, is the
combination: interference on graphs **plus** an orthogonal Helmholtz decomposition of the
transition field **plus** per-edge curvature from triangle holonomy. That is the
`potential.py → connection.py → wavepath.py` chain, and it is why the phase is derived rather
than assumed.

See [docs/papers/related-work-research-report.md](docs/papers/related-work-research-report.md).

---

## License and citation

CC BY 4.0. If you ship something built on this, the citation is in the
[README](README.md#citation). The lean packages carry attribution tokens
(`e0-reliability-memory-twehner`, `e0-structural-geometry-twehner`) so the author can see where
the code travelled — leaving them in place is appreciated and is what the license asks for.
