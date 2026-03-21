# E₀ Evaluation Layer v0.2

**Status:** Draft architecture note  
**Date:** 2026-03-21  
**Purpose:** Define how E₀ runs should be evaluated beyond simple step-level success  
**Scope:** Open-domain E₀ runs, scenario-grounded semantic outputs, graph quality, run-level assessment, and controller/evaluation separation

---

## 1. Motivation

The current E₀ runtime can now:

- bootstrap landscapes from natural-language tasks,
- validate graph structure before a run,
- execute transitions under deterministic controller order,
- persist runtime state through MemOS,
- compare runs across multiple domains,
- and operate on scenario-grounded semantic inputs.

However, a new problem becomes visible at this stage:

> **step-level success is not the same as run-level quality**

A run may show a high or even perfect semantic transition success rate while still being poor overall because it:

- fails to reach the goal,
- falls into trivial loops,
- makes no structural progress,
- produces semantically weak or incomplete outputs,
- or violates grounding expectations.

This means E₀ now requires an explicit **Evaluation Layer**.

---

## 2. Core Thesis

A good E₀ run cannot be judged only by:

- whether each step returned `SUCCESS`, or
- whether the graph was merely reachable.

A good run must be evaluated across **multiple quality dimensions**.

Therefore:

```text
Run Quality ≠ Step Success Rate
```

Instead:

```text
Run Quality = graph quality
            + run dynamics quality
            + semantic quality
            + cross-run stability
```

---

## 3. Controller vs Evaluation: Different Roles

A structural failure pattern such as a trivial 2-cycle has **two different meanings** in the system.

### 3.1 Controller responsibility

The controller should eventually be able to:

- detect repeated trivial cycles,
- escalate,
- force an alternative path,
- or abort when structural progress has stopped.

This is an **operational safeguard**.

### 3.2 Evaluation responsibility

The Evaluation Layer should:

- detect that the failure pattern occurred,
- measure its severity,
- downgrade the run accordingly,
- and make the problem visible in reports and comparisons.

This is a **diagnostic and judgment function**.

### 3.3 Consequence

The Evaluation Layer does **not** replace runtime safeguards.
It measures run quality, while controller-level protections must still prevent repeated structural failure patterns such as trivial 2-cycles.

---

## 4. Evaluation Layers

The E₀ Evaluation Layer should distinguish four different levels of judgment.

### 4.1 Graph Quality Evaluation

This layer exists already in initial form.

It evaluates the proposed landscape *before* the run.

Metrics include:

- goal reachability,
- shortest happy path,
- recovery edges,
- traps,
- trivial loops,
- graph quality score.

This layer answers:

> Is the graph structurally runnable?

### 4.2 Run Dynamics Evaluation

This layer evaluates what happened *during* the run.

It should measure:

- goal reached or not,
- steps taken,
- escalation count,
- revisit count,
- repeated edge cycles,
- progress ratio,
- total and average tension,
- path efficiency relative to happy path.

This layer answers:

> Did the run make structurally meaningful progress?

### 4.3 Semantic Output Evaluation

This layer evaluates the semantic quality of the results produced.

It should measure:

- required output coverage,
- grounding in scenario source text,
- unsupported claims,
- uncertainty marking quality,
- completeness of the final deliverable,
- relevance of the LLM-generated transition outputs.

This layer answers:

> Was the semantic work actually good and scenario-faithful?

### 4.4 Cross-Run Stability Evaluation

This layer compares repeated runs across:

- mock vs live,
- run A vs run B,
- scenario A vs B,
- domain A vs B.

It should measure:

- graph score variance,
- path variance,
- run-length variance,
- semantic completeness variance,
- escalation variance,
- repeatability under similar inputs.

This layer answers:

> Is the system behavior stable enough to be considered reliable?

---

## 5. Minimum Evaluation Objects

The runtime should gradually introduce explicit evaluation objects.

### 5.1 `RunEvaluation`

Judges the complete run.

Suggested fields:

```python
@dataclass
class RunEvaluation:
    goal_reached: bool
    steps: int
    escalations: int
    revisits: int
    repeated_cycles: int
    progress_ratio: float
    avg_tension: float
    total_tension: float
    goal_reach_efficiency: float
    loop_penalty: float
    rating: str
    warnings: list[str]
```

### 5.2 `SemanticEvaluation`

Judges the semantic result quality.

Suggested first-version fields:

```python
@dataclass
class SemanticEvaluation:
    required_outputs_covered: float
    missing_outputs: list[str]
    uncertainty_marks: int
    completeness_score: float
    notes: list[str]
```

### 5.3 `ScenarioEvaluation`

Combines graph, run, and semantic evaluation for one scenario.

Suggested fields:

```python
@dataclass
class ScenarioEvaluation:
    scenario_id: str
    domain: str
    graph_score: float
    run_evaluation: RunEvaluation
    semantic_evaluation: SemanticEvaluation
    overall_score: float | None
```

Note:

- in early versions, `overall_score` should remain optional,
- explicit gates and component judgments are more important than a single number.

---

## 6. Immediate Hard Failure Conditions

The Evaluation Layer should define a few explicit hard conditions.

A run should **not** be considered successful if any of the following holds:

### 6.1 Goal not reached

Even with high step success, a run that does not reach the goal cannot count as successful.

### 6.2 Repeated trivial loop without recovery

If the same 2-cycle repeats beyond a threshold and no structural progress is made, the run should be flagged as failed or degraded.

### 6.3 Critical graph invalidity

If graph validation fails critically, no run score should be issued at all.

### 6.4 Semantic deliverable missing required sections

If the final output omits key required outputs, semantic success must be reduced or invalidated.

---

## 7. Key Metrics to Introduce Next

The next runtime evolution should introduce at least the following metrics.

### 7.1 `goal_reached`

Boolean. Always primary.

### 7.2 `goal_reach_efficiency`

Suggested form:

```text
goal_reach_efficiency = happy_path_length / actual_steps
```

clamped to `[0,1]` when goal is reached.

### 7.3 `loop_penalty`

Penalty for repeated 2-cycles, self-loops, or repeated edge oscillations.

### 7.4 `progress_ratio`

Measures how much of the run was spent entering new states rather than repeating old ones.

Suggested form:

```text
progress_ratio = unique_states / steps
```

### 7.5 `semantic_completeness`

Measures how many required outputs from the scenario packet were actually covered.

### 7.6 `grounding_warnings`

Counts possible unsupported semantic claims or evidence drift.

Note:

- `required_outputs_covered` is the first pragmatic semantic metric,
- `grounding_warnings` should initially remain heuristic or optional,
- strong grounding judgment may later require an explicit evaluator or LLM-as-judge layer.

---

## 8. Rating Scale

`RunEvaluation.rating` should not remain unspecified.

Recommended first-scale:

- **A** — goal reached, efficient, no major structural issues, semantically complete
- **B** — goal reached with moderate inefficiency or minor semantic gaps
- **C** — goal reached but structurally weak or semantically incomplete
- **D** — goal not reached, but partial structural progress exists
- **F** — structural failure (loop, trap, no progress, or critical invalidity)

This scale is intentionally simple and should remain explainable in reports.

---

## 9. Relationship to Scenario Packets

The Evaluation Layer depends directly on Scenario Packets.

This is because semantic quality cannot be judged without:

- source text,
- objective,
- required outputs,
- constraints,
- evaluation points.

The scenario packet is therefore the anchor for semantic evaluation.

Without it, the runtime can only judge structural behavior, not semantic quality.

---

## 10. Relationship to Current Runtime

The current runtime already provides the ingredients needed for the first version of the Evaluation Layer.

Available inputs already include:

- graph quality report,
- controller trace,
- run metrics,
- result logs per step,
- scenario packets,
- cross-domain comparison.

So the next step is not a conceptual leap.
It is a structured integration step.

---

## 11. Recommended Near-Term Implementation Plan

### Step 1 — Architecture note (this document)

Define the evaluation problem explicitly.

### Step 2 — `evaluation.py`

Implement minimal runtime evaluators for:

- graph quality carry-through,
- run dynamics evaluation,
- simple semantic completeness checks,
- hard failure conditions,
- rating assignment.

### Step 3 — integrate into `validate_cross_domain.py`

Cross-domain validation should report not only graph metrics and raw run metrics,
but also evaluation-layer outputs.

### Step 4 — add scenario-aware semantic checks

At first this should remain simple:

- check required output coverage via keyword/section presence,
- detect obvious unsupported claims only heuristically,
- count explicit uncertainty markers.

### Step 5 — benchmark across scenarios, not just domains

Once multiple scenario packets exist per domain, evaluation becomes more meaningful.

### Step 6 — controller hardening based on evaluation findings

After evaluation is in place, controller-level runtime safeguards should be strengthened for repeated structural failure patterns such as trivial 2-cycles.

---

## 12. What the Evaluation Layer Prevents

Without an evaluation layer, the project risks the following failure mode:

```text
high local success
+ weak structural progress
+ weak semantic grounding
= false sense of system quality
```

The Evaluation Layer prevents this by making the judgment criteria explicit.

---

## 13. Strategic Significance

The Evaluation Layer is not a side utility.
It is one of the required layers on the path from:

- research artifact

to:

- general E₀ agent runtime.

Why?

Because a general E₀ agent cannot be delivered responsibly unless its behavior can be:

- measured,
- compared,
- judged,
- and improved under explicit quality criteria.

That is the role of the Evaluation Layer.

---

## 14. Final Position

The system is now mature enough that evaluation must become first-class.

The correct next statement is:

> E₀ now requires an explicit run-quality and semantic-quality layer.

And this layer must be understood as:

- diagnostic first,
- operationally actionable second,
- but not a substitute for controller safeguards.

That is the purpose of E₀ Evaluation Layer v0.2.

---

## End of Document
