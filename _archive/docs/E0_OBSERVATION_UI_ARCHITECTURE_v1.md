# E₀ Observation UI Architecture

**Version:** 1.0  
**Date:** 2026-04-01  
**Commits:** C83–C97  
**Status:** Implemented.  3020 tests.

## 1. The Failed Attempt: Dashboard-First UI (C85)

The first UI implementation (C85, commit `0a63825`) followed standard
practice: a dashboard layout with separate panels for different concerns.

**Components built:**
- `Header.jsx` — session info, state badge, mode indicator
- `ControlPanel.jsx` — input mode selector, start config, run controls
- `HistoryTimeline.jsx` — scrollable step history with outcome markers
- `MetricsPanel.jsx` — success rate charts, learning curves (recharts)
- `PeerDialog.jsx` — human peer interaction panel
- `GraphView.jsx` — Cytoscape graph visualization
- `App.jsx` — sidebar + graph + right panel layout

**Result:** 9 components, 840 lines CSS, 1052KB bundle (including recharts
for charts that added nothing to understanding), 659 module dependencies.

**What went wrong:** This was a conventional UI design — partition the
screen into panels, one per concern. Each panel knows about one aspect
of E₀ (history, metrics, controls, graph). The UI structure does not
reflect E₀'s structure. It imposes an external taxonomy on the system.

This violates Ontodynamics §1: _"The observer is not outside the system."_

A panel-based dashboard positions the user as an external observer
looking at disconnected projections. The information is there, but the
topology is gone. You see numbers in panels but not the relationships
between the numbers. You cannot navigate the system — you can only
scroll through tables.

## 2. The Pivot: Keimzelle (C88)

Three commits after C85, the dashboard was scrapped. C88 (commit
`6e1d13a`, "Keimzelle — graph-centric UI rebuild") stripped everything
back to one principle:

**The graph IS the interface.**

One screen: toolbar → graph → status line. No tabs, no sidebars, no
panels. Every piece of information is projected onto the graph itself
through the field selector (trace_quality, trace_load, S_eff, R_eff,
δ_H, coherence, inertia). Clicking an edge shows the full numeric
profile. Clicking a node starts navigation.

**Result:** 4 files changed, 270 lines CSS (was 840), 653KB bundle
(was 1052KB), header/timeline/metrics/control panels deleted.

**Why it worked:** The graph topology carries the information. Edge
color = tension. Node color = accumulated field value. Gold trail =
where E₀ has walked. You do not need a "history panel" because the
history is written on the graph as trail markers. You do not need a
"metrics panel" because the metrics are the edge colors.

The graph is not a _visualization_ of the data. The graph _is_ the
data. The Landscape IS the system state.

## 3. But Something Was Missing

C88–C93 iterated on the Keimzelle:  C89 added edge labels and status
metrics, C90 added glow and path trail animation, C91 added peer
interaction (Zentrale), C92 added the mechanism indicator, C93 added
14 built-in scenarios with hybrid mode support.

Each iteration added features to the graph view. But the fundamental
problem remained: the UI shows one flat projection of the entire
Landscape at a fixed depth. You see all nodes, all edges, one field
dimension at a time. For a 6-node scenario this is fine. For a 50-node
domain it becomes visual noise.

The question was not "how do we add zoom and filter to the graph" (the
standard UI answer). The question was:

> **How would E₀ itself build the UI?**

## 4. The Insight: Observation as Navigation

If E₀ treats every domain as a navigable state space with tension and
resistance, then observation of E₀ is also a navigation problem.

The observer has a position: _what_ they are looking at (scope) and
_how deeply_ they are looking (depth). Moving between scopes costs
attention. Going deeper costs cognitive effort. These costs have the
same structure as Δ and R₀.

This is not a metaphor. It is a direct application:

- **States** = (scope, depth) pairs. Scope is "global" or "focused on
  node X". Depth is topo → field → dyn → mech → intf.
- **Edges** = admissible observation transitions. You can deepen or
  retreat. You can focus on a node or defocus. You can move between
  neighboring nodes. You cannot change scope and depth simultaneously
  (inadmissibility from Canon §9).
- **Δ** = information change. Deep transitions reveal more data.
  Scope narrowing reveals neighborhood detail.
- **R₀** = cognitive resistance. Deepening costs more than retreating.
  Focusing is cheaper than an overview.
- **Historization** = observer learning. If you repeatedly focus on
  node A, the resistance to observing A decreases. The observer
  develops expertise.

This is the O-Landscape: the Observation Landscape.

## 5. Implementation Arc (C94–C97)

### C94: observation.py — The O-Landscape (commit `9c10217`)

`build_observation_landscape(domain)` takes any domain Landscape and
produces an O-Landscape with (1+N)×5 states (N = domain node count,
5 = depth levels). State encoding: `"{scope}:{depth}"`.

Edge rules enforce the inadmissibility constraint: no simultaneous
scope + depth change. 39 tests.

Key finding: amplitude overlay on the O-Landscape favors scope
transitions over depth progression due to combinatorial path count.
This means goal-directed observation needs explicit intent — the
controller alone makes suboptimal observation choices.

### C95: observation_controller.py — Navigation + Projection (commit `806404c`)

Five navigation primitives:
- `focus(node)` — global → local
- `defocus()` — local → global
- `move(node)` — local → local (domain neighbors)
- `deepen()` — topo → field → … → intf
- `retreat()` — reverse

Plus `project()`: a pure read of the domain through the current
observation lens. What is visible depends on scope (which nodes) and
depth (which data layers). 47 tests.

Observer learning demonstrated: repeated `focus("A")` lowers `R_eff`
for observing A, making A cheaper to study than unvisited nodes.

### C96: rendering_adapter.py — Projection to Wire Format (commit `2915461`)

Pure function `render_observation(ctrl)` converts `project()` output
to the same format as `encode_landscape()` from snapshot_codec. This
means the existing `GraphView.jsx` can render observation output
without any changes to `buildElements()`. 32 tests.

The format match is intentional: the rendering adapter is a codec, not
a UI component. It produces `{states, edges, modulation, observation}`
where the observation key carries metadata (scope, depth, focused_node,
navigation options, history).

### C97: UI Integration (commit `92d86a8`)

Wiring:
- `ServiceSession` gets lazy `observation_ctrl`, `observation_snapshot()`,
  `observation_navigate()` methods
- Server: 3 REST endpoints (`GET /observation`, `GET /observation/meta`,
  `POST /observation/navigate`)
- Client: `getObservation()`, `navigateObservation()` API functions
- UI: Observe toggle button, observation panel with scope/depth display
  and Retreat/Deepen/Defocus controls, node-click = focus/move/defocus

Zero changes to GraphView rendering. 28 tests. 3020 total.

## 6. Architecture Summary

```
Domain Landscape ──────────────────────────────────────────────────
     │                                                            
     ├── E0Controller.cycle()  →  domain decisions (execution)     
     │         │                                                   
     │         └── StepEvent → history → GraphView (domain view)   
     │                                                             
     └── ObservationController  →  observation decisions (viewing)  
              │                                                    
              ├── project()    →  what user can see (scope + depth) 
              ├── navigate()   →  how user moves attention          
              └── render_observation()  →  GraphView (observation)  
                                                                   
GraphView.buildElements(snapshot, field) — unchanged               
  snapshot.landscape.states: [...]                                 
  snapshot.landscape.edges:  { "A→B": {...} }                      
  ↑ same format whether domain snapshot or observation snapshot     
```

The client has two modes:
1. **Domain mode** (default): `GET /snapshot` → full Landscape view
2. **Observation mode** (toggle): `GET /observation` → filtered view
   based on observer position

Both use the same GraphView rendering. The observation system does not
add a new rendering layer — it filters what enters the existing one.

## 7. Design Principles Validated

1. **No special-casing.** Observation uses the same primitives as any
   domain: states, edges, Δ, R₀, historization. No "observation-specific"
   data structures.

2. **The observer is part of the system.** The O-Landscape is itself
   a Landscape. It could be observed by a meta-observer (and this is
   implemented: `render_observation_landscape()`).

3. **UI structure follows domain structure.** The graph IS the interface.
   Observation does not add panels or dashboards. It changes what the
   graph shows.

4. **Historization is universal.** Observer learning (lower R_eff for
   repeated observation) is not a feature — it is a consequence of using
   the same historization mechanism. The observer cannot escape learning.

5. **Inadmissibility protects the observer.** You cannot change scope
   and depth simultaneously. This is not a UI limitation — it is a
   cognitive constraint from Canon §9. The system protects the observer
   from information overload the same way it protects domain navigation
   from incoherent transitions.

## 8. What Was Learned

The dashboard UI (C85) was not wrong in what it showed — it was wrong
in how it structured the showing. It externalized the observation
problem: the developer decides what panels exist, what metrics to show,
what tabs to offer. The user navigates a static taxonomy.

The observation approach (C94–C97) internalizes the observation problem:
the user navigates the information space the same way E₀ navigates the
domain space. Depth is earned, not displayed. Scope is chosen, not
defaulted. Attention has cost, and the system learns where you look.

This is the difference between a map and a journey. The dashboard gives
you the map. The observation system gives you the territory and lets
you walk it.

The practical consequence: zero GraphView changes for observation
support. The rendering pipeline (`buildElements`) does not care whether
the snapshot is a domain snapshot or an observation snapshot. Both are
`{states, edges}`. The only new UI elements are the toggle button and
three navigation controls (Deepen, Retreat, Defocus). Everything else
is the graph.

**Bundle: 653KB. Components: GraphView + obs panel. Tests: 3020.**
