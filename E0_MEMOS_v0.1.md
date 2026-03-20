# E₀ MemOS v0.1

**Status:** Draft architecture note  
**Purpose:** Persistent runtime substrate for Phase 3 (LLM integration)  
**Scope:** Local, session-persistent E₀ state management. No cloud, no multi-user convergence, no distributed system claims.

---

## 1. Motivation

The normal chat thread is an unstable carrier for E₀.

A thread can preserve wording, but not reliably preserve:

- canonical ontological reference,
- persistent landscape state,
- historized transition traces,
- controller runtime state,
- bounded retrieval of structurally relevant prior runs.

For Phase 3, the LLM should not receive only conversation text.
It should receive a **persisted E₀ state snapshot**.

That motivates **E₀ MemOS**:

a persistent runtime layer between the E₀ controller stack and the LLM-facing semantic interface.

---

## 2. Design Principle

E₀ MemOS is **not** the controller.
It is **not** the canon.
It is **not** the LLM.

It is the persistence and retrieval substrate that keeps these layers coherent across runs.

### Architectural asymmetry

```text
Canonical Layer
    ↓
Persistent Landscape Layer
    ↓
Persistent Historization Layer
    ↓
Controller Runtime Layer
    ↓
Semantic Interface Layer (LLM)
```

The LLM is therefore **not sovereign**.
But it is also **not just an arbitrary tool**.
It acts as the semantic interface layer over a persisted E₀ state.

---

## 3. Non-goals for v0.1

E₀ MemOS v0.1 does **not** attempt to provide:

- cloud/distributed infrastructure,
- cross-user convergence,
- universal retrieval over all projects,
- autonomous ontology rewriting,
- replacement of the deterministic controller,
- guaranteed coherence or correctness.

v0.1 is intentionally local, explicit, and bounded.

---

## 4. Minimal Required Layers

### 4.1 Canon Layer (read-mostly)

Relatively stable reference material.

Contents:

- E₀ canonical texts,
- ontodynamic reference material,
- glossary / key term definitions,
- explicit version identifiers.

Properties:

- versioned,
- immutable within a run,
- replaceable only by explicit upgrade.

### 4.2 Landscape Layer

Persistent state of the current modeled domain.

Contents:

- states,
- edges,
- Δ values,
- R₀ values,
- optionally derived phase-layer artifacts (Φ, ω) if cached.

Properties:

- serializable,
- domain-specific,
- reusable across sessions.

### 4.3 Historization Layer

Persistent transition memory.

Contents:

- success traces,
- failure traces,
- trace timestamps / τ markers,
- run history,
- per-edge historization metadata.

Properties:

- affects R_eff / S_eff,
- session-persistent,
- queryable by edge, path, and run.

### 4.4 Controller Runtime Layer

Short-horizon operational state.

Contents:

- recent visited states,
- escalation overlay/buffer,
- current metrics snapshot,
- last decision context,
- optional bounded path cache.

Properties:

- mutable within a run,
- resettable,
- partly persistable between runs.

---

## 5. Minimal Data Model

```python
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any

@dataclass
class CanonRef:
    name: str
    version: str
    path: str
    sha: Optional[str] = None

@dataclass
class LandscapeSnapshot:
    landscape_id: str
    states: List[str]
    edges: List[dict]           # source, target, delta, r0
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class HistorizationSnapshot:
    tau: int
    success_traces: Dict[str, float]
    failure_traces: Dict[str, float]
    records: List[dict] = field(default_factory=list)

@dataclass
class ControllerRuntimeSnapshot:
    recent_states: List[str] = field(default_factory=list)
    escalation_edges: List[dict] = field(default_factory=list)
    metrics: Dict[str, float] = field(default_factory=dict)
    last_decision: Optional[dict] = None

@dataclass
class MemOSContext:
    session_id: str
    canon_refs: List[CanonRef]
    landscape: LandscapeSnapshot
    historization: HistorizationSnapshot
    runtime: ControllerRuntimeSnapshot
    notes: Dict[str, Any] = field(default_factory=dict)
```

This model is intentionally plain and serializable.

---

## 6. Core Responsibilities of MemOS

E₀ MemOS v0.1 should do exactly four things well.

### 6.1 Persist

Save the current E₀-relevant runtime state.

### 6.2 Restore

Reconstruct a usable controller context from persisted data.

### 6.3 Summarize

Produce bounded, token-efficient state summaries for the semantic interface.

### 6.4 Retrieve

Return structurally relevant prior traces, runs, and edge histories.

Not “similar text” retrieval by default, but retrieval based on E₀ structure.

---

## 7. Minimal Runtime Interface

```python
class E0MemoryOS:
    def load_context(self, session_id: str) -> MemOSContext:
        ...

    def save_context(self, context: MemOSContext) -> None:
        ...

    def snapshot_from_runtime(
        self,
        session_id: str,
        landscape,
        historization,
        controller,
    ) -> MemOSContext:
        ...

    def summarize_for_llm(self, context: MemOSContext, current_state: str) -> dict:
        ...

    def retrieve_recent_runs(self, session_id: str, limit: int = 5) -> List[dict]:
        ...

    def retrieve_edge_history(self, session_id: str, edge_key: str) -> dict:
        ...
```

This interface is enough to support Phase 3 without overcommitting to a large platform architecture.

---

## 8. LLM Interface Principle

The LLM should not receive raw thread history as its primary context.

Instead it should receive a bounded E₀ state package such as:

```json
{
  "canon_refs": ["e0-canonical-reference@v1.0"],
  "current_state": "DATA_EXTRACTED",
  "admissible_neighbors": ["CUSTOMER_FOUND", "HUMAN_REVIEW"],
  "edge_history": {
    "DATA_EXTRACTED→CUSTOMER_FOUND": {
      "U": 0.0,
      "F": 2.7,
      "delta_H": 0.54
    }
  },
  "runtime": {
    "recent_states": ["PDF_LOADED", "DATA_EXTRACTED"],
    "escalation_type": "NONE"
  },
  "task": "interpret missing customer match and propose structured next-state candidates"
}
```

This keeps the LLM in **semantic interface mode**, not in uncontrolled freeform mode.

---

## 9. Retrieval Principle

Retrieval in MemOS should be E₀-aware.

Priority order:

1. current landscape neighborhood,
2. current edge historization,
3. recent run traces,
4. structurally similar prior transitions,
5. canon references.

This means retrieval should prefer:

- same state,
- same edge,
- same admissibility situation,
- same escalation type,
- similar recent-state pattern,

before doing any broader semantic recall.

---

## 10. Persistence Format

v0.1 should prefer simple local persistence.

Recommended options:

- JSON snapshots for clarity,
- optional SQLite later for indexed retrieval,
- no remote service required.

Suggested file layout:

```text
memos/
├── canon/
│   └── refs.json
├── sessions/
│   └── <session_id>.json
├── runs/
│   └── <session_id>/
│       ├── run_0001.json
│       ├── run_0002.json
│       └── ...
└── indices/
    └── edge_history.json
```

This is sufficient for the first local MemOS runtime.

---

## 11. Relationship to Current Repo State

MemOS v0.1 is intended to sit **after Phase 2 and before Phase 3**.

It should integrate with the existing `e0_controller/` stack without changing the mathematical core.

It should reuse:

- `Landscape`,
- `Historization`,
- `E0Controller`,
- `RunTrace`,
- phase-layer artifacts where useful.

It should **not** require rewriting controller logic.

---

## 12. Immediate Pre-Phase-3 Use Case

Before LLM integration, MemOS should already support:

1. save controller state after a run,
2. reload it in a fresh process,
3. reconstruct a bounded summary for a target state,
4. show that historization persists across sessions,
5. confirm that controller behavior changes because memory is persisted.

If these five things work, MemOS is already useful.

---

## 13. Recommended Next Step

Introduce a new pre-Phase-3 stage:

### Phase 2c — E₀ MemOS v0.1

Deliverables:

- `memory_os.py`
- serializable snapshot classes
- save/load helpers
- bounded LLM summary builder
- 8–12 tests for persistence and restore correctness
- status update in `E0_CONTROLLER_STATUS.md`

---

## 14. Core Thesis

E₀ does not become stable through larger prompts.
It becomes stable through **persistent structured state**.

Therefore the right way to enter Phase 3 is not:

> “add an LLM to the current controller”

but:

> “insert a persistent E₀ memory substrate, then let the LLM operate over bounded E₀ state snapshots.”

That is the purpose of E₀ MemOS v0.1.
