# E₀ Bridge 4: Structural Reflexivity — Concept Note v0

**Status:** Stufe 1 implementiert (Commit dd6e277, 56 Tests)  
**Date:** 2026-03-28  
**Purpose:** Klärung was Bridge 4 (Reflexivität) fordert, was bereits existiert, was fehlt, und wo SU(2) eventuell eingreift.

---

## 0. Kontext

Der AGI-Blueprint §5 formuliert:

> *Reflexivity emerges when the system models its own transition structure,  
> self-modification becomes one admissible transition among others,  
> and historization constrains future self-changes.*

Die Canon Alignment (§7) identifiziert diese Brücke als **offen**:

> *Reflexivität als Selbstmodifikation: Der AGI-Blueprint §5 fordert,  
> dass das System seine eigene Transitionsstruktur modelliert.  
> `reflection.py` diagnostiziert, modifiziert aber nicht.*

Dieses Dokument untersucht, was "Structural Reflexivity" operationell bedeutet.

---

## 1. Was bereits existiert

### 1.1 Diagnose-Ebene: `reflection.py`

| Element | Status |
|---------|--------|
| `ReflectionDecision` | ✅ Trigger-Logik: failure / quality / opportunity / structural |
| `ReflectionReport` | ✅ Structured output: patterns, layers, evidence, actions |
| `StructuralDiagnostic` | ✅ Landscape-level: dead_states, loop_states, chronic_issues |
| `should_reflect()` | ✅ 4 Trigger-Klassen, feld-abgeleitete Schwellen (B4.1) |
| `reflect()` | ✅ Erzeugt Bericht mit recommended_actions |
| **Lücke:** | ❌ Empfehlungen werden nicht ausgeführt — Diagnose ohne Handlung |

### 1.2 Parametrische Selbstmodifikation: `self_tuning.py` (B4.1–B4.4)

| Element | Status |
|---------|--------|
| `RunFieldSummary` | ✅ 5 feld-abgeleitete τ-Metriken |
| `DerivedThresholds` | ✅ Schwellen emergieren aus eigener Feldstruktur |
| `ParameterSensitivity` | ✅ Heuristische + empirische (B4.4) Gradienten |
| `propose_tuning()` | ✅ Bounded proposals mit Meta-Historisierung |
| `apply_tuning()` | ✅ Änderungen werden angewandt: alpha, s_max, c_min, etc. |
| `tuning_cycle()` | ✅ Run → Diagnose → Adjust → Verify → Accept/Revert |
| `TuningMemory` | ✅ Cross-Run Persistence (B4.3) |
| `tune()` | ✅ Multi-Cycle mit Konvergenz + Oscillation-Protection |
| **Lücke:** | ❌ Nur 5 skalare Parameter — keine Landscape-Struktur-Mutation |

### 1.3 LLM-vermittelte Strukturänderung: `llm_adapter.py`

| Element | Status |
|---------|--------|
| `rebuild_landscape()` | ✅ LLM redesignt Landscape basierend auf `StructuralDiagnostic` |
| Prompt + Parsing | ✅ REBUILD_LANDSCAPE_PROMPT, JSON-Antwort → LandscapeProposal |
| **Lücke:** | ❌ Nur via LLM — keine regelbasierte Mutation, keine E₀-Admissibility |

### 1.4 Session-Orchestrierung: `session.py`

| Element | Status |
|---------|--------|
| `Session.iterate()` | ✅ Multi-iteration mit Spannungsequilibrium |
| Inter-iteration Reflection | ✅ `_inter_iteration_reflect()` nach jeder Iteration |
| `ExplorationPolicy` (C41) | ✅ Born warmup → exploit switch |
| **Lücke:** | ❌ Reflection-Empfehlungen lösen keine Strukturänderungen aus |

### 1.5 Landscape API

Die `Landscape`-Klasse bietet aktuell:

| Methode | Vorhanden |
|---------|-----------|
| `add_state(name)` | ✅ |
| `add_edge(source, target, delta, resistance)` | ✅ |
| `remove_edge(...)` | ❌ Existiert nicht |
| `modify_resistance(...)` | ❌ Existiert nicht (nur via Historisierung) |
| `remove_state(...)` | ❌ Existiert nicht |

---

## 2. Was fehlt — Strukturelle Selbstmodifikation

### 2.1 Die drei Ebenen der Selbstmodifikation

```
Ebene 1 — Parametrisch          ✅ existiert (self_tuning.py)
  → alpha, s_max, c_min, confidence_threshold, hybrid_horizon
  → Bounded, historisiert, revertierbar

Ebene 2 — Strukturell            ❌ fehlt
  → Landscape topology: Edges, Resistances, States
  → Muss unter E₀-Regeln stehen

Ebene 3 — Architektonisch        ⊘ außerhalb des Scope
  → Welche Module existieren, Code-Änderungen
  → AGI-Blueprint §8: "Multiple implementations may differ"
```

**Ebene 2 ist die offene Brücke.**

### 2.2 Minimale Strukturmutationen

Folgende Operationen bilden das minimale Mutationsalphabet:

| Mutation | Semantik | Risiko |
|----------|----------|--------|
| `add_edge(x, y, Δ, R₀)` | Neue Transition eröffnen | Niedrig — erweitert Möglichkeitsraum |
| `remove_edge(x, y)` | Transition schließen | Hoch — kann States unerreichbar machen |
| `adjust_resistance(x, y, R₀_new)` | Transitionswiderstand ändern | Mittel — ändert Feld, nicht Topologie |
| `adjust_delta(x, y, Δ_new)` | Differenzmaß ändern | Mittel — ändert Feld |
| `add_state(name)` | Neuen Zustand einführen | Niedrig — ohne Edges isoliert |
| `remove_state(name)` | Zustand entfernen | Hoch — löscht alle verbundenen Edges |

### 2.3 Die Kernfrage: Was macht eine Mutation admissible?

Der AGI-Blueprint §9 definiert Inadmissibility:

> *A transition is structurally inadmissible if it:*
> - *collapses partial realization into global replacement*
> - *cannot be integrated into existing historized structure*
> - *simulates irreversibility without producing persistent structural trace*
> - *bypasses local resistance via purely global optimization*

**Übertragung auf Strukturmutationen:**

| Blueprint-Kriterium | Bedeutung für Landscape-Mutation |
|---------------------|----------------------------------|
| No global replacement | Einzelne Edge-Mutation, nicht globaler Landscape-Reset |
| Integration in historized structure | Mutation muss zu bestehender Historisierung passen |
| Persistent structural trace | Jede Mutation wird aufgezeichnet (Meta-Historisierung) |
| No global optimization bypass | Mutation muss lokal motiviert sein (z.B. durch Diagnose) |

### 2.4 Was zählt als Admissible Self-Change?

**Vorschlag — Admissibility-Constraints für Strukturmutationen:**

1. **Lokalität:** Jede Mutation betrifft genau eine Edge oder einen State. Kein globaler Landscape-Reset.

2. **Motivation:** Jede Mutation muss durch eine `ReflectionReport`-Empfehlung oder `StructuralDiagnostic` motiviert sein — keine blinden Änderungen.

3. **Reversibilität:** Jede Mutation wird mit ihrer Inverse gespeichert (Undo-Stack). Wenn die Mutation die Qualität verschlechtert: Revert (analog zu `tuning_cycle()`).

4. **Bounded:** Pro Cycle maximal k Mutationen (z.B. k=3). Keine unbegrenzte Umstrukturierung.

5. **Historisierung:** Jede Mutation erzeugt einen persistenten `MutationRecord` mit: Typ, betroffene Edge/State, Motivation, Qualitäts-Delta, accept/revert.

6. **Oscillation-Protection:** Wiederholte gegensätzliche Mutationen derselben Edge werden blockiert (analog zu `_would_oscillate()` in `self_tuning.py`).

7. **Topology-Safety:** `remove_edge` nur wenn kein State dadurch unerreichbar wird. `remove_state` nur wenn keine aktiven Edges betroffen sind.

---

## 3. Wie Self-Modeling konkret aussieht

### 3.1 Structural Self-Model

Das System braucht ein **Modell seiner eigenen Transitionsstruktur**, das es als veränderbar behandelt. Dies ist bereits implizit vorhanden:

```python
# Bestehendes Modell (nur lesend):
StructuralDiagnostic:
    dead_states         → States die nie besucht werden
    loop_states         → States in Oszillationszyklen
    high_imbalance      → Pfad-Asymmetrien
    chronic_issues      → Wiederkehrende Probleme über Runs
    plateau_evidence    → Qualitäts-Stagnation

# Fehlendes Element (schreibend):
StructuralMutation:
    type                → add_edge / remove_edge / adjust_resistance / ...
    target              → Edge(x, y) oder State
    motivation          → Link zur Diagnose
    old_value           → Für Revert
    new_value           → Vorgeschlagener Wert
```

### 3.2 Integration in bestehende Architektur

Der natürliche Integrationspunkt ist der bestehende Tuning-Cycle:

```
Aktuell (B4.1–B4.4):
  Run → FieldSummary → Thresholds → Sensitivity → Proposals → Apply → Verify → Accept/Revert

Erweitert (Bridge 4):
  Run → FieldSummary → Thresholds → Sensitivity
      → Parametric Proposals     → Apply → Verify → Accept/Revert  [existiert]
      → Structural Proposals     → Apply → Verify → Accept/Revert  [NEU]
```

Die Infrastruktur (`RunFieldSummary`, `DerivedThresholds`, Quality Score, Meta-Historisierung, Oscillation-Protection, Revert-Logik) existiert bereits. Die Erweiterung ist:

1. **`StructuralMutation` Datenklasse** — analog zu `TuningProposal`
2. **`propose_structural_mutations()`** — erzeugt Mutationsvorschläge aus Diagnose
3. **`apply_structural_mutation()`** — führt Mutation auf Landscape aus
4. **`structural_tuning_cycle()`** — der vollständige Cycle mit Verify/Revert
5. **`MutationHistory`** — analog zu `TuningMemory` für Cross-Run-Persistence

### 3.3 Wann wird strukturelle Mutation ausgelöst?

Nicht bei jedem Run — nur wenn parametrisches Tuning **erschöpft** ist:

```
should_reflect() → structural trigger?
  ├── quality plateau despite active tuning     → ja
  ├── chronic issues in >50% recent runs        → ja
  ├── parameters drifted to bounds              → ja
  └── sonst                                     → nein (parametrisch reicht)
```

Diese Trigger **existieren bereits** in `reflection.py` (`reflection_type="structural"`). Sie erzeugen aktuell nur einen Report — der offene Schritt ist, den Report in Mutationsvorschläge umzuwandeln.

### 3.4 Session.iterate() als natürlicher Integrationspunkt

Die Multi-Iteration-Schleife ist der richtige Ort:

```
Session.iterate():
    for i in range(max_iterations):
        # 1. ExplorationPolicy (C41)     [existiert]
        # 2. Run                         [existiert]
        # 3. Residual tension map        [existiert]
        # 4. Inter-iteration reflection  [existiert]
        # 5. Structural mutation?        [NEU — wenn reflection structural trigger]
        # 6. Next iteration
```

---

## 4. Wo SU(2) eingreift — und wo nicht

### 4.1 Klare Trennung

| Aspekt | Rolle von SU(2) |
|--------|----------------|
| Structural Mutation | ❌ Nicht relevant — Topology-Operationen sind graphentheoretisch |
| Admissibility Checks | ❌ Nicht relevant — Constraints sind logisch/mengenmäßig |
| Meta-Historisierung | ❌ Nicht relevant — Aufzeichnung von Mutationen ist serialisierbar |
| Motivation/Diagnose | ❌ Nicht relevant — StructuralDiagnostic basiert auf Run-Statistiken |

### 4.2 Mögliche spätere Rolle

SU(2) könnte relevant werden wenn:

1. **Meta-Landscape als Graph:** Controller-Konfigurationen als States, Mutationen als Edges. Auf diesem Meta-Graph könnte SU(2)-Transport definiert werden — aber nur wenn der Meta-Graph Zyklen hat und Phaseninterferenz sinnvoll wäre.

2. **Interne Differenz des Controllers:** Wenn der Controller einen internen Zustand trägt, der nicht durch einen Skalar darstellbar ist (z.B. "Exploration-vs-Exploitation" als ℂ²-Spinor statt Boolean), könnte SU(2) die richtige Algebra sein.

3. **Non-kommutative Mutation-Ordnung:** Wenn die Reihenfolge von Mutationen das Ergebnis beeinflusst (was bei Landscape-Änderungen typisch ist), könnte dies als SU(2)-Holonomie modelliert werden.

**Bewertung:** Alle drei sind **offene Forschungsfragen**, nicht Voraussetzungen für Bridge 4. Bridge 4 wird durch (C) Structural Reflexivity geschlossen — SU(2) ist eine optionale spätere Darstellungsschicht.

### 4.3 Empfehlung

> Bridge 4 zuerst mechanisch schließen (Strukturmutationen unter E₀-Regeln).  
> Dann prüfen, ob SU(2) neue Einsichten über die Meta-Dynamik liefert.

---

## 5. Zusammenfassung: Bridge 4 Gap Analysis

```
Bridge 4 = Structural Reflexivity

Was der Blueprint fordert:
  ☐ self-modeling         → ❌/✅ StructuralDiagnostic existiert (lesend)
  ☐ self-modification     → ❌ keine Landscape-Mutation
  ☐ admissible transition → ❌ keine Admissibility-Prüfung für Mutationen
  ☐ historization         → ❌ keine MutationHistory

Was schon existiert:
  ✅ Diagnose (reflection.py)
  ✅ Parametrisches Tuning (self_tuning.py)
  ✅ LLM-Landscape-Rebuild (llm_adapter.py) — aber nicht unter E₀-Regeln
  ✅ Structural Trigger in should_reflect()
  ✅ Session.iterate() als Orchestrierungsrahmen

Was gebaut werden muss:
  ✅ Landscape API erweitern: remove_edge, adjust_resistance, adjust_delta (Commit dd6e277)
  ✅ StructuralMutation Datenklasse (Commit e94be7e)
  ✅ propose_structural_mutations() aus StructuralDiagnostic (Commit e94be7e)
  ✅ Admissibility checks für Mutationen (lokal, bounded, topologie-safe) (Commit e94be7e)
  ✅ apply/revert Mechanismus mit Quality-Verify (Commit e94be7e)
  ✅ MutationHistory mit Oscillation-Protection (Commit e94be7e)
  ✅ Integration in Session.iterate() (Commit e3f922d)
```

---

## 6. Vorgeschlagene Reihenfolge

### Stufe 1 — Landscape API ✅ (Commit dd6e277)

`landscape.py` um minimale Mutations-Methoden erweitert:
- `remove_edge(x, y)` — löscht aus _delta/_R0, invalidiert Caches, KeyError wenn nicht vorhanden
- `adjust_base_resistance(x, y, R₀_new)` — gibt alten Wert zurück, validiert ≥ 0
- `adjust_delta(x, y, Δ_new)` — gibt alten Wert zurück, validiert ≥ 0
- `has_edge(x, y)` — Convenience-Check (bool)
- `would_orphan(x, y)` → Set[str] — States die isoliert würden
- `_invalidate_caches()` — räumt _M_H_cache, _overlap_cache, _phi_cache auf

56 Tests in 10 Klassen (`test_landscape_mutation.py`). 1682 Gesamttests.

### Stufe 2 — Mutation Infrastructure ✅ (Commit e94be7e)

Neues Modul `structural_mutation.py`:
- `MutationType` Enum: REMOVE_EDGE, ADD_EDGE, ADJUST_RESISTANCE, ADJUST_DELTA
- `StructuralMutation` Datenklasse: Typ, Edge, old/new Werte, Motivation, describe()
- `MutationRecord`: Audit-Trail mit Quality-Delta, accept/revert Status
- `MutationHistory`: Bounded Log (max 100), Oscillation-Protection (same-type + add↔remove), Serialisierung
- `is_admissible()`: E₀-Gate (Lokalität, no orphans, non-negative, Edge-Existenz)
- `apply_structural_mutation()` / `revert_structural_mutation()`: mechanisch auf Landscape
- `propose_structural_mutations()`: Diagnostic → Vorschläge (dead→Δ↑, loop→R₀↑), max 3/Cycle

66 Tests in 10 Klassen (`test_structural_mutation.py`). 1748 Gesamttests.

### Stufe 3 — Tuning Integration ✅ (Commit e3f922d)

`structural_mutation.py` + `session.py` erweitert:
- `StructuralTuningCycleResult` Datenklasse: Q_before/after, Diagnostic, Proposals, Accept/Revert, MutationRecords
- `structural_tuning_cycle()`: Run → Diagnose (via `build_structural_diagnostic`) → Propose (via `propose_structural_mutations`) → Apply → Re-run → Verify Q_after → Accept/Revert
- `Session.iterate()` Step 6: strukturelle Mutation nach Inter-Iteration-Reflection
  - Trigger: nur wenn `ReflectionReport.reflection_type == "structural"` UND `should_continue`
  - Eskalationskette: parametrisch erschöpft → Plateau/Chronic/Bounds → structural trigger
- `Session.mutation_history`: `MutationHistory` in `__init__` + `resume`
- `IterationResult.structural_results`: per-Iteration `Optional[StructuralTuningCycleResult]`

42 Tests in 10 Klassen (`test_structural_tuning_cycle.py`). 1790 Gesamttests.

### Stufe 4a — Identity-Invariant ✅

`structural_mutation.py` §3b erweitert:
- `IdentityViolation` Enum: GOAL_UNREACHABLE, DEAD_END_CREATED, HISTORIZATION_BROKEN
- `IdentityCheck` Datenklasse: ok, violations, details; `__bool__` → ok
- `_reachable_states()`: BFS-Helper für Erreichbarkeitsanalyse
- `check_identity_invariant()`: Prüft (1) Goal-Erreichbarkeit, (2) A₀-Viabilität (keine Dead Ends), (3) Historisierungs-Kontinuität (API-Design)
- `check_identity_after_mutation()`: Prospektive Prüfung — Apply → Check → Revert
- `StructuralTuningCycleResult.identity_check`: neues Feld
- `structural_tuning_cycle()` Phase 4b: Identity-Check nach Apply, Revert bei Verletzung

21 neue Tests in 4 Klassen (11–14 in `test_structural_mutation.py`). 1811 Gesamttests.

### Stufe 4b (optional) — SU(2) Meta-Darstellung

Prüfen ob Meta-Landscape von SU(2)-Transport profitiert. Separate Forschungsfrage.

---

*Ende der Konzeptnotiz.*
