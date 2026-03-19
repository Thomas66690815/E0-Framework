# E₀ Controller — Status, Lücken, Lösungswege

**Stand:** 2026-03-19 (v0.7 — Phase 2a abgeschlossen)
**Kontext:** Neuansatz nach 3 Wochen Pause. Multi-Agent-Orchestrierung (Keimzelle) verworfen.
**Neuer Ansatz:** Einzelner deterministischer E₀ Controller als Reasoning-Engine.

### Aktueller Fortschritt

| Phase | Status | Commit |
|---|---|---|
| **Phase 0** — Dieses Dokument | ✅ Abgeschlossen | `fa278ee` |
| **Phase 1a** — Minimaler Controller + Mini-Domäne | ✅ Abgeschlossen (13/13 Tests) | `8523a9b` |
| **Phase 1a-fix** — K1+K6 Fix, K13 Metriken | ✅ Abgeschlossen | `8eb0e9a` |
| **Phase 1b** — Invoice-Domain (Rechnungsprüfung) | ✅ Abgeschlossen (33/33 Tests) | `cca35bf` |
| **Phase 2-prep** — K3 Fix (difference-Semantik) | ✅ Abgeschlossen | `edcced6` |
| **Phase 2a** — Potential/Connection/WavePath | ✅ Abgeschlossen (56/56 Tests) | — |
| **Phase 2b** — Offene K-Items vor Phase 3 | ⬜ Nicht begonnen | — |
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
| **§9 Φ(x) = Σ Δ·R** | Lokales Potential | `potential.phi()` | ✅ Phase 2a |
| **§10 v_grad = Φ(x)−Φ(y)** | Gradient-Komponente | `potential.v_grad()` | ✅ Phase 2a |
| **§11 v_rot = v − v_grad** | Rotations-Komponente | `potential.v_rot()` | ✅ Phase 2a |
| **§12 ω(x→y) = ½(v_rot,x(y)−v_rot,y(x))** | Connection | `connection.omega()` | ✅ Phase 2a |
| **§13 Θ(p) = Σ ω(e)** | Pfad-Phase | `connection.theta()` | ✅ Phase 2a |
| **§14 Holonomie Θ(γ)** | Geschlossene Schleifen | `connection.holonomy()` | ✅ Phase 2a |
| **§15 Ψ(p) = exp(−S)·exp(iΘ)** | Komplexe Pfad-Darstellung | `wavepath.psi()` | ✅ Phase 2a |
| **§16 Ψ(z) = Σ Ψ(p)** | Pfad-Summation (Interferenz) | `wavepath.sum_paths()` | ✅ Phase 2a |
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

### Phase 1a — Selbstkritik (v0.3, 2026-03-19)

Die folgenden Punkte sind **bekannte Schwächen** der aktuellen Implementierung. Jeder Punkt ist bewertet nach Dringlichkeit (🔴 muss vor Phase 1b, 🟡 sollte vor Phase 2, ⚪ kann warten) und enthält einen konkreten Lösungsvorschlag.

#### K1 — Escalation mutiert die Landscape 🔴

**Problem:** `controller.py:select_next()` ruft `landscape.add_edge()` auf, wenn kein admissible neighbor existiert. Die Entscheidungslogik verändert permanent die Datenstruktur. Escalation-Edges akkumulieren sich und werden nie aufgeräumt. Das vermischt Controller-Logik mit Landscape-Mutation.

**Warum schlimm:** Nach N Escalations ist die Landscape nicht mehr die ursprüngliche Domäne. Analyse, Reproduzierbarkeit und Snapshot/Restore werden unmöglich.

**Lösung:** Escalation-Edges in separater Struktur (`_escalation_edges: Dict[Edge, float]`) im Controller halten. Die Landscape bleibt unveränderlich. Bei `effective_tension()` prüft der Controller beide — reale Edges + Escalation-Edges. Escalation-Edges können ablaufen (TTL) oder bei erfolgreicher Transition bestätigt werden.

#### K2 — Decay ist nur lokal, nicht global (Spec-Abweichung) 🟡

**Problem:** `historization.py:update()` decayed nur die betroffene Edge. Spec §17.1: $U_t(e) = \rho \cdot U_{t-1}(e) + \mathbb{1}_{success}$ — das ρ gilt für **alle** Edges bei **jedem** Zeitschritt. Eine Edge, die 100 Steps nicht benutzt wurde, behält ewig ihre alten U/F-Werte.

**Warum schlimm:** Uralte Traces verzerren R_eff. Eine vor 50 Steps gescheiterte Edge wird nie vergessen, selbst wenn die Spec genau das durch Decay vorsieht.

**Lösung A (exakt):** `decay_all()` Methode, die bei jedem τ alle bekannten Edges decayed. O(|E|) pro Step.
**Lösung B (lazy, effizient):** Beim Lesen eines Trace den Decay nachträglich berechnen: $U_{eff}(e) = U_{stored}(e) \cdot \rho^{(\tau - \tau_{last}(e))}$. O(1) pro Abfrage, kein globaler Sweep.

**Empfehlung:** Lösung B — lazy Decay. Speichere pro Edge den letzten Update-Zeitpunkt `_tau_last[edge]`, berechne Decay bei Abfrage.

#### K3 — `difference()` = 0.0 für nicht-existierende Edges 🟡

**Problem:** `landscape.py:difference()` gibt 0.0 zurück wenn keine Edge existiert. Das bedeutet semantisch "kein Unterschied zwischen den States", nicht "keine Transition definiert". Die korrekte Semantik wäre: keine Edge → kein Δ → Transition ist nicht definiert.

**Warum schlimm:** Δ=0 und R=∞ ergibt S = 0·∞ — mathematisch undefiniert. Unsere `tension()` rettet das durch `if isinf(R): return inf`, aber das ist ein Workaround, nicht korrekte Semantik.

**Lösung:** `difference()` sollte `None` oder `math.nan` zurückgeben für nicht-existierende Edges. Alternativ: gar nicht abfragbar — `KeyError` werfen. Entscheidung hängt davon ab, ob Clients gegen beliebige (x,y)-Paare fragen können sollen.

**Empfehlung:** Optional[float] Return-Type mit `None` für nicht-existierende Edges. `effective_tension()` prüft auf `None` und gibt `inf` zurück.

#### K4 — PARTIAL-Gewichte sind willkürlich und hardcoded ⚪

**Problem:** `historization.py:update()` setzt PARTIAL → U+=0.5, F+=0.3. Diese Werte kommen nicht aus der Spec (§17 definiert nur SUCCESS/FAILURE).

**Warum akzeptabel für v0.1:** PARTIAL war eine bewusste Erweiterung über die Spec hinaus. Die Werte sind arbiträr, aber PARTIAL wird nur in `mixed_outcomes()` im Test verwendet. Kein Real-System nutzt es noch.

**Lösung:** Parameter `partial_u: float = 0.5` und `partial_f: float = 0.3` in `Historization.__init__()`.

#### K5 — Escalation-Ziel ist Heuristik, nicht E₀-Prinzip 🟡

**Problem:** `controller.py:select_next()` wählt bei Escalation den State mit den meisten ausgehenden Kanten. Das ist eine Konnektivitäts-Heuristik — nicht abgeleitet aus Δ, R, S oder C.

**Warum schlimm:** Es widerspricht dem Anspruch, dass der Controller **ausschließlich** nach E₀-Prinzipien operiert. Die Escalation ist der einzige Punkt, wo das Prinzip gebrochen wird.

**Lösung:** Escalation-Ziel über Coherence wählen: $y^* = \arg\max_y \sum_{z} C(y \to z)$ — der State mit dem höchsten Gesamtkohärenz-Ausstoß. Das ist E₀-nativ.

#### K6 — `candidates` im StepResult wird NACH dem Step berechnet ⚪

**Problem:** `controller.py:cycle()` berechnet `admissible_neighbors(current)` **nach** dem Historization-Update. Das zeigt den Zustand nach der Entscheidung, nicht bei der Entscheidung.

**Lösung:** `candidates` vor dem Execute-Schritt erfassen.

#### K7 — Revisit-Penalty ist additiv, skaliert nicht 🟡

**Problem:** $S_{revisit} = S_{eff} + \alpha$. Bei Edges mit hohem S_eff (z.B. 5.0) ist α=2.0 kaum relevant (5.0 → 7.0). Bei Edges mit niedrigem S_eff (z.B. 0.1) dominiert es komplett (0.1 → 2.1).

**Lösung A:** Multiplikativ: $S_{revisit} = S_{eff} \cdot (1 + \alpha)$
**Lösung B:** Hybrid: $S_{revisit} = S_{eff} + \alpha \cdot S_{eff} = S_{eff} \cdot (1 + \alpha)$ — gleich wie A.
**Lösung C:** Skaliert additiv: $S_{revisit} = S_{eff} + \alpha \cdot \bar{S}$ mit $\bar{S}$ = mittlere Tension der Nachbarn.

**Empfehlung:** Lösung A (multiplikativ) — einfach, proportional, keine neuen Parameter.

#### K8 — Test-Domain ist zu gutartig ⚪

**Problem:** Die Mini-Domain wurde für Erfolg konstruiert. Es gibt keinen Test für:
- Adversarial: alle Pfade scheitern
- Parameter-Sensitivität: was passiert bei α=0 oder α=100?
- Konvergenz: stabilisiert sich R_eff?
- Scale: >100 States

**Lösung:** Eigene `test_adversarial.py` in Phase 1b. Kein Blocker für jetzt.

#### K9 — Kein Konvergenz-Kriterium ⚪

**Problem:** Nur `goal`, `max_cycles` oder total dead-end als Stopp. Kein Signal für "System hat sich stabilisiert — weitere Cycles ändern nichts mehr".

**Lösung:** Konvergenz-Check: $|\Delta R_{eff}| < \epsilon$ über letzte k Steps. Einfach, O(1) pro Step.

#### K10 — Kein Callback/Hook-Mechanismus ⚪

**Problem:** `run()` läuft blind durch. Kein Weg für Step-Logging, externe Steuerung, oder Visualisierung.

**Lösung:** `on_step: Optional[Callable[[StepResult], None]]` Parameter in `run()`.

---

#### Zusammenfassung Kritik

| # | Problem | Dringlichkeit | Fix-Aufwand |
|---|---|---|---|
| K1 | Escalation mutiert Landscape | 🔴 Vor Phase 1b | ~30 Zeilen |
| K2 | Decay nicht global | 🟡 Vor Phase 2 | ~20 Zeilen |
| K3 | difference()=0 statt None | 🟡 Vor Phase 2 | ~15 Zeilen |
| K4 | PARTIAL hardcoded | ⚪ Irgendwann | ~5 Zeilen |
| K5 | Escalation-Ziel ad-hoc | 🟡 Vor Phase 2 | ~15 Zeilen |
| K6 | candidates timing | ⚪ Irgendwann | ~3 Zeilen |
| K7 | Penalty skaliert nicht | 🟡 Vor Phase 2 | ~5 Zeilen |
| K8 | Tests zu gutartig | ⚪ Phase 1b | eigenes File |
| K9 | Keine Konvergenz | ⚪ Phase 2 | ~10 Zeilen |
| K10 | Kein Callback | ⚪ Phase 1b | ~5 Zeilen |

**Handlungsplan:** K1 wird vor Phase 1b gefixt (Architektur-Fehler). K2, K3, K5, K7 werden als Batch vor Phase 2 adressiert. K4, K6, K8–K10 laufen mit und werden bei Bedarf erledigt.

---

### Phase 1a — Externe Kritik (ChatGPT-Review, 2026-03-19)

**Gesamturteil (extern):** *"Das ist ein ernstzunehmender erster E₀-Controller, weil er Historisierung, Spannung, Landscape und deterministische Pfadwahl bereits in eine kleine, testbare operative Form gebracht hat."*

**Bestätigt (kein Neubau nötig):**
- Modulstruktur primitives/historization/landscape/tension/controller ist richtig
- Historisierung ist **echt** (U/F-Traces mit Decay, nicht Fake-Memory)
- Landscape als explizites Objekt ist zentral — Controller "schwebt nicht mehr frei"
- Revisit-Penalty ist sinnvolle v0.1-Erweiterung
- Mini-Domain ist strategisch die richtige Entscheidung
- $R_{eff} = R_0 + \delta_H$ → $S_{eff} = \Delta \cdot R_{eff}$ stimmt mit der Theorie überein
- Audit Trail (TraceRecord, StepResult, RunTrace) ist wertvoll

**Überlappung mit eigener Kritik (K1–K10):**

| Externer Punkt | Unser Match | Deckung |
|---|---|---|
| `difference()` = 0.0 problematisch | K3 | ✅ Identisch |
| Escalation erzeugt neue Kanten | K1 | ✅ Identisch (wir gehen weiter: Architektur-Fix) |
| PARTIAL ist ad hoc | K4 | ✅ Identisch |
| Revisit auf Zielzuständen, nicht Pfadmustern | K7 | ✅ Verwandt |

**Neue Punkte aus externer Kritik:**

#### K11 — `admissible_neighbors()` ist zu flach 🟡

**Problem:** Admissibility = "Edge existiert und S_eff < ∞". Das ist fast identisch mit "edge exists". E₀-Theorie kennt reichere Admissibility: Policy blocks, hard constraints, context conditions, Ziel-Kompatibilität.

**Für v0.1 tolerierbar.** Aber für Phase 1b braucht eine echte Domäne echte Admissibility-Filter.

**Lösung:** `AdmissibilityFilter` als Callable/Protocol in Landscape. Default = `S_eff < ∞`. Erweiterbar pro Domäne.

#### K12 — Escalation-Typen nicht getrennt 🟡

**Problem:** "Escalation" vermischt drei verschiedene Konzepte:
1. **Terminal Escalation** — Mensch/externes System übernimmt
2. **Recovery Jump** — interner Struktur-Sprung (was wir jetzt tun)
3. **External Review** — Prüfung, ob der Pfad noch sinnvoll ist

Der Code nennt alles "escalated=True", aber es ist nur ein Recovery Jump.

**Lösung:** Enum `EscalationType(RECOVERY_JUMP, TERMINAL, EXTERNAL_REVIEW)` statt `bool`. Für v0.1: klar dokumentieren, dass die aktuelle Escalation ein "bounded structural jump by inserting a high-tension emergency edge" ist — nicht mehr.

#### K13 — Keine operativen Metriken 🟡

**Problem:** Es gibt Tests (pass/fail), aber keine zusammenfassenden Metriken. Für Phase 1b brauchen wir:
- `deterministic_rate` — Anteil nicht-eskalierter Entscheidungen
- `escalation_count` — wie oft wurde eskaliert
- `revisit_penalties_triggered` — wie oft griff die Penalty
- `average_delta_H` — mittlere Historisierungs-Korrektur
- `average_R_eff_shift` — wie stark verändert sich R_eff

**Lösung:** `RunTrace.metrics()` Methode, die diese Werte aus den bestehenden `StepResult`-Daten aggregiert. ~20 Zeilen.

#### Doku-Punkt: `transition_field()` mit $M_H = 1$ expliziter benennen

**Problem:** Nicht falsch, aber im Code steht "(M_H = 1 for v0.1)" als Kommentar. Das sollte auch im STATUS.md unter "Vereinfachungen" erscheinen.

**Status:** Die aktuelle Implementierung berechnet $v_x(y) = \Delta(x,y) \cdot \exp(-S_{eff})$. Die volle Spec §2.4 definiert $v_x(y) = \Delta \cdot M_H \cdot \exp(-S)$ mit Modulationsfaktor $M_H$. $M_H = 1$ ist die bewusste v0.1-Vereinfachung.

---

#### Aktualisierte Zusammenfassung (K1–K13)

| # | Problem | Quelle | Dringlichkeit | Fix-Aufwand |
|---|---|---|---|---|
| K1 | Escalation mutiert Landscape | Eigen | ✅ Gefixt (`8eb0e9a`) | ~30 Zeilen |
| K2 | Decay nicht global | Eigen | 🟡 Vor Phase 2 | ~20 Zeilen |
| K3 | difference()=0 statt None | Eigen + Extern | ✅ Gefixt (`edcced6`) | ~15 Zeilen |
| K4 | PARTIAL hardcoded | Eigen + Extern | ⚪ Irgendwann | ~5 Zeilen |
| K5 | Escalation-Ziel ad-hoc | Eigen | 🟡 Vor Phase 2 | ~15 Zeilen |
| K6 | candidates timing | Eigen | ✅ Gefixt (`8eb0e9a`) | ~3 Zeilen |
| K7 | Penalty skaliert nicht | Eigen + Extern | 🟡 Vor Phase 2 | ~5 Zeilen |
| K8 | Tests zu gutartig | Eigen | ✅ Adressiert (Phase 1b) | eigenes File |
| K9 | Keine Konvergenz | Eigen | ⚪ Phase 2 | ~10 Zeilen |
| K10 | Kein Callback | Eigen | ⚪ Phase 1b | ~5 Zeilen |
| K11 | Admissibility zu flach | Extern | 🟡 Phase 2 | ~20 Zeilen |
| K12 | Escalation-Typen vermischt | Extern | 🟡 Phase 2 | ~15 Zeilen |
| K13 | Keine operativen Metriken | Extern | ✅ Gefixt (Phase 1b) | ~20 Zeilen |

**Aktualisierter Handlungsplan:**
- **✅ Erledigt:** K1 (Escalation-Buffer), K3 (difference-Semantik), K6 (candidates-timing), K8 (Invoice-Domain), K13 (Metriken)
- **🟡 Phase 2b (Pflicht vor Phase 3):** K2 (lazy Decay), K5 (Escalation-Ziel), K7 (Penalty), K11 (Admissibility-Filter), K12 (Escalation-Typen)
- **⚪ Bei Bedarf:** K4, K9, K10

---

### Phase 1b: Invoice-Domain (Rechnungsprüfung) ✅

**Status:** Abgeschlossen am 2026-03-19. **33/33 Tests bestanden.** Gesamt mit 1a: **46/46.**

**Ziel:** Zweite, realistische Domäne — zeigt, dass der Controller über die Mini-Domäne hinaus generalisiert.

**Domäne:** Rechnungsprüfung / Dokumentenrouting (Empfehlung ChatGPT-Review: prüfbar, operativ, kein Theory-Creep).

**Implementiert:**

```
e0_controller/
├── domain_invoice.py  # 10 States, 16 Edges, 5 Outcome-Szenarien
├── test_invoice.py    # 33 Tests in 11 Test-Klassen
└── controller.py      # + RunTrace.metrics() (K13)
```

**Topologie (10 States, 16 Edges):**
```
RECEIVED → PDF_LOADED → DATA_EXTRACTED → CUSTOMER_FOUND → AMOUNT_OK
               │              │                │               │
               ↓              ↓                ↓               ↓
           REJECTED      HUMAN_REVIEW    HUMAN_REVIEW       REJECTED
                              │
                         CUSTOMER_FOUND / DATA_EXTRACTED / REJECTED

AMOUNT_OK → CONTRACT_MATCH → POLICY_OK → APPROVED
                  │              │
             HUMAN_REVIEW    REJECTED
```

**Kanten-Eigenschaften:**
- Happy Path: 7 Kanten, niedrige Tension (S₀ = 0.02–0.60)
- Fehler-Pfade: 6 Kanten zu REJECTED/HUMAN_REVIEW (höhere Tension)
- Recovery: 3 Kanten aus HUMAN_REVIEW (hohe R₀, aber erreichbar)
- Dead-Ends: REJECTED, APPROVED (keine Ausgangskanten)

**Outcome-Szenarien:**
- `happy_path` — Alles SUCCESS (Baseline)
- `realistic_outcomes` — DATA_EXTRACTED→CUSTOMER_FOUND scheitert immer
- `harsh_outcomes` — Mehrere Failure-Kanten
- `learning_scenario` — Erste N Versuche scheitern, dann SUCCESS (Lernfähigkeit)

**Test-Ergebnisse (33/33 bestanden):**

| Klasse | Tests | Prüft |
|---|---|---|
| TestInvoiceLandscape | 6 | Struktur: 10 States, 16 Edges, Dead-ends, Recovery |
| TestHappyPath | 4 | Happy Path: APPROVED, ≤8 Steps, keine Escalation, 100% SUCCESS |
| TestRealisticOutcomes | 3 | Failures, Historisierung lernt (R_eff steigt) |
| TestHarshOutcomes | 2 | Controller navigiert trotz vieler Fehler |
| TestLearningScenario | 2 | R_eff steigt bei Failures, Lernen funktioniert |
| TestEscalation | 2 | Dead-end → sofortige Escalation, Ziel hat Ausgangskanten |
| TestLandscapeInvariance | 2 | K1-Beweis: Δ und R₀ bleiben nach Run unverändert |
| TestMetrics | 6 | K13: 9 Metriken korrekt, alle Schlüssel, Edge Cases |
| TestMultipleRuns | 1 | Shared Historization: Run 2 profitiert von Run 1 |
| TestHumanReviewRecovery | 2 | Start bei HUMAN_REVIEW → APPROVED erreichbar |
| TestEdgeCases | 3 | Start=Goal, max_cycles, frische Landscape |

**K13 Metriken (implementiert in RunTrace.metrics()):**
- `steps` — Anzahl Schritte
- `deterministic_rate` — Anteil nicht-eskalierter Entscheidungen
- `escalation_count` — Escalation-Häufigkeit
- `success_rate` / `failure_rate` — Outcome-Verteilung
- `avg_tension` — Mittlere Tension (nur endliche)
- `avg_r_eff_shift` — Mittlere R_eff-Veränderung pro Step
- `revisit_count` — Wiederholte State-Besuche
- `unique_states` — Verschiedene besuchte States

**Fixes in Phase 1b:**
- ✅ K1 (bereits in `8eb0e9a`): Escalation mutiert Landscape nicht mehr
- ✅ K6 (bereits in `8eb0e9a`): candidates vor Execute erfasst
- ✅ K13: `RunTrace.metrics()` mit 9 operativen Metriken

**Umfang:** domain_invoice.py ~180 Zeilen + test_invoice.py ~310 Zeilen = ~490 Zeilen neu.

---

### Phase 2-prep: K3 Fix ✅

**Status:** Abgeschlossen. Commit `edcced6`.

`difference()` liefert jetzt `None` für fehlende Kanten (vorher `0.0`).
Semantik korrekt getrennt: `None` = keine Transition, `0.0` = identische States.
Pflicht vor Phase 2, weil Φ(x) auf korrekter Δ-Semantik basiert.

---

### Phase 2a: Potential / Connection / Wave Path ✅

**Status:** Abgeschlossen am 2026-03-19. **56/56 Tests bestanden.** Gesamt: **102/102.**

**Ziel:** Diskrete Phase-/Connection-Schicht als prüfbare Erweiterung der Landscape. Kein Controller-Umbau, kein LLM, keine neue Domäne.

**Implementiert:**

```
e0_controller/
├── potential.py              # §9-11: Φ(x), v_grad, v_rot
├── connection.py             # §12-14: ω(x,y), θ(path), holonomy(cycle)
├── wavepath.py               # §15-16: Ψ(p), sum_paths, intensity
├── test_phase2_minidomain.py # 38 Tests (primäre Validierung)
├── test_phase2_invoice.py    # 18 Tests (Sekundärvalidierung)
└── __init__.py               # v0.2.0, neue Exports
```

**Mathematische Konventionen (explizit dokumentiert):**

1. **Φ(x) = Σ Δ·R_eff** — Spec §9 Definition (lokale Summation, nicht Graph-Laplacian).
   - Dead-ends: Φ = 0 (keine Ausgangskanten).
   - Heuristische Potenzialnäherung. Echte Helmholtz-Zerlegung als spätere Option dokumentiert.

2. **v = v_grad + v_rot** — v_grad(x,y) = Φ(x) − Φ(y), v_rot = v − v_grad.
   - v_grad ist antisymmetrisch: v_grad(x,y) = −v_grad(y,x).
   - v_rot ist nur für existierende Kanten definiert (None für fehlende).

3. **ω auf gerichteten Kanten** — Fehlende Rückkante → v_rot(y,x) = 0.
   - ω(x,y) = ½·(v_rot(x,y) − v_rot(y,x)), Konvention: v_rot = 0 für Nicht-Kante.
   - Antisymmetrie: ω(x,y) = −ω(y,x) gilt konstruktionsbedingt für alle Paare.
   - 2-Kanten-Zyklen (hin und zurück) haben Holonomie = 0 (aus Antisymmetrie).
   - 3+-Kanten-Zyklen können nichttriviale Holonomie tragen.

4. **Ψ(p) = exp(−S + iΘ)** — Bounded explicit path sets, keine automatische Enumeration.
   - |Ψ| = exp(−S) = Kohärenz des Pfads.
   - arg(Ψ) = Θ = akkumulierte Connection-Phase.
   - Inadmissible paths: Ψ = 0.

**Test-Ergebnisse:**

| Test-Datei | Tests | Prüft |
|---|---|---|
| test_phase2_minidomain.py | 38 | Φ, Zerlegung, ω-Antisymmetrie, Holonomie, Ψ, Interferenz, Historisierungs-Effekte |
| test_phase2_invoice.py | 18 | Konsistenz auf Invoice-Domain, schwache Holonomie, Pfad-Vergleich |

**Erfolgskriterien (alle erfüllt):**

| Kriterium | Status |
|---|---|
| Φ(x) ist für alle States berechenbar | ✅ |
| v_grad und v_rot sind konsistent getrennt | ✅ |
| ω(x,y) = −ω(y,x) gilt | ✅ |
| Geschlossene Zyklen können nichttriviale Holonomie tragen | ✅ |
| Ψ(path) ist berechenbar | ✅ |
| Intensitäten ändern sich sinnvoll bei Pfadphasen | ✅ |

**Erwartetes Ergebnis bestätigt:** Invoice-Domain zeigt schwache Holonomie (fast DAG), Mini-Domain zeigt interessantere Phase-Struktur.

---

### Phase 2b: Offene K-Items vor Phase 3 ⬜

**Status:** Nicht begonnen. Pflicht vor Phase 3.

Offene Items:
- K2: Global/lazy Decay
- K5: Escalation-Ziel nicht nur ad-hoc
- K7: Revisit-Penalty-Skalierung
- K11: Echte Admissibility-Schicht
- K12: Escalation-Typen trennen

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
