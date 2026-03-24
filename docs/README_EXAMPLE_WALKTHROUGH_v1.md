# README Example Walkthrough
## How the hybrid controller avoids a greedy trap

**Purpose:** Provide a minimal, intuitive example that demonstrates the difference between the deterministic controller and the hybrid amplitude-aware controller.

---

## Scenario: Local trap vs coherent forward path

We consider a simple structure:

```text
A → C → A   (loop / trap)
A → B → E → G → GOAL   (forward path)
```

### Local (greedy) view

At state `A`, the deterministic controller evaluates immediate burden:

- `A → C` has lower local cost
- `A → B` has slightly higher cost

So the controller chooses:

```text
A → C
```

This leads into a loop (`A ↔ C`) and delays progress toward the goal.

---

### Amplitude (path-family) view

The amplitude layer evaluates *families of future paths* starting from each action.

- Paths through `C` mostly cycle back and do not build strong forward support
- Paths through `B` continue toward `GOAL` and form a coherent forward family

So the amplitude layer assigns higher support to:

```text
A → B
```

---

### Hybrid decision

In hybrid mode (`AMPLITUDE_ON_DISAGREE`):

- Greedy choice = `C`
- Amplitude choice = `B`

Since they disagree, the controller follows the amplitude-supported action:

```text
A → B → E → G → GOAL
```

---

## Key idea

The difference is not about randomness or heuristics.

- Greedy mode: "choose the cheapest next step"
- Hybrid mode: "choose the step whose future *structure* is strongest"

---

## Why this matters

This simple case generalizes:

- Local minima can trap purely greedy controllers
- Path-family coherence can reveal better long-term structure
- The hybrid controller can correct these cases without abandoning deterministic structure

---

## Takeaway

The hybrid E₀ controller does not replace local reasoning.
It augments it with a second view:

> decisions are evaluated both locally (burden) and globally (coherent future support)

and resolved when they disagree.

---

## End of Section
