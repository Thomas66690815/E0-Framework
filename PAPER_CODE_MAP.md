# Paper to Code Mapping (Draft)

This document provides a direct mapping between conceptual elements in the E₀ manuscripts and their implementation in the repository.

It is intended to help reviewers and developers quickly connect formal definitions to executable components.

---

## 1. Paper 1 — Structural Interference Layer

| Concept (Paper) | Implementation (Repo) |
|---|---|
| Transition graph Δ | Graph / domain definitions in benchmark modules |
| Resistance R | Resistance computation utilities |
| Historization H | State / history update mechanisms |
| Potential Φ | Landscape construction modules |
| Gradient / flow fields | Controller / landscape evaluation |
| Connection ω | Connection / phase modules |
| Phase Θ | Phase accumulation logic |
| Path amplitude | Amplitude evaluation functions |
| Path summation | Summation / aggregation logic |
| Interference | Emergent in amplitude aggregation |
| Controller decision (argmax / hybrid) | Controller modules |
| Multi-goal aggregation | Multi-goal logic in controller |

---

## 2. Paper 2 — Spinor Extension

| Concept (Paper) | Implementation (Repo) |
|---|---|
| U(1) transport | Scalar connection / phase modules |
| SU(2) transport | `spinor_connection.py` |
| Spinor amplitude | Spinor amplitude functions |
| Phase halving | SU(2) mapping logic |
| Non-commutativity | Pauli matrix / ordering-sensitive logic |
| Born normalization | Probability / normalization utilities |

---

## 3. Tests as Operational Anchors

For both papers, tests serve as the operational grounding of claims.

Examples:
- Gordian tests → trap / escape behavior
- G5 tests → multi-goal distribution
- Interference tests → constructive / destructive behavior
- Spinor tests → phase halving, non-commutativity

Refer to `E0_TEST_REGISTRY_v2.md` for detailed claim-to-test mapping.

---

## 4. Notes

- This mapping is approximate and may evolve as the codebase changes.
- The goal is orientation, not formal completeness.
- For precise behavior, consult both the implementation and associated tests.
