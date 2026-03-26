# Reproducing Core Results (Draft)

This document provides the shortest path to reproduce the main operational claims of the E₀ framework.

## 1. Setup

Ensure Python environment is active (version used in development recommended).

Install dependencies if required (see repository setup).

## 2. Run Full Test Suite

```bash
python -m unittest discover -s e0_controller -p "test_*.py"
```

Expected outcome:
- All tests pass
- Confirms structural correctness of core implementation

## 3. Key Phenomena to Verify

### 3.1 Greedy Trap vs Amplitude Escape

Relevant tests:
- Gordian trap tests

Expected behavior:
- Greedy fails
- Amplitude-based controller escapes

---

### 3.2 Interference Effects

Relevant tests:
- interference / summation tests

Expected behavior:
- Constructive and destructive interference observed

---

### 3.3 Multi-goal Behavior

Relevant tests:
- G5 domain tests

Expected behavior:
- Distribution across goals (Born mode)
- Lock-in (argmax mode)

---

### 3.4 Spinor Extension (Paper 2)

Relevant tests:
- SU(2), phase halving, non-commutativity

Expected behavior:
- Phase halving effect observable
- Decision flip in Gordian domain

---

## 4. Mapping to Papers

| Phenomenon | Paper |
|-----------|------|
| Interference control | Paper 1 |
| Trap escape | Paper 1 |
| Multi-goal behavior | Paper 1 |
| Spinor lift (SU(2)) | Paper 2 |
| Born normalization | Paper 2 |

## 5. Notes

- This is a minimal operational path.
- For full claim mapping, see `E0_TEST_REGISTRY_v2.md`.
- For theoretical context, see manuscripts.
