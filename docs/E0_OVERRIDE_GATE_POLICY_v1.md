# E₀ Override Gate Policy and Calibration v1

**Work package:** WP-GATE-0.1

**Status:** policy infrastructure implemented; no legacy behavior change

**Date:** 2026-07-31

**Machine-readable companion:** `E0_OVERRIDE_GATE_CALIBRATION_PROTOCOL_v1.json`

## 1. Decision

E₀ does not have a universally validated confidence threshold.

The existing scalar names `confidence_threshold` and `min_confidence` denote a
support margin,

```text
support_margin = P_best - P_second
```

not a calibrated probability that an override is correct. A value of `0.85`
therefore means that the two highest normalized support values differ by 0.85.
It does not mean that the preferred action has an 85% probability of improving
the outcome.

From WP-GATE-0.1 onward:

1. documentation and new protocols call this quantity `support_margin`;
2. `calibrated_confidence` is reserved for an empirically calibrated
   probability of positive incremental utility;
3. every new override experiment names a complete, versioned gate policy;
4. no scalar value is promoted to a framework-wide optimum; and
5. no existing runtime default, snapshot, G1-v1 artifact, or holdout boundary
   changes in this work package.

## 2. Why a scalar default is insufficient

The margin distribution depends on at least:

- score construction and geometry;
- path horizon and enumeration;
- number of admissible actions;
- path-family multiplicity and imbalance;
- phase regime;
- historization state;
- domain topology; and
- normalization over the current candidates.

Equal margin values need not imply equal reliability across those contexts.
Threshold selection is also asymmetric: a harmful override may cost much more
than a missed beneficial override. The gate is therefore a policy with a risk
contract, not merely a numeric cutoff.

## 3. Existing policies are different

The repository currently contains three distinct override contracts.

### 3.1 General controller legacy contract

`E0Controller` defaults to `hybrid_mode="greedy"` and
`confidence_threshold=0.0`. The threshold is inert while greedy mode is active.
If `AMPLITUDE_ON_DISAGREE` is enabled without an explicit threshold, a
disagreement passes the margin check at `0.0`, subject to admissibility and any
active revisit or Self-Graph health guards.

This contract has no path-imbalance or path-cap check.

### 3.2 Structural Geometry legacy contract

`lean.structural_geometry.InfluenceReport.should_override()` defaults to:

```text
min_confidence = 0.85
max_imbalance = 3.0
```

It requires disagreement, sufficient support margin, and bounded path-count
imbalance. The current implementation exposes truncation but does not include
the truncation flag in `should_override()`.

The value `0.85` was transferred from the project-owned C185 traffic study.
That study compared `0.5` and `0.85` over five-seed averages in one traffic
family. It supports a conservative traffic-specific profile; it does not
establish a universal optimum.

### 3.3 G1-v1 frozen contract

G1-v1 variants B through E require:

1. disagreement with the shared greedy action;
2. support margin at least `0.85`;
3. path-count imbalance at most `3.0`; and
4. no path-cap hit.

This contract is immutable for G1-v1. C331 found zero overrides in all
17,929,640 persisted B-E evaluation decisions. In the bounded probe, the
maximum disagreement margin was `0.1945` for B and `0.4240` for C-E. These
values describe reachability, not the outcome quality of a lower threshold.

## 4. Evidence inventory

| Context | Value(s) | Evidence strength | Permitted interpretation |
|---|---:|---|---|
| Controller default | `0.0` | API/repository fact | Backward-compatible legacy behavior, not a validated optimum |
| BPI 2017 | `0.2`, `0.3`, `0.5` | One project-owned process benchmark | Stable result in the tested range and task |
| Wikispeedia | `0.5` after `0.2` | Project-owned selected benchmark | Local configuration choice |
| C185 traffic | `0.5`, `0.85` | Five-seed averages in one family | `0.85` was safer than `0.5` in that setup |
| G1-v1 | `0.85` | Complete development bundle | Gate was causally inactive under G1-v1 |

None of these rows authorizes a new global default.

## 5. Normative policy interface

Any new gate policy must serialize the following fields:

```text
policy_id
policy_version
mode
score_semantics
min_support_margin
max_path_imbalance
forbid_path_cap_hit
revisit_guard
health_guard
scope
provenance
calibration_artifact
```

### 5.1 Modes

- `disabled`: never override.
- `legacy_fixed`: reproduce a named historical contract exactly.
- `fixed`: use an explicitly scoped, preregistered policy.
- `calibrated`: use a frozen calibration artifact and its declared decision
  rule.

### 5.2 Scope

The scope must identify:

- geometry and score implementation;
- horizon or horizon policy;
- action-count range;
- supported phase regimes;
- domain families;
- utility definition; and
- known out-of-scope conditions.

A policy is not portable outside its declared scope without new calibration.

### 5.3 Provenance

Provenance must contain the source commit, protocol ID, split manifest hash,
artifact hash, creation date, and whether protected data were accessed. A
`calibrated` policy without a resolvable calibration artifact is invalid.

## 6. Compatibility and migration

WP-GATE-0.1 specified the migration contract. WP-GATE-0.2 implements its
policy value object, general-controller legacy mapping, Envelope and MemOS
round trips, and public API export. The implementation obeys these rules:

1. Existing `confidence_threshold` and `min_confidence` fields remain readable.
2. Existing snapshots restore the exact prior behavior.
3. Absence of a policy object maps to a named legacy profile; it does not
   silently select a new threshold.
4. New serialized records store both the legacy scalar alias, while required
   for compatibility, and the authoritative `policy_id`.
5. Whether to warn when hybrid override mode uses an implicit legacy policy
   remains a later API-lifecycle decision; no warning alters current behavior.
6. Changing the controller default requires a separate versioned work package,
   migration tests, and release note.
7. G1-v1 files and artifacts are never rewritten to the new schema.

## 7. Calibration protocol

### 7.1 Split discipline

Every calibration experiment has four roles:

1. **Exploration:** prior repository evidence, including C185 and G1-v1. It may
   shape hypotheses but may not confirm a selected policy.
2. **Calibration:** fresh, explicitly enumerated instances used to fit or
   select the policy.
3. **Verification:** fresh instances used once after the policy is frozen.
4. **Protected holdout:** fresh seeds and instances reserved for a later gate.

G1-v1's protected holdout is not available to G1-v2 or to gate calibration.
A new experiment requires a new protected manifest.

### 7.2 Stage A: paired decision evidence

At every eligible disagreement:

1. snapshot the complete decision state;
2. branch into greedy and lookahead actions;
3. use common random numbers and the same rollout budget;
4. measure both outcomes over a preregistered evaluation horizon; and
5. record incremental utility:

```text
delta_utility = utility(lookahead branch) - utility(greedy branch)
```

Required context includes margin, imbalance, path-cap status, geometry,
horizon, action count, phase regime, domain family, state hash, and random
stream identifier.

Decision branches diagnose local causal value. They do not replace closed-loop
evaluation because an override can alter later states and learning.

### 7.3 Stage B: closed-loop policy evaluation

Candidate policies run end to end on paired calibration replicates. The
replicate, not the individual decision, is the primary statistical unit.
Results must report:

- utility difference from no-override greedy/historized control;
- override count and coverage;
- beneficial, neutral, harmful, and unresolved override counts;
- harmful-override severity;
- results per domain family and scale;
- path-cap and infrastructure failures; and
- runtime cost.

### 7.4 Selection rule

Before calibration outcomes are read, the experiment instance freezes:

- candidate policy set or calibration model;
- primary utility;
- risk budget for harmful overrides;
- minimum activation support;
- non-inferiority margin per required domain family;
- confidence interval and multiplicity method; and
- deterministic tie-breaker favoring the simpler or safer policy.

A candidate is eligible only if all frozen safety, support, and
non-inferiority constraints pass. Among eligible candidates, select the policy
with the best primary paired utility. If no candidate is eligible, select
`disabled`. A zero-override or no-selection result is a valid negative result.

### 7.5 Calibration model

If the word `confidence` is used for a learned value, the artifact must show
that it estimates:

```text
P(delta_utility > 0 | recorded decision context)
```

It must include reliability bins, Brier score, calibration error, cross-fit
predictions, and sample counts. Thresholding the uncalibrated support margin
alone must continue to be described as a margin gate.

### 7.6 Verification and holdout

After calibration:

1. freeze the complete policy and artifact hash;
2. execute verification once;
3. reject or retain without retuning;
4. open a fresh protected holdout only if preregistered activation, safety,
   and utility criteria pass; and
5. never return from verification or holdout to policy selection.

## 8. Required artifacts

A completed calibration must emit:

- protocol instance and split manifests;
- source/environment manifest;
- immutable policy record;
- paired branch records;
- closed-loop replicate records;
- selection report with every candidate;
- calibration diagnostics, if applicable;
- verification report;
- checksums for every artifact; and
- explicit `holdout_accessed` and claim-status fields.

Calibration artifacts are development evidence. They are not Gate G1 results.

## 9. Implementation status and next boundary

WP-GATE-0.2 provides:

- immutable `OverrideGatePolicy` and `OverrideGateMode`;
- exact `legacy_controller_v1`, `legacy_structural_geometry_v1`, and
  `legacy_g1_v1` constructors;
- fail-closed margin, imbalance, and path-cap evaluation;
- policy-controlled revisit and Self-Graph health guards;
- the historical `confidence_threshold` scalar as a mutable alias only for
  `legacy_controller_v1`;
- rejection of scalar mutation for disabled, fixed, calibrated, Structural
  Geometry, and frozen G1 policies;
- serializable calibrated-policy records that remain deliberately
  non-executable until a frozen artifact evaluator exists;
- optional policy support in `E0Envelope`;
- policy plus scalar persistence in MemOS and session provenance; and
- old-record restoration when no policy field exists.

Structural Geometry and G1-v1 retain their existing package-local execution
paths. Their policy constructors are authoritative compatibility mappings, not
rewrites of frozen code.

WP-GATE-0.3 freezes that concrete instance in
`E0_OVERRIDE_GATE_CALIBRATION_INSTANCE_v1.json`, with its rationale in
`E0_OVERRIDE_GATE_CALIBRATION_PREREGISTRATION_v1.md`. It fixes:

- `E_FULL_GEOMETRY` at horizon 3 as the only treatment scope;
- the same scorer with overrides disabled as the causal control;
- four domain families, three scales, and three fresh disjoint seed spaces;
- 11 fixed margin candidates plus the disabled control;
- paired branch and closed-loop utility;
- activation, harm, non-inferiority, path-cap, and infrastructure budgets;
- clustered inference, multiplicity correction, and a safety-favoring
  deterministic tie-breaker; and
- single-use verification before any protected-holdout access.

The accompanying validator checks the frozen boundary without importing or
constructing a domain. WP-GATE-0.3 does not execute calibration, select a
threshold, read a holdout, or change runtime behavior.

WP-GATE-0.4 adds the domain-free execution scaffold documented in
`E0_OVERRIDE_GATE_CALIBRATION_RUNNER_v1.md`. It deterministically plans all
tasks and matrix batches, fixes disabled-control pairing, validates
protected-split authorization and artifact shapes, and seals a dry-run
manifest. Its CLI exposes only planning commands: it has no domain import and
no outcome-producing command.

WP-GATE-0.5 adds the calibration-only domain and paired-branch engine described
in `E0_OVERRIDE_GATE_CALIBRATION_ENGINE_v1.md`. The G1-v1 public builders keep
their development-only default; a separate namespace accepts exactly
calibration seeds 2000–2019, while verification and protected-holdout
namespaces remain unavailable. The engine materializes only exact frozen
candidates, snapshots all decision-relevant mutable state, and proves on a
synthetic fixture that diagnostic branches do not mutate the parent episode.
Calibration domains were instantiated only for structure and invariants; no
calibration outcome was observed.

The next boundary is hard process isolation, atomic task shards, resume and
consolidation validation, and the frozen statistical selection implementation.
That runner must be reviewed and its execution commit frozen before the first
preregistered calibration outcome is produced.
