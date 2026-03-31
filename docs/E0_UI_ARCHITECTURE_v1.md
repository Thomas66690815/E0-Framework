# E₀ UI & Integration Architecture v1

**Status:** Architecture Design (pre-implementation)  
**Date:** 2026-03-31  
**Depends on:** E0_ARCHITECTURE_OVERVIEW_v2.md, E0_LLM_BOOTSTRAP_ARCHITECTURE_v1.md  
**Commit baseline:** C82 (e78a217), 2800 tests, 82 commits  

---

## 1. Design Mandate

E₀ is a framework. A framework must be integrable into anything. The UI is therefore not "the application" — it is **one consumer** of an E₀ service layer that any system can use.

Two functional modes define the UI:

- **Oszilloskop** (Observatory): Watch E₀ think. Live graph visualization. Trace evolution, decision rationale, escalation events, learning curves — all visible as they happen.
- **Zentrale** (Command Center): The human IS the peer. When E₀ encounters overload (OI > threshold), it asks. The human sees the candidates, clicks, and E₀ continues. The human is not a spectator — they are a structural participant.

Both modes operate simultaneously. The Oszilloskop is always on; the Zentrale activates when E₀ needs it.

Two input channels:

- **Structured JSON** → Bootstrapper → Landscape (direct, no LLM)
- **Unstructured text** → LLM Adapter → DomainSpec → Bootstrapper → Landscape

---

## 2. Layer Architecture

```
┌──────────────────────────────────────────────────────────────┐
│  Layer A — E₀ CORE (existing, unchanged)                     │
│  Controller, Landscape, Historization, Reflexion, Multiverse │
│  Pure Python. No framework dependencies. No I/O.            │
└──────────────────────┬───────────────────────────────────────┘
                       │ direct Python calls
┌──────────────────────▼───────────────────────────────────────┐
│  Layer B — E₀ SERVICE LAYER (new)                            │
│  SessionManager: lifecycle, event emission, state snapshots  │
│  PeerBridge: async peer_fn ↔ human/API/LLM                  │
│  InputPipeline: text or JSON → validated Landscape           │
│  SnapshotCodec: Landscape ↔ JSON (wire format)               │
└──────────────────────┬───────────────────────────────────────┘
                       │ JSON + WebSocket events
┌──────────────────────▼───────────────────────────────────────┐
│  Layer C — API GATEWAY (new)                                 │
│  FastAPI: REST for CRUD, WebSocket for live stream            │
│  Auth, rate limiting, session routing                        │
└──────────────────────┬───────────────────────────────────────┘
                       │ HTTP + WebSocket
┌──────────────────────▼───────────────────────────────────────┐
│  Layer D — CLIENT (new)                                      │
│  React + Cytoscape.js: graph visualization & interaction     │
│  Real-time event stream, peer dialog, history panel          │
└──────────────────────────────────────────────────────────────┘
```

**Key constraint:** Layer A never changes for the UI. The service layer wraps it. If a future consumer (CLI, embedded system, another AI) wants to use E₀, they depend on Layer B — not on the UI.

---

## 3. Layer B — E₀ Service Layer

### 3.1 SessionManager

Wraps an E₀Controller run with event emission and state management.

```python
class E0Session:
    id: str                          # UUID
    landscape: Landscape
    controller: E0Controller
    mode_controller: ModeController
    state: SessionState              # CREATED, RUNNING, WAITING_PEER, PAUSED, COMPLETED
    current_position: str
    history: List[StepEvent]

    async def start(self, start: str, goal: str = None, max_cycles: int = 50)
    async def pause()
    async def resume()
    async def step()                 # single cycle, returns StepEvent
    def snapshot() -> dict           # full serialized state
```

**Event Bus:** Every `cycle()` call emits a `StepEvent` to all subscribers:

```python
@dataclass
class StepEvent:
    tau: int
    source: str
    target: str
    outcome: Outcome
    s_eff: float
    escalation_type: EscalationType
    candidates: List[str]
    chosen_reason: str               # "greedy", "peer_override", "focus_random"
    trace_snapshot: Dict[str, EdgeInfo]  # all edges with current U, F, q, m
    overlay: Optional[OverlayReport]
    mode: OperatingMode              # LEARN / EXECUTE / COMBINATION
    oi: Optional[float]              # overload index if computed
    timestamp: float
```

This is the **single event contract** between E₀ and any consumer. The Oszilloskop renders it. The Zentrale reacts to it. An external logger stores it. A monitoring system alerts on it.

### 3.2 PeerBridge

The `peer_fn` callback in E0Controller is synchronous: `(landscape, current, neighbors) → target`. For a human peer, this must become asynchronous — the controller pauses until the human responds.

```python
class PeerBridge:
    """Adapts synchronous peer_fn to async human/API interaction."""

    async def request_peer_input(
        self,
        session_id: str,
        current: str,
        neighbors: List[str],
        edge_info: Dict[str, EdgeInfo],  # info per candidate
        oi: float,
    ) -> str:
        # 1. Emit PEER_REQUEST event via WebSocket
        # 2. Set session.state = WAITING_PEER
        # 3. await response (with configurable timeout)
        # 4. Validate response ∈ neighbors (or k+1 custom suggestion)
        # 5. Return chosen target
```

**Implementation pattern:** The controller run executes in an asyncio task. When `peer_fn` is called, it sets an `asyncio.Event`, the WebSocket handler sends the request to the client, and the controller task awaits the response event. No threads, no polling.

**Timeout behavior:** If no human responds within a configurable window (default: 60s), fall back to random selection from candidates (consistent with C81 insight — random is a valid strategy).

### 3.3 InputPipeline

```python
class InputPipeline:
    async def from_json(self, spec: dict) -> Landscape:
        # validate_spec() → bootstrap_landscape()
        # Direct path, no LLM

    async def from_text(self, description: str) -> Landscape:
        # LLMAdapter.propose_and_bootstrap(description)
        # Returns landscape + provenance log

    async def from_canon(self, name: str) -> Landscape:
        # canon_loader.load_canon(name).landscape
```

### 3.4 SnapshotCodec

Standardized JSON wire format for Landscape + Historization, used by both REST API and WebSocket events.

```python
class SnapshotCodec:
    @staticmethod
    def encode_landscape(landscape: Landscape) -> dict:
        # states, edges (with Δ, R₀, R_eff, S_eff, q, m, δ_H per edge),
        # historization summary, modulation flags

    @staticmethod
    def decode_landscape(data: dict) -> Landscape

    @staticmethod
    def encode_step(step: StepResult) -> dict

    @staticmethod
    def encode_strategy_profile(hist: Historization) -> List[dict]
```

---

## 4. Layer C — API Gateway

### 4.1 Technology Choice: FastAPI

**Why FastAPI over alternatives:**

| Criterion | FastAPI | Flask | Django | Litestar |
|-----------|---------|-------|--------|----------|
| Native async | Yes | No (ext.) | No (ext.) | Yes |
| WebSocket built-in | Yes | No (ext.) | No (channels) | Yes |
| Pydantic validation | Native | Manual | Serializers | Native |
| Auto OpenAPI docs | Yes | Ext. | Ext. | Yes |
| Type hints | Core design | Opt. | Partial | Core design |
| E₀ ecosystem fit | Python-native, lightweight | OK | Too heavy | OK |

FastAPI wins because:
1. **WebSocket is first-class** — critical for live E₀ events and peer interaction
2. **Pydantic models match E₀ dataclasses** — StepResult, EdgeSpec, DomainSpec map directly
3. **Async-native** — PeerBridge requires await without blocking other sessions
4. **OpenAPI auto-generation** — any future consumer gets API docs for free

Litestar is a valid alternative with similar capabilities. FastAPI is chosen for ecosystem maturity and broader documentation.

### 4.2 REST Endpoints

```
POST   /sessions                    Create session (from JSON spec, text, or canon name)
GET    /sessions/{id}               Session state + current snapshot
DELETE /sessions/{id}               Terminate session
POST   /sessions/{id}/start         Start run (start state, goal, max_cycles)
POST   /sessions/{id}/pause         Pause run
POST   /sessions/{id}/resume        Resume run
POST   /sessions/{id}/step          Execute single cycle
GET    /sessions/{id}/history       Full step history
GET    /sessions/{id}/strategy      strategy_profile() — what did E₀ learn?
GET    /sessions/{id}/snapshot       Current landscape snapshot (full JSON)
GET    /canons                       List available canons
GET    /canons/{name}                Canon metadata
GET    /health                       Server health
```

### 4.3 WebSocket Protocol

```
WS /sessions/{id}/ws
```

**Server → Client events:**

| Event | Trigger | Payload |
|-------|---------|---------|
| `step` | Every cycle() | StepEvent (full) |
| `escalation` | Any escalation | StepEvent + escalation details |
| `peer_request` | OI > threshold | current, neighbors, edge_info, oi |
| `mode_change` | Mode transition | old_mode, new_mode, coverage |
| `completed` | Run finished | RunTrace.metrics() summary |
| `error` | Exception | error message |

**Client → Server events:**

| Event | Trigger | Payload |
|-------|---------|---------|
| `peer_response` | Human decides | chosen target (must be valid) |
| `pause` | User pauses | — |
| `resume` | User resumes | — |

**Wire format:**
```json
{
    "event": "step",
    "session_id": "uuid",
    "tau": 7,
    "data": { /* StepEvent fields */ }
}
```

---

## 5. Layer D — Client

### 5.1 Technology Choice: React + Cytoscape.js

**Graph visualization is the core requirement.** The Landscape IS a graph. States are nodes. Edges carry Δ, R₀, δ_H, U, F, q, m. The human needs to see structure, not tables.

**Why Cytoscape.js:**
- Purpose-built for graph/network visualization (not repurposed from charting)
- Built-in layout algorithms: force-directed (for organic structure), hierarchical (for derivation levels), circle (for small graphs)
- CSS-like styling: map `trace_quality` → node color, `trace_load` → node size, `S_eff` → edge thickness
- Event system: click on node to select as peer suggestion, hover for edge info
- Handles 100+ nodes smoothly (confirmed by C81 scaling experiments at N=100)
- Active maintenance, MIT licensed

**Why not D3.js:** Maximum control, but requires building graph layout, interaction, and animation from scratch. Cytoscape.js provides all of this purpose-built.

**Why not vis.js:** Simpler API, but less capable styling and weaker layout algorithms for complex graphs.

**Why React:**
- Component model matches the UI structure naturally: GraphView, ControlPanel, HistoryTimeline, PeerDialog, MetricsPanel
- State management (via React state or Zustand) handles complex real-time updates across panels
- Ecosystem: recharts or visx for learning curves, tension evolution, escalation statistics

**Why not Streamlit:** Fast to prototype, but:
- No real-time WebSocket support (server-push only via polling hack)
- No interactive graph visualization (no click-to-select-node)
- Not suitable for Zentrale mode where the human needs sub-second interaction
- Cannot serve as a reusable integration example

### 5.2 UI Layout

```
┌───────────────────────────────────────────────────────────┐
│  HEADER: Session info, mode indicator, tau counter        │
├───────────────┬───────────────────────────────────────────┤
│               │                                           │
│  CONTROL      │           GRAPH VIEW                      │
│  PANEL        │           (Cytoscape.js)                  │
│               │                                           │
│  - Input      │  Nodes: color = trace_quality(q)          │
│    mode       │         size = trace_load(m)              │
│  - Start/     │         glow = current position           │
│    Pause/     │  Edges: thickness = 1/S_eff              │
│    Step       │         color = δ_H (green=good,red=bad) │
│  - focus_k    │         dash = escalation path            │
│  - threshold  │  Click node = peer suggestion             │
│  - Canon      │  Hover edge = info tooltip                │
│    selector   │                                           │
├───────────────┼──────────────────┬────────────────────────┤
│  PEER DIALOG  │  HISTORY         │  METRICS               │
│  (when OI >   │  TIMELINE        │  - Success rate         │
│   threshold)  │  - Step list     │  - Escalation count    │
│               │  - Outcome       │  - Learning curve      │
│  Candidates   │    markers       │  - Mode coverage       │
│  with info    │  - Scroll to     │  - Tension evolution   │
│  [Click to    │    any τ         │  - OI over time        │
│   choose]     │                  │                        │
└───────────────┴──────────────────┴────────────────────────┘
```

### 5.3 Oszilloskop Mode (Observatory)

The graph updates in real time as E₀ runs:

1. **Node color** encodes `trace_quality(q)`: green (+1) → yellow (0) → red (−1)
2. **Node size** encodes `trace_load(m)`: small = unexplored, large = heavily inscribed
3. **Current position** glows/pulses — the user sees where E₀ IS
4. **Edge thickness** ∝ 1/S_eff — low tension edges are thick (preferred), high tension edges are thin
5. **Edge color** encodes δ_H: green = positive history, red = negative history, gray = untouched
6. **Escalation events** flash the affected node/edge — DEAD_END (red flash), OVERLOADED (orange pulse)
7. **Path trail** — last N edges highlighted to show recent trajectory
8. **Learning curve** chart updates per step: success_rate, avg_tension over τ

**Speed control:** Slider from "real-time" (10ms per cycle) to "slow-motion" (1s per cycle) to "step-by-step" (manual advance).

### 5.4 Zentrale Mode (Command Center)

When E₀ emits `peer_request`:

1. Graph freezes at current state
2. **Peer Dialog** panel activates with:
   - Current node (highlighted)
   - All candidate neighbors listed with: `S_eff`, `trace_quality`, `trace_load`, `δ_H`
   - The overload index value
   - A "Why?" tooltip explaining what overloaded means
3. Human clicks a candidate node (either in the dialog list or directly on the graph)
4. The selection is sent via WebSocket as `peer_response`
5. E₀ resumes, graph animation continues
6. The peer's choice is logged in the history timeline with a distinct marker

**The human is a structural participant, not a button-presser.** The UI gives the human the same information E₀ has (edge info, candidates, OI) so the decision is informed.

### 5.5 Multiverse View (Future Extension)

When a MultiverseController is active:

- Side-by-side or layered graph views for Universe A and Universe B
- Coupling edges drawn between them (dashed, with NoveltyGate outcome color)
- Divergence pressure events visualized as new edges appearing
- Turn indicator showing which universe is active

This is a natural extension of the single-graph view. No architectural changes needed — the same `StepEvent` contract applies per universe, the client subscribes to multiple session WebSockets.

---

## 6. Data Flow Diagrams

### 6.1 Input → Run → Observe

```
User enters text ──→ POST /sessions {mode:"text", input:"..."}
                          │
                     InputPipeline.from_text()
                          │
                     LLMAdapter.propose_and_bootstrap()
                          │
                     Landscape created
                          │
                     E0Session created (CREATED)
                          │
User clicks Start ──→ POST /sessions/{id}/start
                          │
                     controller.run() starts in async task
                          │
              ┌───────────┴───────────┐
              │                       │
         cycle() emits          WebSocket pushes
         StepEvent              event to client
              │                       │
         historize()             Graph updates
              │                       │
         next cycle              Metrics update
              │
         ... repeats ...
              │
         goal reached or max_cycles
              │
         COMPLETED event → client shows summary
```

### 6.2 Peer Interaction Flow

```
         cycle() computes OI > threshold
              │
         peer_fn called (PeerBridge)
              │
         Session state → WAITING_PEER
              │
         WebSocket: peer_request {current, neighbors, edge_info, oi}
              │
         Client shows Peer Dialog
              │
         Human clicks candidate
              │
         WebSocket: peer_response {target: "chosen_node"}
              │
         PeerBridge validates, returns target
              │
         Session state → RUNNING
              │
         controller uses target as next state
              │
         cycle() continues normally
```

---

## 7. Integration Patterns

E₀ as a service enables multiple consumer types beyond the UI:

### 7.1 CLI Consumer

```bash
e0 run --spec domain.json --start A --goal Z --focus-k 8
e0 run --text "Optimize supply chain" --start current --max-cycles 100
e0 canons list
e0 session resume <session-id>
```

Uses Layer B directly (no API Gateway needed). Same SessionManager, same events (printed to stdout instead of WebSocket).

### 7.2 Embedded Consumer (Library Mode)

```python
from e0_controller.service import E0Session, InputPipeline

pipeline = InputPipeline()
landscape = await pipeline.from_json(my_spec)
session = E0Session(landscape)

async for event in session.run_stream(start="A", goal="Z"):
    my_system.process(event)  # handle StepEvents as needed
```

No server, no HTTP. Just Python async iteration.

### 7.3 Multi-Agent Consumer

Another AI system acts as peer:

```python
async def ai_peer(session_id, current, neighbors, edge_info, oi):
    # AI analyzes candidates using its own reasoning
    return best_candidate

bridge = PeerBridge(peer_handler=ai_peer)
session = E0Session(landscape, peer_bridge=bridge)
```

The PeerBridge abstracts whether the peer is human, AI, or another E₀ instance.

---

## 8. Session Persistence

Sessions can be saved and restored:

```python
# Save
snapshot = session.snapshot()
# Contains: landscape (full), historization (full), controller config,
# current_position, history, session metadata

# Restore
session = E0Session.from_snapshot(snapshot)
```

The existing `Landscape.to_snapshot_dict()` and `Historization.to_snapshot_dict()` + `from_snapshot_dict()` provide the serialization backbone. The service layer adds session metadata (timestamps, event counts, user annotations).

---

## 9. Security Considerations

- **Input validation:** All JSON specs go through `validate_spec()` (existing, strict). Unstructured text goes through LLM with bounded output.
- **WebSocket auth:** Session tokens issued on creation, required for WebSocket connection.
- **Rate limiting:** Per-session cycle rate limit prevents runaway loops.
- **No code execution:** E₀ never executes arbitrary code. `execute_fn` is either simulated (benchmarks), LLM-backed (structured output), or user-defined at session creation.
- **LLM API key:** Server-side only, never exposed to client.

---

## 10. Implementation Plan

### Phase 1 — Service Layer (Layer B)

Files to create:
- `e0_controller/service.py` — E0Session, SessionManager
- `e0_controller/peer_bridge.py` — PeerBridge (async adapter)
- `e0_controller/input_pipeline.py` — InputPipeline
- `e0_controller/snapshot_codec.py` — SnapshotCodec

Tests:
- `e0_controller/test_service.py`
- `e0_controller/test_peer_bridge.py`
- `e0_controller/test_snapshot_codec.py`

**No external dependencies.** Pure Python + asyncio. This layer is testable without FastAPI or React.

### Phase 2 — API Gateway (Layer C)

Files to create:
- `server/main.py` — FastAPI app
- `server/routes_sessions.py` — REST endpoints
- `server/ws_handler.py` — WebSocket handler
- `server/models.py` — Pydantic models (mapped from E₀ dataclasses)

New dependencies: `fastapi`, `uvicorn`, `websockets`

Tests:
- `server/test_routes.py` (httpx TestClient)
- `server/test_ws.py` (WebSocket TestClient)

### Phase 3 — Client (Layer D)

Files to create:
- `ui/` directory with React + Vite project
- `ui/src/components/GraphView.tsx` — Cytoscape.js wrapper
- `ui/src/components/ControlPanel.tsx`
- `ui/src/components/PeerDialog.tsx`
- `ui/src/components/HistoryTimeline.tsx`
- `ui/src/components/MetricsPanel.tsx`
- `ui/src/hooks/useE0Session.ts` — WebSocket connection management
- `ui/src/types/e0.ts` — TypeScript types matching Python models

New dependencies: `react`, `cytoscape`, `recharts`, `vite`

### Phase 4 — Multiverse View (Extension)

Extend GraphView to support multiple landscapes. No architectural changes needed.

---

## 11. Technology Summary

| Component | Technology | Justification |
|-----------|-----------|---------------|
| Service Layer | Python 3.12 + asyncio | Same language as E₀ core, zero friction |
| API Gateway | FastAPI + Uvicorn | Async-native, WebSocket first-class, Pydantic |
| Client Framework | React 18+ | Component model, state management, ecosystem |
| Graph Visualization | Cytoscape.js | Purpose-built for networks, layout + events |
| Charts | Recharts | React-native, simple API for learning curves |
| Build Tool | Vite | Fast HMR, first-class TypeScript support |
| Wire Format | JSON over WebSocket | Standard, debuggable, matches E₀ serialization |

---

## 12. Open Design Questions

1. **Step speed default:** Should E₀ run at maximum speed with the UI catching up (buffer events), or should it pace itself to animation speed? Recommendation: max speed + client-side buffering with playback control.

2. **Multi-session:** Should the server support multiple concurrent sessions? Recommendation: yes, each session is independent. The SessionManager holds a dict of sessions.

3. **Persistence backend:** File-based JSON snapshots vs. SQLite vs. external DB? Recommendation: start with file-based (JSON), same as current MemOS approach. Upgrade later if needed.

4. **LLM provider:** The LLMAdapter currently uses OpenAI. Should the UI expose provider selection? Recommendation: no, server-side configuration only. The UI should not know about LLM internals.

---

*This document is the contract for implementation. Layer B first, then C, then D. Each layer is independently testable. No layer depends on a layer below it.*
