# E₀ Test Registry v1

> Central reference for all tests in the E₀ Framework.
> **Last verified:** 2026-03-25 — **623 tests** (602 unittest + 21 standalone mini-domain + 1 pre-existing error)

---

## Overview Table

| # | File | Tests | Runner | Domain | Status |
|---|------|------:|--------|--------|--------|
| 1 | `test_amplitude_overlay.py` | 125 | unittest | Ψ-paths, interference, geometries | ✅ GREEN |
| 2 | `test_llm_adapter.py` | 47 | unittest | LLM parsing, normalization, mocks | ✅ GREEN |
| 3 | `test_gordian_trap.py` | 44 | unittest | Holonomy, Gordian trap, multi-goal | ✅ GREEN |
| 4 | `test_evaluation.py` | 42 | unittest | Run/semantic/scenario evaluation | ✅ GREEN |
| 5 | `test_phase2_minidomain.py` | 38 | unittest | Φ, ω, holonomy, Ψ = e^(−S+iΘ) | ✅ GREEN |
| 6 | `test_reflection.py` | 36 | unittest | Reflection triggers, LLM fallback | ✅ GREEN |
| 7 | `test_invoice.py` | 33 | unittest | Invoice domain end-to-end | ✅ GREEN |
| 8 | `test_llm_integration.py` | 32 | unittest | Live LLM (requires API key) | ⚠ CONDITIONAL |
| 9 | `test_g5_edge_cases.py` | 28 | unittest | G5 robustness, 5 families A–E | ✅ GREEN |
| 10 | `test_memory_os.py` | 28 | unittest | Persistence, save/load round-trip | ✅ GREEN |
| 11 | `test_graph_validation.py` | 24 | unittest | Reachability, traps, quality score | ✅ GREEN |
| 12 | `test_topology_classification.py` | 23 | unittest | 380-graph scan, override prediction | ✅ GREEN |
| 13 | `test_phase2_invoice.py` | 18 | unittest | Invoice phase-layer validation | ✅ GREEN |
| 14 | `test_waypoint.py` | 17 | unittest | Goal-with-continuations, H4 | ✅ GREEN |
| 15 | `test_scaling.py` | 14 | unittest | O(n) complexity, n ≤ 500 | ✅ GREEN |
| 16 | `test_spinor.py` | 52 | unittest | SU(2) lift, geometric coupling, 720° | ✅ GREEN |
| 17 | `test_greedy_trap.py` | — | unittest | Greedy-trap walkthrough | ❌ IMPORT ERROR |
| 18 | `test_minidomain.py` | 21 | standalone | Core mechanics, historization, K11/K12 | ✅ GREEN |

---

## Per-File Details

### 1. test_amplitude_overlay.py — 125 tests

**What it tests:** Path enumeration with bounded horizons, Ψ-summation and intensity I = |Ψ|², probability normalization, deterministic vs. amplitude choice, dead-end and single-neighbor edge cases, destructive/constructive interference, multiple domain topologies (Mini-Domain, Diamond, Waypoint), all four geometry variants (simple, prefix, first_arrival, goal_reaching), hybrid controller override behavior.

**Key findings:**
- Probabilities always sum to ≈ 1.0 across all domains and geometries
- I(a) = |Ψ(a)|² holds precisely
- Amplitude choice avoids dead-end traps that greedy selects
- Destructive interference at START in diamond domain suppresses certain paths
- All geometries preserve admissibility constraints

---

### 2. test_llm_adapter.py — 47 tests

**What it tests:** JSON parsing from LLM output (plain, markdown-fenced, whitespace-tolerant), state name normalization (UPPER_SNAKE_CASE), delta/resistance extraction with clamping, state proposal generation, transition result parsing, landscape materialization from proposals, task map generation, snapshot comparison.

**Key findings:**
- Markdown fence stripping works with/without language tag
- Normalization: hyphens → underscores, multi-underscores → single
- Delta/resistance clamped to [0, 1]
- Duplicate state names (post-normalization) deduplicated
- LLMResponseError raised with raw_response on parse failure

---

### 3. test_gordian_trap.py — 44 tests

**What it tests:** Holonomy formula ΔΘ = ½[Σv_loop − Σv_short], destructive interference between A-family paths, B-path dominance at path level, greedy behavior (picks A1), goal-reaching geometry (picks B1 at h ≥ 5), hybrid override A1 → B1, simple geometry preference, historization stability, multi-goal coherence.

**Key findings:**
- ΔΘ_predicted matches ΔΘ_actual to 6 decimals
- cos(ΔΘ) < −0.9 (near-π phase opposition)
- Interference factor < 0.1 (strong destructive)
- h = 3: A1 wins (loop invisible); h = 5: B1 wins (loop visible → destructive)
- P(B1) > 0.9 at h = 5 with goal_reaching geometry
- Multi-goal {G1, G2, G3}: A1 always wins (most coverage)

---

### 4. test_evaluation.py — 42 tests

**What it tests:** Repeated cycle counting, rating assignment (A–F), run evaluation metrics (efficiency, goal reach, loop penalty), semantic coverage scoring, hard failure detection (graph quality, goal reachability, semantic gaps), scenario evaluation composition, hybrid mode metrics (override rate, agreement rate), multi-scenario summary generation.

**Key findings:**
- Ratings correlate with efficiency and cycle patterns
- Hard failures (F) override all other metrics
- Semantic coverage correctly identifies missing outputs
- Zero-step paths handled gracefully

---

### 5. test_phase2_minidomain.py — 38 tests

**What it tests:** Potential Φ(x) computation, Helmholtz decomposition v = v_grad + v_rot, ω antisymmetry ω(x,y) = −ω(y,x), holonomy on closed cycles, path phase Θ accumulation, Ψ = exp(−S + iΘ) formula verification.

**Key findings:**
- Φ correctly captures sink vs. source hierarchy
- v_grad ⊥ v_rot (dot product ≈ 0)
- ω antisymmetric for ALL state pairs, not just edges
- 2-edge cycles: trivial holonomy (exact cancellation); 3+ edges: may be nonzero
- |Ψ| = exp(−S) and arg(Ψ) = Θ to 10+ decimal places

---

### 6. test_reflection.py — 36 tests

**What it tests:** Reflection decision triggers (failure, quality, opportunity), evidence block construction for LLM, result sampling and truncation, JSON parsing of LLM reflection responses, multi-scenario summary formatting.

**Key findings:**
- Hard failures trigger "failure" reflection with high priority
- Goal-not-reached triggers only if progress_ratio < 0.5
- Repeated cycles > 3 with loop_penalty > 0.2 trigger reflection
- Opportunity type only when rating ≥ B and coverage high
- LLM reflection has fallback to rule-based on call failure

---

### 7. test_invoice.py — 33 tests

**What it tests:** Invoice domain as realistic end-to-end validation — graph construction, controller run, evaluation, hybrid mode, memory persistence, full pipeline from START to COMPLETED.

**Key findings:**
- Invoice domain (almost-DAG) successfully runs through entire E₀ pipeline
- Happy path shorter than recovery alternatives
- Hybrid mode makes minor overrides in this low-holonomy domain

---

### 8. test_llm_integration.py — 32 tests ⚠

**What it tests:** Live LLM landscape proposal, transition execution (SUCCESS/FAILURE/PARTIAL), confidence extraction, delta/resistance estimation, full controller run, semantic evaluation, hybrid mode with real LLM, multi-goal handling.

**Key findings:**
- LLM proposes connected graph with ≥ 4 states, goal always reachable
- Graph quality score typically > 0.3
- Confidence clamped to [0, 1]
- Full runs reach goal ≥ 85% with LLM
- Multi-goal runs path to at least one goal

**Note:** Skipped when `OPENAI_API_KEY` not set. Results may vary due to LLM non-determinism.

---

### 9. test_g5_edge_cases.py — 28 tests

**What it tests:** G5 multi-goal robustness across 5 stress families:
- **Family A** — Winner stability as |G| grows from 1 → 5
- **Family B** — Unreachable, weak, and noisy goal injection
- **Family C** — Competing goals (generalist vs. specialist actions)
- **Family D** — Low-δ rescue path threshold crossover
- **Family E** — Selectivity (entropy, top-1 gap) vs. goal count

**Key findings:**
- A: Winner A stable across all |G|, selectivity peaks at |G| = 2–3
- B: Unreachable goals = safe; weak/noisy goals with coherent paths correctly shift winner
- C: Single-goal → specialists win; multi-goal → generalist C wins (P = 0.665)
- D: Rescue from δ = 0.01 (low S = Δ·R → high amplitude); crossover at δ ∈ [0.8, 1.5]
- E: Entropy ↓, gap ↑ with more goals — anti-saturation (no F1 triggered)
- **No failure signatures F1–F4 triggered**

---

### 10. test_memory_os.py — 28 tests

**What it tests:** Edge serialization, context save/load round-trip, landscape/controller restoration from snapshot, E0MemoryOS summarize_for_llm, historization persistence across sessions, behavior change from restored memory, hybrid controller snapshots, session listing.

**Key findings:**
- Edge key format: "SOURCE→TARGET"
- Round-trip: save → load → content identical
- Restored landscape passes integrity checks
- Historization U/F traces survive persistence exactly
- Avoided edge (high F-trace) skipped in restored runs
- Overlay attached in snapshots when hybrid

---

### 11. test_graph_validation.py — 24 tests

**What it tests:** Goal reachability (BFS), shortest path (happy path), recovery edge identification, trap detection (dead-end non-goal), trivial loop detection (2-cycles, self-loops), composite graph quality score.

**Key findings:**
- Quality score = reachable (0.5) + path_length (0.2) + coverage (0.15) + traps (0.1) + loops (0.05)
- Traps correctly identified (no outgoing edges, not goal)
- 2-cycle B↔D detected in trivial_loops
- Recovery edges are out-of-happy-path but contribute to reachability

---

### 12. test_topology_classification.py — 23 tests

**What it tests:** 380-graph parametric scan across triangle/diamond/gordian-lite topologies — override rate prediction from path family count and phase opposition.

**Key findings:**
- Triangle (1 family) → 0% overrides
- Diamond (2 families) → ~37% overrides
- Gordian-lite (2 families + phase opposition) → ~93% overrides
- Prefix = first_arrival (100% agreement)
- Simple ≈ prefix (97.6% agreement)
- G5 exclusive disagreements in ~30% of graphs
- Phase opposition (ΔΘ > π/4) is strong predictor of override

---

### 13. test_phase2_invoice.py — 18 tests

**What it tests:** Invoice domain as secondary validation of Phase 2 layer — Φ computations, ω antisymmetry, holonomy over HUMAN_REVIEW cycle, happy path vs. recovery path interference, phase consistency.

**Key findings:**
- Invoice domain mostly DAG → weak holonomy overall
- Happy path has stronger Ψ than recovery path
- Two-edge cycles verify holonomy = 0
- All edges have finite, non-NaN ω and v_rot

---

### 14. test_waypoint.py — 17 tests

**What it tests:** Goal-with-continuations domain (goal G has outgoing edges), post-goal loop G→Y1→G, path enumeration across geometries, interference when goal is not terminal.

**Key findings:**
- Prefix geometry includes post-goal paths → more paths than first_arrival
- First_arrival stops at goal; prefix/simple continue
- Intensity values genuinely differ between geometries (> 0.1% deviation)
- Post-goal loop effects visible at horizon ≥ 4
- Validates H4 from summation geometry program

---

### 15. test_scaling.py — 14 tests

**What it tests:** Landscape construction at n = 50, 100, 500. Goal reachability, controller run time complexity (greedy), step count growth, amplitude overlay bounded computation, hybrid mode scalability.

**Key findings:**
- Run time subquadratic (500/50 ratio < 50×)
- Step count stays O(n) (< 3n for chains)
- Overlay with h = 3 completes in < 2 seconds at n = 500
- Path count bounded by horizon, not graph size
- No exponential blowup in bounded-horizon analysis

---

### 16. test_spinor.py — 52 tests

**What it tests:** SU(2) lift of the scalar U(1) phase layer — Pauli algebra (anticommutation, hermiticity, tracelessness), 720° periodicity (exp(−iπσ)=−𝕀, exp(−i2πσ)=+𝕀), single-path magnitude consistency (‖Ψ_SU2‖ = |Ψ_U1|), phase halving effect (Θ→Θ/2), winner divergence (U(1) vs SU(2) on Gordian Trap), non-commutativity (multi-axis transport), graph holonomy (loop transport, size dependence), structural invariants (empty paths, inadmissible paths, reference spinor independence), **geometric coupling** (Phase 4b: vorticity-derived axis from Helmholtz decomposition).

**Key findings:**
- **Phase halving:** SU(2) uses exp(−iΘ/2·σ_z)|↑⟩, not exp(iΘ). Relative phase ΔΘ/2 ≈ π/2 (orthogonal) vs ΔΘ ≈ π (destructive in U(1))
- **Winner flips on Gordian Trap:** U(1) I(A1) = 0.018 (B1 wins), SU(2) I(A1) = 0.838 (A1 wins)
- **Geometric coupling (Phase 4b):** su(2) connection vector A⃗ = (A₁, A₂, A₃) from local Helmholtz geometry. A₁ = vorticity gradient (≤92.9% off-axis on Gordian), A₂ = face holonomy (non-zero on triangles). Geometric SU(2) intensity sits between U(1) and minimal SU(2). Gordian A+loop: 55.3% divergence geo vs min. Triangle domain: 16.7% divergence.
- 720° periodicity: exact for all axes, including arbitrary unit vectors
- Non-commutativity: ‖[U(σ_z), U(σ_x)]‖ > 0 on multi-axis domain
- All transport matrices verified SU(2): det = 1, U†U = 𝕀
- Antisymmetry A⃗(y,x) = −A⃗(x,y) and transport reversal U(y,x) = U(x,y)† verified

---

### 17. test_greedy_trap.py — IMPORT ERROR ❌

**What it tests:** Greedy controller trapped in A↔C loop, hybrid escapes via amplitude override.

**Status:** Pre-existing import error (missing dependency or circular import). Does not affect other tests. 4 test methods exist in source.

---

### 17. test_minidomain.py — 21 standalone tests

**Runner:** `python e0_controller/test_minidomain.py` (not unittest-based)

**What it tests:** Mini-Domain graph structure, tension formula S = Δ·R, coherence C = exp(−S), historization U/F traces with decay ρ, K2 lazy global decay, 7 landscape core functions, oscillation breaking via revisit penalty α, dead-end escalation, failure/success learning, full runs reaching GOAL, K11 tension filtering (s_max, c_min), K12 escalation type detection.

**Key findings:**
- Oscillation A↔C broken when α = 2.0 (revisit cost crosses threshold)
- Dead-end D produces escalation (no neighbors)
- E→F fails: R rises from 0.5 → 2.0+ (hits δ_max = 3.0)
- E→G succeeds: R falls from 0.5 → 0.35
- Lazy decay: u_eff = ρ^gap × u_last
- All 7 core functions verified correct
- K12 escalation types: DEAD_END, FILTERED, EXHAUSTED, REVISIT

---

## How to Run

```bash
# Full unittest suite (549 tests + 1 error)
python -m unittest discover -s e0_controller -p "test_*.py" -v

# Standalone mini-domain (21 tests)
python e0_controller/test_minidomain.py

# Single file
python -m unittest e0_controller.test_gordian_trap -v
```

---

## Maintenance Notes

- When adding a new test file: add a row to the **Overview Table** and a **Per-File Details** section.
- Update `Last verified` date and total count after full regression.
- The 1 pre-existing error (`test_greedy_trap`) is a known import issue, not a test failure.
