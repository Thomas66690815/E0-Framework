# E₀ ARC-H: MetaLandscape — Structural Self-Similarity

## Status: PLANNED (post-C297)
## Dependencies: ARC-G (C292-C295 complete), LLM Bootstrap (C43-C47, partial)

---

## 1. Core Claim

E₀ is structurally self-similar:

> The same SELECT → EXECUTE → HISTORIZE mechanism that navigates domain
> edges (Level 1) can navigate PathSignatures (Level 2) — without any
> modification to E0Controller.

This is not an analogy. It is a proof by construction:
build a Landscape where states = PathSignatures, run E0Controller on it,
show that the output is coherent and useful.

---

## 2. Vocabulary

| Level | State | Edge | Outcome source |
|-------|-------|------|----------------|
| L1 (Domain) | domain node ("INBOX") | domain transition | executor reports SUCCESS/FAILURE |
| L2 (Meta) | PathSignature ("(0,1,0)") | consecutive sig pair | coverage_delta from domain session |

**MetaState** = `str(PathSignature)` — e.g. `"(0, 1, 0)"` or `"(0,)"` (single community)
**MetaEdge** = `(MetaState_a, MetaState_b)` — appeared as consecutive signatures in a session
**MetaDelta** = `abs(trace_quality(sig_b) - trace_quality(sig_a))` or `0.5` (cold)
**MetaR0** = `1.0` (standard cold-start)
**MetaH** = `Historization()` — same class, different grain

---

## 3. What PathSignatures Already Have (pre-ARC-H)

From `trajectory.py` (C277, stable):

```python
PathSignature = Tuple[int, ...]     # e.g. (0, 1, 0)
compute_path_signature(path, communities) → PathSignature
TrajectoryHistorization.trace_quality(sig) → float   # [-1, 1]
TrajectoryHistorization.trace_load(sig)    → int      # U + F
TrajectoryHistorization.known_signatures() → List[PathSignature]
```

What is missing:
- No navigation landscape ON TOP of signatures
- No E0Controller operating at signature level
- No mechanism to choose "which pattern to pursue next"

ARC-H fills exactly this gap.

---

## 4. Commit Plan

### C296 — MetaLandscape (core data structure)

**File:** `e0_controller/meta_landscape.py`

```python
class MetaLandscape:
    def from_records(
        records: List[TrajectoryRecord],
        traj_hist: TrajectoryHistorization,
    ) -> Landscape:
        """Build a navigable Landscape from trajectory session records.

        For each consecutive (rec_a, rec_b) in records:
            MetaState_a = str(rec_a.signature)
            MetaState_b = str(rec_b.signature)
            delta = abs(trace_quality(sig_b) - trace_quality(sig_a))
                    or 0.5 if cold (trace_load == 0)
            add_edge(MetaState_a, MetaState_b, delta, resistance=1.0)

        Returns a Landscape ready for E0Controller.
        """
```

Also: `meta_state_to_sig(meta_state: str) → PathSignature` (inverse)

**Tests (C296):** `test_meta_landscape.py`
- MetaLandscape builds correctly from 2+ records
- Cold delta = 0.5 when trace_load == 0
- Warm delta = |trace_quality_b - trace_quality_a| when inscribed
- Single record → landscape with one state, no edges
- Returned object is a valid `Landscape` instance
- `meta_state_to_sig` roundtrip

### C297 — MetaController

**Design decision (no new class needed):**

```python
# MetaController = E0Controller(meta_landscape, meta_execute_fn)
# meta_execute_fn: (meta_state, meta_action) → Outcome

def make_meta_execute_fn(
    domain_session: E0Turn,
    sig_to_goal: Callable[[PathSignature], str],
) -> Callable[[str, str], Outcome]:
    """Return an execute_fn for use with E0Controller on a MetaLandscape.

    When E₀ selects meta_action (a MetaState = PathSignature string),
    the execute_fn:
      1. Translates meta_action → target domain goal
      2. Runs the domain session for N turns toward that goal
      3. Records the resulting TrajectoryRecord
      4. Returns SUCCESS if coverage_delta >= threshold else FAILURE
    """
```

**Proof:** `E0Controller(meta_landscape, meta_execute_fn)` requires
NO changes to E0Controller. Same `cycle()`, same `select_next()`,
same `historize()`. Self-similarity proven.

**Tests (C297):** `test_meta_controller.py`
- meta_execute_fn returns Outcome
- E0Controller on MetaLandscape runs without modification
- MetaLandscape historization updates after meta-cycle
- Two meta-cycles: meta-landscape inertia changes

### C298 — MetaSession (end-to-end demo)

**File:** `e0_controller/demo_meta_landscape.py`

Shows full two-level architecture:
```
Domain session → signature log → MetaLandscape.from_records()
                                → E0Controller(meta_landscape, ...)
                                → meta navigation → strategy selection
                                → direct domain session to goal pattern
```

---

## 5. Why Now Is the Right Time (and Why Not Earlier)

### Ready now (ARC-G complete):
- `E0Turn` + `LlmE2Port` (C292-C293): domain sessions produce structured `TurnResult` history
- `RoutingE2Port` (C295): multi-modal sessions → richer signature diversity
- `TrajectoryHistorization` (C277): U/F traces on signatures already work

### What LLM Bootstrap adds (C43-C47, future):
- LLM-generated landscape expansions create NEW states not in the cold landscape
- These new states cross community boundaries differently → richer PathSignature diversity
- MetaLandscape populated from LLM-bootstrapped sessions has more distinct MetaStates
- Without LLM bootstrap: MetaLandscape is functional but sparse (few distinct signatures)

### Conclusion:
- C296-C297: implement now — infrastructure complete
- C298 demo: can be richer after C43-C47 provides more signature variety
- MetaLandscape proof-of-concept is valid immediately; richness grows with LLM bootstrap

---

## 6. The Self-Similarity Proof (Formal)

Let `L₁ = (S₁, E₁, H₁)` be the domain landscape.
Let `L₂ = (S₂, E₂, H₂)` be the meta-landscape where:
- `S₂ = {str(sig) | sig ∈ TrajectoryHistorization.known_signatures()}`
- `E₂ = {(str(sig_a), str(sig_b)) | sig_a followed by sig_b in session history}`
- `H₂ = Historization()` (same class, different instance)

Then:
- `E0Controller(L₁, exec₁)` navigates `S₁` via `E₁`, inscribes `H₁`
- `E0Controller(L₂, exec₂)` navigates `S₂` via `E₂`, inscribes `H₂`

Both call identical code. The architecture is self-similar at any grain.

**Claim:** for any Landscape `L` satisfying the E₀ primitives,
`E0Controller(L, exec)` operates correctly without knowing what `L` represents.
The MetaLandscape satisfies all Landscape invariants by construction.

QED (by construction).

---

## 7. Open Questions

1. **MetaEdge delta**: use `abs(trace_quality delta)` or fixed 0.5?
   - Fixed 0.5 is simpler and avoids cold-start circular dependency
   - Quality-based delta makes cold MetaLandscape non-uniform (possibly better)
   - Decision: fixed 0.5 cold-start, quality-based after first inscription (same as domain L)

2. **MetaState namespace collision**: `str((0,1,0))` is unique within a session.
   Across multi-domain landscapes, two communities with different content but
   same index could produce the same MetaState. Mitigation: include domain
   hash in MetaState label if multi-domain MetaLandscape needed. Defer.

3. **MetaLandscape growth bound**: how many distinct signatures can exist?
   Upper bound: `|communities|^|max_path_length|` — in practice << 100 for
   normal landscapes. No bounding mechanism needed in C296-C297.

4. **Persistence**: MetaLandscape can be serialized via Landscape's existing
   JSON persistence. No new format needed.

---

## 8. ARC-H Commits Summary

| Commit | File | Content | Tests |
|--------|------|---------|-------|
| C296 | `meta_landscape.py` | MetaLandscape.from_records(), meta_state_to_sig() | ~30 |
| C297 | `meta_controller.py` | make_meta_execute_fn(), self-similarity proof tests | ~25 |
| C298 | `demo_meta_landscape.py` | end-to-end two-level session | 0 (demo) |

Total new tests: ~55
ARC-H target commit: C298

---

_Planned: 2026-05-06_
_Depends on: C292 (E0Turn), C293 (LlmE2Port), C277 (TrajectoryHistorization)_
_Connects to: LLM Bootstrap ARC (C43-C47) for signature richness_
