# E₀ Gate G1 — Development Mechanism Diagnosis v1

**Protocol:** `E0-G1-v1`

**Scope:** development only

**Source run:** GitHub Actions `30526724307`, commit `3990b5d`

**Holdout accessed:** no

**Gate result:** none

## Finding

The remediated WP-2.4 development result is not neutral because the geometry
methods happened to receive equal final scores. The additional lookahead is
causally inactive at the action boundary:

1. the shared confidence gate never permits a lookahead override;
2. the tested fields never leave the gradient phase regime; and
3. the packaged E path is mathematically equivalent to D for the current
   `influence_map` implementation.

Changing the preregistered threshold after seeing these data would be tuning on
the development result. C331 therefore diagnoses the mechanism but does not
change the protocol, policy, threshold, domains, or holdout boundary.

## Authoritative full-run evidence

The verified `g1-development-evidence` artifact contains 31,200 evaluation
episodes and 1,560 development replicates. Across B through E:

| Method | Evaluation decisions | Overrides | Path-cap hits | Phase regimes |
|---|---:|---:|---:|---|
| B | 4,482,410 | 0 | 0 | not applicable |
| C | 4,482,410 | 0 | 0 | not applicable |
| D | 4,482,410 | 0 | 0 | 4,482,410 gradient |
| E | 4,482,410 | 0 | 0 | 4,482,410 gradient |
| **Total** | **17,929,640** | **0** | **0** | no interfering or wrapped decision |

The zero-override result is not a sampling estimate. It is the aggregate over
every persisted evaluation decision in the completed development bundle.

## Bounded decision probe

`e0_controller.g1_mechanism_diagnosis` replayed a bounded, development-only
probe over all 120 preregistered development domain instances:

```text
120 domains × 4 lookahead methods × 1 episode × 20 interactions
= 9,600 inspected decisions
```

The probe uses only development seeds 0–9. It preserves each adapter's normal
learning and environment path, records per-decision diagnostics, and compares
methods only where episode, step, state, and candidates align.

### Gate blockers

| Method | Decisions | Preferred ≠ greedy | Conflict confidence max | Confidence blocks | Imbalance blocks | Overrides |
|---|---:|---:|---:|---:|---:|---:|
| B | 2,400 | 532 | 0.1945 | 532 | 40 | 0 |
| C | 2,400 | 540 | 0.4240 | 540 | 40 | 0 |
| D | 2,400 | 540 | 0.4240 | 540 | 40 | 0 |
| E | 2,400 | 540 | 0.4240 | 540 | 40 | 0 |

The configured confidence threshold is 0.85. No disagreement reaches it.
Every imbalance failure is also a confidence failure, so path imbalance never
acts as the sole blocker.

Some C/D/E decisions have confidence above 0.85, but only when lookahead already
agrees with greedy. High confidence therefore cannot change an action under the
current conjunction.

### Counterfactual threshold reachability

This sweep counts disagreements that would pass confidence and imbalance if
only the confidence threshold changed. It is diagnostic, not a performance
result and not a threshold recommendation.

| Threshold | B eligible | C eligible | D eligible | E eligible |
|---:|---:|---:|---:|---:|
| 0.05 | 316 | 360 | 360 | 360 |
| 0.10 | 304 | 320 | 320 | 320 |
| 0.20 | 0 | 306 | 306 | 306 |
| 0.30 | 0 | 258 | 258 | 258 |
| 0.40 | 0 | 0 | 0 | 0 |
| 0.85 | 0 | 0 | 0 | 0 |

The threshold 0.85 lies outside the observed conflict-confidence support.
Selecting a lower value from this table would be post-hoc optimization and
requires a new calibration split and versioned protocol.

## Where internal differences disappear

All 2,400 bounded probe decisions were context-aligned across B–E. No pair
selected a different action.

| Comparison | Probability vectors differ | Full score ranking differs | Preferred action differs | Selected action differs | Maximum probability delta |
|---|---:|---:|---:|---:|---:|
| B vs C | 1,210 | 36 | 8 | 0 | 0.1803 |
| C vs D | 623 | 19 | 0 | 0 | 0.00000668 |
| D vs E | 0 | 0 | 0 | 0 | 0 |
| B vs E | 1,230 | 55 | 8 | 0 | 0.1803 |

This separates three facts:

1. **Path aggregation is not numerically empty.** B and C frequently assign
   different probabilities and occasionally prefer different actions.
2. **Phase is practically dormant.** D changes C only at tiny numerical scale,
   never changes the preferred action, and is always classified as gradient.
3. **E is a packaged D path.** The current `influence_map` calls the same U(1)
   path superposition used by D. It does not apply a separate curvature damping
   or another full-stack action modifier, so exact D/E equality is expected
   wrapper parity rather than evidence for an additional mechanism.

## Interpretation

The C330 scaling fix was necessary and successful: valid algorithmic timeouts
fell from 183 to 3 without infrastructure failures or path-cap hits. It did not
unmask a hidden geometry benefit.

The development data support the following bounded conclusions:

- G1-v1 does not demonstrate practical phase/interference value.
- Its current domains do not activate an interfering or wrapped phase regime.
- Its confidence gate prevents all lookahead mechanisms from changing an
  evaluation action.
- Lowering the gate alone cannot establish phase attribution because C, D, and
  E have the same conflict profile and D never changes the preferred action
  relative to C.
- Proceeding to holdout cannot rescue the missing development mechanism and
  would spend the protected data without a positive rationale.

## Recommended lifecycle decision

The evidence-preserving default is to close G1-v1 as
**development-negative, holdout-unopened**.

If phase research continues, it should use an explicitly amended `E0-G1-v2`
that:

1. adds a separate calibration split for the override rule;
2. preregisters a phase-excitation check before outcome comparison;
3. includes domains whose development instances reach interfering or wrapped
   regimes without inspecting future holdout outcomes;
4. defines whether E is intentionally packaged-D parity or adds a distinct,
   testable geometry mechanism;
5. creates fresh protected holdout seeds; and
6. keeps the original G1-v1 artifact immutable.

## Reproduction

```text
python -m e0_controller.g1_mechanism_diagnosis \
  --episode-count 1 \
  --interaction-budget 20 \
  --episodes-evidence <bundle>/episodes.jsonl.gz \
  --output artifacts/g1/E0-G1-v1/development/c331/mechanism_diagnosis.json
```

The checked-in C331 JSON contains the bounded probe and the full episode
aggregate. It is explicitly marked `not_g1_result=true` and
`holdout_accessed=false`.
