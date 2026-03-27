# E₀ Structural Core Schema v0.1 (Draft)

## Purpose

This document defines a first repository-native structural schema for data entering, traversing, and leaving an E₀-based system.

The schema is not a final standard. It is a draft protocol layer intended to make the following possible:

- stable ingress from external systems,
- explicit structural handoff into the E₀ core,
- reflective validation and mode selection,
- reproducible egress to downstream software, UI layers, or actuators.

It is written as a companion to the lived-principles note and should be read together with the repository’s implementation, papers, and test registry.

---

## 1. Design principles

The schema is guided by the following principles:

1. **Explicit structure over implicit interpretation**  
   Data should be translated into explicit states, transitions, and local quantities before the controller acts.

2. **Role separation**  
   Ingress translation, structural decision, reflective integrity checks, and egress realization must remain distinguishable.

3. **Bounded operationality**  
   The schema should support real use in bounded systems before aspiring to universal abstraction.

4. **Domain invariance in the core**  
   The core schema should not assume whether the domain is sensing, workflow, finance, planning, or language.

5. **Compatibility with future extensions**  
   The schema must leave room for U(1), SU(2)-minimal, SU(2)-geometric, and future multi-axis transport regimes.

---

## 2. High-level layering

An E₀ system using this schema is assumed to operate in four layers:

1. **Ingress layer**  
   External data is mapped into structural form.

2. **Structural core layer**  
   E₀ operates on states, transitions, local quantities, and mode configuration.

3. **Reflective integrity layer**  
   Mapping confidence, structural consistency, and controller-mode decisions are checked here.

4. **Egress layer**  
   Results are translated into external actions, summaries, machine commands, or workflow outputs.

---

## 3. Minimal top-level envelope

A minimal E₀ exchange object should contain the following top-level blocks:

```json
{
  "schema_version": "0.1",
  "ingress": {},
  "core": {},
  "reflection": {},
  "egress": {},
  "metadata": {}
}
```

Not every block must be fully populated in every context, but the separation should remain visible.

---

## 4. Ingress block

The ingress block records where the structural input came from and how it was produced.

### Required intent

The ingress block should answer:

- What was the source type?
- Was the mapping deterministic or semantic?
- What uncertainties remain?
- What external context still matters?

### Draft shape

```json
{
  "source_type": "sensor | document | api | workflow | user_input | mixed",
  "mapping_mode": "compiled | semantic | hybrid",
  "source_reference": "optional external identifier",
  "mapping_agent": "human | llm | parser | mixed",
  "mapping_confidence": 0.0,
  "unresolved_ambiguities": [],
  "notes": "optional"
}
```

### Interpretation

- **compiled** mapping: stable source, mapping can be reused without an LLM in the control loop.
- **semantic** mapping: open or text-rich source requiring interpretation.
- **hybrid** mapping: deterministic extraction plus semantic structuring.

---

## 5. Core block

The core block is the structural heart of the schema.

It must be sufficient for the E₀ controller to operate without needing to recover hidden semantics from the original source.

### 5.1 States

```json
{
  "states": [
    {
      "id": "S",
      "label": "optional",
      "attributes": {},
      "role": "start | intermediate | goal | terminal | other"
    }
  ]
}
```

### 5.2 Transitions

```json
{
  "transitions": [
    {
      "from": "S",
      "to": "A",
      "delta": 0.35,
      "resistance": 0.70,
      "attributes": {},
      "constraints": [],
      "provenance": "optional"
    }
  ]
}
```

### 5.3 Goal specification

```json
{
  "goals": {
    "target_states": ["G1", "G2"],
    "goal_mode": "single | multi",
    "goal_weights": {
      "G1": 1.0,
      "G2": 0.8
    }
  }
}
```

### 5.4 Context and history handles

```json
{
  "context": {
    "current_state": "S",
    "historization_enabled": true,
    "history_handle": "optional persistent key",
    "memory_context": {}
  }
}
```

### 5.5 Controller configuration

```json
{
  "controller": {
    "mode": "greedy | hybrid | born_sampling",
    "geometry": "simple | goal_reaching | first_arrival | prefix",
    "horizon_edges": 4,
    "transport": "u1 | su2_min | su2_geo | su2_multi_axis",
    "multi_goal": true,
    "confidence_threshold": 0.0
  }
}
```

### Combined example

```json
{
  "states": [...],
  "transitions": [...],
  "goals": {...},
  "context": {...},
  "controller": {...}
}
```

---

## 6. Reflection block

The reflection block is not the decision itself. It is the integrity and meta-configuration layer around the decision.

Its role is to answer questions such as:

- Is the current structural mapping coherent enough to act on?
- Should the controller proceed, reconfigure, escalate, or refuse?
- Is a richer geometry or transport regime justified?

### Draft shape

```json
{
  "mapping_integrity": {
    "status": "ok | uncertain | inconsistent | rejected",
    "consistency_score": 0.0,
    "issues": []
  },
  "mode_selection": {
    "recommended_geometry": "goal_reaching",
    "recommended_transport": "u1",
    "recommended_horizon": 4,
    "reason": "optional"
  },
  "action_guard": {
    "allow_actuation": true,
    "escalate": false,
    "require_remap": false,
    "fallback_mode": "greedy"
  }
}
```

### Interpretation

This block should be able to protect controller identity.

If the ingress mapping is structurally poor, the correct action may be:

- do not act,
- reduce controller complexity,
- request clarification,
- or remap the source entirely.

---

## 7. Egress block

The egress block is the structural output to downstream systems.

It should be interpretable both by software and by humans.

### Draft shape

```json
{
  "decision": {
    "recommended_action": "A1",
    "selected_successor": "B1",
    "confidence": 0.93,
    "mode_used": "hybrid",
    "geometry_used": "goal_reaching",
    "transport_used": "u1"
  },
  "alternatives": [
    {
      "action": "A1",
      "score": 0.12
    },
    {
      "action": "B1",
      "score": 0.88
    }
  ],
  "machine_output": {
    "command_type": "optional",
    "payload": {}
  },
  "ui_output": {
    "summary": "optional human-readable summary",
    "explanation": "optional"
  }
}
```

---

## 8. Metadata block

The metadata block keeps the object replayable and auditable.

```json
{
  "run_id": "optional unique id",
  "timestamp": "ISO-8601",
  "schema_version": "0.1",
  "repository_version": "optional",
  "notes": "optional"
}
```

---

## 9. Minimal end-to-end example

```json
{
  "schema_version": "0.1",
  "ingress": {
    "source_type": "sensor",
    "mapping_mode": "compiled",
    "mapping_agent": "parser",
    "mapping_confidence": 1.0,
    "unresolved_ambiguities": []
  },
  "core": {
    "states": [
      {"id": "S", "role": "start"},
      {"id": "RED", "role": "goal"},
      {"id": "GREEN", "role": "goal"}
    ],
    "transitions": [
      {"from": "S", "to": "RED", "delta": 0.2, "resistance": 0.4},
      {"from": "S", "to": "GREEN", "delta": 0.7, "resistance": 0.3}
    ],
    "goals": {
      "target_states": ["RED"],
      "goal_mode": "single",
      "goal_weights": {"RED": 1.0}
    },
    "context": {
      "current_state": "S",
      "historization_enabled": true
    },
    "controller": {
      "mode": "hybrid",
      "geometry": "goal_reaching",
      "horizon_edges": 2,
      "transport": "u1",
      "multi_goal": false,
      "confidence_threshold": 0.0
    }
  },
  "reflection": {
    "mapping_integrity": {
      "status": "ok",
      "consistency_score": 1.0,
      "issues": []
    },
    "mode_selection": {
      "recommended_geometry": "goal_reaching",
      "recommended_transport": "u1",
      "recommended_horizon": 2,
      "reason": "single-goal control"
    },
    "action_guard": {
      "allow_actuation": true,
      "escalate": false,
      "require_remap": false,
      "fallback_mode": "greedy"
    }
  },
  "egress": {
    "decision": {
      "recommended_action": "RED",
      "selected_successor": "RED",
      "confidence": 0.94,
      "mode_used": "hybrid",
      "geometry_used": "goal_reaching",
      "transport_used": "u1"
    },
    "alternatives": [
      {"action": "RED", "score": 0.94},
      {"action": "GREEN", "score": 0.06}
    ],
    "machine_output": {
      "command_type": "traffic_light_signal",
      "payload": {"state": "red"}
    },
    "ui_output": {
      "summary": "Switch traffic light to red.",
      "explanation": "Target-goal control selected RED with high structural confidence."
    }
  },
  "metadata": {
    "run_id": "example-0001",
    "timestamp": "2026-03-27T00:00:00Z",
    "schema_version": "0.1"
  }
}
```

---

## 10. Co-cognition review and code-mapping (2026-03-27)

This schema was developed across two co-cognition sessions:

1. **Session 1** (ChatGPT + Gemini): Architectural brainstorming — four-layer model, JSON envelope, reflection-as-gate concept.
2. **Session 2** (Copilot / Claude): Systematic mapping against the actual E₀ codebase — field-by-field comparison of schema vs. implementation.

### 10.1 What already exists in code

The **Core block** has strong code backing (~80%):

| Schema field | Code equivalent | Status |
|---|---|---|
| `states[].id` | `Landscape._states: Set[str]` | ✅ exists |
| `transitions.from/to/delta/resistance` | `Edge`, `Landscape._delta`, `Landscape._R0` | ✅ exists |
| `goals.target_states` | `E0Controller.hybrid_goals` + `goal` param | ✅ exists |
| `controller.mode` | `HybridMode` enum (GREEDY, AMPLITUDE_ON_DISAGREE, BORN_SAMPLING) | ✅ exists |
| `controller.geometry` | `hybrid_geometry: str` (simple, goal_reaching, first_arrival, prefix) | ✅ exists |
| `controller.horizon_edges` | `hybrid_horizon: int` + `DynamicHorizon` strategies | ✅ exists |
| `controller.confidence_threshold` | `confidence_threshold: float` | ✅ exists |
| `context.history_handle` | `Session.session_id` → `E0MemoryOS` persistence | ✅ exists |
| `context.memory_context` | `MemOSContext` dataclass (richer than schema proposes) | ✅ exists |

Partial matches:
- `states[].role` — implicit (start/goal are runtime args, not state metadata)
- `controller.transport` — binary `use_su2` flag, not a typed enum of transport regimes
- `goals.goal_mode` — implicit via presence/absence of `hybrid_goals`
- `egress.alternatives` — `OverlayReport.action_infos` (richer: intensity, phase, probability)

### 10.2 What is speculative (no code basis)

| Block | Schema fields | Code coverage |
|---|---|---|
| **Ingress** | source_type, mapping_mode, mapping_agent, mapping_confidence, unresolved_ambiguities | ~5% — only `ProvenanceLog.source_id` loosely analogous |
| **Reflection** | mapping_integrity (status/score/issues), mode_selection, action_guard (allow_actuation/escalate/require_remap) | ~0% — **fundamentally different concept** |
| **Egress wrapper** | machine_output, ui_output, decision.geometry_used, decision.transport_used | ~0% |
| **Core extensions** | states[].label, states[].attributes, transitions[].constraints, goal_weights | 0% |

### 10.3 Critical finding: Reflection concept mismatch

The existing `reflection.py` operates as **post-run diagnostics** — it evaluates run quality after the controller has acted (patterns, recommended_actions, layers).

The schema proposes a **pre-decision integrity gate** — it would decide *whether to act at all*, *which geometry to use*, and *whether to escalate or refuse*.

These are fundamentally different roles. The schema's reflection block is an **open research question**, not a formalization of existing behavior. The question "Is this structural mapping good enough to act on?" has no current answer in code.

### 10.4 ProvenanceLog overlap

`ProvenanceLog` (implemented, tested, live-validated) and the schema carry overlapping data:

| ProvenanceLog stage | Schema block overlap |
|---|---|
| `InputRecord` (text, SHA-256, source_id) | Ingress (source_reference) |
| `LLMCallRecord` (prompt, response, model, timing) | Ingress (mapping_agent) |
| `ProposalRecord` (states, edges) | Core (states, transitions) |
| `RunRecord` (path, config, overrides) | Egress (decision) |
| `EvaluationRecord` (findings) | Reflection (post-run) |

Key difference: ProvenanceLog is a **temporal audit chain** (what happened when). The schema proposes a **structural envelope** (simultaneous snapshot). Both are needed, but must be designed together to avoid redundancy.

---

## 11. Strategic decision: Domänen → Schema, not Schema → Domänen

### The risk of premature standardization

The E₀ project has built everything bottom-up: each feature proven by tests, then formalized, then extended. The Beipackzettel demo showed how valuable this is — real data, real LLM-generated edges, real provenance chain.

This schema was developed top-down (co-cognition brainstorming). Standardizing Ingress/Reflection/Egress before a second real-world domain risks freezing the wrong abstractions.

### The plan

```
Beipackzettel (Domäne 1)     ✅ done — 8 states, 10 edges, live provenance
         ↓
Zweite reale Domäne           → build next
         ↓
Dritte reale Domäne           → build after
         ↓
Cross-domain comparison       → what was EQUAL across all ingress paths?
         ↓
Schema v0.2                   → formalize the ACTUAL commonalities
```

### What to implement now

| Action | Rationale |
|---|---|
| **Core block → `E0Envelope` dataclass** | ~80% proven. Stabilizes the existing interface between adapters and controller. |
| **Core.controller.transport → `TransportRegime` enum** | Replace binary `use_su2` flag with typed `u1 / su2_min / su2_geo / su2_multi_axis`. |
| **Core.states[].role → optional per-state metadata** | Useful for LLM-generated landscapes (start/goal/intermediate). |

### What to defer

| Block | Wait for |
|---|---|
| **Ingress** | 2nd + 3rd real domain → observe actual ingress patterns |
| **Reflection (pre-decision gate)** | Research question — needs a concrete mechanism, not just a schema shape |
| **Egress (machine_output, ui_output)** | 1st real integration target (API, UI, actuator) |
| **goal_weights** | Real multi-goal domain where weighting matters |

---

## Status

**Status:** Draft protocol note + co-cognition review  
**Version:** 0.1 → reviewed, partially actionable  
**Origin:** ChatGPT/Gemini brainstorming + Copilot/Claude code-mapping  
**Relation to canon:** compatible, not canonical  
**Relation to implementation:**
- Core block → ready for `E0Envelope` implementation
- Ingress/Reflection/Egress → deferred until 2–3 real-world domains provide evidence  

**Relation to papers:** architectural companion, not a substitute for formal derivation  
**Next action:** Build second real-world domain, then revisit schema with cross-domain evidence
