# E₀ Evidence & Falsification Status v1

**Status:** Working note  
**Date:** 2026-03-24  
**Purpose:** Summarise what has been empirically demonstrated in the current hybrid architecture, what remains unproven, and how the present claims could be falsified.  
**Scope:** Covers deterministic controller, amplitude/summation layer, and hybrid arbitration.

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

---

## 2. Partial evidence / open questions

| Topic | Current status | Needed for closure |
|-------|----------------|--------------------|
| Phase derivation (`Θ` from `v_rot`) | Partially derived, operationally heuristic | Formal proof + regression tests |
| Born-style interpretation (I=|Ψ|²) | Operationally useful, not universally proven | Domain-independent derivation or counterexample |
| Summation geometry minimality | Simple geometry empirically best, not proven necessary | Proof that other geometries violate constraints or fail tests |
| Amplitude scaling to large branching factors | Only tested on bounded enumerations | Algorithmic optimisation or proof of limits |
| Inline Verdichtungssnapshots (Claude thread) | Observed, not yet formalised | Mapping to MemOS structures |

---

## 3. Active falsification targets

The following experiments or findings would falsify the current runtime claims:

1. **Hybrid failure cases:** Demonstrate a scenario where AMPLITUDE_ON_DISAGREE consistently performs worse than GREEDY despite accurate amplitude computation.
2. **Geometry contradiction:** Produce a domain where the preferred `simple` geometry yields inconsistent endpoint ordering against direct enumeration.
3. **Phase irrelevance:** Show that varying `Θ` does not change interference outcomes when the rest of the setup is held constant.
4. **MemOS persistence gap:** Recover a hybrid snapshot and show that overrides or phase data are missing/inaccurate.
5. **Evaluation blind spots:** Find a run where the evaluation layer rates an obviously failed hybrid execution as `A` or `B`.

If any of these occur, the respective layer must be revisited or downgraded in the Derived/Empirical/Heuristic map.

---

## 4. Recommended next experiments

1. **Automated trap benchmark:** Batch-run the hybrid controller on synthetic trap graphs with different branching factors, logging override success rate.
2. **Phase perturbation test:** Inject controlled phase shifts into path families and confirm predicted interference changes.
3. **Geometry stress test:** Re-run summation comparison on randomly generated landscapes to ensure `simple` remains stable.
4. **Hybrid persistence replay:** Load a MemOS snapshot mid-run and continue execution to confirm identical hybrid decisions.
5. **Evaluation regression:** Expand `e0_controller/test_evaluation.py` with hybrid-specific edge cases (e.g., high override count but low efficiency).

---

## 5. Reporting commitments

- Each new milestone must update this document with fresh evidence and revised falsification targets.
- When a claim moves from “partial” to “demonstrated”, link the corresponding tests or datasets.
- If a falsification event occurs, document it here before changing code.

---

_End of document._
