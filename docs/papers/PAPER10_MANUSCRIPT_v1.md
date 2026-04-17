# E₀-X: Perception-Driven Communication — Learnable Human Interaction from Historization

**Thomas Wehner**

---

## Abstract

Papers 1–9 describe a system that navigates, learns, and tunes itself.
None address how it communicates with humans. This paper presents a
four-layer communication architecture — Perception, Intent Detection,
UI Emission, and Feedback — that uses E₀'s existing Historization
mechanism to learn how to communicate. The Perception layer defines 22
primitives (10 visual, 5 language, 7 rendering) connected by 35 directed
edges in a landscape that evolves through use. The Intent Detection layer
reads controller state from five independent sources (Self-Graph, step
results, dream observations, landscape topology, and learning rounds) and
produces urgency-ranked communication intents. The UI Emission layer maps
intents to perception primitives via heuristic affinities (cold start)
that are progressively overridden by learned strengths (warm state). The
Feedback layer closes the loop: human actions (click, ignore, follow-up,
dismiss) are mapped to Outcomes and fed into the perception landscape's
Historization, refining which primitives are selected in future
interactions. No new learning mechanism is introduced — standard
Historization handles all perception adaptation. The architecture is
validated by 180 tests across four modules (C158–C161) with extensions
for learnable rendering (C164), task-aware intent detection (C166), and
learning-cycle integration (C212). All claims are classified as derived,
empirical, or heuristic.

---

## 1. Introduction

### 1.1 The Communication Problem

A system that learns, decides, and self-tunes must eventually communicate
its state to a human operator. This communication is itself a choice
under uncertainty: which aspects of the internal state matter? How should
they be presented? What modality (visual, linguistic, structural) is
appropriate?

Most AI systems solve this with static dashboards or hard-coded logging.
E₀'s approach is different: treat communication as a *learnable domain*
within the same framework that handles all other domains.

### 1.2 Design Principles

Three principles guide the architecture:

1. **No new primitives.** Communication uses Historization, landscapes,
   and trace quality — the same mechanisms as domain navigation.

2. **Cold start capability.** The system must communicate usefully
   from the first interaction, before any feedback has been received.
   Heuristic affinities provide this baseline.

3. **Learnable refinement.** Over time, human feedback shifts
   communication toward what actually helps. Primitives that receive
   positive feedback gain strength; those that are ignored or dismissed
   lose strength.

### 1.3 Architecture Overview

The four layers form a pipeline with a feedback loop:

```
Controller State ──→ [1. Perception] ──→ PerceptionSnapshot
                     [2. Intent Detection] ──→ IntentReport
                     [3. UI Emission] ──→ UISpec
                     [4. Feedback] ←── HumanAction
                          │
                          └──→ Historization(perception edges)
                                     │
                                     └──→ Updated PerceptionSnapshot (next round)
```

Each layer adds structure: raw controller state → normalised perception
primitives → urgency-ranked intents → concrete rendering specification →
actionable feedback that refines the entire chain.

---

## 2. Perception Layer (C158)

### 2.1 Perception Primitives

The perception ontology defines 22 primitives in three kinds:

**Visual Primitives** (10, Gestalt-derived):
proximity, emphasis, hierarchy, sequence, grouping, contrast, density,
motion, label, absence.

**Language Primitives** (5):
assertion, question, uncertainty, reference, enumeration.

**Rendering Primitives** (7, added C164):
heatmap, tree, timeline, bar, text, highlight, dashboard.

**Claim 2.1** (Primitive Completeness, *heuristic*). The 22 primitives
cover the basic vocabulary of human-computer interaction: spatial
relationships (proximity, grouping, density), emphasis mechanisms
(emphasis, contrast, highlight), temporal structure (sequence, timeline,
motion), linguistic acts (assertion, question, uncertainty), and
visualisation types (heatmap, tree, bar, dashboard). The set is
extensible — adding a primitive requires only adding a node and edges
to the perception landscape.

### 2.2 Perception Landscape

The 22 primitives are connected by 35 directed edges, forming a
landscape that E₀ can navigate and learn from:

| Edge Category | Count | Example |
|---------------|-------|---------|
| Visual→Visual (Gestalt support) | 11 | proximity → grouping |
| Language→Visual | 4 | question → emphasis |
| Visual→Language | 3 | absence → uncertainty |
| Language→Language | 2 | question → uncertainty |
| Perception→Rendering (C164) | 15 | emphasis → heatmap |

Each edge carries standard E₀ properties: delta (structural difference),
resistance (initial friction), and historization counters (U, F). The
edges encode *which primitives support or lead to which others* —
a Gestalt-theoretic structure adapted for computational use.

### 2.3 Perception Profile and Snapshot

**Definition 2.1** (Perception Profile). *For a primitive p, its profile
summarises its current state:*

- *name*: primitive identifier
- *kind*: VISUAL | LANGUAGE | RENDERING
- *trace_load*: U(p) + F(p) across all edges touching p
- *quality*: (U − F) / (U + F + ε), ε = 10⁻¹²
- *outgoing_edges*: count of edges from p
- *avg_outgoing_quality*: mean quality across outgoing edges

**Definition 2.2** (Perception Strength).

$$\text{strength}(p) = \text{trace\_load}(p) \times \max(0, \text{quality}(p))$$

Strength ≥ 0 by construction. A primitive with high trace_load but
negative quality (more failures than successes) has zero strength —
it is actively suppressed.

**Definition 2.3** (Perception Snapshot). A snapshot aggregates all
profiles at a point in time, providing:
- `profiles[]`: all 22 primitive profiles
- `total_load`: sum of all trace_loads
- `visual_load`, `language_load`: per-kind aggregates
- `ranked()`: profiles sorted by strength (descending)
- `top(n, kind)`: top-n strongest of a specific kind

**Claim 2.2** (Learning Signal, *derived*). Perception strength
monotonically increases with positive feedback (U grows, quality
improves) and stagnates or drops with negative feedback (F grows,
quality decreases). This is not a custom mechanism — it is standard
Historization applied to perception edges.

### 2.4 Persistence

`PerceptionDomain.save_state()` serialises the perception landscape
(including all historization data) and `from_saved()` restores it.
This enables cross-session perception learning.

---

## 3. Intent Detection Layer (C159)

### 3.1 Intent Types

Six intent types capture the space of controller-to-human communication:

| IntentType | Meaning | Example |
|------------|---------|---------|
| UNCERTAINTY | Controller is unsure | Confused Self-Graph component |
| DECISION | Controller made a non-trivial choice | Multiple candidates with similar S_eff |
| PATTERN | Controller detected a regularity | Resistance stabilising on a path |
| REQUEST | Controller needs external input | Dead-end with no admissible neighbours |
| STATUS | Routine state report | Component health summary |
| ANOMALY | Something unexpected occurred | Dream detected broken equivalence |

Each intent carries:
- `type`: IntentType
- `urgency`: float ∈ [0, 1] (higher = more critical)
- `subject`: what the intent is about
- `summary`: human-readable description
- `evidence`: dict of supporting data

### 3.2 Five Independent Detectors

Intent detection draws from five sources, each operating independently:

**Detector 1: Self-Graph (Self-Graph → UNCERTAINTY, REQUEST)**

Reads component diagnosis. Harmful components (negative quality) generate
UNCERTAINTY intents with urgency proportional to severity:

$$u = 0.7 + |q_{\text{component}}| \times 0.3$$

Components with insufficient data generate REQUEST intents.

**Detector 2: Step Results (StepResult → DECISION, UNCERTAINTY, PATTERN)**

Reads the most recent navigation step. Multiple candidates with similar
S_eff generate DECISION intents. Escalation (DEAD_END, EXHAUSTED)
generates UNCERTAINTY. Resistance drops > 30% generate PATTERN (path
stabilising).

**Detector 3: Dream Observations (DreamObserver → ANOMALY, PATTERN)**

Reads dream-mode equivalence checks. Quality < −0.3 generates ANOMALY
(broken cross-domain mapping). Quality > 0.5 generates PATTERN (strong
equivalence).

**Detector 4: Landscape Topology (Landscape + Trace → STATUS, DECISION,
PATTERN, UNCERTAINTY, ANOMALY, REQUEST)** *(C166 task-aware)*

Reads the actual problem graph and run trace. Detects dead-ends
(REQUEST, urgency 0.9), high-tension edges (DECISION), repeated
failures (UNCERTAINTY), stabilising paths (PATTERN), and overall
navigation status (STATUS, urgency 0.1).

**Detector 5: Learning Rounds (C212)**

Reads multi-domain learning cycle results. Generates PATTERN and
UNCERTAINTY intents from round-level quality metrics.

### 3.3 Unified Intent Report

`detect_intents()` combines all five detectors into a single
`IntentReport`, sorted by urgency descending:

**Claim 3.1** (Urgency Ordering, *derived*). The urgency ranking ensures
critical issues (harmful components, dead-ends) surface before routine
status reports. This ordering is preserved through UI emission — the
first panel always corresponds to the most urgent intent.

**Claim 3.2** (Source Independence, *derived*). Each detector operates
on a different controller subsystem. Adding a new detector does not
modify existing detectors. The only coupling point is the shared
IntentReport output format.

---

## 4. UI Emission Layer (C160)

### 4.1 From Intent to Panel

For each intent, the emitter selects three primitives:

1. **Visual perception** — which visual primitive to use
2. **Language act** — which linguistic framing to apply
3. **Rendering suggestion** — which widget to display

Selection follows a two-stage process: heuristic affinity (cold start)
refined by learned strength (warm state).

### 4.2 Heuristic Affinities (Cold Start)

Each IntentType has a default affinity to specific primitives:

| IntentType | Visual Affinity | Language Act | Rendering |
|------------|----------------|--------------|-----------|
| UNCERTAINTY | emphasis, contrast, label | uncertainty | heatmap |
| DECISION | hierarchy, sequence | assertion | tree |
| PATTERN | grouping, proximity | assertion | timeline |
| REQUEST | emphasis, label | question | text |
| STATUS | density, grouping | enumeration | dashboard |
| ANOMALY | contrast, absence | uncertainty | highlight |

These affinities encode human interface conventions: uncertainty maps to
emphasis and contrast (draw attention to ambiguity), decisions map to
hierarchy and sequence (show the choice structure), etc.

**Claim 4.1** (Immediate Usability, *heuristic*). The heuristic
affinities produce sensible interface specifications from the first
interaction, without any prior feedback. The mappings are conventional
(e.g., uncertainty → emphasis) rather than arbitrary, reducing the
learning burden.

### 4.3 Learned Override

When a PerceptionSnapshot is available, the emitter checks learned
strengths:

```
For each affinity primitive p:
    strength(p) = perception_snapshot.by_name(p).strength
Pick primitive with highest strength
Fall back to first affinity if all strengths ≤ 0
```

**Claim 4.2** (Smooth Transition, *derived*). As feedback accumulates,
learned strengths override heuristic affinities for primitives where
evidence exists, while retaining heuristic fallbacks for primitives
without feedback. The transition is continuous — there is no discrete
switch from "cold" to "warm" mode.

### 4.4 Layout Selection

The layout is determined by urgency and intent count:

| Condition | Layout |
|-----------|--------|
| max_urgency ≥ 0.8 | alert |
| intent_count ≤ 3 | narrative |
| otherwise | dashboard |

**Claim 4.3** (Cognitive Load Management, *heuristic*). Alert layout
focuses attention on a single critical issue. Narrative layout presents
a coherent story for small intent sets. Dashboard layout organises large
intent sets into a scannable grid. Panel count is capped at 10 to
prevent cognitive overload.

### 4.5 UISpec

The output is a `UISpec`: a structured, agent-agnostic specification
that decouples *what to communicate* from *how to render*.

```python
@dataclass(frozen=True)
class UISpec:
    panels: Tuple[UIPanel, ...]
    layout: str        # "alert" | "narrative" | "dashboard"
    generated_at: float
    context: str       # task description
```

Each `UIPanel` contains: intent, perception primitive, language act,
data source path, suggested visual widget, urgency, label, and evidence.

**Claim 4.4** (Agent-Agnostic, *derived*). UISpec contains no rendering
code — only structured descriptions. The same UISpec can drive an HTML
dashboard, a terminal output, an IDE panel, or a voice interface. The
rendering implementation is external to the communication architecture.

---

## 5. Feedback Layer (C161)

### 5.1 Human Actions

Six actions represent the space of human responses to a UI panel:

| HumanAction | Outcome Mapping | Interpretation |
|-------------|-----------------|----------------|
| CLICK | SUCCESS | User engaged with content |
| FOLLOWUP | SUCCESS | User requested more detail |
| ACKNOWLEDGE | SUCCESS | User confirmed understanding |
| IGNORE | FAILURE | User did not engage |
| CONFUSION | FAILURE | User was confused by presentation |
| DISMISS | FAILURE | User actively rejected content |

### 5.2 Historization Feedback

For each panel receiving a human action, the feedback layer:

1. Maps action → Outcome (SUCCESS or FAILURE)
2. Finds the perception edge(s) associated with the panel's visual
   primitive and language act
3. Calls `landscape.historize(edge, outcome)` on each edge
4. If rendering edges exist (C164), also historizes the rendering
   primitive edge

**Claim 5.1** (Loop Closure, *derived*). The feedback loop is complete:
UI emission selects primitives based on strength → human responds with
action → action is historized on perception edges → strength changes →
next emission selects differently. No additional learning mechanism is
required.

**Claim 5.2** (Rendering Learning, *derived, C164*). By adding
perception→rendering edges to the landscape, the system learns not
just *which perception primitive* to use but *which rendering widget*
to pair with it. A heatmap that receives positive feedback when showing
uncertainty will be preferred over a highlight for future uncertainty
intents.

### 5.3 Audit Trail

`ingest_feedback()` returns a `FeedbackResult` containing:
- `events[]`: each FeedbackEvent (panel, action, outcome)
- `edges_updated`: count of edges that received historization
- `panels_without_feedback`: panels the user did not interact with

This audit trail enables analysis of which communication patterns
succeed and which fail.

---

## 6. Extensions

### 6.1 Learnable Rendering (C164)

The original architecture (C158–C161) selected rendering widgets via
static heuristic. C164 adds 15 perception→rendering edges to the
landscape:

| Source Perception | Target Rendering | Example |
|-------------------|------------------|---------|
| emphasis | heatmap, highlight, bar | 3 edges |
| hierarchy | tree, dashboard | 2 edges |
| grouping | dashboard, heatmap | 2 edges |
| sequence | timeline, bar | 2 edges |
| contrast | heatmap, highlight | 2 edges |
| density | heatmap, bar | 2 edges |
| label | text, highlight | 2 edges |

These edges are historizable: when a user clicks a panel that used
emphasis→heatmap, the edge emphasis→heatmap receives SUCCESS. Over
time, the system learns which rendering widgets work best for each
perception primitive.

### 6.2 Task-Aware Intent Detection (C166)

`detect_landscape_intents()` reads the actual problem graph and run
trace, producing task-specific intents:

- Dead-end detection (no admissible neighbours, urgency 0.9)
- High-tension edges (S_eff > 0.5, DECISION intent)
- Repeated failures at specific states (UNCERTAINTY intent)
- Path stabilisation (resistance drop > 30%, PATTERN intent)

**Claim 6.1** (Contextual Grounding, *derived*). Task-aware detection
ensures communication is about the specific problem being solved, not
just generic system status. A dead-end in the navigation graph produces
a REQUEST intent with the dead-end state as subject.

### 6.3 Learning Cycle Integration (C212)

`detect_round_intents()` generates intents from multi-domain learning
cycle results, connecting the perception-communication stack to the
broader E₀ learning architecture.

---

## 7. Key Properties

### 7.1 Self-Application

The perception-communication architecture is itself an instance of
E₀ dynamics:

| E₀ Concept | Communication Instance |
|------------|----------------------|
| State x ∈ X | Perception primitive |
| Edge (x, y) | Primitive supports/leads-to primitive |
| S_eff | Perception strength (learned) |
| Outcome | Human action → SUCCESS/FAILURE |
| Historization | Standard H(U, F) on perception edges |
| Navigation | Selecting which primitive to use next |

**Claim 7.1** (No New Primitives, *derived*). The entire communication
architecture reuses Historization, landscapes, and trace quality. The
only additions are the 22 perception node names and 35 edge definitions —
domain content, not mechanism.

### 7.2 Urgency as Resource Allocation

The urgency ranking across intents functions as an attention allocation
mechanism: scarce human attention is directed to the most critical
issues first. This mirrors E₀'s own resource allocation — visiting
states with lowest S_eff first.

**Claim 7.2** (Attention Optimality, *heuristic*). Urgency-ranked
communication is locally optimal: the panel most likely to require
human action (highest urgency) is presented first. This assumes urgency
correlates with action-necessity, which is empirically validated but not
formally proven.

### 7.3 Composability

The four layers compose independently:
- Replace the perception ontology (different domains, different
  primitives)?  Only layer 1 changes.
- Add a new intent source (e.g., external monitoring)? Only layer 2
  gains a detector.
- Change the rendering target (terminal instead of HTML)? Only the
  consumer of UISpec changes; layers 1–4 are unaffected.
- Change the feedback mechanism (eye-tracking instead of clicks)?
  Only layer 4's action mapping changes.

**Claim 7.3** (Layer Independence, *derived*). Each layer depends only
on the output type of the previous layer (PerceptionSnapshot →
IntentReport → UISpec → FeedbackResult). The internal implementation
of each layer can change without affecting others.

---

## 8. Experimental Validation

### 8.1 Test Infrastructure

| Module | Test File | Tests | Commits |
|--------|-----------|-------|---------|
| perception.py | test_perception.py | 48 | C158 |
| communication.py | test_communication.py | 70 | C159, C166, C212 |
| ui_emitter.py | test_ui_emitter.py | 32 | C160, C164 |
| feedback.py | test_feedback.py | 30 | C161, C164 |
| **Total** | | **180** | |

### 8.2 Validated Properties

| Property | Test Category | Key Test |
|----------|---------------|----------|
| Primitive completeness | test_perception | All 22 nodes, 35 edges present |
| Profile computation | test_perception | strength = trace_load × quality |
| Snapshot ranking | test_perception | top(n) returns highest strength |
| Intent detection (per source) | test_communication | Each detector produces correct types |
| Urgency ordering | test_communication | Report sorted by urgency desc |
| Multi-source combination | test_communication | detect_intents() merges all sources |
| Heuristic affinity | test_ui_emitter | Cold-start produces valid UISpec |
| Learned override | test_ui_emitter | High-strength primitive selected |
| Layout selection | test_ui_emitter | Urgency → alert, low count → narrative |
| Action→Outcome mapping | test_feedback | 3 success actions, 3 failure actions |
| Historization feedback | test_feedback | Edge U/F updated after action |
| Rendering learning (C164) | test_ui_emitter, test_feedback | Rendering edges historized |
| Task-aware detection (C166) | test_communication | Dead-end, high-tension intents |
| Round integration (C212) | test_communication | Learning cycle round intents |
| Serialisation | test_perception | save_state / from_saved round-trip |

### 8.3 Key Results

| Claim | Type | Evidence |
|-------|------|----------|
| No new primitives | Derived | §7.1 — only Historization used |
| Immediate cold-start usability | Heuristic | §4.2 — affinities produce valid UISpec |
| Smooth cold→warm transition | Derived | §4.3 — strength override is continuous |
| Feedback closes the loop | Derived | §5.2 — standard Historization |
| Rendering is learnable (C164) | Derived | §6.1 — perception→rendering edges |
| Task-aware communication (C166) | Derived | §6.2 — landscape topology → intents |
| Layer independence | Derived | §7.3 — interface-only coupling |

---

## 9. Limitations and Open Questions

### 9.1 What We Do NOT Prove

1. **Perceptual optimality.** The 22 primitives and 35 edges are a
   heuristic Gestalt-derived vocabulary. We do not prove this is the
   minimal or optimal set for human-computer interaction.

2. **Urgency calibration.** Urgency values are threshold-based heuristics.
   We do not prove they correspond to actual human attention priorities.

3. **Convergence speed.** We do not prove how many feedback cycles are
   needed before learned strengths reliably outperform heuristic
   affinities. This depends on feedback frequency and consistency.

4. **User modelling.** All users receive the same perception treatment.
   Individual differences in visual/linguistic preferences are not
   modelled (though per-user perception landscapes could address this).

### 9.2 Open Questions

1. Can perception primitives themselves be discovered rather than
   predefined? A meta-perception layer could propose new primitives
   based on feedback patterns.

2. Can the urgency model be calibrated from human response times?
   Faster responses to certain urgency levels would validate or
   correct the heuristic urgency assignments.

3. Can the architecture support multi-modal output (simultaneous
   visual and audio) with learned modality preferences?

---

## 10. Conclusion

Perception-driven communication in E₀ follows the framework's core
design principle: use the same mechanism at every level. The perception
landscape is a landscape. Feedback is Historization. Primitive selection
is navigation by strength. Intent detection reads controller state
without special instrumentation. UI emission maps structured intents to
structured specifications without being tied to any rendering technology.

The architecture's key property is **learnability without new mechanisms**.
A system that already learns path preferences through Historization
naturally learns communication preferences through the same process.
The human operator is not a special case — they are another part of the
landscape, reachable through perception edges whose resistances are
shaped by experience.

The 180 tests across four modules (C158–C161) validate structural
correctness, cold-start capability, learned refinement, and feedback
closure. Extensions C164 (learnable rendering), C166 (task-aware
detection), and C212 (learning cycle integration) demonstrate the
architecture's extensibility within the same mechanistic framework.

---

## Appendix A: Claim Classification

| # | Claim | Type | Section |
|---|-------|------|---------|
| 2.1 | Primitive completeness | Heuristic | §2.1 |
| 2.2 | Learning signal from Historization | Derived | §2.3 |
| 3.1 | Urgency ordering preserved | Derived | §3.3 |
| 3.2 | Source independence | Derived | §3.3 |
| 4.1 | Immediate usability | Heuristic | §4.2 |
| 4.2 | Smooth cold→warm transition | Derived | §4.3 |
| 4.3 | Cognitive load management | Heuristic | §4.4 |
| 4.4 | Agent-agnostic rendering | Derived | §4.5 |
| 5.1 | Loop closure | Derived | §5.2 |
| 5.2 | Rendering learning | Derived | §5.2 |
| 6.1 | Contextual grounding | Derived | §6.2 |
| 7.1 | No new primitives | Derived | §7.1 |
| 7.2 | Attention optimality | Heuristic | §7.2 |
| 7.3 | Layer independence | Derived | §7.3 |

## Appendix B: Perception Primitives

### Visual (10)
proximity, emphasis, hierarchy, sequence, grouping, contrast, density,
motion, label, absence

### Language (5)
assertion, question, uncertainty, reference, enumeration

### Rendering (7)
heatmap, tree, timeline, bar, text, highlight, dashboard

## Appendix C: Perception Edge Topology

| Category | Count | Example |
|----------|-------|---------|
| Visual→Visual (Gestalt) | 11 | proximity → grouping |
| Language→Visual | 4 | question → emphasis |
| Visual→Language | 3 | absence → uncertainty |
| Language→Language | 2 | question → uncertainty |
| Perception→Rendering (C164) | 15 | emphasis → heatmap |
| **Total** | **35** | |
