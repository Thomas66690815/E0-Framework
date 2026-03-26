# Claims to Tests Mapping (Draft)

This document provides a compact mapping from major conceptual claims in the E₀ project to the test and evidence structure in the repository.

It is intended as a quick scientific index, complementing the more detailed `E0_TEST_REGISTRY_v2.md`.

---

## 1. Paper 1 — E₀: Structural Interference in Discrete Transition Systems

| Paper 1 claim | Status | Evidence / Test area |
|---|---|---|
| Structural amplitudes can be derived from difference, resistance, and historization | Derived | Core landscape / amplitude tests; registry entries for structural chain |
| Interference occurs under path summation and can be constructive or destructive | Derived | Interference and summation tests |
| Holonomy-dependent phase differences matter operationally | Derived / Empirical interface | Connection / omega / holonomy tests; benchmark domains |
| Greedy local control is vulnerable to structural traps | Empirical | Greedy trap tests; Gordian and related domains |
| Amplitude-based control can escape traps missed by greedy | Empirical | Gordian override tests; hybrid controller tests |
| Summation geometry changes controller outcomes materially | Empirical | Geometry comparison tests; goal-reaching vs simple geometry |
| Goal-reaching geometry is necessary in trap domains | Empirical | Gordian geometry tests; topology scan |
| Multi-goal aggregation produces rescue / redistribution effects | Empirical | G5 multi-goal tests |
| Historization modifies future control behavior | Derived / Empirical | Historization update tests; stability scenarios |
| Path-family count and phase opposition predict usefulness of interference | Empirical | Topology classification scan |
| Scaling behavior is only partially established | Partial / Open | Registry marks scaling as partial |
| LLM integration exists operationally but is not a core theoretical claim | Partial | Registry marks LLM coupling as partial |

---

## 2. Paper 2 — E₀-II: Spinor Amplitudes and the Born Criterion

| Paper 2 claim | Status | Evidence / Test area |
|---|---|---|
| Internal difference forces a non-abelian carrier beyond U(1) | Derived | Carrier minimality argument; manuscript + algebraic support |
| SU(2) on C^2 is the minimal faithful non-abelian carrier | Derived | Carrier minimality section |
| 720° periodicity follows from SU(2) transport | Derived | Periodicity tests |
| Magnitude consistency between U(1) and SU(2) holds on single paths | Derived | Single-path magnitude tests |
| Phase halving changes interference behavior | Derived | Phase-halving tests |
| Non-commutativity makes path order structurally significant | Derived | Pauli / non-commutativity tests |
| Spinor interference exists analogously to scalar interference | Derived | Spinor interference tests |
| Born normalization is justified under bounded exclusive realization | Derived (conditional) | Born criterion tests + theorem assumptions |
| U(1) and SU(2) can produce different decisions | Empirical | Gordian decision-flip tests |
| Geometric coupling can diverge from minimal embedding | Empirical | Geometric coupling / divergence tests |
| Geometric lifting is admissible but not unique | Open / structural | Manuscript limitation + future work |
| SU(2) topology classification remains incomplete | Open | Marked open in manuscript / registry |

---

## 3. Recommended Reading Order for Verification

1. `README_SCIENTIFIC.md`
2. `E0_TEST_REGISTRY_v2.md`
3. Paper 1 manuscript
4. Paper 2 manuscript
5. Test files corresponding to the relevant claim family

---

## 4. Notes

- This file is intentionally compact.
- It is not a substitute for the full registry.
- Where the status says *Derived*, this means derived **within the framework’s stated assumptions**.
- Where the status says *Empirical*, this means supported by benchmark or test evidence in the repository, not analytically universal.
