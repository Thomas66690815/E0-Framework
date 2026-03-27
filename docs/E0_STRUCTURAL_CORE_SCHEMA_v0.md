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

## 10. Current status of this schema

This schema is a **draft working proposal**.

It should currently be read as:

- a design bridge between architecture and implementation,
- a future interface contract for hooks and adapters,
- and an explicit statement that E₀ should act on structure, not on hidden semantic residue.

It is not yet a canonical law. It is a repository-native proposal emerging from the lived principles of the work.

---

## Status

**Status:** Draft protocol note  
**Version:** 0.1  
**Relation to canon:** compatible, but not canonical  
**Relation to implementation:** intended future bridge between adapters and controller  
**Relation to papers:** architectural companion, not a substitute for formal derivation
