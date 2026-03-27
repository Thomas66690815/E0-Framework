# E₀: A Structural Transition Framework With Hybrid Path-Family Control

**Draft manuscript — work in progress**  
**Date:** 2026‑03‑25  
**Status:** Section headings + initial text stubs; to be expanded step by step.

---

## Abstract (to be written last)

> *Placeholder*: Summarise primitives, controller, amplitude layer, hybrid mode, empirical evidence, open issues.

---

## 1. Introduction

*Goal:* Motivate structural decision-making beyond greedy local rules; highlight contributions; state honesty pledge (derived vs empirical vs heuristic).

**1.1 Motivation**  
*(text TBD)*

**1.2 Contributions**  
- TBD bullet list (theory, implementation, empirical, reflection of limitations).

**1.3 Scope & Honesty Statement**  
- Derived/Empirical/Heuristic classification; explicit statement referencing `docs/E0_DERIVED_EMPIRICAL_HEURISTIC_MAP_v1.md`.

---

## 2. Related Work

Brief pointers to reinforcement learning, structural controllers, amplitude-based planning, spinor/topological analogies. *(text TBD).*

---

## 3. Theory (Canonical Layer)

**3.1 Primitives and Axiom A₀**  
- Define S, Δ, P, R, H, τ, v; state Axiom A₀ and Central Law.

**3.2 Derived Dependency Chain**  
`Δ → R₀ → H → δ_H → R_eff → S → C → Φ → v_rot → ω → Θ → Ψ`.  
Explain each arrow succinctly.

**3.3 Interpretation (State vs Historisation)**  
- Clarify difference between sediment and irreversible transition landscape.

---

## 4. Implementation Layer

**4.1 Deterministic Controller** — burden minimisation, historisation, escalation.  
**4.2 MemOS** — persistence, snapshots, hybrid params.  
**4.3 Evaluation & Reflection** — scoring, ratings, trigger logic.

---

## 5. Amplitude & Summation Geometry

**5.1 Path amplitude definition** — `Ψ(p)=exp(-S(p))exp(iΘ(p))`.  
**5.2 Summation geometries** — prefix vs simple vs first_arrival; summarise empirical findings (`docs/E0_SUMMATION_GEOMETRY_COMPARISON_v1.md`).  
**5.3 Limitations** — Θ not fully derived, enumeration complexity.

---

## 6. Hybrid Controller

**6.1 Modes** — GREEDY vs AMPLITUDE_ON_DISAGREE.  
**6.2 Arbitration & Safety** — spec requirements.  
**6.3 Metrics** — override count/rate, agreement, trap escapes; instrumentation details.

---

## 7. Empirical Evaluation

**7.1 Trap benchmark** — demo + metrics.  
**7.2 Domain case studies** — invoice, research brief, incident postmortem.  
**7.3 Summation geometry comparison results.**  
**7.4 Hybrid metrics summary.**

---

## 8. Open Issues & Falsification Targets

List from `docs/E0_EVIDENCE_AND_FALSIFICATION_STATUS_v1.md`: phase derivation, geometry proof, scaling, spinor, Verdichtungssnapshots. Include experiments that would invalidate claims.

---

## 9. Discussion

Interpretation, Claude convergence event, implications for LLM steering, limitations.

---

## 10. Conclusion & Future Work

Wrap-up, mention roadmap (phase derivation, spinor tests, automated benchmarks).

---

## Appendices (planned)

- Canon summary (plain-text).  
- Derived/Empirical/Heuristic table.  
- Test registry excerpt + reproducibility instructions.  
- Additional plots/tables (summation geometry, hybrid logs).

---

*This draft will be filled sequentially in future steps.*
