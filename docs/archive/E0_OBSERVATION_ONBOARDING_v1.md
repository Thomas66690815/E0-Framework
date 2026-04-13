# E₀ Observation System — Onboarding Guide

**Version:** 1.0  
**Date:** 2026-04-04  
**Prerequisite commits:** C94–C97  
**Companion doc:** `docs/E0_OBSERVATION_UI_ARCHITECTURE_v1.md` (design philosophy)

## 1. What Is Observation?

E₀ treats observation as navigation.  The observer has a **scope** (which
nodes are visible) and a **depth** (how much data is revealed).  Moving
between scopes costs attention; going deeper costs cognitive effort.
These costs use the same (Δ, R₀) primitives as domain navigation.

The result is an **O-Landscape** — a Landscape whose states represent
observation positions.  Because it is a real Landscape, it historizes:
repeated observation of the same area lowers its resistance.  The
observer learns.

## 2. Quickstart — Python Only (No Server)

```python
from e0_controller.landscape import Landscape
from e0_controller.observation_controller import ObservationController

# 1. Build a domain
domain = Landscape()
domain.add_edge("A", "B", delta=0.3, resistance=0.4)
domain.add_edge("B", "C", delta=0.5, resistance=0.3)
domain.add_edge("C", "A", delta=0.2, resistance=0.5)

# 2. Create an observer
obs = ObservationController(domain)
print(obs.current)        # "g:topo"  (global scope, topology depth)
print(obs.scope)          # "g"
print(obs.depth)          # "topo"

# 3. Navigate
obs.focus("A")            # global → local(A)
obs.deepen()              # topo → field (scalar values now visible)
obs.move("B")             # A → B (domain neighbor)
obs.retreat()             # field → topo
obs.defocus()             # local → global

# 4. See what's visible
projection = obs.project()
print(projection["nodes"])   # visible nodes (scope-dependent)
print(projection["edges"])   # visible edges
print(projection.get("field"))  # None at topo, dict at field+

# 5. Check navigation options
for opt in obs.options():
    print(f"  → {opt['target']}  r_eff={opt['r_eff']:.2f}")
```

### StepResult

Every navigation method returns a `StepResult`:

```python
result = obs.focus("A")
result.success    # bool — did the transition work?
result.previous   # "g:topo"
result.current    # "n:A:topo"
result.r_eff      # cognitive resistance of this step
result.s_eff      # change magnitude
```

## 3. Depth Levels

| Index | Name | What `project()` adds | Meaning |
|-------|------|-----------------------|---------|
| 0 | **topo** | `nodes`, `edges` | Structure only — no numeric values |
| 1 | **field** | + `field` dict | Δ, R₀, R_eff, S_eff per edge |
| 2 | **dyn** | + `dynamics` dict | U, F, trace_load, trace_quality — history |
| 3 | **mech** | + `mechanism` dict | Controller state (extension point) |
| 4 | **intf** | + `interference` dict | Amplitude overlay (extension point) |

Transition costs increase with depth:

| Transition | Δ | R₀ |
|------------|---|-----|
| topo → field | 0.3 | 0.3 |
| field → dyn | 0.4 | 0.5 |
| dyn → mech | 0.6 | 0.8 |
| mech → intf | 0.8 | 1.2 |
| Any retreat | 0.1 | 0.1 |

## 4. Scope Levels

| Scope | Visible | Transitions |
|-------|---------|-------------|
| **g** (global) | All domain nodes | Can `focus(node)` on any node |
| **n:X** (local) | Node X + its domain neighbors | Can `move(neighbor)` or `defocus()` |

**Constraint (Canon §9):** Scope and depth cannot change simultaneously.
`focus("A")` then `deepen()` — never both at once.

## 5. Wire Format — Rendering Adapter

```python
from e0_controller.rendering_adapter import render_observation

wire = render_observation(obs)
# Returns GraphView-compatible JSON:
# {
#   "states": [...],
#   "edges": { "A→B": { "source", "target", "delta", "R_eff", ... } },
#   "modulation": { "curvature": bool, "overlap": bool, "inertia": bool },
#   "observation": {
#     "state": "n:A:field",
#     "scope": "n:A",
#     "depth": "field",
#     "depth_index": 1,
#     "focused_node": "A",
#     "history": ["g:topo", "n:A:topo", "n:A:field"],
#     "options": [ { "target": ..., "r_eff": ..., "s_eff": ... }, ... ],
#   },
# }
```

This is the **same format** as domain snapshots.  `GraphView.jsx` renders
both without any code changes.

## 6. Server + UI Quickstart

### Start the backend

```bash
py -3 -m uvicorn server.main:app --reload
# Listens on http://localhost:8000
# OpenAPI docs: http://localhost:8000/docs
```

### Start the frontend

```bash
cd client
npm install
npm run dev
# Listens on http://localhost:5173 (proxies /sessions to :8000)
```

### Use observation in the browser

1. Open `http://localhost:5173`
2. Load any scenario (or create a session via API)
3. Click the **👁 Observe** toggle button in the toolbar
4. The graph switches from domain view to observation view
5. Use **▼ Deepen** / **▲ Retreat** buttons to change depth
6. Click a node to **focus** on it (scope narrows to node + neighbors)
7. Click another node to **move** (if it is a domain neighbor)
8. Click the focused node again (or press **⊕ Defocus**) to return to global

### REST endpoints

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/sessions/{id}/observation` | Current observation snapshot |
| `GET` | `/sessions/{id}/observation/meta` | O-Landscape itself (meta-view) |
| `POST` | `/sessions/{id}/observation/navigate` | Navigate: `{ "action": "focus\|defocus\|deepen\|retreat\|move", "node_id": "..." }` |

### Client API (JavaScript)

```javascript
import { getObservation, getObservationMeta, navigateObservation } from './api';

const snap = await getObservation(sessionId);
console.log(snap.observation.depth);  // "topo"

await navigateObservation(sessionId, 'focus', 'nodeA');
await navigateObservation(sessionId, 'deepen');

const updated = await getObservation(sessionId);
console.log(updated.observation.depth);  // "field"
```

## 7. Attaching Observation to Existing Code

Observation plugs into any code that has a `Landscape`:

```python
from e0_controller.observation_controller import ObservationController

# Works with any Landscape — domain, canon, bootstrapped, etc.
obs = ObservationController(my_landscape)

# Navigate, project, render — all the same API
obs.focus("some_node")
obs.deepen()
print(obs.project())
```

In `ServiceSession`, observation is lazy-initialized automatically.
Any session that has a Landscape gets observation for free — no
configuration needed.

## 8. Historization — The Learning Effect

Every observation transition updates the O-Landscape's historization:

```python
obs.focus("A")   # First time: R_eff = R₀ + δ_H(0, 0)
obs.defocus()
obs.focus("A")   # Second time: R_eff < first (traces accumulated)
obs.defocus()
obs.focus("A")   # Third time: even cheaper
```

The observer cannot escape learning.  Frequently visited observation
paths become easier.  This is not a feature — it is a consequence of
using standard historization.

## 9. Key Design Properties

1. **No special-casing.** O-Landscape uses the same `Landscape` class,
   same `Edge`, same `Historization` as any domain.

2. **Same rendering pipeline.** `GraphView.buildElements()` does not
   know whether it renders a domain or an observation snapshot.

3. **Inadmissibility protects the observer.** No scope+depth cross-
   transitions.  Information overload is structurally prevented.

4. **Session-scoped.** Each session has its own `ObservationController`.
   Multiple observers on the same domain have independent histories.

5. **Meta-observation exists.** `render_observation_landscape(obs)`
   renders the O-Landscape itself as a graph — the observer can observe
   the observation space.

## 10. Test Coverage

| Module | File | Tests |
|--------|------|-------|
| O-Landscape builder | `test_observation.py` | 39 |
| Navigation + projection | `test_observation_controller.py` | 47 |
| Wire format | `test_rendering_adapter.py` | 32 |
| REST + session | `test_observation_integration.py` | ~10 |

~128 observation-specific tests within the framework suite.
