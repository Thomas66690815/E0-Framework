# E₀ Framework — Scientific Overview (Draft)

## Purpose

This document provides a concise scientific entry point to the E₀ Framework repository. It is intended for reviewers, researchers, and technically oriented readers who want a minimal, publication-facing overview of the repository without the broader narrative framing of the main `README.md`.

## Repository Scope

The repository contains:

- a formal and operational implementation of the E₀ framework for discrete transition systems,
- hybrid controller logic based on structural amplitudes,
- benchmark and validation domains,
- a test registry linking claims to evidence,
- an SU(2) / spinor extension corresponding to the second manuscript.

The repository should be read as a research artifact, not as a production software package.

## Core Research Claims

At a high level, the repository supports investigation of the following claims:

1. Structural amplitudes can be derived on directed transition graphs from difference, resistance, and historization.
2. Interference between path families can expose structural traps that are not detected by greedy local control.
3. Summation geometry is a first-order design variable for amplitude-based control.
4. A spinor lift from U(1) to SU(2) becomes structurally motivated when internal difference requires non-abelian transport.
5. Born-style normalization can be justified as a minimal rule under bounded exclusive realization.

Claim status is not uniform. The project explicitly distinguishes:

- **Derived**: follows from the stated structural chain,
- **Empirical**: supported by experiments or tests,
- **Open / Heuristic**: operationally motivated but not yet fully derived.

For the detailed mapping, see `E0_TEST_REGISTRY_v2.md`.

## Repository Components

Representative components include:

- `e0_controller/` — core implementation of the E₀ controller stack
- controller and amplitude modules — local greedy, hybrid arbitration, and amplitude evaluation
- benchmark domains — Gordian, Diamond, G5, workflow-style and related topologies
- `spinor_connection.py` — SU(2) transport and spinor amplitude extension
- test suite — unit and structural tests used to validate implementation-level claims
- `E0_TEST_REGISTRY_v2.md` — claim-to-test and claim-to-status mapping

## Reproducibility Summary

The repository is structured so that main implementation claims can be inspected through:

1. source modules,
2. explicit benchmark definitions,
3. a test suite,
4. a registry mapping claims to evidence.

Main test invocation:

```bash
python -m unittest discover -s e0_controller -p "test_*.py"
```

This command should be interpreted as a verification entry point, not as a substitute for reading the claim/status distinctions in the registry.

## What This Repository Does Not Claim

This repository does **not** by itself establish:

- real-world deployment validity,
- universal superiority over standard planning or learning methods,
- a complete physical theory,
- a resolved measurement theory,
- a final or unique formulation of every geometric lifting used in the SU(2) extension.

## Recommended Reading Order

1. `README.md` — broad conceptual and operational context
2. `README_SCIENTIFIC.md` — concise scientific framing
3. `E0_TEST_REGISTRY_v2.md` — claim/evidence map
4. Paper 1 manuscript — structural interference on discrete transition systems
5. Paper 2 manuscript — spinor amplitudes and the Born criterion

## Notes on Authorship and Cognitive Contribution

This repository documents work developed in close Human–AI collaboration. In the publication context, the exact wording around authorship, co-design, or synthetic contribution may need to vary by venue, because academic norms currently differ.

The project itself takes the position that high-level structural synthesis across multiple technical domains can emerge through sustained Human–Synthetic Cognitive Partnership. That position is part of the broader research context, but should be distinguished from venue-specific authorship policy.
