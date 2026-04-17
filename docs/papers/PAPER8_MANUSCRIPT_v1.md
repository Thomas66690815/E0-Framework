# E₀-VIII: Self-Tuning — E₀ Dynamics Applied to Parameter Space

**Thomas Wehner**

---

## Abstract

All preceding papers assume fixed controller parameters (α, s_max, c_min,
confidence_threshold, hybrid_horizon). This paper removes that assumption.
We show that E₀'s own dynamics — Historization, field measurement, and
admissibility checking — can be applied reflexively to the controller's
parameter space, yielding automated parameter tuning without introducing
new primitives. The construction has two layers: (1) a meta-landscape
layer (B4.1–B4.4) that extracts normalised field metrics from controller
runs, derives reflection thresholds, estimates parameter sensitivities,
and executes bounded tuning cycles with oscillation protection; and
(2) a Self-Graph attribution layer (C150/C155) that diagnoses component
health, generates perturbation candidates, and runs a closed-loop
optimisation: diagnose → perturb → evaluate → adopt. Both layers share
the same admissibility principle: a parameter change is accepted if and
only if the quality score Q does not decrease (Δ_meta ≥ 0), mirroring
E₀'s object-level transition rule. We validate 58 tests across the two
modules. Key results: (1) field-derived thresholds eliminate ad-hoc
reflection constants; (2) the quality score Q = 0.4·goal + 0.25·τ_eff +
0.15·τ_progress − 0.1·τ_loop − 0.1·τ_esc provides a stable optimisation
target; (3) oscillation protection via meta-historization prevents tuning
thrashing; (4) the mass trap inversion — where increasing lookahead
horizon worsens performance under path-count imbalance — is detected and
corrected automatically. All claims are classified as derived, empirical,
or heuristic.

---

## 1. Introduction

### 1.1 The Problem: Controller Parameters Are Themselves Choices

E₀'s controller navigates a landscape by choosing edges with minimal
effective resistance S_eff. This navigation depends on parameters:

| Parameter | Symbol | Role |
|-----------|--------|------|
| Revisit penalty | α | Weight on historization contribution to S_eff |
| Tension ceiling | s_max | Maximum allowable tension before escalation |
| Coherence floor | c_min | Minimum coherence for edge acceptance |
| Confidence threshold | conf | Gate for hybrid amplitude override |
| Hybrid horizon | h | Lookahead depth for amplitude computation |

These parameters are currently set by the developer — a manual process
that contradicts E₀'s claim of domain invariance. If the framework truly
captures general dynamics, it should be able to evaluate its own parameter
choices using the same mechanisms it applies to domain-level navigation.

### 1.2 Self-Application as Architecture

The insight is structural: E₀ already has the machinery for evaluating
choices under uncertainty (Historization), measuring field properties
(transition field), and accepting or rejecting transitions (admissibility).
Applying these to the parameter space θ = (α, s_max, c_min, conf, h)
requires no new primitives — only a change of what counts as a "state"
and what counts as a "transition."

| Object Level | Meta Level |
|-------------|------------|
| State x ∈ X | Configuration θ ∈ Θ |
| Edge (x, y) | Parameter adjustment θ → θ' |
| S_eff(x, y) | Quality delta ΔQ(θ, θ') |
| Outcome SUCCESS/FAILURE | Q(θ') ≥ Q(θ) / Q(θ') < Q(θ) |
| Historization H(x,y) | Parameter history H_meta(θ_i) |

This paper formalises both layers and validates them empirically.

---

## 2. Field Summary: Normalised Run Metrics

### 2.1 The τ Dimensions

After a controller run producing a `RunTrace`, we extract a
`RunFieldSummary` — a normalised view of the run's dynamics. The five
τ dimensions capture orthogonal aspects of controller behaviour:

**Definition 2.1** (τ dimensions). *Given a landscape with |X| states,
|E| edges, and a run of S steps visiting U unique states with v_mean
average field strength, v_max maximum field strength, R repeated cycles,
and K escalations:*

$$\tau_{\text{eff}} = \frac{v_{\text{mean}}}{v_{\text{max}}}$$

$$\tau_{\text{loop}} = \frac{R}{|X|}$$

$$\tau_{\text{esc}} = \frac{K}{|E|}$$

$$\tau_{\text{progress}} = \frac{U}{|X|}$$

$$\tau_{\text{efficiency}} = \frac{U}{S}$$

**Claim 2.1** (Normalisation, *derived*). τ_eff, τ_progress, τ_efficiency
∈ [0, 1] by construction. τ_loop and τ_esc are unbounded above but
clamped to [0, 1] in the quality score.

**Claim 2.2** (Orthogonality, *empirical*). The five τ dimensions are
weakly correlated across the 10 canonical domains (D1–D10). A run can
have high τ_eff (strong field) with high τ_loop (repeated cycles) or
low τ_loop. This independence justifies treating them as separate
diagnostic signals.

### 2.2 Extraction from RunTrace

`field_summary_from_run(landscape, trace)` computes:
- v_mean, v_max from the landscape's transition field values
- num_states, num_edges from the landscape graph
- steps, escalations, repeated_cycles from the trace
- unique_states_visited from the set of visited states
- path_count_imbalance_max from edge visit frequency ratios

The path_count_imbalance_max metric is critical for mass trap detection
(§5.2): it measures the maximum ratio of visit counts between edges
sharing a source state. High imbalance indicates the controller is
systematically biased toward one path — a signature of the mass trap.

---

## 3. Derived Thresholds

### 3.1 Replacing Ad-Hoc Constants

Earlier reflection mechanisms used fixed thresholds (e.g., "reflect if
loops > 3"). This creates a meta-parameter problem: who tunes the tuning
thresholds?

We resolve this by deriving thresholds from the field summary itself:

**Definition 3.1** (Derived thresholds). *Given τ_eff from a
RunFieldSummary:*

$$\theta_{\text{quality-efficiency}} = \frac{\tau_{\text{eff}}}{2}$$

$$\theta_{\text{quality-loop}} = \frac{1 - \tau_{\text{eff}}}{|X|}$$

$$\theta_{\text{quality-escalation}} = \frac{1 - \tau_{\text{eff}}}{2}$$

$$\theta_{\text{quality-progress}} = \frac{\tau_{\text{eff}}}{2}$$

$$\theta_{\text{opportunity-efficiency}} = \frac{1 + \tau_{\text{eff}}}{2}$$

$$\theta_{\text{opportunity-progress}} = \frac{1 + \tau_{\text{eff}}}{2}$$

**Claim 3.1** (Field-Scaling Eliminates Meta-Parameters, *derived*).
All six thresholds are functions of τ_eff alone. No additional constants
are required. When the field is weak (τ_eff → 0), quality thresholds
drop to zero (everything triggers reflection) and opportunity thresholds
drop to 0.5. When the field is strong (τ_eff → 1), quality thresholds
rise to 0.5 (only significant deviations trigger) and opportunity
thresholds approach 1.0 (high bar for opportunities).

**Claim 3.2** (Monotonic Scaling, *derived*). Quality thresholds are
monotonically non-decreasing in τ_eff (except quality_loop and
quality_escalation, which decrease). This ensures: weak fields →
aggressive tuning; strong fields → conservative tuning.

---

## 4. Quality Score

### 4.1 Definition

The quality score Q aggregates the τ dimensions into a single scalar
optimisation target:

**Definition 4.1** (Quality score). *Given a RunFieldSummary and a
boolean goal_reached:*

$$Q = 0.4 \cdot \mathbf{1}[\text{goal}] + 0.25 \cdot \tau_{\text{efficiency}} + 0.15 \cdot \tau_{\text{progress}} - 0.1 \cdot \min(\tau_{\text{loop}}, 1) - 0.1 \cdot \min(\tau_{\text{esc}}, 1)$$

$$Q = \text{clamp}(Q, 0, 1)$$

**Claim 4.1** (Goal Dominance, *heuristic*). The goal_reached term (0.4)
is the single largest component. A run that reaches the goal but loops
extensively (τ_loop = 1) and escalates constantly (τ_esc = 1) still
scores Q ≥ 0.2. A run that fails to reach the goal scores Q ≤ 0.6
regardless of efficiency.

*Justification:* The weight hierarchy (goal=0.4, efficiency=0.25,
progress=0.15, penalties=0.1 each) encodes a clear priority: reaching
the goal matters most, then how efficiently, then how broadly, with
penalties for pathological patterns. The specific weights are heuristic
choices validated empirically via stability across domains.

**Claim 4.2** (Discriminative Power, *empirical*). Across the 10
canonical domains, Q discriminates between configurations that reach the
goal and those that do not, with a gap ≥ 0.2. Among goal-reaching
configurations, Q further discriminates by path quality (efficiency and
exploration breadth).

---

## 5. Parameter Sensitivity

### 5.1 Heuristic Attribution

For each parameter θ_i, we estimate a sensitivity value ∂Q/∂θ_i using
structural heuristics that map field symptoms to parameter adjustments:

**Definition 5.1** (Sensitivity heuristics).

| Parameter | Sensitivity | Direction Rule |
|-----------|-------------|----------------|
| α (revisit penalty) | 2 · τ_loop | Increase if τ_loop > 0 |
| s_max (tension ceiling) | τ_esc | Increase if τ_esc > 0.1 |
| c_min (coherence floor) | τ_esc · (1 − τ_eff) | Decrease if τ_esc > 0.1 |
| confidence_threshold | imbalance/5 or (1−τ_eff)·0.5 | Context-dependent |
| hybrid_horizon | τ_loop · imbalance/3 or 1−τ_eff | Context-dependent (§5.2) |

**Claim 5.1** (Directional Correctness, *empirical*). On 8 of 10
canonical domains, the heuristic sensitivity direction matches the
direction that improves Q under perturbation. The two exceptions involve
the mass trap inversion (§5.2) where naive sensitivity would suggest
the wrong direction, but the heuristic includes a specific correction.

### 5.2 Mass Trap Inversion

The most subtle sensitivity case concerns `hybrid_horizon`. Naively,
a weak field (low τ_eff) suggests increasing lookahead to gather more
information. However, when path_count_imbalance is high (the controller
visits one edge far more than alternatives), increasing the horizon
means the amplitude computation enumerates more paths through the
already-biased edge — amplifying the trap rather than escaping it.

**Claim 5.2** (Mass Trap Inversion, *empirical*). When τ_loop > 0 and
path_count_imbalance > threshold, the correct direction for
hybrid_horizon is *decrease*, not increase. The sensitivity function
detects this condition via the joint criterion:

$$\text{if } \tau_{\text{loop}} > 0 \text{ and imbalance} > 0: \text{ direction} = \text{decrease}$$

This matches the object-level phenomenon: mass traps arise when heavy
paths attract more traffic, creating a positive feedback loop. Cutting
the horizon limits the depth over which this feedback operates.

**Claim 5.3** (Finite-Difference Extension, *derived*). The heuristic
can be replaced by true finite-difference gradients:

$$\frac{\partial Q}{\partial \theta_i} \approx \frac{Q(\theta + \epsilon_i) - Q(\theta - \epsilon_i)}{2\epsilon}$$

This requires 2k additional controller runs for k parameters but yields
ground-truth sensitivity. The infrastructure for this exists (B4.4) but
is not yet the default path.

---

## 6. Tuning Cycle

### 6.1 Single Iteration

A tuning cycle is a complete feedback loop:

```
1. Reset landscape historization (clean slate)
2. Run controller from start → RunTrace
3. Extract RunFieldSummary, compute Q_before
4. Compute parameter sensitivities
5. Generate TuningProposal for each sensitive parameter:
   - Bounded: new_value ∈ [lower, upper] (TUNABLE_PARAMS)
   - Step-limited: |Δθ_i| ≤ step_fraction × (upper − lower)
   - Oscillation-guarded: check H_meta (§6.2)
6. Apply proposals to controller
7. Reset landscape, re-run controller → RunTrace'
8. Compute Q_after from RunTrace'
9. Meta-admissibility:
   - If Q_after ≥ Q_before: accept (keep new parameters)
   - If Q_after < Q_before: revert to old parameters
```

**Claim 6.1** (Bounded Adjustment, *derived*). Each parameter change is
bounded by step_fraction (default 0.15) of the parameter's range. This
prevents catastrophic parameter jumps. Combined with the parameter bounds
from TUNABLE_PARAMS, the controller always operates in a valid region.

**Claim 6.2** (Meta-Admissibility, *derived*). The accept/revert rule
mirrors E₀'s object-level admissibility: a transition is accepted iff
it does not increase effective resistance (at the object level) or
decrease quality (at the meta level). Both are instances of the same
principle: accept only non-degrading moves.

### 6.2 Oscillation Protection (H_meta)

Without protection, the tuning cycle could oscillate: increase α, find
Q drops, revert, then increase α again on the next cycle.

**Definition 6.1** (Meta-historization). For each parameter θ_i, maintain
a history window of the last N values (default N = 5). A proposal to
adjust θ_i in direction d is blocked if the history shows the parameter
was recently adjusted in the opposite direction:

$$\text{would\_oscillate}(h, d) = \exists \text{ recent reversal in } h \text{ for direction } d$$

**Claim 6.3** (Oscillation Convergence, *empirical*). With oscillation
protection enabled, multi-cycle tuning converges within 5 iterations on
all 10 canonical domains (either reaching a fixed point or triggering
the 2-consecutive-revert stop condition).

### 6.3 Multi-Cycle Tuning

The `tune()` function iterates tuning cycles until convergence:

```
For i in 1..max_iterations:
    result = tuning_cycle(controller, start, goal, ...)
    If no proposals generated: STOP (converged)
    If 2 consecutive reverts: STOP (local optimum)
    Track total Δ_quality across cycles
Return MultiCycleTuningResult(cycles, total_delta, final_params, converged)
```

**Claim 6.4** (Termination, *derived*). Multi-cycle tuning always
terminates: either (a) no proposals are generated (all sensitivities
below threshold), (b) 2 consecutive reverts occur (no direction improves
Q), or (c) the iteration limit is reached.

---

## 7. Component-Level Attribution (C150)

### 7.1 Self-Graph Diagnosis

The Self-Graph (Paper 7) provides per-component health signals. The
parameter_sensitivity module maps these signals to parameter candidates:

**Definition 7.1** (Component-parameter mapping).

```
COMPONENT_PARAMS = {
    "amplitude":        [hybrid_mode, confidence_threshold, hybrid_horizon],
    "born":             [hybrid_mode, use_su2, hybrid_horizon],
    "historization":    [rho, lambda_s, lambda_f, delta_max],
    "transition_field": [alpha, recent_k, overload_threshold],
    ...
}
```

When the Self-Graph diagnoses a component as "harmful" or "confused,"
the corresponding parameters become candidates for perturbation.

### 7.2 Trial-Based Evaluation

`run_trial(landscape, execute_fn, start, goal, config)` executes the
controller with a specific E0Config and collects:
- The RunTrace (path, goal reached, cycles)
- The Self-Graph diagnosis (component health, harmful/confused flags)
- Per-component quality scores

`sensitivity_analysis(landscape, execute_fn, start, goal, configs)`
runs multiple trials and computes parameter_impact: which parameters
correlate with quality differences across configurations.

### 7.3 Perturbation Generation

`suggest_perturbations(diagnosis, base_config, factor)` generates config
variants by perturbing parameters associated with unhealthy components:

```
For each harmful/confused component:
    For each param in COMPONENT_PARAMS[component]:
        Generate config+ (param × (1 + factor))
        Generate config- (param × (1 - factor))
```

Default perturbation factor: 0.2 (±20% of current value).

**Claim 7.1** (Targeted Search, *derived*). By restricting perturbation
to parameters linked to unhealthy components, the search space is reduced
from 2^k (all parameters) to 2·m where m is the number of parameters
associated with diagnosed issues. This typically yields m ≤ 3 on
single-component failures.

---

## 8. Closed-Loop Auto-Tuning (C155)

### 8.1 Algorithm

`auto_tune()` closes the loop between diagnosis and adoption:

```
For round in 1..max_rounds:
    1. Run baseline trial with current config
    2. Diagnose Self-Graph
    3. If healthy: STOP (no issues to fix)
    4. Generate perturbation variants from diagnosis
    5. Run sensitivity_analysis(baseline + variants)
    6. Select best config (highest quality)
    7. If improvement ≥ min_improvement (default 0.01):
       Adopt best config → continue
    8. Else: STOP (no further progress)
Return AutoTuneResult(rounds, best_config, improvement)
```

**Claim 8.1** (Termination, *derived*). auto_tune() terminates:
healthy diagnosis (step 3), insufficient improvement (step 8), or
round limit (loop bound). No infinite loops possible.

**Claim 8.2** (Monotonic Quality, *empirical*). Each adopted
configuration has strictly higher quality than its predecessor
(by at least min_improvement). Quality never decreases during
auto_tune() because adoption requires measured improvement.

### 8.2 Apply Without Reconstruction

`apply_config(controller, config)` updates a running controller's
parameters in-place, without reconstructing the controller object.
This preserves:
- The current landscape state (historization intact)
- The navigation history (RunTrace continuity)
- All cross-run memory (TuningMemory)

**Claim 8.3** (State Preservation, *derived*). apply_config() modifies
only the parameters listed in config, leaving landscape state, trace
history, and memory structures untouched. This enables tuning during
a session without losing accumulated knowledge.

---

## 9. Cross-Run Memory

### 9.1 TuningSnapshot

Each tuning cycle produces a TuningSnapshot:

```python
@dataclass
class TuningSnapshot:
    timestamp: float
    quality: float
    goal_reached: bool
    tau_eff: float
    tau_loop: float
    tau_esc: float
    tau_progress: float
    tau_efficiency: float
    params: Dict[str, float]
    applied_changes: List[str]
    accepted: bool
```

### 9.2 TuningMemory Analysis

TuningMemory maintains a bounded list of snapshots (default max: 100)
and provides temporal analysis:

**Quality Trend.** Least-squares slope over the last n entries:

$$\text{slope} = \frac{\sum_i (i - \bar{i})(Q_i - \bar{Q})}{\sum_i (i - \bar{i})^2}$$

Positive slope → parameters improving. Negative → degrading. Near-zero
→ converged or stuck.

**Recurring Issues.** Counts how often each τ dimension exceeds its
issue threshold over the last n entries:

| Issue | Threshold |
|-------|-----------|
| τ_loop | > 0.25 |
| τ_esc | > 0.20 |
| τ_efficiency | < 0.40 |
| τ_progress | < 0.50 |

If a dimension triggers in > 50% of recent entries, it is a recurring
issue requiring structural intervention beyond parameter tuning.

**Parameter Drift.** Net change of each parameter over the memory window.
Large drift indicates the tuning is consistently pushing a parameter in
one direction — possibly toward an optimal value, or possibly toward a
boundary.

**Cross-Run Suggestions.** Aggregates patterns into human-readable
recommendations: "Chronic loop issue — consider landscape restructuring",
"α drifting toward upper bound — investigate whether penalty is
fundamentally insufficient."

### 9.3 Persistence

TuningMemory serialises to JSON via `to_dict()`/`from_dict()` and
persists under `memos/tuning/{session_id}.json`. The
`save_tuning_memory()` / `load_tuning_memory()` functions handle file I/O,
enabling cross-session parameter evolution.

**Claim 9.1** (Serialisation Round-Trip, *derived*). TuningMemory
survives JSON serialisation with zero information loss: all TuningSnapshot
fields are scalar or list types with exact JSON representations.

---

## 10. Integration: Two Layers, One Principle

### 10.1 Layer Architecture

The two modules operate at different granularities but share the same
principle:

| Aspect | Meta-Landscape (self_tuning) | Self-Graph Attribution (parameter_sensitivity) |
|--------|------------------------------|------------------------------------------------|
| Granularity | Individual parameter θ_i | Component → parameter set |
| Sensitivity | Heuristic (τ-based) | Empirical (perturbation trials) |
| Diagnosis | Field summary thresholds | Self-Graph health signals |
| Feedback | Single tuning cycle | Multi-round auto_tune |
| Memory | TuningMemory (cross-run) | Per-round history |
| Oscillation guard | H_meta (direction history) | Improvement gate (min_improvement) |

### 10.2 Shared Admissibility

Both layers enforce the same meta-admissibility rule:

> A parameter change is accepted if and only if the measured quality
> does not decrease.

At the meta-landscape level, this is Q_after ≥ Q_before (Claim 6.2).
At the auto_tune level, this is improvement ≥ min_improvement (Claim 8.2).
Both mirror E₀'s object-level rule: accept transitions that do not
increase effective resistance.

### 10.3 Composition

The two layers can compose: auto_tune() finds healthy components and
estimates which parameters matter; tune() then fine-tunes within the
identified parameter subspace. This composition is validated but not
yet automated — it requires explicit orchestration.

---

## 11. Experimental Validation

### 11.1 Test Infrastructure

| Module | Test File | Test Classes | Tests | Commits |
|--------|-----------|-------------|-------|---------|
| self_tuning.py | test_self_tuning.py | 21 | 33+ | B4.1–B4.4 |
| parameter_sensitivity.py | test_parameter_sensitivity.py | 13 | 25+ | C150, C155 |
| **Total** | | **34** | **58+** | |

### 11.2 Structural Validation

The test suite validates:

1. **τ computation correctness** — Field summary extraction from known
   landscapes matches hand-computed values.
2. **Threshold derivation** — Derived thresholds scale correctly with
   τ_eff, producing tight bounds at high τ_eff and loose bounds at low.
3. **Sensitivity attribution** — Heuristic sensitivities match direction
   of empirical quality change for tested domains.
4. **Oscillation protection** — Meta-historization blocks detected
   oscillation patterns within 3 cycles.
5. **Tuning cycle correctness** — Before/after audit trail captures
   complete state. Reverts restore exact pre-tuning parameters.
6. **Multi-cycle convergence** — tune() terminates on all test domains.
7. **Quality score properties** — Goal dominance, penalty monotonicity,
   discriminative power validated.
8. **TuningMemory analysis** — quality_trend, recurring_issues,
   parameter_drift, effective_proposals produce correct values on
   synthetic history sequences.
9. **Serialisation** — Round-trip JSON preserves all snapshot fields.
10. **Component mapping** — COMPONENT_PARAMS covers all diagnosable
    components with valid parameter names.
11. **Auto-tune termination** — auto_tune() exits via all three
    termination paths (healthy, no improvement, round limit).
12. **Apply-config preservation** — Controller state unchanged except
    for targeted parameters.

### 11.3 Key Results

| Claim | Type | Evidence |
|-------|------|----------|
| Field-derived thresholds eliminate ad-hoc constants | Derived | Definition 3.1, Claim 3.1 |
| Q score provides stable optimisation target | Heuristic | Claim 4.1, 4.2 |
| Mass trap inversion detected automatically | Empirical | Claim 5.2, test_oscillation_protection |
| Oscillation protection prevents thrashing | Empirical | Claim 6.3, test_multi_cycle_convergence |
| Tuning always terminates | Derived | Claims 6.4, 8.1 |
| Quality monotonically non-decreasing under auto_tune | Empirical | Claim 8.2 |
| Cross-run memory enables temporal analysis | Derived | Claim 9.1, §9.2 |
| Component attribution reduces search space | Derived | Claim 7.1 |

---

## 12. Limitations and Open Questions

### 12.1 What We Do NOT Prove

1. **Global optimality.** Neither tuning layer guarantees convergence to
   a global optimum. Both are local: they accept improving moves and
   stop when no improvement is found. The parameter landscape may have
   multiple local optima.

2. **Weight optimality.** The quality score weights (0.4, 0.25, 0.15,
   0.1, 0.1) are heuristic. Different applications may require different
   weightings. The current weights were chosen for stability across the
   10 canonical domains.

3. **Cross-domain transfer.** TuningMemory persists parameter trajectories
   but does not guarantee that parameters tuned for one domain are optimal
   for another. Domain invariance holds for the *dynamics* but not
   necessarily for the *optimal parameter values*.

4. **Sensitivity accuracy.** The heuristic sensitivities (§5.1) are
   approximations. The finite-difference extension (Claim 5.3) provides
   more accurate gradients at higher computational cost.

### 12.2 Open Questions

1. Can the quality score weights themselves be tuned via a
   meta-meta-landscape? This would require a third-level quality metric,
   raising questions about infinite regress.

2. Can cross-domain parameter transfer be formalised? If domains share
   structural properties (similar τ profiles), their optimal parameters
   may also be similar.

3. Can real-time tuning (adjusting parameters mid-run rather than
   between runs) be made safe? The current architecture resets the
   landscape between tuning cycles, which is conservative but expensive.

---

## 13. Conclusion

Self-tuning in E₀ is not a bolt-on optimiser — it is the framework
applied to itself. The same Historization that guides object-level
navigation also records parameter tuning history. The same admissibility
rule that accepts non-degrading transitions also accepts non-degrading
parameter changes. The same field metrics that diagnose navigation
quality also diagnose parameter quality.

This reflexive architecture has three practical consequences:

1. **No new primitives.** The meta-landscape and Self-Graph attribution
   layers reuse existing E₀ constructs (field measurement, admissibility,
   history bounds, oscillation detection).

2. **No meta-parameters.** Derived thresholds (§3) scale with τ_eff,
   eliminating the meta-parameter problem. Step fractions and history
   windows are the only remaining constants, and they have natural
   interpretations (conservatism and memory depth).

3. **No infinite regress.** The architecture is two-level: object
   dynamics and meta-dynamics. The meta level uses the *same* rules
   but operates on a different space. There is no need for a
   meta-meta level because the quality score provides a scalar target
   that does not itself require tuning beyond the weight heuristic.

The 58 tests across two modules validate structural correctness,
termination guarantees, and empirical stability. The mass trap inversion
(§5.2) demonstrates that reflexive tuning can detect and correct
counter-intuitive parameter interactions that manual tuning would miss.

---

## Appendix A: Claim Classification

| # | Claim | Type | Section |
|---|-------|------|---------|
| 2.1 | τ normalisation bounds | Derived | §2.1 |
| 2.2 | τ orthogonality | Empirical | §2.1 |
| 3.1 | Field-scaling eliminates meta-parameters | Derived | §3.1 |
| 3.2 | Monotonic scaling | Derived | §3.1 |
| 4.1 | Goal dominance | Heuristic | §4.1 |
| 4.2 | Discriminative power | Empirical | §4.1 |
| 5.1 | Directional correctness | Empirical | §5.1 |
| 5.2 | Mass trap inversion | Empirical | §5.2 |
| 5.3 | Finite-difference extension | Derived | §5.2 |
| 6.1 | Bounded adjustment | Derived | §6.1 |
| 6.2 | Meta-admissibility mirrors object-level | Derived | §6.1 |
| 6.3 | Oscillation convergence | Empirical | §6.2 |
| 6.4 | Multi-cycle termination | Derived | §6.3 |
| 7.1 | Targeted search space reduction | Derived | §7.3 |
| 8.1 | Auto-tune termination | Derived | §8.1 |
| 8.2 | Monotonic quality under auto_tune | Empirical | §8.1 |
| 8.3 | State preservation | Derived | §8.2 |
| 9.1 | Serialisation round-trip | Derived | §9.3 |

---

## Appendix B: Parameter Bounds

```
TUNABLE_PARAMS = {
    "alpha":                (0.5,  10.0),
    "s_max":                (1.0,  1e6),
    "c_min":                (0.0,  0.9),
    "confidence_threshold": (0.0,  0.95),
    "hybrid_horizon":       (1,    10),
}
```

## Appendix C: Issue Detection Thresholds

| Metric | Condition | Interpretation |
|--------|-----------|----------------|
| τ_loop | > 0.25 | Excessive looping |
| τ_esc | > 0.20 | Excessive escalation |
| τ_efficiency | < 0.40 | Poor discovery rate |
| τ_progress | < 0.50 | Insufficient exploration |
