# E₀ Evidence & Falsification Status v1

**Status:** Working note  
**Date:** 2026-03-24 (updated: Phase 3q results)  
**Purpose:** Summarise what has been empirically demonstrated in the current hybrid architecture, what remains unproven, and how the present claims could be falsified.  
**Scope:** Covers deterministic controller, amplitude/summation layer, hybrid arbitration, and interference routing.

---

## 1. Demonstrated evidence (2026-03-24)

| Claim | Evidence | Artefact |
|-------|----------|----------|
| Greedy traps exist in bounded domains | `demo_greedy_trap`, `test_phase2_minidomain` | `e0_controller/test_phase2_minidomain.py` |
| Amplitude overlay reproduces constructive/destructive interference | `docs/E0_SUMMATION_GEOMETRY_RESULTS_v1.txt`, `explore_amplitude.py` | Summation geometry program |
| Simple summation geometry reduces path inflation vs prefix | `docs/E0_SUMMATION_GEOMETRY_COMPARISON_v1.md` | Empirical comparison runs |
| Hybrid overrides occur and escape traps | `demo_greedy_trap --hybrid`, `demo_invoice_llm --hybrid` | MemOS run logs (`hybrid_override_count`) |
| Hybrid metrics remain bounded/stable | `e0_controller/evaluation.py` (A/B ratings, override rate) | Validation runs |
| MemOS persists hybrid state (landscape + overrides) | `test_memory_os.py`, hybrid demo runs | Snapshot diff |
| **Holonomy independence: ΔΘ from forward edges only** | **Proven analytically + verified to 6 decimal places** | `test_gordian_trap.py::TestHolonomyFormula` |
| **Destructive interference suppresses greedy-preferred path** | **factor = 0.02 (98% cancellation)** | `test_gordian_trap.py::TestPathLevelInterference` |
| **Goal-reaching geometry (G5) resolves prefix inflation** | **P(B1) = 96.2% under G5 vs P(A1) dominant under simple** | `test_gordian_trap.py::TestOverlayGoalReaching` |
| **Hybrid override via interference routing** | **Greedy A1 → Override B1, path = START→B1→B2→GOAL** | `test_gordian_trap.py::TestHybridOverride` |
| **Negative control: simple geometry does NOT override** | **simple still picks A1 (prefix dominance confirmed)** | `test_gordian_trap.py::TestSimpleGeometryNoOverride` |
| **Horizon-dependent interference onset** | **h=3: A1 wins (loop invisible); h=5: B1 wins** | `test_gordian_trap.py::test_h3_a1_wins`, `test_h5_b1_wins` |
| **Scaling to n=500 states** | **14 tests, pure E₀ evaluation, canonical backward deltas** | `e0_controller/test_scaling.py` |
| **LLM integration round-trip** | **24 live API tests** | `e0_controller/test_llm_integration.py` |

---

## 2. Partial evidence / open questions

| Topic | Current status | Needed for closure |
|-------|----------------|--------------------|
| Phase derivation (Θ from v_rot) | Partially derived, operationally heuristic. Holonomy independence strengthens v_rot's role. | Formal proof + regression tests |
| Born-style interpretation (I=|Ψ|²) | Operationally useful; G5 provides Born-aligned geometry | Domain-independent derivation or counterexample |
| Summation geometry minimality | Simple empirically best for exploration; G5 proven for goal semantics | Proof that geometries are non-interchangeable (partially done: Gordian Trap shows simple fails where G5 succeeds) |
| Amplitude scaling to large branching factors | Scaling tests pass at n=500, but path enumeration is O(paths) | Algorithmic optimisation or proof of limits |
| Inline Verdichtungssnapshots (Claude thread) | Observed, not yet formalised | Mapping to MemOS structures |
| **Interference stability under historization** | **Confirmed (12 tests)** — 4 scenarios (repeated, adversarial A-short/A-loop, mixed); cos(ΔΘ) stays < 0 in all cases; three structural stability mechanisms identified | RESOLVED |
| **Multi-goal behavior under G5** | **Untested** | How does G5 superpose paths to different goals? |
| **Spinor extension (Θ → SU(2))** | **Theoretical (3 documents)** | Lift scalar Θ to SU(2) generator; test on Gordian Trap |
| **Topology classification** | **Open** | Which graph structures admit interference-based routing? |

---

## 3. Active falsification targets

The following experiments or findings would falsify the current runtime claims:

1. **Hybrid failure cases:** Demonstrate a scenario where AMPLITUDE_ON_DISAGREE consistently performs worse than GREEDY despite accurate amplitude computation.
2. **Geometry contradiction:** Produce a domain where the preferred `simple` geometry yields inconsistent endpoint ordering against direct enumeration.
3. **Phase irrelevance:** Show that varying Θ does not change interference outcomes when the rest of the setup is held constant. *(Note: Phase 3q provides strong counter-evidence — Gordian Trap interference is entirely phase-driven.)*
4. **MemOS persistence gap:** Recover a hybrid snapshot and show that overrides or phase data are missing/inaccurate.
5. **Evaluation blind spots:** Find a run where the evaluation layer rates an obviously failed hybrid execution as `A` or `B`.
6. **Holonomy independence violation:** Find a topology where ΔΘ between two paths depends on edges outside both paths. *(Note: theorem says this cannot happen. A counterexample would require fixing the proof.)*
7. **G5 false positive:** Find a topology where goal_reaching geometry overrides greedy to a *worse* action — i.e., the coherent path is structurally inferior to the greedy choice despite higher amplitude support.
8. **Historization breaks Gordian:** ~~Run the Gordian Trap with accumulating historization and show the interference effect degrades or inverts.~~ **TESTED — interference survives.** 12 formal tests confirm stability under repeated, adversarial, and mixed historization. Target remains: can extreme historization (δ_max ≫ R₀) eventually break it?

If any of these occur, the respective layer must be revisited or downgraded in the Derived/Empirical/Heuristic map.

---

## 4. Recommended next experiments

1. **Automated trap benchmark:** Batch-run the hybrid controller on synthetic trap graphs with different branching factors, logging override success rate.
2. **Phase perturbation test:** Inject controlled phase shifts into path families and confirm predicted interference changes. *(Partially addressed by holonomy formula verification.)*
3. **Geometry stress test:** Re-run summation comparison on randomly generated landscapes to ensure `simple` remains stable.
4. **Hybrid persistence replay:** Load a MemOS snapshot mid-run and continue execution to confirm identical hybrid decisions.
5. **Evaluation regression:** Expand `e0_controller/test_evaluation.py` with hybrid-specific edge cases.
6. **Historization × Gordian:** ~~Run Gordian Trap with `history_mode=True`.~~ **DONE** (commit 551ab80). Next: test extreme δ_max ≫ R₀ regime.
7. **Multi-goal Gordian:** Add a second GOAL node, test G5 behavior with competing goal states.
8. **SU(2) pilot:** Implement matrix-valued Ψ on Gordian Trap, compare interference predictions with scalar model.
9. **Random topology scan:** Generate random graphs, identify those where G5 overrides greedy, verify override quality.

---

## 5. Reporting commitments

- Each new milestone must update this document with fresh evidence and revised falsification targets.
- When a claim moves from “partial” to “demonstrated”, link the corresponding tests or datasets.
- If a falsification event occurs, document it here before changing code.

---

_End of document._
