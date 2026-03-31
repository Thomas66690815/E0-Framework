# E₀ Multiverse Design Document v1

**Status:** Working reference  
**Date:** 2026-03-31  
**Modules:** C54 (`raumzeit_coupling`), C60 (`multiverse`), C61 (`benchmark_multiverse`), C62 (`cross_reflexion`), C63 (`controller.py` — OVERLOADED escalation), C66 (`coupling_router`)  
**Tests:** 121+ dedicated tests across 5 test files  
**Paper coverage:** None yet — candidate for Paper 5

---

## 1. Problem Statement

When two E₀-aware systems interact (e.g., two LLMs in co-cognition), they converge within 5–6 turns. Consensus emerges quickly and blocks further exploration. This phenomenon — **Δ-Kollaps** — is structurally identical to the Gordian Trap (P1 §5): a system that only produces SUCCESS outcomes reinforces existing paths and cannot find new ones.

**Observation:** Consensus without novelty is indistinguishable from stagnation. The systems agree — but on what? On the first sufficient answer. Not on the best one.

---

## 2. Theoretical Foundation

### 2.1 Coupling Necessity Theorem (C54)

Proven in `raumzeit_coupling.py`:

> A closed E₀ system (all outcomes SUCCESS) reinforces existing paths through historization and cannot escape deep traps. Only coupling — interaction with an outside that delivers real FAILURE signals — creates the resistance asymmetry necessary for trap escape.

This connects to Ontodynamics §4: time = ordering of historizations. If historization only reinforces (closed system), the topology is monotone — no new structure emerges. Only through coupling does historization produce asymmetry. This asymmetry IS emergent temporal structure.

### 2.2 Δ-Kollaps as Trap

When two systems converge:
- All coupling interactions produce SUCCESS (they agree)
- R_eff on coupling edges drops (reinforced)
- The systems keep using the same coupling paths
- No FAILURE = no exploration pressure
- Structural novelty halts

This IS a trap in the coupling landscape. The solution must come from the same E₀ mechanisms that solve traps in single systems — but applied at the coupling level.

---

## 3. Architecture

```
┌─────────────┐                         ┌─────────────┐
│ Universe A   │                         │ Universe B   │
│              │    Coupling Landscape    │              │
│  Landscape   │◄──────────────────────►│  Landscape   │
│  Historiz.   │   edges: A↔B, modes     │  Historiz.   │
│  Controller  │   outcomes: NoveltyGate │  Controller  │
│  execute_fn  │                         │  execute_fn  │
└─────────────┘                         └─────────────┘
```

The coupling landscape is a standard E₀ landscape. Its outcomes are NOT determined by domain execution, but by the **NoveltyGate** — did the interaction produce structural novelty?

### 3.1 Turn Protocol

```
Turn N:
  1. Snapshot BEFORE: (state_count, edge_count, total_delta) for both universes
  2. Execute turn function: active universe navigates, interacts with passive
  3. Snapshot AFTER: same metrics
  4. NoveltyGate evaluates: new_states > 0 OR new_edges > 0 OR delta_growth > threshold?
     → YES: SUCCESS (novel interaction)
     → NO:  FAILURE (stale consensus)
  5. Historize coupling edge with outcome
  6. Check convergence: last N turns all FAILURE?
     → YES: apply divergence pressure
```

### 3.2 Key Insight: Divergence Timing

Divergence pressure must be applied **during** the next turn, between the before/after snapshots. If applied after a turn, the next turn's "before" snapshot already includes the new edges — NoveltyGate cannot see the change.

Implementation: `diverge_next` flag delays divergence injection to the optimal moment.

---

## 4. Components

### 4.1 NoveltyGate

```python
NoveltyGate.evaluate(before_a, after_a, before_b, after_b) → Outcome
```

Measures three structural novelty signals:
- **New states**: states added to either universe
- **New edges**: edges added to either universe  
- **Delta growth**: total Δ increase beyond threshold

Any one signal suffices for SUCCESS. All zero = FAILURE.

The `delta_threshold` parameter (default 0.5) prevents noise from triggering false novelty.

### 4.2 Divergence Pressure

When convergence is detected (N consecutive FAILURE turns):

1. **New coupling mode**: Add intermediate state `mode_N` with fresh low-R edges in coupling landscape → new, cheap interaction pathway
2. **Exploration edges**: For each universe, find the least-connected state pair with no direct edge and add one with high Δ → structural tension toward unexplored territory

### 4.3 Cross-Reflexion (C62)

When Universe A is stuck at a frontier, Universe B's accumulated experience informs hypothesis edges in A — edges that **never existed in either universe**.

```python
cross_propose_edges(stuck_landscape, donor_landscape, current, goal)
```

Pipeline:
1. Extract `experienced_pattern()` from both landscapes (Δ/R₀ medians of successful edges)
2. `blend_patterns()`: weighted merge (self_weight = sample_size, donor_weight = sample_size × coupling_discount)
3. Find candidate targets (unreachable states in stuck landscape)
4. Scale R₀ by inverse confidence (cross-hypotheses are cautious)
5. Sort by goal proximity

**Coupling discount** (default 0.5): Foreign experience carries more uncertainty than self-experience. 1.0 = full trust, 0.0 = ignore donor.

**Confidence cap** at 0.7 (vs 0.8 for self-reflexion): Structurally encodes that foreign experience is less certain.

### 4.4 Overload Escalation (C63)

Integrated into the controller's `select_next()`:

```
Overload Index = N_admissible × (1 − mean|trace_quality|)
```

- Many paths + little experience = overwhelmed
- When OI > threshold → `peer_fn(landscape, current, neighbors) → Optional[str]`
- Self-resolving: as historization builds, OI drops below threshold

The `peer_fn` is intentionally generic: it can be another E₀ system (cross-reflexion), an LLM, or a human advisor. The interface is always: `(landscape, current, neighbors) → Optional[str]`.

---

## 5. Distinction of Edge Discovery Mechanisms

| Mechanism | Module | What it does | Creates new edges? |
|-----------|--------|--------------|:------------------:|
| Reactive Reflexion (C56) | `reflexive_edge_proposal` | Stuck → propose from own experience | Yes, from self |
| Proactive Reflexion (C57) | `reflexive_edge_proposal` | Frontier → propose before getting stuck | Yes, from self |
| Knowledge Exchange (C61) | `benchmark_multiverse` | Copy existing edges from A → B | No — transfers |
| Cross-Reflexion (C62) | `cross_reflexion` | Donor experience → new hypotheses in recipient | **Yes, from other** |
| Divergence Pressure (C60) | `multiverse` | Connect least-connected states | Yes, mechanical |

The qualitative difference: C56/C57 use **self-experience**. C62 uses **foreign experience**. C61 copies **existing edges**. C60 injects **mechanical exploration edges**.

---

## 6. Empirical Results (C61 Benchmark)

Five structurally diverse cross-domain pairings, 12 turns each:

| Pairing | Domain A | Domain B | Novelty Rate | Converged? | Conv. Turn | Divergences |
|---------|----------|----------|:------------:|:----------:|:----------:|:-----------:|
| P1 | Linear | Gordian Trap | 50% | Yes | T7 | 1 |
| P2 | Diamond | Wide DAG | 67% | No | — | 0 |
| P3 | Grid | Bottleneck | 75% | No | — | 0 |
| P4 | Star | Nested Cycles | 67% | Yes | T9 | 1 |
| P5 | Greedy Trap | Invoice | 75% | No | — | 0 |

**Key findings:**
- Average novelty rate: 67% — most turns produce genuine structural change
- Structural diversity delays convergence: Grid×Bottleneck (75% novelty, no convergence) vs Linear×Gordian (50%, converges at T7)
- Only 2/5 pairings converge within 12 turns
- Divergence pressure activates exactly when needed and breaks convergence
- Knowledge exchange adds 2–4 coupling edges per pairing

---

## 7. Integration Points

### 7.1 Controller ↔ Multiverse

The controller's OVERLOADED escalation (C63) enables the multiverse to be consulted **within** normal navigation:

```python
def my_peer_fn(landscape, current, neighbors):
    """Consult donor universe for guidance."""
    result = cross_propose_edges(landscape, donor.landscape, current, goal)
    if result.proposals:
        return result.proposals[0].target
    return None

ctrl = E0Controller(landscape, execute_fn, peer_fn=my_peer_fn, overload_threshold=3.0)
```

### 7.2 MultiverseController Turn Functions

Custom turn functions implement different coupling strategies:

| Turn Function | What it does |
|---------------|--------------|
| `_default_turn` | Run controller in active universe (5 cycles) |
| `knowledge_exchange_turn` | Navigate active + transfer edges to passive |
| `cross_reflexion_turn` | Navigate active + cross-propose at frontiers |

All are `TurnFn = Callable[[Universe, Universe], None]` — the interface is stable.

### 7.3 Self-Graph Integration (future)

The self-graph (C43) could observe coupling quality: which coupling modes produce novelty? Which don't? This would enable **reflexive coupling** — the system reflects on the quality of its interaction, not just on its own navigation.

---

## 8. Open Questions (for later)

1. **N > 2 Universes**: ✅ **RESOLVED (C66)**. `CouplingRouter` maintains a complete-graph routing landscape over N universes. Partner selection uses dual pressure: RECOVERY → argmax(trace_quality) (proven partner), EXPLORATION → argmax(Δ) (most structurally different). Dynamic membership via `add_universe()` / `remove_universe()`. 33 tests in `test_coupling_router.py`. The key insight: partner selection IS E₀ navigation — the same primitives that navigate domains also navigate the space of coupling partners.

2. **Asymmetric Coupling**: Currently both universes have equal standing. In practice, a domain expert and a generalist might need different coupling weights.

3. **Coupling Self-Graph**: The coupling landscape itself could have a self-graph — tracking which coupling modes work. This would be Stufe-3 reflexion at the multi-system level.

4. **Multiverse Benchmark with Cross-Reflexion**: C61 uses knowledge_exchange_turn. A benchmark with `cross_reflexion_turn` would test whether foreign-experience proposals outperform simple edge copying.

5. **OVERLOADED Benchmark**: C63 has unit tests but no domain-scale benchmark. How does peer consultation affect 10-domain performance?

6. **LLM Co-Cognition**: The original motivation. Two LLMs with E₀ controllers, coupled via multiverse, with NoveltyGate preventing premature consensus. The infrastructure exists — the integration test doesn't yet.

---

## 9. Module Map

```
raumzeit_coupling.py (C54) ─── Theorem: coupling is necessary
         │
         ▼
multiverse.py (C60) ────────── Core: NoveltyGate, divergence, coupling
         │
    ┌────┴────┐
    ▼         ▼
benchmark_    cross_reflexion.py (C62) ─── Foreign experience → new edges
multiverse.py       │
(C61)          ┌────┴────┐
               ▼         ▼
         controller.py   coupling_router.py (C66)
         (C63)           N>2 dynamic partner selection
         OVERLOADED      RECOVERY vs EXPLORATION
         + peer_fn       + make_routed_peer_fn
```

---

## 10. Test Coverage

| Module | Test File | Tests | Classes |
|--------|-----------|------:|---------|
| `multiverse.py` | `test_multiverse.py` | 35 | 8 classes |
| `benchmark_multiverse.py` | `test_benchmark_multiverse.py` | 19 | 5 classes |
| `cross_reflexion.py` | `test_cross_reflexion.py` | 19 | 5 classes |
| C63 (controller) | `test_overload_escalation.py` | 15 | 4 classes |
| `coupling_router.py` | `test_coupling_router.py` | 33 | 10 classes |
| `raumzeit_coupling.py` | `test_raumzeit_coupling.py` | varies | — |
| **Total** | | **121+** | |
