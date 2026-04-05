# E0 Human Communication Design v1

**Status:** Concept note — architectural vision
**Date:** 2026-04-05
**Scope:** C158–C162 (Perception Ontology → Human Feedback Loop → Proof-of-Concept)
**Context:** After closing all internal integration gaps (C155–C157), E0 has no external communication channel. This document defines how E0 learns to communicate with a human peer — not via a hardcoded UI, but by acquiring perception and communication as learnable domains.

---

## §1 — The Core Problem

E0 optimizes internally: it historizes, inscribes, builds inertia, traverses landscapes, reflects, dreams. But none of this reaches the human. The human sees nothing — or sees a developer-built dashboard that shows whatever the developer decided was important.

This is backwards. E0 knows what is important (Self-Graph health, decision uncertainty, emerging patterns). E0 should decide what to communicate. The question is: **how does a system that operates on landscapes learn to produce human-perceivable output?**

This is not a UI problem. It is a translation problem — the same class of problem E0 solved in C133–C137 (seedless cross-domain translation). There, E0 translated between two natural-language landscapes. Here, E0 translates between its internal state landscape and a human perception landscape.

## §2 — Architecture: Three Layers

### Layer 1: Perception Ontology (what the human can perceive)

A landscape domain that encodes human visual/textual perception primitives. Not CSS properties — Gestalt principles and information design fundamentals:

| Node | Meaning | Example signal |
|------|---------|----------------|
| `proximity` | Spatial closeness = relatedness | Group related components |
| `emphasis` | Size, contrast, color = importance | Highlight unhealthy nodes |
| `hierarchy` | Nesting = structural subordination | Show layer → component → metric |
| `sequence` | Ordering = time or causality | Trace evolution over steps |
| `grouping` | Boundary, similarity = category | Cluster by subsystem |
| `contrast` | Difference = distinction | Show before/after |
| `density` | Information per unit area | Summarize vs. detail |
| `motion` | Change over time = dynamics | Animate convergence |
| `label` | Textual annotation = naming | Name what is shown |
| `absence` | What is NOT shown = deliberate omission | Hide healthy/boring |

These are taught monolingually by the LLM (same mechanism as C134a bootstrapper-as-teacher). E0 builds trace_load and quality on perception nodes through normal historization. High trace_load on `emphasis` means E0 has learned that emphasis is a frequently useful perception tool.

Additionally, a small number of **language primitives** are included — not a full language model, but enough for E0 to understand the Babel problem:

| Node | Meaning |
|------|---------|
| `assertion` | Stating a fact |
| `question` | Requesting input |
| `uncertainty` | Hedging / expressing doubt |
| `reference` | Pointing to prior context |
| `enumeration` | Listing items |

The LLM provides the natural-language surface form. E0 provides the structural intent.

### Layer 2: Communication Intent (what E0 wants to say)

E0 derives communication intents from its own internal state. These are not hardcoded categories — they emerge from Self-Graph diagnosis and controller state:

| Intent | Source | Trigger |
|--------|--------|---------|
| **uncertainty** | Self-Graph component health | quality < threshold on any component |
| **decision** | Controller step outcome | A ≠ B was chosen, B discarded |
| **pattern** | Trace-load dynamics | trace_load growing on specific path |
| **request** | Low inertia + low quality | E0 cannot proceed without input |
| **status** | Periodic / on-demand | Summary of current state |
| **anomaly** | Dream equivalence outlier | Unexpected cross-domain mapping |

Intent detection is a function: `f(self_graph, controller_state, dream_observer) → List[CommunicationIntent]`. Each intent carries:
- `type`: one of the above
- `urgency`: derived from quality (low quality = high urgency)
- `subject`: reference to the landscape node(s) involved
- `evidence`: the raw data supporting this intent

### Layer 3: UI-Schema Emission (the bridge format)

E0 maps (Intent × Perception) → a structured specification that a coding agent can consume. The schema is intentionally minimal — it describes *what* to show and *why*, not *how* to render it.

```python
@dataclass
class UIPanel:
    intent: str              # "uncertainty", "decision", ...
    perception: str          # "emphasis", "hierarchy", ...
    data_source: str         # dotted path into E0 state
    filter: dict             # conditions on the data
    suggested_visual: str    # "heatmap", "tree", "timeline", ...
    urgency: float           # 0.0 = informational, 1.0 = critical
    label: str               # human-readable title (LLM-generated)

@dataclass  
class UISpec:
    panels: List[UIPanel]
    layout: str              # "dashboard", "narrative", "alert"
    language: str            # "de", "en" — for LLM text generation
    generated_at: str        # ISO timestamp
    context: str             # what E0 was doing when this was generated
```

A coding agent (Copilot, Cursor, etc.) receives the UISpec and generates a concrete frontend (React, HTML, terminal, whatever the target platform is). The human interacts with the result. The interaction flows back as outcome signal.

### The Feedback Loop

```
E0 internal state
       ↓
  Intent detection
       ↓
  Perception mapping
       ↓
  UISpec emission ──→ Coding Agent ──→ Rendered UI
                                           ↓
                                      Human interaction
                                           ↓
                                      Outcome signal ──→ E0 (new step)
```

The feedback loop is critical. Without it, E0 emits specs into the void. With it, E0 learns which communication strategies work:
- Human clicked on the uncertainty panel → that intent was useful → reinforce
- Human ignored the status panel → low engagement → reduce urgency next time
- Human asked a follow-up question → E0's explanation was incomplete → adjust density

This is online learning through the normal E0 mechanism: outcome → historization → trace_load update → behavior change.

## §3 — The Babel Problem

E0 operates on landscapes (structural). Humans operate on language (symbolic). The LLM bridges this gap — but how does E0 know the bridge is faithful?

**Answer: the same way E0 handles score noise (C138b).** E0 is robust against translation noise as long as the *correlation* between intent and human understanding is preserved. The feedback loop provides the error signal: if the human's response is incoherent with E0's intent, the communication failed, and E0 adjusts.

Concretely:
- E0 emits a `CommunicationIntent` with type=uncertainty and subject=component_X
- LLM translates: "I'm not confident about component X's behavior"
- Human responds with relevant input → correlation preserved → E0 continues
- Human responds with confusion → correlation broken → E0 tries different perception strategy (more `contrast`, less `density`)

The language primitives in the Perception Ontology (`assertion`, `question`, `uncertainty`, `reference`, `enumeration`) give E0 structural handles on linguistic acts without requiring E0 to "understand" language.

## §4 — Why This Is Not Just UI Generation

The litmus test: **does E0 generate different UIs for different situations without us coding the rules?**

A template system would always show the same dashboard. E0 should:
- Show a `hierarchy` + `emphasis` view when one component is critically unhealthy
- Show a `sequence` + `contrast` view when a decision was made between alternatives
- Show `density` + `grouping` when the landscape is stable and the human needs overview
- Show `absence` when most things are fine and only anomalies matter

These choices emerge from the mapping of intent × perception, mediated by trace_load on perception nodes. If E0 has historized that `emphasis` works well for `uncertainty` intents (because humans respond usefully), it will prefer that combination — without any rule saying "use emphasis for uncertainty".

## §5 — The Stress Test Dimension

This is the ultimate E0 stress test because it requires:

1. **Self-Knowledge** — Self-Graph must accurately reflect what is important
2. **Theory of Mind (approximation)** — Perception Ontology must model how humans perceive
3. **Actionable Output** — E0 must emit a spec that actually builds something
4. **External Feedback Loop** — the ground truth is outside E0 (the human)
5. **Cross-Domain Translation** — internal state ↔ human perception (C137 machinery)
6. **Online Adaptation** — E0 must learn from communication success/failure

If this works, E0 has demonstrated that it can not only optimize internally but also function as a communicating agent — the minimal viable form of an autonomous system that collaborates with humans.

## §6 — Implementation Roadmap

| Commit | Name | Scope | Depends on |
|--------|------|-------|------------|
| **C158** | Perception Ontology | ~15 perception primitives as landscape domain, LLM-taught via Bootstrapper | Bootstrapper (C44), Landscape |
| **C159** | Communication Intent | Intent detection from Self-Graph + controller state, `detect_intents()` function | Self-Graph (C43), Controller |
| **C160** | UI-Schema Emitter | Deterministic mapping (Intent × Perception) → `UISpec` dataclass, `emit_ui_spec()` | C158, C159 |
| **C161** | Human Feedback Loop | Outcome ingestion from human interaction, maps user action → E0 Outcome | C160, Session |
| **C162** | Proof-of-Concept | End-to-end: E0 generates dashboard spec, coding agent builds it, human tests | C158–C161 |

C158 and C159 are independent and can be developed in parallel (conceptually). C160 is the join point. C161 adds the closed loop. C162 is the integration test.

### Estimated scope per commit
- **C158:** `perception.py` + tests (~150–200 LOC, ~15 tests)
- **C159:** `communication.py` + tests (~200–250 LOC, ~20 tests)
- **C160:** `ui_emitter.py` + tests (~150–200 LOC, ~15 tests)
- **C161:** Extension to `session.py` or new `feedback.py` (~100–150 LOC, ~10 tests)
- **C162:** `demo_human_communication.py` + integration tests (~200 LOC, ~5 tests)

## §7 — Open Questions

1. **Perception granularity:** Are 10–15 primitives enough, or does E0 need to discover sub-primitives (e.g., `emphasis.color` vs. `emphasis.size`)?
2. **Multi-modal:** Should E0 learn to emit audio/haptic specs, or is visual+text sufficient for now?
3. **Coding agent interface:** Do we standardize on a specific agent (Copilot?) or keep the UISpec agent-agnostic?
4. **Feedback latency:** Human feedback is slow (seconds to minutes). How does E0 handle the async gap?
5. **Intent composition:** Can E0 compose multiple intents into one panel, or is it always one intent per panel?
6. **Adversarial communication:** What if the human deliberately gives misleading feedback? (Robustness question, analogous to C138b noise.)

---

*Concept by Thomas + Copilot, 2026-04-05. Pre-implementation analysis — no code yet.*
