# E₀ Architecture

**14 layers, bottom-up.** Each layer depends only on layers above it.  
Code comments are the primary documentation — every module header explains what, why, and which axiom.

```
 Layer 1 — PRIMITIVES         Edge, Outcome, Tension, Coherence
 Layer 2 — INSCRIPTION        Historization (U/F traces, δ_H, trace_load/quality)
                               Landscape (states, edges, Δ, R₀)
 Layer 3 — FIELD THEORY       Potential (Φ, v), Connection (ω, Θ), Wave (Ψ, I)
                               Overlap M_H, Resonator
 Layer 4 — CONTROLLER         Selection (argmin S_eff), Escalation, Hybrid Modes
                               Amplitude Overlay, Dynamic Horizon
 Layer 5 — REFLEXION          Self-Graph, Dual Reflection, Reflexive Edge Proposal
                               Integrated Reflexion, SU(2) Perspective Diagnostic
 Layer 6 — MULTI-SYSTEM       Multiverse, Cross-Reflexion, Coupling Router
                               Overload Escalation (peer_fn)
 Layer 7 — INFRASTRUCTURE     Session, MemOS, LLM Adapter, Bootstrapper
                               Config, Curriculum, Evaluation
 Layer 8 — OBSERVATION        O-Landscape, Observation Controller, Rendering
 Layer 9 — DREAM MODE         Edge/Node Fingerprints, DreamObserver
                               Hungarian Matching, Bridge Hypotheses
 Layer 10 — STRUCTURAL ENTROPY  Inscription Threshold, Anchor Analysis, Decay
 Layer 11 — SLEEP–WAKE        Dream Pressure, SleepWakeCycle Orchestrator
 Layer 12 — HUMAN COMM        Perception Ontology, Intent, UISpec Emitter
 Layer 13 — UI RENDERING      UISpec → HTML, Visual Pretraining
 Layer 14 — SESSION RUNNER    Task → LLM → Controller → Perception → UI
```

## Core Formulas

| Formula | Code | Purpose |
|---------|------|---------|
| $S_{\text{eff}} = \Delta \cdot R_{\text{eff}}$ | `controller._effective_tension()` | Transition burden |
| $R_{\text{eff}} = R_0 + \delta_H$ | `historization.delta_H()` | Historized resistance |
| $\Psi(p) = e^{-S(p)} \cdot e^{i\Theta(p)}$ | `wavepath.psi()` | Path amplitude |
| $I = \|\sum_p \Psi(p)\|^2$ | `amplitude_overlay.analyze_controller_state()` | Endpoint intensity |
| $q = (U - F) / (U + F + \epsilon)$ | `historization.trace_quality()` | Inscription quality |
| $I_{\text{inertia}} = 1 - \alpha \cdot \frac{m}{m+\mu} \cdot (1-\|q\|)$ | `historization.inertia_factor()` | Inertia modulation |

## Key Design Decisions

1. **Bottom-up**: Features emerge from primitives. No top-down schema.
2. **Honest activation** (C151): Components only marked active when they actually participated.
3. **Revisit-aware override** (C193): Amplitude respects greedy's revisit window via self-graph.
4. **Structural entropy**: The system forgets — inscription threshold, decay, sleep–wake.
5. **Dream ≠ action**: Dreaming is passive observation across domains, not navigation.

## Navigating the Code

Start here → read in this order:
1. `e0_controller/primitives.py` — 7 primitives, one axiom
2. `e0_controller/historization.py` — U/F traces, the core learning mechanism
3. `e0_controller/controller.py` — The decision engine
4. `e0_controller/amplitude_overlay.py` — Path-family lookahead
5. `e0_controller/self_graph.py` — E0 reflecting on itself

Each file's module docstring is a self-contained architectural document.

## Statistics

| Metric | Count |
|--------|-------|
| Production modules | 76 |
| Test files | 122+ |
| Tests | 4369 |
| Demos | 17 |
| Explorations | 65+ |
| Production lines | ~31,000 |
