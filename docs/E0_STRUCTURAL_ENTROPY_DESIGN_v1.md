# E₀ Structural Entropy — Forgetting as Structural Necessity

**Status**: Design Note  
**Date**: 2026-04-02  
**Depends on**: Historization (L2), Dream Mode (L9, C109–C112), Controller (L4)  
**Canon alignment**: §4 Irreversibility (structural inscription), §5 Reflexivity (threshold of relevance)

---

## 1. Problem Statement

E₀ accumulates structure monotonically. Every transition is inscribed (`historize_outcome()`), every state persists, every edge remains in the landscape forever. K2 lazy decay reduces the *amplitude* of traces (ρ^gap), but never removes *structure* — the entries in `_U`, `_F`, `_tau_last` exist indefinitely.

This contradicts every natural system:

- **Physics**: entropy, decoherence, information loss at horizons
- **Biology**: synaptic pruning, apoptosis, sleep consolidation
- **Consciousness**: forgetting as prerequisite for generalization

The consequence is threefold:
1. Landscapes grow without bound — deployment hits memory limits
2. Dream Mode operates on full graphs including noise — cannot distinguish signal from historical artifact
3. No genuine generalization — consciousness generalizes *because* it forgets details and retains only patterns

**Structural Entropy** introduces the destructive complement to E₀'s constructive inscription. Not as an external cleanup mechanism, but as an emergent property of the same principles that govern inscription.

---

## 2. Two Types of Forgetting

Derived from phenomenological analysis of human memory:

### Type 1: Non-Inscription (Inscription Threshold)

*"I drive the route but don't remember driving."*

The transition occurs but produces no new inscription because the outcome is expected. No new δ_H is generated. The system operates on pure inertia — freeing reflexive capacity for other tasks.

**Key insight**: This is not forgetting. It is a *threshold on inscription*. The event happens but is not *noted* because it carries no new information.

**Structural consequence**: Transitions below the inscription threshold do not trigger reflexive overhead (no self_graph update, no dual_reflection check, no dream_mode observation). The controller becomes a pure inertia system for these edges.

### Type 2: Structural Decay (Anchor-Based Pruning)

*"I once knew this, but it no longer matters for the paths ahead."*

Information was inscribed but has lost its value for future navigation. What remains are *anchors* — states with strong emotional (quality) signatures — and the relationships between them are *reconstructible* but not stored.

**Key insight**: Memory does not store the full graph. It stores landmarks (anchors) with high quality amplitude, and everything between them dissolves. Access to the past goes through the emotional anchor — then reconstruction fills in the relations.

---

## 3. Structural Temperature — Self-Calibrating Forgetting

Forgetting follows global laws but manifests locally. The analogy is thermodynamic temperature: a global measure that determines local behavior (which bonds break, which molecules escape).

### Definition

```
T_s = m̄ / q̄

where:
  m̄ = mean(trace_load(e)) over all historized edges
  q̄ = mean(|trace_quality(e)|) over all historized edges + ε
```

| Regime | m̄ | q̄ | T_s | Meaning |
|--------|---|---|-----|---------|
| Cold | low | high | low | Little experience, but clear — stable, nothing to forget |
| Warm | high | high | moderate | Rich experience, clear — mature system, gentle pruning |
| Hot | high | low | high | Much experience, contradictory — overloaded, aggressive pruning |
| Virgin | 0 | 0 | 0 | No experience — nothing to forget |

**Self-calibration**: T_s requires no external parameter. It is fully determined by the landscape's own inscription statistics. A system full of contradictory experience "runs hot" and must shed structure. A system with clear judgments is "cold" and retains everything.

### Derived Quantities

**Inscription threshold** (Type 1):

```
ε(e) = ε₀(T_s) · (1 − exp(−trace_load(e) / μ))

where:
  ε₀(T_s) = 1 − exp(−T_s / T_ref)
  T_ref = μ  (half-load reference from inertia_factor — no new parameter)
  μ = existing parameter from inertia_factor (default 5.0)
```

At T_s = 0 → ε₀ = 0 → everything is inscribed (cold system, no forgetting).  
At T_s → ∞ → ε₀ → 1 → only extreme surprises are inscribed (hot system, aggressive filtering).

The per-edge scaling `(1 − exp(−m/μ))` ensures:
- Virgin edges (m = 0) → ε = 0 → always inscribed (you always remember the first time)
- Experienced edges (m >> μ) → ε ≈ ε₀ → only novelty is inscribed

**Dormancy threshold** (Type 2):

```
τ_dormant = ⌈log(θ_trace) / log(ρ)⌉

where:
  θ_trace = 0.01  (trace below 1% of peak → effectively forgotten)
  ρ = existing decay parameter (default 0.95)
```

At ρ = 0.95: τ_dormant ≈ 90 cycles.  
At ρ = 0.99: τ_dormant ≈ 459 cycles.

Again: no new parameter. Fully derived from existing ρ.

---

## 4. Novelty — The Inscription Gate

### Definition

```
novelty(e, outcome) = |signal(outcome) − expected(e)|

where:
  signal(SUCCESS) = +1
  signal(FAILURE) = -1
  signal(PARTIAL) = 0
  expected(e) = trace_quality(e)  ∈ (−1, +1)
```

### Examples

| Edge State | trace_quality | Outcome | signal | novelty | ε (if m=10, μ=5) |
|------------|--------------|---------|--------|---------|-------------------|
| Mostly succeeds | +0.8 | SUCCESS | +1 | 0.2 | ~0.51 · ε₀ → likely below threshold |
| Mostly succeeds | +0.8 | FAILURE | -1 | 1.8 | ~0.51 · ε₀ → likely above threshold |
| Unknown | 0.0 | SUCCESS | +1 | 1.0 | ~0.51 · ε₀ → above threshold |
| Virgin | 0.0 | SUCCESS | +1 | 1.0 | 0 → always inscribed |

### Decision

```
should_inscribe(e, outcome) = novelty(e, outcome) > ε(e)
```

When `should_inscribe` returns False:
- `historize_outcome()` is **skipped**
- `self_graph` is **not updated**
- `dual_reflection` is **not triggered**
- `dream_mode` does **not observe** this transition
- The controller proceeds to the next cycle with minimal overhead

This is the "autopilot" mode — the system navigates on inertia, freeing capacity.

---

## 5. Anchor Analysis

### Anchor Score

```
anchor_score(s) = |q̄_s| · m_max(s) · log(1 + degree(s))

where:
  q̄_s = mean(trace_quality(e)) over all edges incident to s
  m_max(s) = max(trace_load(e)) over all edges incident to s
  degree(s) = number of edges incident to s
```

Components:
- **|q̄_s|**: clarity of experience at this state (emotional valence)
- **m_max(s)**: depth of experience (how much happened here)
- **log(1 + degree(s))**: structural centrality (hub vs leaf)

A state that is emotionally strong, deeply experienced, and well-connected is an anchor. A state that is emotionally neutral, lightly experienced, and peripheral is not.

### Decay Candidates

```
decay_candidate(s) = anchor_score(s) < θ_decay(T_s)
                     AND min_gap(s) > τ_dormant
                     AND s ∉ {start, goal, current}  # safety

where:
  θ_decay(T_s) = θ_base · (1 + T_s)  # hotter system → higher threshold → more pruning
  θ_base = calibrated from empirical anchor_score distribution
  min_gap(s) = τ − max(τ_last(e)) over edges incident to s
```

Both conditions must hold: the state must be *both* structurally unimportant *and* dormant for a long time. Neither alone is sufficient.

Safety: start states, goal states, and the current position are never decay candidates.

---

## 6. DecayTrace — The Residue

When a state decays, what remains at its surviving neighbors:

```python
@dataclass(frozen=True)
class DecayTrace:
    """What remains after structural decay — the anchor's memory of the lost."""
    original_state: str
    surviving_neighbors: Tuple[str, ...]   # only anchors that survived
    mean_quality: float                     # was the experience good or bad?
    peak_load: float                        # how significant was it?
    decayed_at_tau: int                     # when it dissolved
```

This is an *anecdote* — not the full experience, but enough to recognize it if encountered again. The `bootstrapper` could reconstruct a state from a DecayTrace if the system needs to re-explore that region (memory reconstruction via anchor).

DecayTraces are stored on the surviving neighbor states, not globally. Each anchor carries the ghosts of what used to surround it.

---

## 7. Structural Decay Process

### Step-by-Step

```
apply_decay(landscape, historization, candidates) → DecayReport:

  for each state s in candidates:
    1. Compute DecayTrace from current data
    2. Store DecayTrace on each surviving neighbor
    3. Remove all edges incident to s from landscape
    4. Remove s from landscape._states
    5. Delete _U[e], _F[e], _tau_last[e] for removed edges
    6. Append to decay log

  return DecayReport(removed_states, removed_edges, traces_created)
```

### Invariants Preserved

| Invariant | How Preserved |
|-----------|--------------|
| τ never decreases | Decay does not touch τ |
| Surviving edges have valid historization | Only edges of removed states are cleaned |
| No orphan edges | Edges are removed with their states |
| Goal reachability | Safety check excludes start/goal/current |
| Audit trail | DecayTrace preserves summary; _log entries for removed edges remain (historical record) |

### What Happens to the Audit Log

The `_log` (List[TraceRecord]) is **not** truncated. Historical events remain in the log even after the edge is removed. The log is a record of what *happened*, not what *exists*. This matches human memory: you can recognize "I've been here before" even when the detailed structure has decayed.

---

## 8. Integration with Dream Mode

Dream Mode becomes the natural site for structural decay — mirroring biological sleep consolidation.

### Extended Dream Cycle

```
DreamObserver.dream_cycle():
  1. Compute T_s from all registered landscapes    [NEW]
  2. For each domain pair:
     a. Build DreamLandscape (existing)
     b. find_equivalences (existing)
  3. Identify decay candidates per landscape        [NEW]
  4. Create DecayTraces for candidates              [NEW]  
  5. Apply decay                                    [NEW]
  6. Return DreamReport (equivalences + decay_report)
```

**Why Dream Mode is the right place:**

- Biologically correct: consolidation and pruning happen during sleep
- Structurally sound: Dream Mode already has read access to all landscapes
- Temporally appropriate: dream cycles are periodic, not per-transition
- The equivalence scan happens *before* decay — so patterns are extracted from the full graph, then the graph is compressed

### Dream Mode on Anchors

After decay, subsequent dream cycles operate on a compressed landscape: fewer states, but each one is an anchor with high |trace_quality|. This means:

1. **EdgeFingerprints become sharper** — computed from clear, significant edges only
2. **Equivalences become deeper** — matching essential structure, not noise
3. **Bridge hypotheses become stronger** — connecting genuine landmarks, not incidental states

This is exactly why dreams are fragmentary but *meaningful*: they operate on the compressed, emotionally salient residue of experience.

---

## 9. Integration with Controller

### Modified cycle() Flow

```
controller.cycle(current):
  target = select_next(current)
  outcome = execute_fn(current, target)
  edge = (current, target)
  
  # --- Inscription threshold (Type 1) ---
  if should_inscribe(edge, outcome):        # NEW
      historize_outcome(edge, outcome)       # existing
      update_self_graph(...)                 # existing
      notify_dream_observer(...)            # existing
  else:
      # Autopilot: no inscription, no reflexive overhead
      pass                                   # NEW
  
  return StepResult(...)
```

### Impact on Existing Mechanisms

| Component | Change | Reason |
|-----------|--------|--------|
| `historization.update()` | Called conditionally | Inscription threshold |
| `self_graph` | Not updated below threshold | Reduces reflexive overhead |
| `dual_reflection` | Not triggered below threshold | Same |
| `dream_mode.DreamObserver` | Extended with decay step | Consolidation during dream |
| `scoped_reflexion` | Scope computed on anchors only | Locality over essential structure |
| `controller.select_next()` | Unchanged | Selection still uses all edges (including non-recent ones with K2 decay) |
| `landscape` | Needs `remove_state()`, `remove_edge()` | Structural decay |

**Critical**: `select_next()` is not changed. The controller can still *traverse* edges that were not inscribed — it just doesn't *learn* from them. Navigation continues; recording stops. This is the autopilot.

---

## 10. Structural Temperature Dynamics

T_s is not static — it evolves as the system operates:

```
Phase 1 (Bootstrap): T_s ≈ 0
  Everything is new, everything is inscribed. No forgetting.

Phase 2 (Learning): T_s rises
  Experience accumulates, some edges become contradictory.
  Inscription threshold starts filtering routine transitions.

Phase 3 (Maturation): T_s stabilizes  
  System has clear opinions about most edges.
  Only novelty is inscribed. Dream cycles prune dormant structure.

Phase 4 (Overload): T_s spikes
  New domain or paradigm shift. Many edges become contradictory.
  Aggressive pruning clears old structure to make room for new.
```

This mirrors biological development:
- **Childhood**: massive synaptic growth, then aggressive pruning
- **Adulthood**: stable, selective inscription
- **Crisis/Learning**: temporary increase in plasticity (= higher T_s)

---

## 11. Parameter Summary

| Parameter | Source | Value | New? |
|-----------|--------|-------|------|
| ρ | Existing (Historization) | 0.95 | No |
| μ | Existing (inertia_factor) | 5.0 | No |
| T_ref | = μ | 5.0 | No (derived) |
| τ_dormant | ⌈log(0.01)/log(ρ)⌉ | ~90 at ρ=0.95 | No (derived) |
| ε₀ | 1 − exp(−T_s/T_ref) | dynamic | No (derived) |
| θ_base | Calibrate empirically | TBD | **Yes** — the only new parameter |

**One new parameter**: θ_base (anchor score threshold baseline). Everything else is derived from existing E₀ parameters. θ_base will be calibrated from empirical anchor_score distributions in `explore_structural_entropy.py`.

---

## 12. Implementation Plan

| Commit | Scope | Module |
|--------|-------|--------|
| C114 | Inscription Threshold + Structural Temperature | `structural_entropy.py` |
| C115 | Anchor Analysis + Decay Candidates | `structural_entropy.py` |
| C116 | Landscape remove_state/remove_edge + DecayTrace | `landscape.py`, `structural_entropy.py` |
| C117 | Controller integration (conditional inscription) | `controller.py` |
| C118 | Dream Mode integration (decay during dream_cycle) | `dream_mode.py` |
| C119 | End-to-end exploration | `explore_structural_entropy.py` |

Each commit includes tests. Bottom-up: primitives first, integration last.

---

## 13. Open Questions

1. **Should DecayTraces themselves decay?** An anecdote that no anchor ever references again — does it eventually dissolve too? (Recursive forgetting.)

2. **Reconstruction fidelity**: When bootstrapper reconstructs from DecayTrace, how much structure is recovered? Is it the original, or a simplified version? (Memories are not accurate — they are reconstructed narratives.)

3. **Collective forgetting in multiverse**: When Universe A prunes a state that Universe B has an equivalence to — what happens to the cross-domain bridge? Does the bridge become a DecayTrace too?

4. **θ_base sensitivity**: Is there a critical θ_base below which the system retains too much, and above which it forgets too aggressively? Is there a phase transition?

---

## 14. Canon Alignment

| Canon Concept | Structural Entropy Mapping |
|---------------|---------------------------|
| §4 Irreversibility | Inscription is irreversible in the moment. Decay adds a second irreversibility: once forgotten, the exact original is lost — only the DecayTrace remains. Both directions of time's arrow. |
| §5 Reflexivity | Inscription threshold is reflexive: the system judges whether its own experience is worth recording. This is a higher level of self-knowledge than the Self-Graph — it is the system deciding what counts as experience. |
| §7 Structural Admissibility | Decay preserves admissibility: only structurally unimportant states are removed. The K11 threshold still governs which edges are traversable; decay governs which edges *exist*. |
| Axiom A₀ | "Structure arises from difference." The complement: structure *dissolves* when difference is exhausted. When trace_quality → 0 and trace_load decays below threshold, the structural difference that justified the state's existence is gone. |
