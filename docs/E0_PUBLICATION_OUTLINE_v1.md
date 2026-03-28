# E₀ Publication Outline v1

**Status:** Draft blueprint for a scientific paper**  
**Date:** 2026‑03‑25**  
**Purpose:** Provide the structure, key claims, and honesty checklist for a first formal publication covering the current E₀ system (theory → implementation → empirical results → open gaps).  
**Scope:** High-level outline only; actual manuscript still to be written.

---

## 1. Working title

> **“E₀: A Structural Transition Framework With Hybrid Path-Family Control”**

Alternate subtitle: *“From Transcendental Difference to Executable Hybrid Controllers in LLM-integrated Systems.”*

---

## 2. Proposed paper structure

1. **Abstract**  
   - 150–200 words summarising: primitives, deterministic controller, amplitude layer, hybrid mode, empirical evidence, open questions.

2. **Introduction**  
   - Motivation (structural decision layer, beyond greedy local heuristics).  
   - Contributions bullet list.  
   - Honest scope statement (what is derived vs empirical).

3. **Related Work**  
   - Brief comparison to: reinforcement learning, amplitude-based planners, structural controllers, spinor/topological discussions.

4. **Theory (Canon)**  
   - Primitives (S, Δ, P, R, H, τ, v).  
   - Axiom A₀ and Central Law.  
   - Derived chain Δ → R₀ → H → δ_H → R_eff → S → C → Φ → v_rot → ω → Θ → Ψ.  
   - Clarify difference between sediment/state and historisation.

5. **Implementation Layer**  
   - Deterministic controller (burden minimisation, historisation, escalation).  
   - MemOS (persistence, snapshots).  
   - Evaluation & Reflection (A–F ratings, triggers).

6. **Amplitude & Summation Geometry**  
   - Definition of Ψ(p) = exp(-S) exp(iΘ).  
   - Summation geometries (prefix, simple, first_arrival) with reproducible scripts.  
   - Evidence for choosing `simple` as operational default (with caveat: not yet derived).

7. **Hybrid Controller**  
   - GREEDY vs AMPLITUDE_ON_DISAGREE.  
   - Arbitration rules, safety conditions, metrics (override count/rate, trap escapes).  
   - Link to demos / MemOS logging.

8. **Empirical Evaluation**  
   - Trap-escape demo, invoice domain, cross-domain validation.  
   - Summation geometry experiments, amplitude overlay results.  
   - Metrics table summarising runs.  
   - Derived/Empirical/Heuristic map referenced to keep claims honest.

9. **Open Issues & Falsification Targets**  
   - Phase derivation from v_rot.  
   - Formal proof of summation geometry minimality.  
   - Scalability of amplitude enumeration.  
   - Spinor/topological hypotheses.  
   - Specific experiments that would falsify current claims.

10. **Discussion**  
    - Implications for LLM steering, structural decision layers.  
    - Connection to Claude convergence event (structural attractor).  
    - Limitations (no probabilistic guarantees, bounded horizons, heuristics).

11. **Conclusion & Future Work**  
    - Summarise takeaways.  
    - Outline roadmap (phase derivation, spinor tests, automated benchmarks).

12. **Appendices**  
    - Canon text (short).  
    - Implementation references (Git commit, tests).  
    - Additional data from summation geometry & hybrid logs.

---

## 3. Honesty checklist

Before submission, confirm that:

- Derived vs Empirical vs Heuristic classification is explicitly stated (use the existing map as a figure/table).  
- All experiments are reproducible (scripts + seeds + dataset references).  
- Open questions are not downplayed (Phase, Geometry, Scaling, Spinor).  
- Evidence includes failure cases / limitations where appropriate.  
- External availability (code, docs, test registry) is cited.

---

## 4. Needed artefacts per section

| Section | Source / Status |
|---------|-----------------|
| Theory | `docs/E0_FORMAL_PAPER_DRAFT_v1.md`, Canon files |
| Implementation | `README`, `controller.py`, `memory_os.py`, `evaluation.py`, `reflection.py` |
| Geometry experiments | `docs/E0_SUMMATION_GEOMETRY_COMPARISON_v1.md`, `E0_SUMMATION_GEOMETRY_RESULTS_v1.txt` |
| Hybrid spec | `docs/E0_HYBRID_CONTROLLER_SPEC_v1.md`, `E0_CODE_ANALYSIS_2026-03-24.md` |
| Evidence section | `docs/E0_EVIDENCE_AND_FALSIFICATION_STATUS_v1.md`, MemOS logs |
| Honesty map | `docs/E0_DERIVED_EMPIRICAL_HEURISTIC_MAP_v1.md` |
| Tests appendix | `docs/E0_TEST_REGISTRY_v1.md`, `test_*.py` suites |

---

## 5. Immediate next steps toward the manuscript

1. Draft the introduction + contributions list.  
2. Integrate Derived/Empirical/Heuristic table as a central figure.  
3. Collect empirical results into reproducible tables/plots (trap escapes, override rates, geometry comparisons).  
4. Write explicit “Limitations & Falsification” section.  
5. Set up repository tag or branch for publication snapshot.

---

_End of outline._
