# Changelog

All notable changes to the E₀ Framework.

This project uses sequential commit IDs (C1–C193) for traceability.
Only major arcs are listed here — see `git log` for the full history.

---

## [1.1.0] — 2026-04-11

**96 numbered commits (C195–C290), 5980 tests, 78 production modules.**

Core theme: *difference is primary*. Every input source — LLM, sensor, human, agent — now enters through a universal protocol. The system gained trajectory-level memory, empirically confirmed structural limits, and deep self-reflection infrastructure.

### New: Community Detection (C255–C262)

- Structural communities derived directly from the R_eff matrix — no manual labels
- Replaces the prefix-domain partitioning used in v1.0.0
- Dream mode, tuning, sleep–wake, and diagnostics all use the emergent partition
- `community_of(node, communities)` is now the canonical membership lookup

### New: Trajectory Historization (C277–C283)

- `TrajectoryHistorization` accumulates evidence on path *patterns*, not just edges
- Closes the non-Markov signal gap: choice at time t now depends on trajectory history
- Backward-compatible: `trajectory_hist` field in `SessionState` with graceful migration
- `trajectory` command added to the interactive session

### New: Falsification Benchmark (C272)

- Four structural test cases with confirmed outcomes:
  - **F1 (Depth):** E₀ reaches goal at depths 5–500; greedy fails via distractor loops ✅
  - **F2 (Non-stationarity):** E₀ adapts fully when executor switches; no ossification ✅
  - **F3 (Dense branching):** Both E₀ and greedy fail; combinatorial explosion exceeds the penalty mechanism ❌
  - **F4 (Non-Markov):** E₀ avoids the trap but cannot learn the required sequence; credit assignment is edge-local ❌

### New: ARC-D — LLM Integration Protocol (C285–C287)

- `DifferenzPort` ABC: universal protocol for all external difference sources
- `E1Monitor`: tracks LLM-proposed landscape structure per community × per function
- `SessionState` refactored: three old ARC-D fields replaced by `e1_monitor: E1Monitor`
- Backward-compatible `load_session()` migration for sessions saved before C285

### New: ARC-E — Universal Difference Input (C288–C290)

- `ObservationPort`: second concrete `DifferenzPort` for direct outcome signals (sensor, human, agent)
- `cmd_ports` command: inspect all active difference input ports with quality and dampening
- `_active_ports(state)` as the single enumeration point — extend here to add new ports
- Compliance test suite: `TestDifferenzPortABCCompliance` runs against all registered implementations

### Infrastructure

- Python 3.11 compatibility maintained (PEP 701 f-string backslash fix, C290+)
- CI matrix unchanged: 3.11, 3.12, 3.13
- `bootstrap.json` now carries U/F traces on working principles and Gordian Trap recurrence counts

---

## [1.0.0] — 2026-04-09

**First public release.** 193 numbered commits, 4369 tests, 14 integrated layers.

### Arcs

#### Foundation (pre-C36)
- Canon formalized: 7 primitives, Axiom A₀, Central Law
- Plain ASCII canon (`canon/e0-canon-plain.txt`) — 155 lines, zero byte-tokens
- Early experiments: QM reconstruction, GPT-2 structural measurements, reservoir hypothesis
- Measurement infrastructure: token-level R, H, Φ, v metrics

#### Controller Core (C36–C55)
- Structural reflection, graduated overlap (M_H), stochastic exploration
- **C42: 4-layer rename** — Historization → Inscription → Inertia → Mass
- Amplitude overlay: path-integral interference for lookahead
- Hybrid controller: greedy + amplitude with escalation logic

#### Path Interference (C56–C80)
- SU(2) spinor transport for geometric phase
- Born-probability selection, phase accumulation
- Dynamic horizon: forward lookahead adapts to landscape complexity
- Holonomy detection and geometric phase correction

#### Self-Reflection (C81–C105)
- Self-Graph: E₀ monitors its own components via differential sampling
- Dual reflection: domain graph + self-graph update in parallel
- Cross-reflexion: multi-agent shared historization
- Gordian Trap detection (GT-1 through GT-4)

#### Multi-Domain (C106–C145)
- Multiverse architecture: coupled domains with independent landscapes
- Dream mode: passive cross-domain pattern discovery via WL isomorphism
- **C137: Hungarian optimal assignment** — 100% node equivalence (was 34/44)
- Coupling router: dream quality signals bias partner selection
- Sleep–wake cycle: entropy-driven consolidation and forgetting
- Curriculum learning: level-by-level knowledge acquisition
- 17 demos covering all major capabilities

#### Human Communication (C158–C166)
- Perception ontology: learnable domain for human interaction
- Communication intent detection from E₀ state
- UI-Schema emitter: (Intent × Perception) → UISpec
- Human feedback loop: closes the learning cycle
- UI renderer: stateless UISpec → HTML
- Unified session runner: end-to-end 14-layer pipeline

#### Validation & Hardening (C167–C193)
- Compatibility-gated dreaming with threshold calibration
- Adversarial stability: structural skepticism + self-honesty
- Causal binding: implicit intervention via natural path alternation
- N-domain mesh scaling (N=2 → N=18, no collapse)
- **C184–C185:** Real-world validation (Wikispeedia, BPI 2017, traffic simulation)
- **C189:** Shared historization — the Gordian Trap escape (+128–244%)
- **C191:** 14-layer integration proof — 5 feedback loops, composition creates value
- **C193:** GT-5 resolved — revisit-aware override gate + self-graph override quality

### Infrastructure
- GitHub Actions CI: 3 Python versions (3.11, 3.12, 3.13)
- 122 test files, 76 production modules, 17 demos, 65 explorations
- `bootstrap.json`: persistent AI collaboration state across context windows
- Parameter registry (`E0Config`): single source of truth for all defaults
- Session persistence with provenance tracking
