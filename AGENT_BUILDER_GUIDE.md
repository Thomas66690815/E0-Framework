# E₀ — Agent Builder Guide

How to build an agent using E₀ mechanisms. Structured as progressive layers — each layer is independently runnable. Add the next only when the previous works.

Target audience: developers building decision-making agents that need persistent memory, learning from experience, and explainable navigation.

---

## The Full Loop

```
Δ (structural difference)
    ↓
[DifferenzPort] — input: sensor, LLM proposal, human instruction, API response
    ↓
E₀Controller — selects next state via argmin(S_eff / I)
    ↓
[E2Port] — executes in the world: API call, tool call, actuator, LLM generation
    ↓
Outcome (SUCCESS / FAILURE)
    ↓
Historization — inscribes U/F on the traversed edge
    ↓
(loop)
```

E₀ does not know what E2Port does. It only sees states and outcomes. Structure emerges from historization.

---

## Layer 0 — Minimal Controller (no LLM, no persistence)

**What you need:** `Landscape`, `E0Controller`, an `execute_fn`

```python
from e0_controller import E0Controller, Landscape, Outcome

# 1. Define your domain as states and transitions
L = Landscape()
L.add_edge("idle",       "processing",  delta=1.0, resistance=1.0)
L.add_edge("processing", "done",        delta=1.0, resistance=1.0)
L.add_edge("processing", "error",       delta=0.5, resistance=2.0)
L.add_edge("error",      "idle",        delta=1.0, resistance=1.0)

# 2. Define what "executing a transition" means in your domain
def execute(source: str, target: str) -> Outcome:
    # Replace with your actual domain logic
    success = run_my_system(source, target)
    return Outcome.SUCCESS if success else Outcome.FAILURE

# 3. Run
ctrl = E0Controller(L, execute)
trace = ctrl.run(start="idle", goal="done", max_steps=20)
print(trace.summary())
```

**What you get:** A controller that navigates from start to goal, learns which edges work (U traces) and which fail (F traces), and avoids high-resistance paths. After 10+ runs, it knows the domain.

---

## Layer 1 — Persistent Memory (MemOS)

**Add when:** the agent must survive across sessions (restart, new process, context window limit).

**What you need:** `memory_os.py` → `LandscapeSnapshot`, `HistorizationSnapshot`

```python
from e0_controller.memory_os import LandscapeSnapshot, HistorizationSnapshot
import json
from pathlib import Path

SNAPSHOT_PATH = Path("agent_state.json")

# --- Save after a run ---
def save_state(landscape, controller):
    state = {
        "landscape": LandscapeSnapshot.from_landscape(landscape).__dict__,
        "historization": HistorizationSnapshot.from_historization(
            landscape.historization
        ).__dict__,
    }
    SNAPSHOT_PATH.write_text(json.dumps(state, indent=2))

# --- Restore before next run ---
def restore_state() -> tuple[Landscape, None]:
    if not SNAPSHOT_PATH.exists():
        return Landscape(), None
    state = json.loads(SNAPSHOT_PATH.read_text())
    hist = HistorizationSnapshot(**state["historization"]).to_historization()
    landscape = LandscapeSnapshot(**state["landscape"]).to_landscape(historization=hist)
    return landscape, hist
```

**What you get:** Full U/F trace reconstruction including per-edge timestamps (K2-compatible lazy decay). The restored controller behaves identically to the original — no approximation. Episodic memory across context windows.

**Key invariant:** `tau_last` per edge is preserved — this means decay is correctly applied to edges that weren't visited during the gap between sessions.

---

## Layer 2 — E2Port (connect to any external system)

**Add when:** the agent needs to execute real actions (API calls, tool calls, database queries, LLM generation).

**What you need:** `e2_port.py` → `E2Port`, `ExecutionResult`

```python
from e0_controller.e2_port import E2Port, ExecutionResult
from e0_controller.primitives import Outcome

class MyAPIPort(E2Port):
    def port_id(self) -> str:
        return "my_api_v1"

    def execute(self, state: str, action: str) -> ExecutionResult:
        try:
            response = call_my_api(endpoint=action, context=state)
            return ExecutionResult(
                new_state=action if response.ok else state,
                outcome=Outcome.SUCCESS if response.ok else Outcome.FAILURE,
                payload=response.data,   # E₀ ignores payload — it's yours
            )
        except Exception as e:
            return ExecutionResult(
                new_state=state,
                outcome=Outcome.FAILURE,
                error=str(e),
            )
```

**Contract:**
- `execute()` MUST NOT raise — catch all errors, return `FAILURE`
- `new_state` should equal `action` on SUCCESS
- `new_state` may equal `state` on FAILURE (no movement)
- `payload` is invisible to E₀ — use it for your own processing (logging, LLM summarization, etc.)

**Full loop with E2Port:**

```python
from e0_controller.e0_turn import E0Turn   # wires E0Controller + E2Port

port = MyAPIPort()
turn = E0Turn(landscape=L, port=port)
for step in turn.run(start="idle", goal="done", max_steps=50):
    print(f"{step.source} → {step.target}: {step.outcome}")
    # step.payload contains your domain data
```

**What you get:** Clean separation between navigation (E₀) and execution (your code). E₀ learns which API calls succeed and which fail — without knowing anything about the API.

---

## Layer 3 — LLM as E1 (Skeleton + Muscle)

**Add when:** the domain is too large or dynamic to define manually. LLM derives the landscape from a task description.

**Architecture:**
```
Task description (text)
    ↓
LLM (E1) — bootstrapper.py / llm_adapter.py
    ↓
Landscape (states + edges derived from task)
    ↓
E0Controller (E0) — navigates the derived landscape
    ↓
E2Port (E2) — executes transitions
    ↓
Outcome → Historization
    ↓
LLM (E1) — summarizes outcomes, proposes new states when stuck
```

**Roles are strict:**
- E₀ = skeleton: structure, judgment, memory, navigation
- LLM = muscle: generation, exploration, language
- LLM proposes. E₀ decides. E₀ historizes. LLM never overrides navigation.

**Minimal LLM bootstrap:**

```python
from e0_controller.e0_session import run_session

result = run_session(
    task="Process incoming invoice and route for approval",
    start=None,   # LLM derives from task
    goal=None,    # LLM derives from task
)
# result.html — rendered session output
# result.trace — RunTrace with full step history
```

**Two-LLM co-cognition (when one LLM isn't enough):**

```python
from e0_controller.llm_cocognition import run_cocognition

result = run_cocognition(
    task="Analyze competitor announcement → produce briefing",
    start="RAW_ANNOUNCEMENT",
    goal="BRIEFING_DELIVERED",
)
# LLM_A (temp=0.2) + LLM_B (temp=0.6) → different topologies
# MultiverseController + NoveltyGate prevents sterile consensus
# result.total_enrichment = new edges gained through coupling
```

**Why two LLMs?** Different temperatures produce genuinely different landscape topologies. The NoveltyGate (M9) ensures they only couple when it produces new structure — preventing the convergence trap.

---

## Layer 4 — Self-Graph (metacognitive loop)

**Add when:** the agent runs for many sessions and you want it to detect when its own components are failing.

```python
from e0_controller.self_graph import SelfGraph
from e0_controller.controller import E0Controller

sg = SelfGraph()
ctrl = E0Controller(landscape, execute_fn, self_graph=sg)

# After each run, query component health:
print(sg.component_quality("amplitude"))    # is lookahead helping?
print(sg.component_quality("historization")) # is memory working?
print(sg.component_inertia("curvature"))     # is curvature confused?
```

**Level 3 (deactivate failing components):**

```python
if sg.component_quality("curvature") < -0.2:
    landscape.curvature_modulation = False   # deactivate
```

**What you get:** The agent knows which of its own mechanisms are working. A component with persistent negative quality is a signal that the mechanism is misconfigured for this domain — not that the domain is hard.

---

## Layer 5 — Structural Entropy (controlled forgetting)

**Add when:** the agent runs for many episodes and the landscape grows unbounded, or past knowledge becomes misleading.

```python
from e0_controller.structural_entropy import (
    structural_temperature,
    dream_pressure,
    EntropyController,
)

# Check if the system needs consolidation
T_s = structural_temperature(landscape.historization)
pressure = dream_pressure(landscape.historization)

if pressure > 0.7:
    # System is "hot" — much experience, little clarity
    # Time to prune low-anchor nodes
    entropy_ctrl = EntropyController(landscape)
    entropy_ctrl.apply_decay(theta_base=0.3)
```

**Type 1 (novelty gate) — prevent over-inscription:**

```python
ctrl = E0Controller(
    landscape, execute_fn,
    inscription_threshold=True   # skip inscribing expected outcomes
)
```

**What you get:** The agent forgets less-useful structure rather than accumulating it indefinitely. Memory stays bounded and signal quality stays high.

---

## Layer 6 — Multi-Agent (NoveltyGate coupling)

**Add when:** multiple agents work on the same domain and you want them to share knowledge without converging to the same solution.

```python
from e0_controller.multiverse import Universe, MultiverseController

agent_a = Universe("agent_a", landscape_a, execute_fn_a, start="S0", goal="G")
agent_b = Universe("agent_b", landscape_b, execute_fn_b, start="S0", goal="G")

ctrl = MultiverseController(agent_a, agent_b)
result = ctrl.run(max_turns=20)

print(f"Novelty rate: {result.novelty_rate:.0%}")
print(f"Convergence at turn: {result.convergence_turn}")
```

**What NoveltyGate guarantees:** Agents only couple when the interaction produces new states, new edges, or structural delta growth. Unproductive agreement increases coupling resistance automatically — no manual tuning.

---

## Decision Guide: Which Layers Do You Need?

| Use case | Minimum layers |
|----------|---------------|
| Stateless task navigator | Layer 0 |
| Agent that remembers across restarts | Layer 0 + 1 |
| Agent that executes real-world actions | Layer 0 + 1 + 2 |
| Agent that derives its own domain from text | Layer 0 + 1 + 2 + 3 |
| Long-running agent with self-monitoring | Layer 0–4 |
| Long-running agent, unbounded landscape | Layer 0–5 |
| Multiple agents, shared domain | Layer 0–3 + 6 |

---

## What E₀ Does Not Do

These are not gaps — they are explicit design boundaries:

| Concern | E₀'s position |
|---------|---------------|
| Probability distributions | Not used. Navigation from structural difference only. |
| Training data | Not required. Learning is from runtime inscription. |
| Neural networks | Not used at E₀ core. LLM is E1 (optional muscle). |
| Natural language understanding | Delegated to E1 (LLM). E₀ sees states as strings. |
| Goal decomposition | Delegated to E1. E₀ navigates toward a goal state. |
| Branching factor > 3 | F3: known limit. Use hierarchical decomposition. |
| Non-adjacent credit assignment | F4: known limit. PathSignature (M6) partially closes this. |

---

## Quick Reference: Module → Layer

| Layer | Module | Primary entry point |
|-------|--------|---------------------|
| 0 | `controller.py`, `landscape.py` | `E0Controller(landscape, execute_fn)` |
| 1 | `memory_os.py` | `LandscapeSnapshot`, `HistorizationSnapshot` |
| 2 | `e2_port.py` | `class MyPort(E2Port)` |
| 3 | `e0_session.py`, `llm_cocognition.py` | `run_session(task=...)` |
| 4 | `self_graph.py` | `SelfGraph()` |
| 5 | `structural_entropy.py` | `structural_temperature()`, `dream_pressure()` |
| 6 | `multiverse.py` | `MultiverseController(a, b)` |

Full mechanism reference: [`AGENT_REFERENCE.md`](../AGENT_REFERENCE.md)
Formal canon: [`canon/e0-canon-plain.txt`](canon/e0-canon-plain.txt)
