# SU(2) as Self-Graph Differentiator — Research Note

**Date:** 2026-04-04  
**Context:** C150 Parameter Sensitivity revealed that 6 of 8 Self-Graph components have no tunable parameters.  
**Status:** Empirically validated — SU(2) produces ranking reversals

---

## 1. The Structural Gap

C150 introduced `COMPONENT_PARAMS` — a mapping from Self-Graph components to tunable E0Config fields. The mapping is honest:

| Component         | Tunable Parameters                    | Count |
|-------------------|---------------------------------------|-------|
| historization     | rho, λ_s, λ_f, δ_max                 | 4     |
| transition_field  | alpha, recent_k, overload_threshold   | 3     |
| amplitude         | —                                     | 0     |
| born              | —                                     | 0     |
| realization       | —                                     | 0     |
| inertia           | —                                     | 0     |
| curvature         | —                                     | 0     |
| overlap           | —                                     | 0     |

When `suggest_perturbations()` encounters a harmful or confused component in {amplitude, born, realization, inertia, curvature, overlap}, it has nothing to suggest. The system is blind to 75% of its own structure.

But the problem runs deeper than missing knobs.

---

## 2. The Deeper Problem: Core Component Degeneracy

Empirically verified:

```
Component qualities (standard setup, 10 SUCCESS + 3 FAILURE):
  amplitude             quality=+0.5385  load=13.0
  born                  quality=+0.5385  load=13.0
  realization           quality=+0.5385  load=13.0
  historization         quality=+0.5385  load=13.0
  inertia               quality=+0.5385  load=13.0
  transition_field      quality=+0.5385  load=13.0
  curvature             quality=+0.0000  load=0.0
  overlap               quality=+0.0000  load=0.0
```

**All 6 core components are degenerate.** They share identical quality, identical load, identical inertia. The Self-Graph cannot distinguish between them.

**Root cause:** `self_historize(components, outcome)` applies the *same* outcome to *all* edges whose source and target are in the active set. Since all 6 core components are always active (they are in `CORE_COMPONENTS` unconditionally), all 6 core edges receive every outcome identically.

The differential sampling mechanism (C147) only works for modulation components (curvature, overlap) because their activation is conditional on landscape flags. Core components never experience differential activation.

**Diagnosis:** The Self-Graph can detect whether *the system as a whole* is healthy or harmful — but it cannot tell you *which core component* is responsible. If amplitude guidance is making bad decisions, the Self-Graph records this as: "everything is equally bad."

---

## 3. How SU(2) Currently Works

SU(2) is fully implemented but dormant by default (`use_su2=False`, `hybrid_mode=GREEDY`).

### 3.1 Three Transport Regimes

| Regime          | `use_su2` | Amplitude Space | Interference |
|-----------------|-----------|-----------------|-------------|
| U(1)            | `False`   | ℂ¹ (scalar)     | Commutative |
| SU(2) minimal   | `True`    | ℂ² (spinor)     | Non-commutative, axis=ẑ |
| SU(2) geometric | `"geometric"` | ℂ² (spinor) | Non-commutative, axis from landscape |

### 3.2 Decision Flow

```
transition_field (greedy):  target = argmin S_eff(x→y)
         ↓
amplitude (overlay):        I(a) = ‖Σ_p Ψ(p)‖²   ← spinor interference
         ↓
born (sampling/override):   P(a) = I(a) / Σ I     ← Born rule
         ↓
realization (execute):      outcome = execute_fn(source, target)
         ↓
historization (record):     H.update(edge, outcome)
         ↓
inertia (dampen):           I(e) = 1 − α·(m/(m+μ))·(1−|q|)
```

SU(2) affects decisions **only through amplitude and born** — it changes the intensity computation, which changes the Born probability, which changes which action is selected. But this causal chain is invisible to the Self-Graph because:

1. amplitude is always marked as active, whether or not the overlay was used
2. born is always marked as active, whether or not Born sampling was used
3. All core components see the same outcome regardless

### 3.3 Existing SU(2) Parameters

| Parameter            | Location        | In E0Config? | In run_trial? |
|---------------------|------------------|--------------|---------------|
| `use_su2`           | E0Controller     | No           | No            |
| `axis_fn`           | E0Controller     | No (callable)| No            |
| `hybrid_mode`       | E0Controller     | No (enum)    | No            |
| `hybrid_horizon`    | E0Controller     | Yes          | No            |
| `confidence_threshold` | E0Controller  | Yes          | Yes           |
| `warmup`            | ExplorationPolicy| Yes          | No            |
| `overlay_horizon`   | `run()`          | No           | No (=0)       |

Key finding: `run_trial()` currently runs in pure GREEDY mode with `overlay_horizon=0`. SU(2) is never exercised in sensitivity analysis.

### 3.4 The Geometric Connection

The geometric SU(2) mode (`use_su2="geometric"`) derives its rotation axis **entirely from the landscape topology**:

```
A⃗(x,y) = [A₁(vorticity gradient), A₂(face holonomy), A₃(ω)]
U(x,y) = exp(−i/2 · A⃗ · σ⃗)
```

This is parameter-free — the landscape's own geometry determines the spinor transport. This is significant: SU(2) geometric does not add parameters, it extracts latent structure.

---

## 4. Three Proposals

### 4.1 Proposal A: Conditional Component Activation ("Honest Self-Graph")

**Idea:** Make amplitude and born activation conditional on whether they actually participated in the decision.

```python
def active_components(
    *,
    curvature_active: bool = False,
    overlap_active: bool = False,
    inertia_active: bool = False,
    amplitude_active: bool = True,   # NEW: False when overlay_horizon=0
    born_active: bool = True,        # NEW: False when mode=GREEDY
) -> List[str]:
```

| Condition | amplitude active? | born active? |
|-----------|:-:|:-:|
| GREEDY, no overlay | ✗ | ✗ |
| AMPLITUDE_ON_DISAGREE, overlay computed | ✓ | ✗ |
| BORN_SAMPLING, overlay computed | ✓ | ✓ |
| BORN_SAMPLING, no overlay | ✗ | ✗ |

**Effect:** Core components become differentially sampled. When amplitude is harmful but born is not, the Self-Graph can see it.

**Pros:**
- No new parameters needed
- Self-Graph becomes genuinely informative for core components
- Direct: the activation reflects ground truth about which components participated

**Cons:**
- In GREEDY mode (the dominant mode), amplitude and born would never accumulate data → always `insufficient_data`
- Only useful when hybrid modes are used
- Changes Self-Graph semantics — existing tests may need updating

**Assessment:** Necessary but insufficient. Breaks degeneracy only when hybrid mode is active.

### 4.2 Proposal B: SU(2) Parameters in Sensitivity Analysis

**Idea:** Extend `run_trial()` to enable hybrid mode with SU(2), and add relevant parameters to `COMPONENT_PARAMS`.

Step 1 — Extend `run_trial()`:
```python
ctrl = E0Controller(
    L, execute_fn,
    alpha=config.alpha,
    ...
    use_su2=config.use_su2,                    # NEW
    hybrid_mode=config.hybrid_mode,            # NEW
    hybrid_horizon=config.hybrid_horizon,      # Already in E0Config
    confidence_threshold=config.confidence_threshold,
)
trace = ctrl.run(start, max_cycles=max_cycles, goal=goal,
                 overlay_horizon=config.hybrid_horizon)  # NEW: actually compute overlay
```

Step 2 — Add to E0Config:
```python
@dataclass(frozen=True)
class E0Config:
    ...
    # Transport / Hybrid (NEW)
    use_su2: object = False           # False / True / "geometric"
    hybrid_mode: str = "greedy"       # "greedy" / "born" / "amplitude_on_disagree"
```

Step 3 — Extend COMPONENT_PARAMS:
```python
COMPONENT_PARAMS = {
    "amplitude":        ["confidence_threshold", "hybrid_horizon"],
    "born":             ["warmup"],
    "transition_field": ["alpha", "recent_k", "overload_threshold"],
    "historization":    ["rho", "lambda_s", "lambda_f", "delta_max"],
    ...
}
```

**Pros:**
- Fills the sensitivity gap for amplitude and born
- Uses existing infrastructure (confidence_threshold, warmup already in E0Config)
- Enables empirical comparison: GREEDY vs BORN_SAMPLING via sensitivity_analysis()

**Cons:**
- SU(2) mode (use_su2) and hybrid_mode are categorical, not continuous — perturbation factor ±20% doesn't apply
- `suggest_perturbations()` needs discrete variant logic for categorical params
- hybrid_mode changes the entire decision structure, not just one knob

**Assessment:** Practical and achievable. But hybrid_mode is a regime change, not a parameter perturbation — it changes what "amplitude" and "born" even mean.

### 4.3 Proposal C: SU(2) as Perspective Rotation ("Beobachtungswinkel")

**Idea:** Instead of perturbing scalar parameters, use SU(2) to view the same landscape from different "angles." The sensitivity analysis becomes: does the system's health depend on the observation perspective?

Mechanism: The `axis_fn` in SU(2) minimal mode determines the rotation axis per edge. Different axis functions produce different interference patterns, which produce different Born probabilities, which produce different trajectories and outcomes.

```python
def axis_fn_x(L, x, y): return [1, 0, 0]  # σ_x axis
def axis_fn_y(L, x, y): return [0, 1, 0]  # σ_y axis
def axis_fn_z(L, x, y): return [0, 0, 1]  # σ_z axis (default)
def axis_fn_mixed(L, x, y):
    w = omega(L, x, y)
    return [math.cos(w), math.sin(w), 0]   # landscape-dependent axis
```

Each axis function represents a "perspective." Running sensitivity_analysis with different axis functions answers: "Is the system's health robust under perspective changes?"

If health is robust → the structure is genuine.
If health is fragile → the structure is an artifact of the observation angle.

**Pros:**
- Theoretically deepest: uses SU(2)'s non-Abelian structure meaningfully
- Doesn't require new scalar parameters — uses the geometric freedom inherent in SU(2)
- Connects to the physics: holonomy measures curvature, and curvature is observer-independent if real

**Cons:**
- axis_fn is a function, not a scalar — doesn't fit E0Config frozen dataclass
- Adds complexity to the sensitivity API
- Not clear what "perspective robustness" means operationally for parameter tuning

**Assessment:** Research-worthy but not immediately actionable. Could become a diagnostic tool rather than a tuning mechanism.

### 4.4 Meta-Cognitive Interpretation of Proposal C

The deeper insight: Proposal C is not parameter tuning — it is **meta-cognition**.

Greedy navigation is inherently perspective-bound. The controller stands at state S and asks: *"What is best from here?"* — `argmin S_eff(S→y)`. This is always relative to the current state and current frame.

SU(2) rotation changes something qualitatively different: the spinor interference sums over *paths*, not local edges. When the axis rotates, the same landscape produces different constructive/destructive interference patterns:

```
U(1):               Path A→B→C has intensity 0.8
SU(2) axis ẑ:       Same path has intensity 0.6  (spinor phase shift)
SU(2) axis x̂:       Same path has intensity 0.3  ← different path becomes dominant
```

If the system's health is **fragile** under perspective rotation — if a rotation from ẑ to x̂ reverses the action ranking — then the system's current assessment depends on the observation angle, not on the structure itself. This is a diagnostic that no scalar parameter perturbation can provide.

**The crucial consequence:** If health is perspective-dependent, then the question is not "which parameter is wrong?" but "is my frame wrong?" — including whether the *starting point* itself needs to change. This is meta-cognition in the precise sense: the system steps outside its current state to evaluate whether the state itself is the problem.

Operationally, this maps to:
- **Perspective-robust health** → the structure is genuine, parameters can be tuned within the current frame
- **Perspective-fragile health** → the frame is wrong. Possible responses:
  - Change the starting point (re-seed the landscape)
  - Change the goal (the current goal may be unreachable from this perspective)
  - Restructure the topology (reflexive edge proposals informed by perspective fragility)

The non-Abelian property is essential here: `U(ẑ→x̂) ≠ U(x̂→ẑ)` means the perspective change is irreversible. Once you've seen the system from a different angle and discovered fragility, you cannot "unsee" it. This is honest meta-cognition — it produces irreversible knowledge.

**Connection to E0 canon:** This is "Lösung aus dem aktuellen Zustand" formalized. The 4-layer model (Historization → Inscription → Inertia → Mass) describes how structure accumulates. SU(2) perspective rotation is a mechanism for *questioning* accumulated structure — not by forgetting (structural entropy) or by dreaming (cross-domain equivalence), but by looking at the same structure from a different angle and checking whether it holds.

---

## 5. Synthesis: Recommended Path

### Phase 1 — Honest Activation (Proposal A, partial)

Break core component degeneracy by making amplitude/born activation conditional. This is a precondition for any SU(2) integration to matter.

**But:** Only apply conditional activation when hybrid mode is active. In GREEDY mode, keep current behavior (all core active, uniform quality). This preserves backward compatibility and avoids `insufficient_data` for amplitude/born in the dominant use case.

Decision point: Is the honest Self-Graph (with conditional activation) worth pursuing even without SU(2)? If yes → implement first, independently.

### Phase 2 — Hybrid Mode in Sensitivity (Proposal B)

Add `hybrid_mode` and `hybrid_horizon` forwarding to `run_trial()`. This enables:
```python
configs = [
    DEFAULTS,                                          # GREEDY baseline
    replace(DEFAULTS, hybrid_mode="born", hybrid_horizon=3),  # Born sampling
    replace(DEFAULTS, confidence_threshold=0.3, hybrid_horizon=3),  # Amplitude override
]
report = sensitivity_analysis(L, exec_fn, "S", None, configs)
```

The system can then empirically compare: does enabling amplitude guidance help or hurt?

### Phase 3 — SU(2) Regime Comparison (Proposals B+C)

Once hybrid mode works in sensitivity analysis:
```python
configs = [
    replace(DEFAULTS, hybrid_mode="born", hybrid_horizon=3),                    # U(1) Born
    replace(DEFAULTS, hybrid_mode="born", hybrid_horizon=3, use_su2=True),      # SU(2) Born
    replace(DEFAULTS, hybrid_mode="born", hybrid_horizon=3, use_su2="geometric"), # Geometric Born
]
```

This answers: does SU(2) produce better Born sampling decisions than U(1)?

### Open Questions (Updated After Pretest)

1. ~~**Does SU(2) geometric actually produce different intensities than U(1)?**~~
   **ANSWERED: Yes.** 7.0% ranking reversal rate on random topologies (slightly
   higher than minimal SU(2) at 6.3%).

2. ~~**Is the non-Abelian property useful?**~~
   **ANSWERED: Yes, operationally.** Multi-path interference with half-frequency
   phase produces different constructive/destructive patterns. 43% reversal rate
   on near-degenerate landscapes confirms non-trivial path-order sensitivity.

3. **Can axis_fn be meaningfully parameterized?** Still open. The pretest used
   fixed axes (ẑ, x̂, ŷ, mixed) — all produced identical results on the simple
   topologies. However, on 5+ node graphs axis choice may matter. Needs testing.

4. **What about the 720° periodicity?** Still open. Holonomy measurements show
   98.8° on the extreme triangle (Pretest 4) — not yet reaching the 360°/720°
   regime where sign flips occur. Longer cycles on larger graphs could reach it.

5. **NEW: What is the minimum graph complexity for SU(2) relevance?**
   Pretests 1–4 (3 nodes) showed zero effect. Pretest 5 (5–6 nodes) showed
   6–7% effect. The transition likely occurs at 4–5 nodes with sufficient
   edge density to create multi-path interference. This sets a practical
   lower bound for when SU(2) perspective analysis is useful.

---

## 6. Empirical Pretest — Results

### 6.1 Pretests 1–4: Simple Topologies (False Negative)

Initial tests on small triangles (3 nodes) and hand-crafted topologies showed
**identical rankings** across all three regimes (U(1), SU(2), geometric).
This initially suggested SU(2) was inert.

Root cause analysis (Pretest 3) revealed: on small symmetric graphs, maximum
omega per edge is ~1.4°. SU(2) rotation is omega/2 ≈ 0.7° — negligible.
With extreme directional asymmetry (delta=10/R=0.1 vs delta=0.01/R=10),
omega reaches 87°, but with only 2 actions and 1 path each, unitarity
guarantees `‖U·|ref⟩‖² = 1` — no ranking change possible.

The simple topologies were not representative because they lacked
**multi-path interference**: the mechanism by which SU(2) changes outcomes.

### 6.2 Pretest 5: Large-Scale Sweep (Breakthrough)

20,000 random asymmetric topologies (5–6 nodes, random edge density ~50–60%,
log-uniform delta ∈ [0.01, 100], log-uniform resistance ∈ [0.01, 100]).

| Phase | Description | Topologies | Reversals | Rate |
|-------|-------------|-----------|-----------|------|
| 1 | Random 5-node, SU(2) vs U(1) | 4,114 | 260 | **6.3%** |
| 2 | Random 5-node, Geometric vs U(1) | 4,077 | 285 | **7.0%** |
| 3 | Near-degenerate (I₂/I₁ > 0.8), horizon=4 | 579 | 247 | **42.7%** |

**Key findings:**

1. **SU(2) is NOT inert.** On general topologies, it changes the action ranking
   in ~6–7% of cases. This is a genuine operational effect, not noise.

2. **SU(2) is selectively active.** On near-degenerate landscapes — where U(1)
   intensities for the top two actions are within 20% of each other — SU(2)
   reverses the ranking in **43% of cases**. This is the meta-cognitive profile:
   it stays silent when the answer is clear, and speaks up when it matters.

3. **Geometric SU(2) is slightly more active than minimal SU(2)** (7.0% vs 6.3%),
   consistent with the three-component axis `A⃗ = [A₁, A₂, A₃]` providing
   richer rotational structure than the fixed ẑ-axis.

4. **All three modes can disagree with each other.** Phase 3 examples show
   cases where U(1), SU(2), and geometric each produce distinct rankings
   (e.g., Trial 274: U(1)=[A,B,D], SU(2)=[D,B,A], Geo=[B,A,D]).

### 6.3 Mathematical Explanation

With fixed axis ẑ, SU(2) is equivalent to U(1) with **half the phase**:

- U(1): `Ψ(p) = exp(-S) · exp(iθ)` → interference ∝ `cos(θ₁ - θ₂)`
- SU(2): `Ψ(p) = exp(-S) · U(θ/2)·|↑⟩` → interference ∝ `cos((θ₁ - θ₂)/2)`

For **single-path actions**, `‖U·|ref⟩‖² = 1` (unitarity) → no ranking change.
For **multi-path actions**, the half-frequency cosine `cos(Δθ/2)` vs `cos(Δθ)`
changes constructive/destructive interference patterns across all path pairs.

Critical reversal scenario:
```
Action A: paths with Δθ ≈ 2π → U(1): cos(2π)=+1 (constructive)
                                → SU(2): cos(π)=−1 (DESTRUCTIVE)
Action B: paths with Δθ ≈ π  → U(1): cos(π)=−1 (destructive)
                                → SU(2): cos(π/2)=0 (neutral)
→ U(1): A wins, SU(2): B wins → RANKING REVERSAL
```

This requires:
- At least 2 actions, each with multiple contributing paths (horizon ≥ 3)
- Sufficient omega magnitude to produce phase differences near π or 2π
- Asymmetric topology (symmetric graphs give all actions similar path structure)

All three conditions are naturally met on 5+ node graphs with random asymmetric
edge weights — explaining the 6–7% baseline reversal rate.

### 6.4 Implications for Proposal C

The pretest confirms that SU(2) perspective rotation is **operationally real**:

- It changes decisions (not just intensities) in a meaningful fraction of cases
- It is most active precisely where the decision is most uncertain
- The geometric variant extracts this perspective purely from topology

This validates the meta-cognitive interpretation from §4.4: SU(2) provides a
second opinion that is structurally different from U(1), not just a rescaling.
When the two perspectives disagree, the system has evidence that its assessment
is perspective-dependent — the very signal needed to trigger frame questioning.

---

## 7. Relationship to E0 Principles

The Subagent's own reasoning process (documented in the prompt) mirrors E0's navigation:

- **Greedy first:** start with the obvious mapping (exploration, selection)
- **Sackgasse:** real API doesn't match → escalation
- **Reflexion:** realize the graph needs more branching → restructure
- **Zweifel:** recognize that uniform SUCCESS produces no signal → introduce failure
- **Honest mapping:** accept that most components are emergent → don't pretend otherwise

### Three Layers of Self-Knowledge in E0

With this research, three distinct mechanisms for questioning accumulated structure emerge:

| Mechanism | What it questions | How |
|-----------|------------------|-----|
| **Structural Entropy** (C114–C121) | "Is this edge still relevant?" | Forgetting: inscription threshold + decay |
| **Dream Mode** (C109–C139) | "Does this pattern exist elsewhere?" | Cross-domain fingerprint matching |
| **SU(2) Perspective** (this proposal) | "Is this structure real or perspectival?" | Same landscape, different interference geometry |

Structural Entropy removes. Dream Mode discovers. SU(2) Perspective *validates*.

All three are forms of meta-cognition, but they operate at different levels:
- Entropy is **local** (single edge: keep or forget?)
- Dream is **lateral** (cross-domain: is there an analogy?)
- Perspective is **vertical** (same domain: does the assessment hold from above?)

SU(2) perspective rotation is the only mechanism that can distinguish between "the system is healthy" and "the system *appears* healthy from the current observation angle." This is the difference between first-order knowledge ("I know X") and second-order knowledge ("I know that my knowledge of X is robust").

Whether this second-order diagnostic produces actionable improvements is the empirical question that Phase 3 must answer.
