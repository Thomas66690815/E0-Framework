# E₀ — Erkenntnisse Phase 2

**Status:** Reflektive Synthese  
**Datum:** 2026-03-27  
**Scope:** Commits `f2782d5` bis `c41a0ff` (ProvenanceLog → C37b Reflexion im Iterate-Loop)  
**Teststand:** 1483 (von 1138 → +345 Tests, +30%)  

---

## 0. Worum es geht

Dieses Dokument hält die Erkenntnisse fest, die seit dem letzten umfassenden Review (`E0_CODE_ANALYSIS_2026-03-26.md`, Teststand 1138) entstanden sind.  Es ist keine Code-Analyse — es ist eine **Erkenntnis-Synthese**.

Phase 1 (die ersten 7 Tage) hat die Maschine gebaut: Controller, Amplituden-Overlay, SU(2), Curvature, Evaluation, Reflexion, Self-Tuning, Born-Regime, MemOS, LLM-Adapter.

Phase 2 hat die Maschine **benutzt** — und dabei verstanden, was sie wirklich tut.

---

## 1. Die drei Domänen

### 1.1 Beipackzettel (Domäne 1)

Die erste reale Domäne — ein medizinischer Beipackzettel, LLM-geparst in eine Landscape mit 8 States und 10 Edges.  Hier wurde der **Mass Trap** entdeckt: Der Amplituden-Overlay erzeugt konstruktive Interferenz an NEBENWIRKUNG-Knoten, weil die Pfadfamilien dort verzweigen.  Der Controller zykliert, der Greedy-Modus entkommt.

Erkenntnis: Das Phänomen ist **amplituden-strukturell**, nicht graph-strukturell.

### 1.2 EZB-Zinsentscheidung (Domäne 2)

Geldpolitik der EZB mit 11 States und 16 Edges.  Drei Szenarien:

1. **Inflationsbekämpfung:** INFLATION_HOCH → PREISSTABILITAET (geradlinig, Zinserhöhung nötig)
2. **Rezession mit Multi-Goal:** REZESSION → {WACHSTUM, PREISSTABILITAET} (erste echte Multi-Goal-Anwendung)
3. **Stagflation als Gordian Trap:** STAGFLATION hat drei Ausgänge, alle mit hohem Widerstand — ein genuiner Trap, kein künstliches Deadlock

**Zentrale Erkenntnis:** Der Mass Trap tritt auch hier auf.  INFLATION_HOCH → STAGFLATION erzeugt dieselbe konstruktive Interferenz wie NEBENWIRKUNG im Beipackzettel.  Greedy entkommt, Amplitude zykliert.  `path_count_imbalance > 3.0` bestätigt das Muster cross-domain.

→ **Der Mass Trap ist kein Domänen-Artefakt.  Er ist ein strukturelles Phänomen des Amplituden-Overlays.**

### 1.3 Burnout Composite (Domäne 3)

Fünf Quellenfragmente (ökonomisch, psychologisch, journalistisch, Erfahrungsbericht, autofiktional) werden zusammengeführt.  Die Landscape wird erstmals **vollständig vom LLM generiert** — kein vordesignter Graph.

Das LLM erzeugt typischerweise 11–13 States, 14–17 Edges, mit Feedback-Schleifen (LOOP_UNRESOLVED → REFRAMING_NEEDED) und Error-Recovery-Pfaden.  Graph quality liegt bei 0.97–1.00.

**Zentrale Erkenntnis:** Die LLM-generierte Topologie ist strukturell sinnvoll.  Die Controller-Engine navigiert sie sauber.  Aber der Controller wählt konsistent den kürzesten Pfad zum Ziel und **ignoriert** unbesuchte Äste (Erfahrungsbericht, Autofiktion, Error-Recovery).  Diese Äste behalten ihre volle Spannung.

→ **Der Controller optimiert lokal korrekt, nutzt aber die Landscape nicht vollständig.  Das ist kein Bug — es ist ein strukturelles Merkmal, das erst durch die Residual-Tension-Messung sichtbar wird.**

---

## 2. Die fünf strukturellen Erkenntnisse

### Erkenntnis 1: Der Mass Trap ist domänenübergreifend

| Domäne | Trigger-Knoten | Imbalance | Verhalten |
|---|---|---|---|
| Beipackzettel | NEBENWIRKUNG | > 3.0 | Amplitude zykliert, Greedy entkommt |
| EZB | INFLATION_HOCH → STAGFLATION | > 3.0 | Amplitude zykliert, Greedy entkommt |

**Mechanismus:** Wenn ein Knoten deutlich mehr Pfadfamilien empfängt als andere (durch Verzweigung in der Topologie), entsteht konstruktive Interferenz.  Diese Interferenz ist korrekt berechnet — sie spiegelt tatsächliche strukturelle Dominanz wider.  Aber die daraus resultierende Entscheidung kann pathologisch sein: Der Controller folgt der Interferenz in einen Zyklus.

**Lösung:** Der Mass Trap Detector erkennt `path_count_imbalance > 3.0 + repeated_cycles > 0` und **invertiert** die Self-Tuning-Reaktion: Statt den Horizont zu erhöhen (was die Interferenz verstärkt), wird er reduziert.  Gleichzeitig steigt `confidence_threshold`, um den Amplituden-Override zu erschweren.

**Warum das wichtig ist:** Das ist keine Heuristik — es ist eine prinzipielle Korrektur.  Die Diagnose (Imbalance) und die Therapie (Horizont-Inversion) folgen aus dem gleichen strukturellen Argument.

### Erkenntnis 2: Domänen vor Schema

Beim Schema-Review (v0.1) stand eine Entscheidung an: Soll das Schema die Implementierung treiben, oder sollen reale Domänen das Schema informieren?

**Entscheidung:** Domänen → Schema.

| Was | Status |
|---|---|
| Core (E0Envelope, TransportRegime) | ✅ implementiert (48 Tests) |
| Ingress (Parsing, Proposal) | ⏳ wartet auf 2–3 Domänen-Vergleich |
| Reflection (pre-decision Gate) | ⏳ wartet auf reale Mechanismen |
| Egress (Ausgabe, Integration) | ⏳ wartet auf erstes Integrationsziel |

**Begründung:** Premature Standardization birgt das Risiko, die falschen Abstraktionen einzufrieren.  Besser: Drei reale Domänen bauen (Beipackzettel ✅, EZB ✅, Burnout ✅), dann vergleichen, was tatsächlich gleich war.

→ **Die Domänen haben tatsächlich unterschiedliche Ingress-Pfade, aber identische Core-Mechanik (Spannung, Interferenz, Mass Trap).  Das Schema muss diese Asymmetrie abbilden.**

### Erkenntnis 3: Iteration als Spannungsträger

Die wichtigste konzeptionelle Erkenntnis dieser Phase.

**Ausgangsfrage:** Wie viele Iterationen braucht ein Problem?

**Falsche Antwort:** "Das legen wir fest" (max_iterations=5).

**Richtige Antwort:** "Das ergibt sich" — aus der Spannungsstruktur der Landscape.

Die Einsicht kam aus der Diskussion über das Continuum: *"In Iterationen muss man Spannungen aushalten und diese für die nächste Iteration nehmen."*  Das ist exakt Axiom A₀ auf Iterationsebene:

> **Ruhe bedarf der Erklärung. Veränderung nicht.**

Wenn sich die Residualspannung zwischen Iterationen nicht verändert (Stagnation: `|Δmean| < 0.02`), ist das erklärungsbedürftig — nicht normal.  Wenn sie sich verändert, läuft der Prozess weiter.

**Die ResidualTensionMap** macht das operativ:

- **Vor dem Run:** `snapshot_tensions()` — S_eff jeder Kante
- **Nach dem Run:** `compute_residual_map()` — was hat sich verändert?
- **Entscheidung:** `should_continue()` — Equilibrium, Stagnation, oder weiter?
- **Reflexion:** Wenn Stagnation oder Amplifikation → `reflect()` feuert

Der Iterate-Loop ist kein Retry-Mechanismus.  Er ist ein **Spannungsprozessor**.  Jede Iteration transformiert die Landscape (durch Historization), und die Residualspannung zeigt, ob diese Transformation zur Ruhe führt oder neue Spannung erzeugt.

### Erkenntnis 4: Die Reflexion schließt den Loop

Phase 1 hatte Reflexion als **post-run Diagnostik**: War der Run gut?  Was ging schief?  Empfehlung für nächstes Mal.

Phase 2 hat Reflexion zu einem **aktiven Bestandteil des Iterate-Loops** gemacht:

```
run → messen → reflektieren → nächste Iteration (oder Stopp)
```

Die Zwei-Stufen-Filterung ist wichtig:

1. **Iterate-Level:** `verdict.should_reflect` ist ein Hinweis ("es gibt Grund zu reflektieren")
2. **Reflexions-Level:** `reflect()` entscheidet, ob die Bedingungen tatsächlich einen Report rechtfertigen

Damit kann `should_reflect = True` feuern (weil Stagnation erkannt wurde), aber `reflect()` keinen Report produzieren (weil der Run trotzdem A-Rating hatte und die Reflexionsschicht keinen Trigger findet).  Oder umgekehrt: Beim finalen Stopp wird *immer* Reflexion versucht — aber nur bei echtem Befund kommt ein Report.

**Beobachtung aus den Live-Demos:**

| Stopp-Grund | Reflexions-Typ | Inhalt |
|---|---|---|
| Stagnation (Burnout, Mock) | opportunity | "A-rated run, graph_design hat Potential" |
| Stagnation (Burnout, Live) | opportunity | "Hohe Effizienz, ungenutzte Äste" |
| Goal nicht erreicht | failure | "Goal not reached" + Pfad-Analyse |

Die Reflexion erkennt korrekt den Unterschied zwischen "schlecht gelaufen" (failure) und "gut gelaufen, aber mehr möglich" (opportunity).  Das ist die strukturell richtige Diagnose: Der Controller hat sein Ziel erreicht, aber die Landscape bietet mehr, als er nutzt.

### Erkenntnis 5: Provenance als Ergebniskette

Die ProvenanceLog schafft etwas, das vorher fehlte: **Nachvollziehbarkeit**.

Sechs Stufen, lückenlos:

```
InputRecord → LLMCallRecord → ProposalRecord → LandscapeRecord → RunRecord → EvaluationRecord
```

Jeder Schritt hat: Timestamp, SHA256-Fingerprint (Input), Rohdaten (LLM-Response), strukturierte Daten (Proposal, Landscape, Trace), Bewertung (Evaluation).  Die Kette ist serialisierbar (`to_dict()/from_dict()`) und persistent (`save()/load()`).

**Warum das wichtig ist:**

Das System trifft Entscheidungen auf Basis von LLM-generierten Landschaften.  Ohne Provenance ist nicht nachvollziehbar, warum der Controller eine bestimmte Route gewählt hat — man sieht nur das Ergebnis.  Mit Provenance sieht man: Welcher Text wurde eingegeben → Was hat das LLM daraus gemacht → Wie wurde das materialisiert → Wie ist der Controller gelaufen → Wie wurde das bewertet.

Das ist die Voraussetzung für jede Form von **Audit, Debugging, und Vertrauen**.

---

## 3. Die Architektur nach Phase 2

```
┌─────────────────────────────────────────────────────────────┐
│                     Session.iterate()                        │
│  ┌────────┐   ┌──────────┐   ┌──────────┐   ┌───────────┐  │
│  │  run() │ → │ residual │ → │ verdict  │ → │ reflect() │  │
│  │        │   │ tension  │   │          │   │           │  │
│  └────────┘   │   map    │   │ continue │   │ failure   │  │
│       ↑       └──────────┘   │ stagnate │   │ quality   │  │
│       │                      │ equilib. │   │ opportun. │  │
│       │                      │ budget   │   │ structur. │  │
│       │                      └──────────┘   └───────────┘  │
│       │                                          │          │
│       └──────────────────────────────────────────┘          │
│                  (nächste Iteration)                         │
└─────────────────────────────────────────────────────────────┘
         ↕                    ↕                    ↕
    Historization        TuningMemory         ProvenanceLog
    (Kanten lernen)      (Parameter lernen)   (Audit-Kette)
```

**Neue Schichten seit Phase 1:**

| Schicht | Phase 1 | Phase 2 |
|---|---|---|
| Iterate-Kontrolle | — | ResidualTensionMap, should_continue(), emergente Iterationszahl |
| Inter-Iteration-Reflexion | — | _inter_iteration_reflect(), ReflectionReport zwischen Runs |
| Strukturelle Reflexion | — | StructuralDiagnostic, rebuild_landscape(), REBUILD_LANDSCAPE_PROMPT |
| Konfiguration | kwargs-Wörterbuch | E0Envelope (frozen, typisiert, serialisierbar) |
| Transport-Regime | `use_su2=True/False/"geometric"` | TransportRegime Enum (U1, SU2_MINIMAL, SU2_GEOMETRIC) |
| Mass Trap | Beobachtet (Beipackzettel) | Detektiert + korrigiert (path_count_imbalance, Horizont-Inversion) |
| Provenance | — | 6-stufige Ergebniskette, Input bis Evaluation |
| Domänen | 1 (Beipackzettel) | 3 (+ EZB, + Burnout), cross-domain validiert |

---

## 4. Was offen ist

### 4.1 Der Controller nutzt Landschaften nicht vollständig

Observation aus Domäne 3: Der Controller findet den kürzesten Pfad zum Ziel und ignoriert Seitenäste.  Die ResidualTensionMap zeigt das (unbesuchte Hotspots), die Reflexion diagnostiziert das (opportunity: graph_design), aber **niemand handelt darauf**.

Nächster Schritt: Die Reflexion muss Konsequenzen haben — entweder der Controller exploriert gezielt unbesuchte Äste, oder die Landscape wird umgebaut (C36 Structural Reflection hat das Werkzeug, aber es wird nicht automatisch aufgerufen).

### 4.2 Ingress ist nicht standardisiert

Drei Domänen haben drei verschiedene Ingress-Pfade:
- Beipackzettel: Einzeltext → LLM → Landscape
- EZB: Handdesignter Graph (test fixture)
- Burnout: 5 Fragmente → zusammengesetzt → LLM → Landscape

Was davon verallgemeinert werden kann, ist erst nach Vergleich klar.

### 4.3 Schema v0.2 steht aus

Die drei Domänen liefern jetzt genug Evidenz für einen zweiten Schema-Versuch.  Insbesondere:
- Core-Block (E0Envelope) ist stabil
- Ingress-Block muss die Asymmetrie Text→LLM vs. Fixture abbilden
- Reflection-Block im Schema ist ein pre-decision Gate, im Code ist es post-run Diagnostik — das muss geklärt werden

### 4.4 Egress fehlt komplett

Das System produziert Traces, Evaluations, Reflections, Provenance — aber es gibt keinen standardisierten Ausgabepfad.  Kein API-Endpoint, kein UI-Format, kein Actuator-Interface.  Das ist bewusst aufgeschoben (Schema-Entscheidung), aber es limitiert die Nutzbarkeit.

### 4.5 Automatische Landscape-Reparatur

C36 liefert `StructuralDiagnostic` und `REBUILD_LANDSCAPE_PROMPT`.  C37 erkennt Stagnation.  Aber es gibt noch keinen automatischen Pfad von "Stagnation erkannt" → "Landscape umbauen" → "neu iterieren".  Das wäre der nächste Schließungsschritt.

---

## 5. Metriken

| Metrik | Phase 1 (Tag 7) | Phase 2 (Tag 10) | Delta |
|---|---|---|---|
| Tests | 1138 | 1483 | +345 (+30%) |
| Test-Dateien | 29 | 40+ | +11 |
| Module (e0_controller/) | ~22 | ~26 | +4 |
| Domänen | 1 | 3 | +2 |
| Commits (Phase) | 25 | ~15 | — |
| Live-LLM-Tests | 0 (gemischt) | 41 (separiert) | Sauber getrennt |
| Provenance-Kette | — | 6/6 Stufen | Komplett |

---

## 6. Abschluss

Phase 1 hat gezeigt, dass E₀ **funktioniert**: Spannungsnavigation, Interferenz, Gordian Traps, Born-Regime.

Phase 2 hat gezeigt, was E₀ **bedeutet**:

1. **Der Mass Trap ist real und domänenübergreifend.**  Es ist kein Bug, sondern ein strukturelles Phänomen der Amplituden-Interferenz, das prinzipiell korrigiert werden kann.

2. **Iteration ist kein Retry.**  Es ist ein Spannungsprozess, dessen Länge aus der Landscape emergiert.  Stagnation ist erklärungsbedürftig, Veränderung nicht.

3. **Reflexion ist kein Nachdenken über den Run.**  Es ist Teil des Runs — eingebettet zwischen Iterationen, mit konkreten Triggern und typisierten Reports.

4. **Provenance macht Entscheidungen nachvollziehbar.**  Ohne sie ist der Controller eine Blackbox, mit ihr eine auditierbare Entscheidungskette.

5. **Schema folgt Evidenz, nicht umgekehrt.**  Drei reale Domänen zeigen: der Core ist stabil, der Rest muss sich noch finden.

Die Maschine läuft.  Jetzt muss sie lernen, was sie sieht, auch zu nutzen.
