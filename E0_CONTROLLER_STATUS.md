# E₀ Controller — Status, Lücken, Lösungswege

**Stand:** 2026-03-19 (v0.3 — Phase 1a abgeschlossen)
**Kontext:** Neuansatz nach 3 Wochen Pause. Multi-Agent-Orchestrierung (Keimzelle) verworfen.
**Neuer Ansatz:** Einzelner deterministischer E₀ Controller als Reasoning-Engine.

### Aktueller Fortschritt

| Phase | Status | Commit |
|---|---|---|
| **Phase 0** — Dieses Dokument | ✅ Abgeschlossen | `fa278ee` |
| **Phase 1a** — Minimaler Controller + Mini-Domäne | ✅ Abgeschlossen (12/12 Tests) | `8523a9b` |
| **Phase 1b** — Strukturierte Praxis-Domäne | ⬜ Nicht begonnen | — |
| **Phase 2** — Connection & Phase (§9–16) | ⬜ Nicht begonnen | — |
| **Phase 3** — LLM-Integration | ⬜ Nicht begonnen | — |
| **Phase 4** — Spin-1/2 offene Punkte | ⬜ Nicht begonnen (parallel) | — |

---

## 1. Was existiert

### 1.1 Kanonische Texte (stabil, unverändert)

| Dokument | Inhalt | Status |
|---|---|---|
| `canon/ontodynamics.txt` | Pre-physischer Kanon: Difference, Local Realization, Connection, Overlap, Historization | **Kanonisch** |
| `canon/e0-canonical-reference.txt` | E₀ v1.0: 7 Primitive, Axiom A₀, Central Law, Konsequenzen | **Kanonisch** |
| `canon/e0-canon-plain.txt` | Dasselbe in Plain Language | **Kanonisch** |
| `canon/e0-agi-blueprint.md` | AGI-Blueprint: Operationale Schicht über E₀ | **Kanonisch** |

### 1.2 Bestehender Code (`e0_core/`)

| Modul | Klassen/Funktionen | Deckt ab |
|---|---|---|
| `primitives.py` | `State`, `Path`, `Historization`, `difference()`, `rate()` | §2.1–2.3 der Spec (teilweise) |
| `engine.py` | `TransitionEngine`, `axiom_a0()`, `TransitionResult` | Axiom A₀ + einfache Pfadwahl |
| `ontodynamics.py` | `DirectedDifference`, `Connection`, `Topology`, `OntodynamicAdmissibility` | Topologie + Admissibility-Checks |
| `guards.py` | `StructuralGuard`, `AdmissibilityVerdict` | Collapse/Integrability/Trace Guards |
| `reflexivity.py` | `MetaState`, `ReflexiveEngine` | Selbstmodellierung (Meta-Ebene) |

### 1.3 E₀ Controller Specification v0.1 (neu, aus ChatGPT-Session)

20 formal-mathematische Sektionen — der operative Kern der neuen Architektur.
Vollständig dokumentiert im Perplexity-Thread. **Noch nicht implementiert.**

### 1.4 Spin-1/2 Derivation (neu, aus Claude-Session)

Ableitung von komplexen Zahlen, SU(2) und 720°-Symmetrie aus E₀-Primitiven.
**Konzeptionell stark, mathematisch noch drei offene Punkte.**

---

## 2. Controller Spec v0.1 — Mapping auf bestehenden Code

Die folgende Tabelle zeigt exakt, wo der bestehende Code die Spec abdeckt und wo Lücken sind.

| Spec-Sektion | Formalisierung | Bestehender Code | Status |
|---|---|---|---|
| **§2.1 Δ(x,y)** | Difference-Maß | `primitives.difference()` — Euklidisch | ✅ Vorhanden, aber nur Euklidisch |
| **§2.2 R(x→y \| H,L)** | Resistance abhängig von H und L | `Path.resistance` — statischer Wert | ⚠️ Keine H/L-Abhängigkeit |
| **§2.3 H_t = (e₁...e_t)** | Historization als Sequenz | `Historization` — hat `decay_factor` | ⚠️ Kein U/F-Trace-Split |
| **§2.4 v_x(y) = Δ·M_H·exp(−S)** | Lokales Transitionsfeld | — | ❌ Fehlt komplett |
| **§3 S(x→y) = Δ·R** | Tension | Implizit in `engine.py` | ⚠️ Nicht als eigenes Konzept |
| **§4–5 Pfade, Pfad-Tension S(p)** | Pfad-Summation | `Path` — hat `resistance`, keine Summation | ⚠️ Nur Einzel-Edges |
| **§6 C(p) = exp(−S(p))** | Kohärenz | — | ❌ Fehlt |
| **§7 L_t = (X_t, E_t, v_t, S_t, H_t)** | Landschaft als Gesamtzustand | — | ❌ Fehlt |
| **§8 Non-Integrable Structure** | Integrable vs. nicht-integrable Komponenten | `OntodynamicAdmissibility.check_integrability` | ⚠️ Prüft, aber dekomponiert nicht |
| **§9 Φ(x) = Σ Δ·R** | Lokales Potential | — | ❌ Fehlt |
| **§10 v_grad = Φ(x)−Φ(y)** | Gradient-Komponente | — | ❌ Fehlt |
| **§11 v_rot = v − v_grad** | Rotations-Komponente | — | ❌ Fehlt |
| **§12 ω(x→y) = ½(v_rot,x(y)−v_rot,y(x))** | Connection | `ontodynamics.Connection` — aber andere Semantik (Overlap) | ⚠️ Mismatch |
| **§13 Θ(p) = Σ ω(e)** | Pfad-Phase | — | ❌ Fehlt |
| **§14 Holonomie Θ(γ)** | Geschlossene Schleifen | — | ❌ Fehlt |
| **§15 Ψ(p) = exp(−S)·exp(iΘ)** | Komplexe Pfad-Darstellung | — | ❌ Fehlt |
| **§16 Ψ(z) = Σ Ψ(p)** | Pfad-Summation (Interferenz) | — | ❌ Fehlt |
| **§17.1 U_t / F_t Traces** | Success/Failure-Trennung | — | ❌ Fehlt |
| **§17.2 δ_H = λ_f·F − λ_s·U** | Historization-Korrektur | — | ❌ Fehlt |
| **§17.3 Clipping** | Bounded Dynamics | — | ❌ Fehlt |
| **§18 p\* = argmin S_eff** | Controller-Kernregel | `engine.find_best_path` — ähnlich, aber ohne S_eff | ⚠️ Konzeptionell nah |
| **§19 Stability Z_t** | Diskretes dynamisches System | — | ❌ Fehlt |

**Zusammenfassung:** Die Prozente (~25/15/60) sind weniger wichtig als die **kritischen Abhängigkeiten**. Wenn vier Dinge stehen — Landscape, Historization(U/F), Controller-Loop, v_x(y) — ist v0.1 operativ. §9–16 (Φ, ω, Θ, Ψ) können warten.

---

## 3. Identifizierte Lücken

### Lücke 1: Kein Landschaft-Objekt

Die Spec definiert $L_t = (X_t, E_t, v_t, S_t, H_t)$ als zentralen Zustand. Der bestehende Code hat `Topology` (Knoten + Connections) und `Historization` (Sequenz), aber kein einheitliches Landscape-Objekt, das alle Komponenten zusammenführt.

**Auswirkung:** Ohne Landscape hat der Controller keinen kohärenten Zustand zum Operieren.

### Lücke 2: Kein Transitionsfeld v_x(y)

Die lokale Transition-Kapazität $v_x(y) = \Delta(x,y) \cdot M_H(x,y) \cdot \exp(-S(x \to y))$ ist das zentrale Evaluierungsinstrument. Existiert nicht im Code.

**Auswirkung:** Der Controller kann nicht berechnen, welche Transitionen strukturell offen sind.

### Lücke 3: Keine Gradient/Rotation-Zerlegung

Die Zerlegung $v = v_{grad} + v_{rot}$ und die daraus abgeleitete Connection $\omega$ fehlen komplett. Das bestehende `Connection`-Objekt in `ontodynamics.py` modelliert *Overlap* (gradueller Verknüpfungsgrad), nicht die antisymmetrische Connection der Spec.

**Auswirkung:** Ohne $\omega$ keine Phase Θ, keine Holonomie, kein $\Psi$.

### Lücke 4: Keine komplexe Pfad-Struktur

$\Psi(p) = \exp(-S) \cdot \exp(i\Theta)$ und die Pfad-Summation $\Psi(z) = \sum \Psi(p)$ fehlen.

**Auswirkung:** Die gesamte Interferenz-Logik und die Brücke zur Spin-1/2-Derivation fehlen.

### Lücke 5: Historization ohne U/F-Split

Die bestehende `Historization`-Klasse hat `decay_factor` und senkt R pauschal. Die Spec unterscheidet explizit Success-Traces $U_t$ und Failure-Traces $F_t$ mit getrennten Lernraten $\lambda_s, \lambda_f$.

**Auswirkung:** Kein differenziertes Lernen aus Erfolg vs. Scheitern.

### Lücke 6: Controller-Loop fehlt als eigenes Modul

`engine.py` hat `TransitionEngine.step()` und `.run()`, aber der Controller-Loop der Spec (candidates → argmin → escalate → execute → historize) ist nicht als eigene, saubere Abstraktion implementiert.

**Auswirkung:** Keine klare Schnittstelle für externe Systeme (LLM, Simulation, Analyse).

### Lücke 7: Pfad-Suche skaliert nicht

Die Spec sagt $p^* = \arg\min_{p} S_{eff}(p)$ — das ist über alle möglichen Pfade in einem großen State-Raum NP-hart. Keine Approximationsstrategie definiert.

**Auswirkung:** Funktioniert für 5-10 States, bricht bei großen Räumen zusammen.

### Lücke 8: Δ-Bestimmung aus realen Daten

Die Spec nimmt Δ(x,y) als gegeben an. In der Praxis (Iran-Analyse, LLM-Reasoning) muss Δ aus unstrukturierten Daten *extrahiert* werden. Kein Mechanismus dafür definiert.

**Auswirkung:** Ohne Δ-Extraktion kein realer Einsatz.

---

## 4. Spin-1/2 Derivation — Status

### Was abgeleitet wurde (aus E₀-Primitiven):

1. **Komplexe Zahlen als notwendige Path-Encoding:**
   $\Psi = \exp(-S) \cdot \exp(i\Theta)$ — erzwungen durch zwei unabhängige Pfad-Größen (Magnitude S, Orientation Θ) mit verschiedenem algebraischem Charakter.

2. **Historization → 720°-Symmetrie:**
   State = Configuration + Ankunftsgeschichte. Unter Historization sind $\uparrow_+$ und $\uparrow_-$ verschieden, weil verschiedene Pfade verschiedene strukturelle Spuren hinterlassen. Eine 360°-Rotation schließt die Pfadhistorie nicht — man braucht 720°.

3. **SU(2) als minimale Symmetriegruppe:**
   Die Transformationsgruppe, die {↑₊, ↑₋, ↓₊, ↓₋} unter Erhaltung von ω abbildet, ist genau SU(2).

### Was offen ist:

| Offener Punkt | Beschreibung | Schwierigkeit |
|---|---|---|
| **ω-Fixierung** | Der Wert $\omega = \pi/2$ wurde gesetzt, nicht aus E₀ hergeleitet. E₀ muss den minimalen nicht-trivialen ω-Wert eindeutig erzwingen. | Mittel |
| **Warum genau 2 Base-States?** | Plausibel, aber nicht bewiesen, dass das Minimum für nicht-triviale Connection genau 2 ist. | Mittel |
| **Diskret → Kontinuum** | Der Übergang von diskreter E₀-Struktur zu kontinuierlicher SU(2)-Darstellung braucht ein Grenzwertargument. | Hoch |

---

## 5. Architektur-Entscheidungen (offen)

### Entscheidung A: Soll der Controller das LLM steuern oder das LLM den Controller ausführen?

**Option A1 — Controller steuert LLM:**
Der Controller evaluiert $S_{eff}$ über Pfade und beauftragt das LLM, den gewählten Pfad auszuführen (Text generieren, Code schreiben, etc.). LLM = Executor.

**Option A2 — LLM führt Controller aus:**
Das LLM bekommt die Controller-Logik als Prompt/Context und evaluiert $\Delta$, $R$, $S_{eff}$ selbst als Teil seines Reasoning. LLM = Runtime.

**Option A3 — Hybrid:**
Python-Controller berechnet $S_{eff}$ und Pfadwahl deterministisch; LLM wird nur für Δ-Extraktion und Pfad-Beschreibung eingesetzt.

**Empfehlung:** A3 — Hybrid. Deterministische Mathematik in Python, LLM für das, was LLMs können (Sprache, Kontext, Einschätzung).

### Entscheidung B: Bestehendes `e0_core` refactoren oder Neuimplementierung?

**Option B1 — Refactoring:**
`primitives.py`, `engine.py` erweitern. Vorteil: bestehende Struktur nutzen. Risiko: Mismatch bei `Connection` (Overlap ≠ ω).

**Option B2 — Neuimplementierung `e0_controller/`:**
Neues Paket, das die Spec v0.1 sauber umsetzt. `e0_core/` bleibt als Referenz. Vorteil: kein Legacy-Ballast. Risiko: Dopplung.

**Option B3 — Schrittweiser Ersatz:**
Neues `e0_controller/` als primäres Paket; `e0_core/` als Read-Only-Archiv.

**Empfehlung:** B3 — Neu bauen, Altes behalten.

### Entscheidung C: Pfad-Suche Approximation

$\arg\min_p S_{eff}(p)$ über alle Pfade ist NP-hart. Mögliche Strategien:

**C1 — Nur direkte Transitionen (1-Schritt):**
$p^* = \arg\min_{y \in N(x)} S_{eff}(x \to y)$. Einfach, skaliert, aber kurzsichtig.

**C2 — Beam Search (k beste Pfade, Tiefe d):**
Exploration mit begrenzter Breite. Skalierbar, guter Kompromiss.

**C3 — Dynamische Programmierung** bei DAG-Struktur.

**C4 — Greedy + Escalation:**
1-Schritt-Greedy, bei Deadlock ($S = \infty$) breitere Suche.

**Empfehlung:** C4 für v0.1, C2 für v0.2.

**Ergänzung (v0.1):** Revisit-Penalty für Short-Cycle-Suppression. Ohne das dreht Greedy Schleifen zwischen zwei States. Einfachste Form: $R_{revisit}(x \to y) = R_{eff}(x \to y) + \alpha \cdot \mathbb{1}[y \in \text{recent}(k)]$ mit kleinem $\alpha > 0$ und Fenster $k$.

---

## 6. Vorgeschlagener Implementierungs-Plan

### Phase 0: Dieses Dokument ✅
Bestandsaufnahme, Lücken, Entscheidungen.

---

### Phase 1a: Minimaler Controller + kontrollierte Mini-Domäne ✅

**Status:** Abgeschlossen am 2026-03-19. Commits `8523a9b`, `96c93f5`.

**Ziel:** §2–6, §17–18 der Spec als lauffähiger Python-Code.

> **Scope-Begrenzung:** Sections §8–16 (Potential Φ, Connection ω, Phase Θ, komplexe Pfaddarstellung Ψ) are not required for a first operational controller and remain theory-level for v0.1 runtime.

**Implementiert:**

```
e0_controller/
├── __init__.py        # Package-Exports, Version 0.1.0
├── primitives.py      # Edge (NamedTuple), Outcome (Enum)
├── landscape.py       # L_t = (X, E, v, S, H) — 5 Core Functions
├── historization.py   # U/F-Traces, δ_H, Clipping (§17)
├── tension.py         # S(e), S(p), C(p) (§3, §5, §6)
├── controller.py      # E0Controller: Greedy + Revisit-Penalty + Escalation (§18)
└── test_minidomain.py # 8 States, 10 Edges, 12 Validierungstests
```

**7 Kern-Funktionen (verbindlicher Scope) — alle implementiert und getestet:**

| # | Funktion | Modul | Status |
|---|---|---|---|
| 1 | `difference(x, y)` — Δ zwischen States | `landscape.py` | ✅ |
| 2 | `base_resistance(x, y)` — R₀ aus Landscape | `landscape.py` | ✅ |
| 3 | `effective_resistance(x, y)` — R₀ + δ_H(U,F) | `landscape.py` | ✅ |
| 4 | `effective_tension(x, y)` — S_eff = Δ · R_eff | `landscape.py` | ✅ |
| 5 | `admissible_neighbors(x)` — alle y mit S_eff < ∞ | `landscape.py` | ✅ |
| 6 | `select_next(x)` — Greedy + Revisit-Penalty + Escalation | `controller.py` | ✅ |
| 7 | `update_historization(edge, outcome)` — U/F-Trace Update | `historization.py` | ✅ |

**Test-Ergebnisse (12/12 bestanden):**

| Test | Prüft | Ergebnis |
|---|---|---|
| `test_primitives` | Edge, Outcome Typen | ✅ |
| `test_tension_math` | S=Δ·R, C=exp(-S), Pfadsummation | ✅ |
| `test_historization` | U/F-Traces, δ_H, Clipping | ✅ |
| `test_landscape_core_functions` | Alle 5 Landscape-Funktionen | ✅ |
| `test_landscape_info` | 8 States, 10 Edges, Inspektion | ✅ |
| `test_seven_core_functions` | Alle 7 Funktionen aufrufbar + korrekt | ✅ |
| `test_oscillation_breaking` | A↔C pendelt nicht (Revisit-Penalty) | ✅ |
| `test_dead_end_escalation` | D (Dead-end) → Escalation → weiter | ✅ |
| `test_failure_increases_resistance` | E→F: R steigt nach Failures | ✅ |
| `test_success_decreases_resistance` | E→G: R sinkt nach Successes | ✅ |
| `test_failure_avoidance` | Controller meidet failure-prone E→F | ✅ |
| `test_full_run_to_goal` | Kompletter Lauf A → GOAL | ✅ |

**Mini-Domäne Topologie:**
```
A ──(Δ=0.5/R₀=1.0)──→ B ──(0.3/0.8)──→ E ──(0.2/0.5)──→ G ──(0.1/0.3)──→ GOAL
│                       │                │
├──(0.4/0.8)──→ C       │                └──(0.4/1.2)──→ F ──(0.3/1.0)──→ G
│               │        │
│    (0.4/0.8)←─┘        └──(0.6/1.5)──→ D (Dead-end)
│
└──(0.7/3.0)←─ C→D
```

**Design-Entscheidungen (implementiert):**
- States sind String-IDs (graphen-basiert, nicht vektor-basiert) → domain-invariant
- Δ und R₀ pro Edge gespeichert (nicht pro State-Paar berechnet)
- Historization: ρ=0.9, λ_s=0.15, λ_f=0.20, δ_max=3.0
- Revisit-Penalty: α=2.0, recent_k=3
- Escalation: Δ=1.0, R=max_escalation_R=5.0, Ziel = State mit meisten ausgehenden Kanten
- R_eff hat strukturellen Floor (≥ 1e-10, nie negativ)

**Umfang:** 580 Zeilen Implementierung + 390 Zeilen Tests = ~970 Zeilen gesamt.

**Warum kein Iran-Szenario hier:** Eine offene geopolitische Domäne zieht Δ-Extraktion, State-Modellierung, unscharfe Ziele und LLM-Unsicherheit gleichzeitig hinein. Man testet dann nicht den Controller, sondern alles auf einmal — und weiß bei Scheitern nicht, woran es lag.

---

### Phase 1b: Strukturierte Praxis-Domäne ⬜

**Status:** Nicht begonnen. Voraussetzung: Phase 1a ✅

**Ziel:** Zweite Domäne mit realer Struktur (z.B. Dokumenten-Routing, Rechnungsprüfung, Workflow-Steuerung).

- Deterministische Tools, klare Admissibility, klare Outcomes
- Messbar: deterministische Lösungsrate, Eskalationsrate, Wirkung von δ_H
- Zeigt, dass der Controller über die Test-Domäne hinaus generalisiert

**Offene Frage:** Welche Domäne? Kandidaten:
1. Dokumenten-Routing (States = Bearbeitungsstufen, Edges = Weiterleitungen)
2. Rechnungsprüfung (States = Prüfstatus, Edges = Prüfschritte)
3. Einfacher Workflow-Automat (States = Aufgabenphasen)

---

### Phase 2: Connection & Phase (§9–16) ⬜ ⬜

**Status:** Nicht begonnen. Voraussetzung: Phase 1a ✅ (erfüllt), Phase 1b empfohlen.

**Ziel:** Gradient/Rotation-Zerlegung, ω, Θ, Ψ(p), Pfad-Summation.

```
e0_controller/
├── potential.py       # Φ(x), v_grad, v_rot
├── connection.py      # ω(x→y), Θ(p), Holonomie
├── wavepath.py        # Ψ(p) = exp(-S)·exp(iΘ), Ψ(z) = Σ Ψ(p), I(z)
```

**Geschätzt:** 200–300 Zeilen. Brücke zur Spin-1/2-Derivation.

---

### Phase 3: LLM-Integration (semi-strukturierte Textwelt) ⬜ ⬜

**Status:** Nicht begonnen. Voraussetzung: Phase 1b + Phase 2.

**Ziel:** E₀ Controller als Reasoning-Engine für LLMs.

- Δ-Extraktion: LLM identifiziert States und Differences aus Text
- R-Schätzung: LLM bewertet Resistance qualitativ → Controller normiert
- Controller evaluiert $S_{eff}$, wählt Pfad
- LLM führt den gewählten Pfad aus (generiert Antwort/Analyse)

**Wichtig:** Erst hier kommen offene Domänen (Iran-Analyse, Business Cases) ins Spiel. Vorher wird nicht der Controller, sondern Controller + Parsing + Weltmodellierung + LLM-Unsicherheit gleichzeitig getestet.

---

### Phase 4: Spin-1/2 — Offene Punkte schließen (parallel, nicht blockierend) ⬜ ⬜

**Status:** Nicht begonnen. Parallele theoretische Linie. Nicht in der kritischen Kette.

- ω-Wert aus E₀ herleiten
- Minimalitätsbeweis für 2 Base-States
- Diskret → Kontinuum Grenzwert

---

## 7. Was wir stoppen

Die folgenden Arbeitsstränge aus der vorherigen Phase werden **eingefroren**:

- **Keimzelle Multi-Agent-System** (keimzelle/): Orchestrierung war Sackgasse
- **Diskurs-Modus UI** (keimzelle/ui/): Nicht mehr primärer Fokus
- **Ko-Kognitions-Engine** (keimzelle/rounds.py): Wird nicht weiterverfolgt
- **Phase-basierter Server** (keimzelle/server.py): Pausiert

Der Code bleibt im Repository als Referenz, aber aktive Entwicklung geht in `e0_controller/`.

---

## 8. Kernfrage

> *"E₀ und Ontodynamics wirken wie ein Betriebssystem auf ein LLM."*

Das ist die zentrale Hypothese. Der Controller ist der Versuch, diese Hypothese operativ zu testen:

- Kann ein deterministischer Transition-Loop bessere Reasoning-Ergebnisse liefern als rein probabilistisches Token-Sampling?
- Kann Historization (strukturelles Lernen) Halluzinationen und Regressionen verhindern?
- Ist die Pfad-Summation $\Psi(z) = \sum \Psi(p)$ eine brauchbare Alternative zu Beam Search / Tree of Thought?

Die Antwort kommt nicht aus Theorie, sondern aus **Implementierung und Test**.
