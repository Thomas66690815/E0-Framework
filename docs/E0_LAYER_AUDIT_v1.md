# E0 Layer Audit v1

Status: in progress
Date: 2026-04-16
Scope: architectural audit for layer violations and "smuggled" higher-level concepts in `e0_controller/`

## Purpose

This note persists the ongoing audit beyond the current context window.
It does not propose code changes yet. It records:

- the normative audit frame,
- current findings,
- provisional classifications,
- the next audit trail.

## Normative Frame

The current audit uses three explicit project anchors:

1. Canon:
   - E0 is pre-domain and not a theory of objects, meanings, goals, agents, or domains:
     `canon/e0-canonical-reference.txt:45`
     `canon/e0-canonical-reference.txt:47`
     `canon/e0-canonical-reference.txt:200`
     `canon/e0-canonical-reference.txt:217`
2. Architecture:
   - the repo explicitly models higher layers above the core:
     `docs/ARCHITECTURE.md:3`
     `docs/ARCHITECTURE.md:18`
     `docs/ARCHITECTURE.md:20`
     `docs/ARCHITECTURE.md:25`
3. Bootstrap / GT-7:
   - domains are E2, not E0 primitives:
     `bootstrap.json:126`
     `bootstrap.json:130`
     `bootstrap.json:235`
     `bootstrap.json:236`
     `bootstrap.json:394`

Working rule for this audit:

- A higher-level concept is admissible if it stays in a clearly derived layer or interface.
- It becomes a layer violation candidate when it is stored inside E0-core state, used as part of core decision logic, or imported back into lower layers in a way that changes primitive behavior.

## Current Classification

### 1. Core that currently looks clean

The following modules still look structurally grounded in Delta / Resistance / Historization:

- `e0_controller/primitives.py:1`
- `e0_controller/tension.py:1`
- `e0_controller/wavepath.py:1`

Notes:

- `primitives.py` uses the wording "controller domain", but the actual implementation remains graph-primitive based and explicitly claims domain-invariance:
  `e0_controller/primitives.py:4`
  `e0_controller/primitives.py:8`
- `landscape.py` still looks mostly clean at the mechanism level. It stores Delta, R0, Historization, and free metadata, but the primitive mechanics are not metadata-driven:
  `e0_controller/landscape.py:77`

### 2. Positive correction already present in code

`community.py` is an explicit repair of the GT-7 error:

- emergent structure from historization, not labels:
  `e0_controller/community.py:4`
- "built from E0 primitives only":
  `e0_controller/community.py:15`
- explicit replacement of prefix/domain partitioning as an E2-on-E0 error:
  `e0_controller/community.py:22`

This module is currently the strongest positive example of layer discipline.

### 3. Strongest current layer-violation candidate: Historization

`historization.py` is currently the main audit hotspot.

Reasons:

1. `InscriptionContext` stores higher-layer semantics directly in the core memory object:
   - `relation_type`
   - `bridge_type`
   - `source_domain`
   - `target_domain`
   - "narrative trace"

   References:
   `e0_controller/historization.py:93`
   `e0_controller/historization.py:100`
   `e0_controller/historization.py:108`
   `e0_controller/historization.py:115`

2. `classify_experience()` explicitly speaks in domain terms:
   - "domain character"
   - "What kind of problem am I in?"
   - "domain-awareness"

   References:
   `e0_controller/historization.py:376`
   `e0_controller/historization.py:387`

3. The controller writes contextual metadata into Historization during the normal loop:
   `e0_controller/controller.py:722`
   `e0_controller/controller.py:725`

Current judgment:

- This is not yet proven to be a hard behavioral corruption of the E0 core.
- But it is already a structural mixing of layers, because semantic / domain annotations live inside the core historization object rather than only in a derived observation or interface layer.

### 4. Secondary candidate: Goal semantics in the controller

`controller.py` contains explicit goal semantics in the run loop:

- `hybrid_goals`:
  `e0_controller/controller.py:264`
- stopping condition on `goal`:
  `e0_controller/controller.py:837`
  `e0_controller/controller.py:858`

Current judgment:

- This is weaker than the Historization issue.
- The selection mechanism still seems tension-driven.
- But "goal" is canonically not an E0 primitive, so this needs a careful distinction between:
  - admissible operational interface,
  - inadmissible primitive assumption.

### 5. Coupling-back from higher layers into lower layers

The controller imports and uses higher-layer helpers:

- `envelope`:
  `e0_controller/controller.py:288`
- `structural_entropy.should_inscribe`:
  `e0_controller/controller.py:716`
- `self_graph.active_components`:
  `e0_controller/controller.py:741`

Current judgment:

- This is a real architectural coupling issue.
- It is not automatically wrong, because the architecture intentionally contains reflexive and entropy layers.
- But it weakens the claim that the lower controller layer depends only on primitive-near machinery.

This needs a dedicated pass:

- which imports are just optional overlays,
- which ones actually alter core behavior,
- which ones should be inverted or isolated.

## Legitimate Higher Layers So Far

The following modules currently look like valid derived layers, not immediate violations, as long as they remain one-way and do not redefine the core:

- Bootstrapper:
  `e0_controller/bootstrapper.py:1`
- Observation:
  `e0_controller/observation.py:1`
- Perception:
  `e0_controller/perception.py:1`
- Communication:
  `e0_controller/communication.py:1`
- UI emitter:
  `e0_controller/ui_emitter.py:1`
- Dream mode:
  `e0_controller/dream_mode.py:1`
- Coupling router:
  `e0_controller/coupling_router.py:1`

Why they currently look admissible:

- they explicitly declare themselves as higher or derived layers,
- they operate on top of Landscapes rather than redefining Delta / Resistance / Historization,
- they expose interface-specific semantics openly instead of pretending to be primitive.

Examples:

- observation is explicitly "Visualization as a domain":
  `e0_controller/observation.py:4`
- perception is explicitly a learnable human-facing domain:
  `e0_controller/perception.py:4`
- communication is explicitly part of human communication architecture:
  `e0_controller/communication.py:11`
- UI emitter is explicitly layer 3 of that architecture:
  `e0_controller/ui_emitter.py:6`
- dream mode explicitly constrains itself to passive cross-domain observation:
  `e0_controller/dream_mode.py:8`
- coupling router explicitly models partner selection as a higher-level routing landscape:
  `e0_controller/coupling_router.py:11`

## Boundary Cases

### Self-Graph

`self_graph.py` remains a boundary case, but currently a justified one:

- it explicitly grounds itself in Selbstunterscheidung:
  `e0_controller/self_graph.py:6`
- "E0's first domain is E0":
  `e0_controller/self_graph.py:8`

Current judgment:

- provisional classification: admissible reflexive extension, not yet a false E2 insertion.
- it stays structurally close to E0 machinery:
  - fixed Landscape topology of components:
    `e0_controller/self_graph.py:15`
  - component nodes and dependency edges, not semantic domain labels:
    `e0_controller/self_graph.py:23`
  - cumulative self-knowledge via Historization:
    `e0_controller/self_graph.py:153`

Current risk:

- not a primitive leak by itself,
- but it creates a feedback channel from meta-diagnosis back into controller behavior, so it must be watched as a coupling boundary rather than a semantic corruption.

### Reflection / Dual Reflection

`reflection.py` and `dual_reflection.py` are clearly meta-layers, but they already mix:

- evaluation,
- semantic quality,
- LLM interfaces,
- layer attribution,
- controller and graph recommendations.

References:

- `e0_controller/reflection.py:1`
- `e0_controller/reflection.py:189`
- `e0_controller/reflection.py:352`
- `e0_controller/reflection.py:686`
- `e0_controller/dual_reflection.py:1`
- `e0_controller/dual_reflection.py:209`

Current judgment:

- these are probably valid higher layers,
- but they must not silently push semantic assumptions back into the primitive core.
- they are explicitly not free introspection, but bounded meta-diagnostics:
  `e0_controller/reflection.py:1`
  `e0_controller/reflection.py:66`
  `e0_controller/reflection.py:666`
- they openly depend on evaluation and LLM-facing structures:
  `e0_controller/reflection.py:22`
  `e0_controller/reflection.py:24`
- quality reflection already uses semantic coverage as a trigger:
  `e0_controller/reflection.py:185`
  `e0_controller/reflection.py:350`
  `e0_controller/reflection.py:415`
- dual reflection cross-references domain-level reflection with self-graph diagnosis:
  `e0_controller/dual_reflection.py:230`
  `e0_controller/dual_reflection.py:272`
  `e0_controller/dual_reflection.py:304`

Current classification:

- admissible as meta-layer,
- not admissible as evidence for E0 purity.

In other words:

- reflection is allowed to talk about semantics, prompts, graph design, and controller layers,
- but any recommendation or diagnosis produced there must still be treated as a higher-level intervention, not as part of the primitive mechanism itself.

### Structural Mutation

`structural_mutation.py` currently looks like a valid derived reflexive layer, not a hidden semantic leak:

- it explicitly declares itself as topology-level self-modification:
  `e0_controller/structural_mutation.py:1`
  `e0_controller/structural_mutation.py:5`
- mutation types remain edge/topology primitives:
  `e0_controller/structural_mutation.py:40`
  `e0_controller/structural_mutation.py:49`
- admissibility is still phrased structurally:
  `e0_controller/structural_mutation.py:112`
- identity invariant includes goal reachability, dead-end avoidance, and historization continuity:
  `e0_controller/structural_mutation.py:203`
  `e0_controller/structural_mutation.py:217`

Current judgment:

- this is a higher reflexive layer built on top of E0, not an E0 primitive.
- the use of `goal` here is operational and evaluative, not evidence that topology mutation itself smuggles semantic categories into Delta / Resistance / Historization.

Current risk:

- the structural tuning cycle imports reflection and evaluation to generate proposals:
  `e0_controller/structural_mutation.py:644`
  `e0_controller/structural_mutation.py:649`
  `e0_controller/structural_mutation.py:650`
- therefore the risk is again architectural back-coupling, not primitive contamination.

### Dream Mode / Coupling Router

These two modules remain the direct GT-7 test case.

Current observation:

- both still use the word `domain` heavily and explicitly:
  `e0_controller/dream_mode.py:1`
  `e0_controller/coupling_router.py:17`
- but unlike the old prefix-based architecture, they currently expose their grouping assumptions openly as higher-level observer/router concepts rather than silently baking them into the primitive core.

Dream mode:

- stores registered landscapes under names in `_domains`:
  `e0_controller/dream_mode.py:763`
  `e0_controller/dream_mode.py:785`
- runs pairwise compatibility and equivalence detection across those registered units:
  `e0_controller/dream_mode.py:807`
  `e0_controller/dream_mode.py:847`
  `e0_controller/dream_mode.py:865`
- bridge proposals still operate in terms of `target_domain` / `partner_domain`:
  `e0_controller/dream_mode.py:1271`
  `e0_controller/dream_mode.py:1332`

Coupling router:

- models universes explicitly as states in a routing landscape:
  `e0_controller/coupling_router.py:11`
  `e0_controller/coupling_router.py:136`
- selection is still structurally computed from Delta and historized quality:
  `e0_controller/coupling_router.py:188`
  `e0_controller/coupling_router.py:229`
  `e0_controller/coupling_router.py:240`

Current judgment:

- provisional classification: improved relative to GT-7, but not fully discharged.
- reason: the mechanism now appears structurally expressed, but the observer/router layer still relies on externally named units (`domain`, `universe`) rather than fully emergent substructures.

This is not the same error as prefix partitioning.
But it remains a live audit target:

- if these names are only handles for already-derived higher-layer units, this is acceptable;
- if they become hidden prerequisites for what should be emergent grouping, the GT-7 pattern would reappear in a subtler form.

### Session / Orchestration

`session.py` makes the back-coupling problem explicit:

- it presents itself as a thin orchestration layer above the controller:
  `e0_controller/session.py:1`
- but it wires together:
  - persistence,
  - tuning memory,
  - self-graph,
  - dual reflection,
  - reflexive action,
  - structural mutation,
  - auto-tuning.

References:

- imports and orchestration scope:
  `e0_controller/session.py:30`
  `e0_controller/session.py:46`
  `e0_controller/session.py:55`
  `e0_controller/session.py:60`
- self-graph is attached directly to the controller in session construction:
  `e0_controller/session.py:144`
- session-level reflection fabricates a scenario object with `domain="iterate"`:
  `e0_controller/session.py:483`
  `e0_controller/session.py:485`
- dual reflection is then called with live landscape and tuning memory:
  `e0_controller/session.py:499`
  `e0_controller/session.py:552`

Current judgment:

- `session.py` is not a primitive leak.
- it is the main runtime integration point where higher-layer diagnostics can influence behavior.

Therefore:

- the primitive core can remain conceptually clean,
- while the runtime system as a whole still becomes architecturally impure through orchestration feedback loops.

That distinction is important for the final judgment:

- "Is E0 pure?" and
- "Is the running E0 framework layer-disciplined?"

are no longer the same question.

This needs a separate audit pass.

## Current Provisional Verdict

At the current stage, the strongest evidence is:

1. The repo already knows about the main domain error and has begun correcting it (`community.py`, GT-7).
2. The primitive mathematical core still looks mostly clean.
3. The most serious remaining candidate is not obvious "domain partitioning" anymore, but semantic/contextual material being stored inside `Historization`.
4. The second major issue is layer back-coupling: higher layers influencing the controller directly.
5. `self_graph`, `reflection`, `dual_reflection`, and `structural_mutation` currently look like legitimate higher layers, but they reinforce the same architectural concern: the system is cleanest at the primitive-math level and progressively less clean as higher layers feed back into runtime decisions.
6. `dream_mode` and `coupling_router` no longer look like the old prefix error, but they still need a final verdict on whether their unit boundaries are truly emergent or still partly imposed by orchestration.
7. `session.py` is the clearest place where runtime impurity accumulates: not by changing Delta / Resistance / Historization directly, but by wiring reflection, self-knowledge, mutation, and tuning back into the live system.

## Refined Pass: Historization vs Controller

### Historization: the issue splits into three different questions

The earlier suspicion around `historization.py` needs a sharper split.

1. Observational annotation:
   - `classify_experience()` and `adapt_from_experience()` do create a feedback loop that changes future inscription behavior:
     `e0_controller/historization.py:375`
     `e0_controller/historization.py:413`
     `e0_controller/controller.py:768`
   - But the implementation does **not** classify semantic domains. It classifies volatility from confirmations and surprises only:
     `e0_controller/historization.py:389`
     `e0_controller/historization.py:430`

2. Storage contamination:
   - `InscriptionContext` stores `relation_type`, `bridge_type`, `source_domain`, and `target_domain` directly inside `Historization` state:
     `e0_controller/historization.py:93`
     `e0_controller/historization.py:115`
     `e0_controller/historization.py:159`
     `e0_controller/historization.py:453`
   - `inscription_summary()` and `inscription_stats()` then aggregate those higher-level fields as `relation_types`, `domain_pairs`, and `domain_crossing_count`:
     `e0_controller/historization.py:470`
     `e0_controller/historization.py:499`
     `e0_controller/historization.py:515`
     `e0_controller/historization.py:537`

3. Behavioral contamination:
   - I still do **not** see evidence that those semantic/domain context fields influence the primitive runtime calculations:
     `e0_controller/historization.py:258`
     `e0_controller/historization.py:313`
     `e0_controller/historization.py:596`
     `e0_controller/historization.py:619`
     `e0_controller/historization.py:642`
     `e0_controller/controller.py:306`
     `e0_controller/controller.py:322`
   - The current downstream readers of inscription context look observational/narrative, not control-critical:
     `e0_controller/evidence_interpreter.py:85`
     `e0_controller/evidence_interpreter.py:145`
     `e0_controller/observation_controller.py:353`

Updated judgment for `Historization`:

- Proven: storage-level layer mixing is real.
- Not yet proven: semantic/domain context corrupts `delta_H`, trust, inertia, or neighbor ranking.
- Important nuance: the phrase "domain character" in `classify_experience()` is conceptually misleading. The code is classifying volatility, not ontology.

### Controller: goals are not primitive, but they are also not the same problem

`controller.py` now looks like two distinct cases:

1. Primitive-near selection path:
   - `_effective_resistance()` and `_effective_tension()` still resolve through `R0 + delta_H` and `Delta * R_eff`:
     `e0_controller/controller.py:306`
     `e0_controller/controller.py:322`
   - This remains the cleanest part of the runtime controller.

2. Higher-layer operational semantics:
   - `goal` in `run()` is just a stopping condition:
     `e0_controller/controller.py:832`
     `e0_controller/controller.py:857`
     `e0_controller/controller.py:870`
   - `hybrid_goals` matter when the amplitude overlay is active, because they shape `first_arrival` / `goal_reaching` geometries:
     `e0_controller/controller.py:236`
     `e0_controller/controller.py:615`
     `e0_controller/controller.py:809`
     `e0_controller/amplitude_overlay.py:154`
     `e0_controller/amplitude_overlay.py:157`
     `e0_controller/amplitude_overlay.py:166`

Updated judgment for goals:

- `goal` / `hybrid_goals` are higher-layer runtime parameters.
- They are not evidence that the primitive equations themselves have absorbed goals.
- They do become behaviorally relevant once overlay-based selection is enabled, so they belong to the "runtime impurity via optional overlays" category.

### Controller back-coupling: this is now the strongest proven behavioral impurity

The sharper controller finding is not "goal contamination", but optional higher-layer feedback paths that really do alter behavior:

1. Inscription threshold:
   - `structural_entropy.should_inscribe()` can suppress historization altogether when `inscription_threshold` is enabled:
     `e0_controller/controller.py:710`
     `e0_controller/controller.py:715`
     `e0_controller/structural_entropy.py:229`

2. Adaptive dampening:
   - the controller calls back into `Historization.adapt_from_experience()` after inscription:
     `e0_controller/controller.py:768`
     `e0_controller/historization.py:413`
   - This is real behavioral feedback, but still grounded in revisit statistics rather than semantic labels.

3. Self-graph override gating:
   - amplitude overrides are blocked when recent-loop evidence or accumulated override quality say they are harmful:
     `e0_controller/controller.py:638`
     `e0_controller/controller.py:645`
     `e0_controller/controller.py:650`
     `e0_controller/self_graph.py:177`
     `e0_controller/self_graph.py:256`
     `e0_controller/self_graph.py:273`
   - This is a genuine higher-layer influence on action choice, but it is scoped to hybrid override mode, not the greedy base path.

4. Benign coupling:
   - `transport` importing `use_su2_to_transport()` looks like representational/backward-compatible mapping, not a meaningful layer violation by itself:
     `e0_controller/controller.py:284`
     `e0_controller/envelope.py:47`

Updated controller judgment:

- In greedy mode, the controller remains comparatively close to the primitive core.
- In hybrid / adaptive / reflective modes, the runtime becomes architecturally impure by design through optional feedback channels.
- Therefore the strongest proven behavioral impurity is now back-coupling, not domain semantics inside the primitive equations.

## Next Audit Trail

The next pass should focus on:

1. Final verdict pass on `dream_mode.py` and `coupling_router.py`: emergent grouping vs named higher-layer units
2. Audit whether any production navigation path outside `controller.py` uses edge metadata (`relation_type`, `bridge_type`, domain labels) as live decision input rather than as annotation
3. Final synthesis matrix:
   - storage contamination
   - behavioral contamination
   - observational annotation
   - legitimate derived layer
4. Separate the final verdict into two explicit questions:
   - Is the primitive E0 kernel still clean?
   - Is the running framework architecturally layer-disciplined?

## Working Constraint

This note records analysis only.
No code changes are implied by it.
