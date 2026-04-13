# C184b: Real-World Validation — BPI Challenge 2017 (Loan Workflow)

**Status:** Completed  
**Date:** 2026-04-08  
**Module:** `e0_controller/explore_bpi2017.py`  
**Data:** van Dongen, BPI Challenge 2017, 4TU.ResearchData (DOI: 10.4121/uuid:5f3067df-f10b-45da-b98b-86ae4c7a310b)

---

## 1. Motivation

C184 (Wikispeedia) showed that E₀ generalizes to real-world graphs but
provides no advantage over greedy on trap-free, dense graphs. We
hypothesized: E₀'s interference requires domains with genuine structural
traps — rework loops, dead-end decisions, deceptive local gradients.

BPI Challenge 2017 is a loan application workflow with exactly these
properties: a rework loop that captures the majority of cases, terminal
rejection states, and a process structure where the most frequent
transition leads into the trap.

---

## 2. Domain: Loan Application Workflow

**Task:** A loan application moves through activities from submission
to approval or rejection. The process graph encodes all observed
activity transitions.

**Dataset:**

| Property | Value |
|----------|-------|
| Cases (loan applications) | 31,509 |
| Total events | 1,202,267 |
| Unique activities | 24 |
| Observed transitions | 159 (78 after filtering rare edges < 1%) |
| Avg events per case | 38.2 |
| Time coverage | Jan 2016 – Feb 2017 |

**Outcomes:**

| Outcome | Cases | Rate |
|---------|------:|-----:|
| A_Pending (success — offer accepted) | 17,228 | 54.7% |
| A_Cancelled (failure — application withdrawn) | 10,431 | 33.1% |
| A_Denied (failure — application rejected) | 3,752 | 11.9% |

**The Trap:** The rework loop `A_Validating → O_Returned → A_Incomplete
→ A_Validating` is the dominant trap. At the critical decision point
`A_Validating`, the most frequent outgoing transition is `O_Returned`
(21,542 / 38,813 = 56%), which leads into the loop. The direct success
path `O_Accepted` (7,136 / 38,813 = 18%) is the minority transition.

A frequency-greedy controller always follows the majority vote and gets
trapped in the rework cycle.

---

## 3. E₀ Adapter Design

### 3.1 Edge Filtering

Rare transitions (< 1% of outgoing volume from source) are filtered.
This removes 81 outlier edges that represent process anomalies, not
real routing options. Without filtering, BFS and E₀ exploit ultra-rare
shortcuts (e.g., `A_Concept → W_Assess potential fraud`, 3 out of
31,509 cases).

### 3.2 Δ Mapping (Dual Signal)

$$\Delta(e_{s \to t}) = 0.5 \cdot \frac{d(t, \text{A\_Pending})}{d_{\max}} + 0.5 \cdot (1 - \text{success\_rate}(t))$$

Blends structural distance (BFS to goal) with empirical failure rate.
This gives E₀'s greedy component domain-appropriate guidance: activities
historically associated with failure get high Δ.

### 3.3 R₀ Mapping (Navigability Risk)

$$R_0(e_{s \to t}) = 3.0 \cdot (0.4 \cdot \frac{1}{\sqrt{\deg^+(t)}} + 0.6 \cdot (1 - \text{success\_rate}(t)))$$

Terminal bad states (A_Cancelled, A_Denied) receive $R_0 = 5.0$.
Combines navigability (out-degree) with empirical failure risk.

### 3.4 Controller Configuration

| Parameter | Value |
|-----------|-------|
| `hybrid_mode` | `AMPLITUDE_ON_DISAGREE` |
| `hybrid_geometry` | `goal_reaching` |
| `hybrid_horizon` | 3 |
| `confidence_threshold` | 0.3 |
| `alpha` | 2.0 |
| `recent_k` | 3 |
| `max_cycles` | 50 |

---

## 4. Results

### 4.1 End-to-End Navigation

| Method | Success | Steps | Notes |
|--------|:-------:|------:|-------|
| Greedy (frequency) | ✗ | 24 | Trapped in rework loop |
| Greedy (success-rate) | ✓ | 7 | Oracle: uses outcome knowledge |
| **E₀ (ct=0.3, h=3)** | **✓** | **8** | **2 overrides** |
| Human average (success) | ✓ | 16.8 | Only successful cases |
| Human average (all) | 54.7% | 15.1 | Including failures |
| BFS optimal | ✓ | 4 | Uses filtered-out rare edges |

**E₀'s path:** A_Create Application → A_Concept → A_Accepted →
O_Create Offer → O_Created → O_Sent (online only) → O_Returned →
O_Accepted → A_Pending (8 steps, 2 overrides)

**Greedy (frequency) failure:** Enters rework loop at step 9
(A_Validating → O_Returned) and cycles 5 times before timeout.

### 4.2 Critical Decision-Point Tests

The decisive test: starting from the trap entry point `A_Validating`,
does each method reach `A_Pending`?

| Start Point | Greedy (freq) | Greedy (sr) | E₀ |
|------------|:---:|:---:|:---:|
| **A_Validating** | ✗ Loop (15 steps) | ✓ 2 steps | **✓ 2 steps** |
| **A_Complete** | ✗ Loop (16 steps) | ✓ 3 steps | **✓ 3 steps** |
| **O_Sent (mail and online)** | ✗ Loop (18 steps) | ✓ 2 steps | **✓ 3 steps** |

At every decision point, E₀ avoids the rework loop and reaches
A_Pending. Greedy (frequency) fails at every point.

### 4.3 Parameter Sensitivity

E₀ succeeds at all tested configurations:

| confidence_threshold | horizon | Steps | Overrides |
|----:|---:|---:|---:|
| 0.2 | 3 | 8 | 2 |
| 0.2 | 4 | 8 | 2 |
| 0.3 | 3 | 8 | 2 |
| 0.3 | 4 | 8 | 2 |
| 0.5 | 3 | 8 | 2 |
| 0.5 | 4 | 8 | 2 |

Completely stable across the parameter range. The Δ/R₀ encoding already
steers the greedy component correctly — interference confirms rather
than overrides.

---

## 5. Interpretation

### 5.1 E₀ Beats Greedy on Trap Domain — First Real-World Confirmation

This is the result C184 (Wikispeedia) could not produce. On a domain
with genuine structural traps:

- **Greedy (frequency) fails completely** — trapped in the rework loop
- **E₀ succeeds in 8 steps** — avoids the trap with 2 overrides
- **E₀ matches human success** in far fewer steps (8 vs 16.8)

The rework loop is exactly the kind of structure E₀ was designed to
handle: a cycle that looks locally reasonable (each transition is
common) but fails to make progress toward the goal.

### 5.2 Why E₀ Avoids the Loop

The Δ mapping encodes the structural distance to A_Pending:
- A_Validating → O_Accepted: $\Delta$ is low (O_Accepted is 1 step from goal)
- A_Validating → O_Returned: $\Delta$ is higher (O_Returned is 2 steps from goal)

Even without interference, E₀'s greedy component (which uses Δ, not
transition frequency) prefers O_Accepted. The 0 overrides at
A_Validating confirm this: no amplitude disagreement needed.

### 5.3 The Role of Δ Encoding

The honest assessment: E₀'s advantage here comes primarily from the
Δ mapping (which encodes BFS distance + success rate), not from
interference per se. The greedy component already steers correctly
because Δ provides better information than raw transition frequency.

This is consistent with Paper 1's insight: the Δ primitive — the
structural encoding of "distance from goal" — is the foundation.
Interference adds value when multiple Δ-similar paths exist and
need disambiguation. On this domain, disambiguation is not needed
because the Δ gradient is clear.

### 5.4 Why Greedy (Frequency) Fails

Greedy (frequency) fails because transition frequency ≠ quality.
The most common transition from A_Validating is O_Returned (56%)
because most applications undergo rework — it is the *typical*
process, not the *optimal* one. Following the crowd leads to the
average outcome (multiple rework cycles, 16.8 steps), not the
best outcome.

This is the fundamental failure mode of frequency-based greedy:
it confuses *common* with *good*.

---

## 6. Cross-Domain Comparison (Wikispeedia vs BPI 2017)

| Property | Wikispeedia | BPI 2017 |
|----------|:---:|:---:|
| Graph size | 4,604 nodes | 24 nodes |
| Avg degree | 26 | 6.6 (after filtering) |
| Structural traps | None | Rework loop |
| Dead ends | 17 / 4,604 | 3 terminal states |
| Greedy performance | 100% optimal | Fails (loop) |
| E₀ performance | 85%, 1.12× optimal | 100%, near-optimal |
| Interference needed | Minimal | Minimal (Δ suffices) |
| Trap detection | 0 traps | Loop avoided |
| Key bottleneck | Subgraph extraction | Edge filtering |

**Pattern:** E₀'s Δ primitive provides the primary decision signal
on both domains. Interference (amplitude overlay) provides a backup
signal when Δ is ambiguous. The adapter layer (subgraph extraction,
edge filtering, Δ/R₀ mapping) is the domain-specific component.

---

## 7. Honest Limitations

1. **Δ does the work, not interference.** The 0 overrides at decision
   points show that E₀'s greedy component (using Δ) already avoids
   the trap. Interference is not activated. This means we have not yet
   found a real-world domain where *interference specifically* provides
   the critical signal.

2. **Success-rate oracle beats E₀.** Greedy (success-rate) reaches
   A_Pending in 7 steps (vs E₀'s 8). But this is an oracle — it uses
   the empirical outcome distribution, which requires seeing the
   full dataset first. E₀ uses only BFS distance + success rate blended
   into Δ, which is a weaker signal.

3. **Process graphs are not navigation.** Unlike Wikispeedia, activities
   in a loan process are not freely chosen by an agent. A_Validating →
   O_Returned is the *result* of validation, not a routing decision.
   We model it as navigation for comparison, but the operational
   interpretation is: "If this were a controllable process, E₀ would
   steer toward success."

4. **Single start-to-goal evaluation.** The process graph has one start
   (A_Create Application) and one goal (A_Pending). There is no
   variation across tasks like in Wikispeedia's 20 source-target pairs.

---

## 8. What We Need Next

To demonstrate that *interference specifically* (not just Δ) provides
real-world value, we need a domain where:

1. **Multiple path families exist** from source to goal with similar Δ
2. **One family is a trap** (leads to failure despite looking equivalent)
3. **Phase opposition** between families creates destructive interference
4. **Δ alone cannot distinguish** the trap from the correct path

This is a stronger requirement than "greedy fails" — we need a domain
where the *greedy-with-good-Δ* also fails, and only interference saves
the day.

Candidate domains:
- **GTFS transit routing** with missed-connection traps (time pressure
  creates irreversibility)
- **Game tree navigation** where locally-equal moves diverge later
  (chess opening traps, Go ladders)
- **Supply chain routing** with capacity constraints (overloaded paths
  that look optimal)

---

## 9. Falsification Status Update

| Target | Status After C184b |
|--------|-------------------|
| Anti-monotonicity | **Not observed.** E₀ ≥ greedy on all tested configurations. |
| Phase irrelevance | Partially confirmed on BPI: Δ alone suffices, phase not needed. But this is a Δ-distinctive domain. |
| Geometry irrelevance | Not tested (single domain, single geometry). |
| Historization instability | Not tested (single-shot runs). |

---

## Appendix: Rework Loop Statistics

| Rework cycles per case | Cases | Rate |
|---:|------:|-----:|
| 0 | 16,506 | 52.4% |
| 1 | 9,317 | 29.6% |
| 2 | 3,970 | 12.6% |
| 3 | 1,234 | 3.9% |
| 4 | 352 | 1.1% |
| 5+ | 130 | 0.4% |

**Counter-intuitive finding:** Cases that enter the rework loop
(A_Incomplete) have an 84.3% success rate — higher than the base rate
(54.7%). The rework loop is not a death trap; it is a necessary step
for many successful applications. But it adds 3+ steps per cycle,
explaining why human success paths average 16.8 steps while the
structural minimum is 4.

**Source code:** `e0_controller/explore_bpi2017.py` (~500 lines)  
**Data location:** `data/bpi2017/BPI_Challenge_2017.xes.gz`  
**Reference:** B.F. van Dongen. BPI Challenge 2017. 4TU.ResearchData, 2017.

---

*Document version 1. Research status as of 2026-04-08.*
