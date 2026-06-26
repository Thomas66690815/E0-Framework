# Reliability Memory — the lean core of E₀ for agent builders

A self-contained, ~600-line memory layer that learns **which action is reliable in which
context** from outcomes, and adapts how fast it forgets to the volatility of the domain.

This is the distilled kernel of the [E₀ Framework](https://github.com/Thomas66690815/E0-Framework).
The full framework is ~36k LOC across 81 modules (amplitude/quantum interference, dream-mode
cross-domain transfer, multiverse coupling, perception/UI). **None of that is here.** The
framework's own bootstrap states the design principle that justifies this reduction:

> *"Historization is the dominant mechanism — other features add incremental value."*
> — confirmed 6×, contradicted 0× (E₀ `bootstrap.json`, working principles)

So we keep only the dominant mechanism and the two refinements that make it better than naive
memory: **doubt that decays with staleness** and **forgetting that adapts to volatility**.

---

## 1. Why this matters for a today-agent

An LLM agent picks tools/actions from a system prompt. That prompt is static: it cannot know
that `tool_X` worked reliably last week but started failing today, or that `search→summarize`
is a productive sequence while `search→browse` usually dead-ends. Vector "memory" stores facts
but has no notion of *staleness* or *reliability decay*.

Reliability Memory sits **beside** the model as a sidecar:

```
            ┌─────────────────────────────────────┐
   context  │  agent (LLM)  proposes candidates    │  outcome
   ───────► │                                      │ ───────►
            └──────────┬──────────────▲────────────┘
                       │ recommend()  │ observe()
                       ▼              │
            ┌─────────────────────────────────────┐
            │      Reliability Memory (this)       │
            │  per (context → action) success/     │
            │  failure traces, decay, trust        │
            └─────────────────────────────────────┘
```

1. Before acting, the agent calls `recommend(context, candidates)` → a prior over which
   candidate has historically worked best in this context.
2. After acting, the agent calls `observe(context, action, outcome)` → the trace updates.
3. On cold start (too few observations) `recommend` returns `None` — the agent decides freely
   and the memory simply learns.

The value concentrates in **repetitive, long-running agents** (support, ops, data pipelines,
recurring workflows) where the same context→action pairs are exercised many times. For
genuinely one-shot tasks the memory is empty and adds nothing — that is by design, and it says
so honestly via the cold-start gate.

---

## 2. The model in one screen

Every `(context, action)` pair is an **edge** `e`. Each edge accumulates two decaying traces:

| Term (mainstream)        | E₀ term        | Meaning                                            |
|--------------------------|----------------|----------------------------------------------------|
| success trace `U(e)`     | U / success    | decayed count of successes                          |
| failure trace `F(e)`     | F / failure    | decayed count of failures                           |
| reliability `q(e)`       | trace_quality  | net direction `(U−F)/(U+F)` ∈ (−1, +1)             |
| evidence `m(e)`          | trace_load     | total weight `U+F` ∈ [0, ∞)                         |
| cost `R_eff(e)`          | R_eff          | ranking cost: lower = pick this action             |
| trust `t(e)`             | trust          | how much to believe a stale memory ∈ (0, 1]        |

**Update on each outcome** (decay then inscribe):

```
U(e) ← ρ · U(e) + w · 1[success]
F(e) ← ρ · F(e) + w · 1[failure]
```

`ρ` (0.9) is the decay: 1.0 = perfect memory, 0.0 = instant forget. `w` is the inscription
weight (normally 1.0; halved to 0.5 for *surprises* — see §3).

**Correction and cost.** Successes lower an action's cost, failures raise it:

```
penalty(e) = clip( λ_f · F(e) − λ_s · U(e),  −δ_max, +δ_max )      # E₀: δ_H
R_eff(e)   = base_cost(e) + penalty(e) · trust(e)                  # base_cost default 0.3
```

**Ranking.** Among candidates from the current context, pick the one with the lowest
`cost = Δ · R_eff` (with `Δ` a per-edge difficulty, default 0.5; for pure tool-reliability you
can hold `Δ` constant, which makes ranking depend on `R_eff` alone). Lowest cost = most reliable.

That is the whole engine. Everything below is the two refinements that beat naive memory.

---

## 3. Refinement A — Doubt that decays with staleness (epistemic trust)

A fixed decay rate treats a rock-stable edge and a flaky edge identically. Real reliability is
not just *how often* an action worked but *how consistently the world keeps agreeing*.

On every **revisit** (the edge was seen before, not on the immediately preceding step) the
engine checks whether the new outcome matched the edge's predicted direction (`q > 0` predicts
success). Match = **confirmation**; mismatch = **surprise**.

```
stability(e) = confirmations(e) / (confirmations(e) + surprises(e) + 1)   ∈ [0, 1)
τ_doubt(e)   = τ_base / (1 − stability(e) + ε)         # stable edge → large → slow doubt
trust(e)     = exp( −staleness(e) / τ_doubt(e) )       ∈ (0, 1]
```

`τ_base` is the **median inter-visit interval** — self-calibrated from the agent's own access
pattern, no external parameter. The cost formula multiplies the correction by `trust`, so a
stale-and-flaky edge's learned correction fades toward zero and the action returns to its
neutral base cost: *"I remember this was bad, but I'm no longer sure that's still true."*

Virgin edges and just-visited edges have `trust = 1.0`.

## 3b. Refinement B — Forgetting that adapts to volatility (surprise dampening)

> *"The bridge was full" ≠ "the bridge is bad."*

A single surprising outcome in a volatile domain should not overwrite stable knowledge; in a
stable domain, full-weight learning is correct. The engine measures its own volatility:

```
surprise_rate = Σ surprises / (Σ confirmations + Σ surprises)

classify():  events < 3      → 'exploratory'   (hold)
             surprise_rate<0.3 → 'stable'       (learn at full weight, w=1.0)
             surprise_rate≥0.3 → 'volatile'     (dampen surprises, w=0.5)
```

When `adaptive` is on, the engine flips dampening on/off automatically as the domain's
character reveals itself. This closes the loop: the memory learns *how to learn* from the
domain it is in. (E₀: C186 epistemic trust, C187 surprise dampening, C188 adaptive observation.)

---

## 4. The three things that decide whether this works

These are honest limitations, not marketing. Address them before expecting value.

**1. Outcome signal quality is the crux.** The engine is only as good as the SUCCESS/FAILURE
signal you feed it. Garbage in → garbage memory. Best sources, in order: an explicit
verification/test step > error-vs-no-error > LLM-judge > delayed user feedback. `PARTIAL` exists
as a runtime convenience (`U += 0.5, F += 0.3`) but is **not canonical** — the unresolved
remainder is silently dropped (E₀'s open gap GT-8). Prefer binary outcomes where you can.

**2. The context abstraction makes or breaks learning.** An edge is `(context_id → action)`.
If `context_id` is too fine-grained, nothing is ever revisited and nothing is learned; too
coarse and everything collapses into one undifferentiated node. Start with a small, deliberately
bucketed context (e.g. task-type, not full conversation hash). Inconsistent context naming is
the most common failure mode.

**3. It needs revisits.** Benefit accrues after the same context→action pairs recur many times.
This is why the sweet spot is repetitive production agents, and why the cold-start gate returns
`None` honestly instead of pretending to know.

---

## 5. Integration recipe (MCP sidecar)

The reference implementation exposes four MCP tools so any MCP-capable agent can use it without
code changes:

- `observe(signal_id, outcome)` — record an aggregate outcome for a step/tool.
- `observe_edge(source, target, outcome)` — record a directed `context → action` outcome.
- `recommend(state, candidates)` — get the best next action, or `null` on cold start.
- `status()` — landscape size, observation count, cold-start flag.

Drop-in loop for a coding agent:

```python
mem = ReliabilityStore.load()                      # persisted JSON, survives restarts
rec = mem.recommend(state, candidates)             # None on cold start → decide freely
action = rec.recommended or agent_choose(candidates)
outcome = run(action)                               # YOUR verification → success/failure
mem.observe_edge(state, action, outcome)           # learn
mem.save()
```

Enable the two refinements with `epistemic_trust=True, adaptive=True`. Defaults
(`ρ=0.9, λ_s=0.15, λ_f=0.20, δ_max=3.0, cold_start=5`) are the framework's validated values.

---

## 6. What was deliberately left out

Dropped from the full framework because it adds complexity without serving the reliability-memory
use case: amplitude/Born/SU(2) interference routing, dream-mode cross-domain transfer, multiverse
coupling & NoveltyGate, structural-entropy pruning, sleep-wake, curriculum, perception/UI,
self-graph metacognition, trajectory/PathSignature. Several are genuinely interesting (NoveltyGate
for multi-agent, PathSignature for loop detection) and can be re-added later as opt-in layers — but
they are not the dominant mechanism, and a lean core that one engineer can read in an afternoon is
worth more for adoption than a complete one nobody finishes reading.

The machine-readable build specification for this core is in `lean_core.bootstrap.json` —
hand it to a coding agent to reconstruct the implementation from scratch.

---

## Appendix — E₀ ↔ mainstream vocabulary

| E₀ canon                  | This document            |
|---------------------------|--------------------------|
| Historization            | Reliability Memory        |
| Landscape / Edge          | context→action graph / edge |
| Outcome (SUCCESS/FAILURE) | outcome                   |
| U / F traces              | success / failure trace   |
| trace_quality `q`         | reliability               |
| trace_load `m`            | evidence                  |
| δ_H                       | penalty / correction      |
| R_eff = R₀ + δ_H          | cost = base_cost + penalty |
| S_eff = Δ · R_eff         | ranking cost              |
| trust(e)                  | trust (staleness-decayed) |
| epistemic_trust (C186)    | doubt that decays         |
| surprise_dampening (C187) | volatility-adaptive forgetting |
| adaptive (C188)           | learning-to-learn loop    |
| ObservationPort           | outcome sensor adapter    |
| cold start (MIN_INSCRIPTIONS) | cold-start gate       |
