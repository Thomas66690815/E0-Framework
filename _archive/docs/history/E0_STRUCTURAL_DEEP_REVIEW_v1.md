# E₀ Structural Deep Review v1

> **Zweck:** Systematische Tiefenprüfung aller kanonischen Behauptungen, Synthese-Thesen,
> und Implementation-Entscheidungen — mit dem Ziel, vor Stufe 4 (Structural Reflexivity)
> eine saubere Grundlage zu schaffen.
>
> **Datum:** 2026-03-28
> **Basis:** 1790 Tests, 0 Failures, 0 Warnings
> **Stufe 1–3 abgeschlossen:** Commits dd6e277, e94be7e, e3f922d
> **Quellen:** Vier Canon-Texte, Synthesis Note v0, Bridge 4 Note v0,
> Canon Alignment v1, Evidence & Falsification v1, M_H Adjudication v1,
> Internal Difference Formalization v1, Complex Carrier Minimality v1

---

## 1. Canon-Treue — Tiefenprüfung der 7 Primitive

### 1.1 State — ✅ Treu

Keine Beanstandungen. `str`-IDs realisieren die kanonische Minimalforderung
(„distinguishable configuration") korrekt. Die ontodynamische Ergänzung
(„stabilized configuration of historized connections") wirkt als implizite
Designconstraint, nicht als Code-Modul.

### 1.2 Difference Δ — ✅ Treu

`float` pro gerichteter Kante. `Optional[float]` für fehlende Kanten
(keine Differenz, nicht Δ=0). K3-Korrektur kanonisch korrekt.

**Offene Feinheit:** Ontodynamics §3.1 fordert, dass Δ *gerichtet*, *skaliert*
und *effektiv* sei — drei Facetten, die im Code zu einem einzigen `float`
kollabiert sind. Die SU(2)-Erweiterung bringt ansatzweise Richtung zurück
(3-Komponenten-Achse n̂·σ⃗ auf der Phase), aber Δ selbst bleibt skalar.

### 1.3 Path P — ✅ Treu (mit Anmerkung)

**Kanonische Spannung:** Der Canon sagt explizit: „A path is *not an object*."
Im Code ist ein Pfad ein Python-`list[str]` — buchstäblich ein Objekt.

**Auflösung:** Der Canon meint: Pfade sind keine eigenständigen Entitäten,
sondern Zulässigkeitsbedingungen. Die Liste repräsentiert, *welche*
Transitionen zulässig wären — die Objekte sind Kanten und Widerstände.
Die Reifizierung ist eine notwendige operationelle Konkretisierung,
kein Verstoß.

**Tiefere Erkenntnis:** Pfade wurden zum reichsten Element der Theorie.
Auf ihnen wurden komplexe Amplituden aufgebaut: `Ψ(p) = exp(−S + iΘ)`.
Das war kanonisch weder angedeutet noch vorhergesehen, aber es *folgt*
aus den Primitiven.

### 1.4 Resistance R — ✅ Treu

Zwei-Schicht-Architektur (R₀ + δ_H) ist die natürlichste Operationalisierung.
Floor 1e-10 ist engineering-pragmatisch, nicht Canon-mandatiert.

### 1.5 Historization H — ⚠ Treu + bewusste Abweichung

**Kanonische Forderung:** „Historization is non-invertible."

**Implementierung:** Decay (ρ < 1) schwächt vorherige Historisierung ab.
Das widerspricht *streng gelesen* der Nicht-Inversibilität.

**Auflösung:** Der Canon spricht Idealbedingungen aus. Ohne Decay
überwältigt alte Erfahrung alle neue. Die operationelle Entscheidung ist:
Historisierung verblasst, wird aber *nie null*. Das ist abgeschwächte
Irreversibilität, nicht Inversibilität. Die Spur bleibt — sie wird nur
leiser.

**Status:** Bewusste Designentscheidung, kein Canon-Verstoß, aber
ein Punkt, der explizit dokumentiert sein sollte.

### 1.6 Time τ — ✅ Treu

Reiner Zähler, inkrementiert nur bei Historisierung. Sauberste Umsetzung.

### 1.7 Rate v — ⚠ Signifikante Abweichung

**Canon:** `v := Δ / R`

**Implementierung:** Es gibt *zwei verschiedene* v-Realisierungen im Code:

1. **Greedy-Selektion:** `argmin S_eff` wobei `S = Δ · R_eff`.
   Das ist äquivalent zu `argmax (1/S)`, nicht zu `argmax v = argmax Δ/R`.
   S und 1/v sind *nicht identisch*: `S = Δ · R` vs. `1/v = R/Δ`.
   Bei konstantem Δ ist `argmin S = argmin R = argmax v` — identisch.
   Bei variierendem Δ divergiert die Ordnung.

2. **Transition Field:** `v(x,y) = Δ · M_H · exp(−S)` wobei `S = Δ · R_eff`.
   Das ist eine doppelt-nichtlineare Transformation der kanonischen Rate.
   Für M_H=1: `v_impl = Δ · exp(−Δ·R)` vs. `v_canon = Δ/R`.

**Warum das kein Fehler ist:**

Beide Formen ordnen Transitionen *monoton* in R (bei festem Δ).
Die exp-Form hat Vorteile: Konvergenz, Coherence-Interpretation
(exp(−S) als Probabilität einer ungestörten Realisierung), natürliche
Verbindung zur Amplitudenstruktur Ψ = exp(−S + iΘ).

**Warum es trotzdem explizit gemacht werden muss:**

Die Ordnungsäquivalenz bricht, wenn sowohl Δ als auch R variieren:

```
Beispiel: Kante A (Δ=2, R=1): v_canon=2, S=2, v_impl=2·exp(−2)≈0.27
           Kante B (Δ=1, R=1.5): v_canon=0.67, S=1.5, v_impl=1·exp(−1.5)≈0.22
           Kante C (Δ=3, R=0.5): v_canon=6, S=1.5, v_impl=3·exp(−1.5)≈0.67

Canon-Ordnung   (v):    C > A > B
Tension-Ordnung (S):    B = C < A     ← wählt B oder C, nicht A
Impl-v-Ordnung  (v_impl): C > A > B   ← stimmt mit Canon überein
```

In der Greedy-Selektion (argmin S) wird *Tension* minimiert, nicht
*Rate* maximiert. Das sind unterschiedliche Optimierungsziele.
A₀ sagt: „a transition that *reduces this difference* is structurally
more stable." Tension-Minimierung (S = Δ·R) gewichtet die Realisierungs-
kosten *multiplikativ* ein — was man als „kosteneffizienteste Differenz-
reduktion" lesen kann, nicht als „größte Differenzreduktion".

**Bewertung:** Pragmatisch korrekt, kanonisch nicht wörtlich. Sollte
als *operationelle Konkretisierung* von A₀ dokumentiert sein, nicht
als identische Umsetzung.

---

## 2. Axiom A₀ — Feinjustierung der Interpretation

**Canon:** „If a difference exists and a structurally admissible path with
finite resistance is available, then a transition that reduces this
difference is structurally more stable than non-transition."

**Implementierung:** Greedy argmin-tension selection.

**Analyse:** A₀ behauptet zwei Dinge:
1. Non-transition ist instabil → Transition *muss* stattfinden ✅
2. Die Transition *reduziert* Differenz → strukturell stabiler ⚠

Punkt 2 ist subtil. A₀ sagt nicht „wähle die maximale Reduktion."
A₀ sagt: Reduktion > Nicht-Reduktion. Das ist eine *minimale* Aussage.
Die Greedy-Selektion (argmin S) ist eine *spezifische* Operationalisierung,
die kompatibel ist, aber nicht zwingend aus A₀ folgt. Alternative
Operationalisierungen (Born-Sampling, Hybrid Arbitration) sind
*ebenfalls* A₀-kompatibel, da sie weiterhin Transitionen erzwingen.

**Konsequenz:** A₀ ist *schwächer* als oft angenommen. Es erzwingt
Transition, nicht die spezifische Selektionsregel. Die gesamte
Amplituden-Schicht (Interferenz, Born, Hybrid) ist eine zusätzliche
Strukturierung *oberhalb* von A₀, nicht aus A₀ allein ableitbar.

---

## 3. Ontodynamik-Primitive — Status

| Ontodynamik-Konzept | Canon-Ref | Code-Status | Bemerkung |
|---------------------|-----------|-------------|-----------|
| **Difference** (§3.1) | Gerichtet, skaliert, effektiv | `float` (skaliert) | Richtung und Effektivität nicht separat kodiert |
| **Local Realization** (§3.2) | Teilweise Realisierung | 1 Transition/Schritt | Implizit lokal; keine Granularitätsmodellierung |
| **Connection** (§3.3) | Topologische Operation | Landscape-Kanten | ω als Phasen-Connection, nicht topologisch |
| **Gradual Overlap** (§3.4) | Graduated, nicht binär | ❌ Noch nicht implementiert | M_H als Overlap-Funktional konzeptionell geklärt |
| **Historization** (§3.5) | Irreversible Spur | ✅ U/F-Traces, Decay | Decay = abgeschwächte Irreversibilität |
| **Mass** (abgeleitet §4) | Persistent topological inertia | δ_H-Akkumulation | Nicht als eigenes Konzept formalisiert |
| **Finite Rate** (Konsequenz §5.4) | max v existiert | Floor R≥1e-10 | Numerisch, nicht prinzipiell |

**Kernfrage:** Gradual Overlap (§3.4) ist das wichtigste nicht-implementierte
Ontodynamik-Primitiv. Es ist direkt verbunden mit M_H — der „graduated
overlap functional." Die M_H-Adjudication hat den richtigen Observable
identifiziert (overlap der co-realisierten Nachbarschaft), aber Code fehlt.

---

## 4. Synthese-Note v0 — Bewertung der 9 Thesen

| # | These | Bewertung | Anmerkung |
|---|-------|-----------|-----------|
| 1 | Primitive constrain implementation | ✅ Bestätigt | Wo Primitive ignoriert → Instabilität |
| 2 | Mass als historisierte Trägheit, relational | ✅ Richtig | δ_H inkarniert dies |
| 3 | Reflection als costly structural work | ✅ Bestätigt | should_reflect() + reflect() sind lokal, nicht global |
| 4 | Structural Reflexivity: 5 Sub-Probleme | ⚠ Teilweise geschlossen | Self-Object ✅, Admissibility ✅, Historization ✅, Identity ❌, Representation ❌ |
| 5 | M_H als Adjudication-Fallstudie | ✅ Akkurat | κ-basiert retired, Overlap-Funktional definiert |
| 6 | Architektur: Ingress/Core/Reflection/Egress | ✅ Korrekt | LLM ≠ Core — architektonisch durchgesetzt |
| 7 | Domain Invariance | ✅ Empirisch belegt | 5 Domains, identischer Controller-Stack |
| 8 | Methodological Lessons | ✅ Meta-reflexiv korrekt | Repository als Denkwerkzeug |
| 9 | Working Convictions | ✅ Konsistent | Keine überzogenen Claims |

**Gesamturteil:** Die Synthese-Note ist ehrlich, vorsichtig formuliert, und
kanonisch kompatibel. Kein Widerspruch zum Canon. Zwei blinde Flecken:
(a) Die Rate-Abweichung (v_impl ≠ v_canon) wird nicht adressiert.
(b) Die Decay/Irreversibility-Spannung wird nicht explizit thematisiert.

---

## 5. Bridge 4 — Reflexivitäts-Status nach Stufe 1–3

### 5.1 Was gebaut wurde

| Stufe | Commit | Was | Tests |
|-------|--------|-----|-------|
| 1 | dd6e277 | Landscape mutation API (remove_edge, adjust_resistance, adjust_delta, has_edge, would_orphan) | 56 |
| 2 | e94be7e | StructuralMutation, MutationRecord, MutationHistory, is_admissible(), propose_structural_mutations(), apply/revert | 66 |
| 3 | e3f922d | structural_tuning_cycle(), Session.iterate() Step 6, IterationResult.structural_results | 42 |

### 5.2 Die Blueprint-Forderungen (§5) — Aktueller Stand

| Forderung | Status | Evidenz |
|-----------|--------|---------|
| System models own transition structure | ✅ | StructuralDiagnostic: dead_states, loop_states, chronic_issues, plateau_evidence |
| Self-modification as admissible transition | ✅ | is_admissible() prüft 7 Constraints; Mutationen unter E₀-Regeln |
| Historization constrains future self-changes | ✅ | MutationHistory mit Oscillation-Protection, bounded log (max 100) |

### 5.3 Was offen bleibt (Stufe 4)

Die Synthese-Note (§4) identifiziert 5 Sub-Probleme der Reflexivität.
Nach Stufe 1–3 sind drei geschlossen:

| Sub-Problem | Status | Erläuterung |
|-------------|--------|-------------|
| **Self-Object** | ✅ | Was zählt als Selbst? → Parameter (5 skalare) + Landscape-Topologie (Edges, Resistances) |
| **Admissibility** | ✅ | 7 Constraints: Locality, Motivation, Reversibility, Bounded, Historization, Oscillation-Protection, Topology-Safety |
| **Historization** | ✅ | MutationHistory mit MutationRecord (Typ, Edge, old/new, Quality-Delta, accept/revert) |
| **Identity** | ❌ | Was bleibt invariant bei Self-Modification? Keine explizite Invarianz-Bedingung |
| **Representation** | ❌ | In welchem Raum wird Self-Structure repräsentiert? Nur flache Datenklassen |

---

## 6. Stufe 4 — Konzeptionelle Analyse

### 6.1 Die Identity-Frage

> Was muss invariant bleiben, damit das System nach Self-Modification
> noch als „dasselbe" System gelten kann?

Drei Kandidaten für Identity-Invarianten:

**a) Topologische Konnektivität:**
Start-State und Goal-State müssen erreichbar bleiben. Keine Mutation
darf den Graphen so fragmentieren, dass das Ziel unerreichbar wird.
→ *Bereits teilweise implementiert* (would_orphan(), Topology-Safety).

**b) Historisierungs-Kontinuität:**
Die akkumulierte Historie (U/F-Traces, τ) darf nicht gelöscht oder
global zurückgesetzt werden. Mutationen ändern Topologie, nicht Geschichte.
→ *Bereits implementiert* (Mutationen berühren R₀, nicht δ_H).

**c) Axiom-Treue:**
A₀ (Transition Enforcement) muss nach jeder Mutation weiterhin gelten.
Wenn eine Mutation dazu führt, dass das System in einem Zustand ohne
zulässige Transitionen steckt, ist die Mutation identitätszerstörend.
→ *Teilweise durch Topology-Safety*, aber nicht als explizite
Invarianzprüfung formuliert.

**Vorschlag:** Ein `IdentityInvariant`-Check, der nach jeder Mutation
verifiziert:
1. Goal erreichbar von aktuellem State
2. Historisierung unberührt
3. Mindestens eine zulässige Transition von jedem erreichbaren State

### 6.2 Die Representation-Frage

Aktuell werden Controller-Konfigurationen als flache Datenklassen
repräsentiert (TuningProposal, StructuralMutation). Es gibt keine
zusammenhängende Darstellung des *Konfigurationsraums*.

Optionen für Stufe 4:

| Darstellung | Komplexität | Nutzen | SU(2)-relevanz |
|-------------|-------------|--------|----------------|
| Skalarer Parameterraum (5D) | Niedrig | Bereits vorhanden | Keine |
| Mutation-Sequenz-Log | Niedrig | MutationHistory existiert | Keine |
| Meta-Graph (Konfigurationen als States) | Mittel | Würde Meta-Pfade sichtbar machen | Nur wenn Zyklen |
| Meta-Landscape (volle E₀-Struktur) | Hoch | Self-Navigation möglich | Ja — wenn Meta-Graph Zyklen hat |

**Empfehlung:** Meta-Graph als *Analysewerkzeug* (nicht als Laufzeit-
Struktur) — erlaubt zu prüfen, ob Mutationssequenzen zyklisch sind
und ob SU(2) auf der Meta-Ebene Sinn ergibt.

### 6.3 SU(2) auf der Meta-Ebene — Prüfung

Die Internal-Difference-Formalisierung (v1) definiert:

> System hat interne Differenz ⟺ ∃ψ₁, ψ₂ die nicht durch globale
> Phase verwandt sind und deren Relation unter Transformation erhalten bleibt.

**Prüfung am Meta-Controller:**

- Parameter (alpha, s_max, etc.) sind unabhängige Skalare → keine
  interne Differenz im Sinne der Formalisierung
- Exploration vs. Exploitation (Born/Greedy) ist ein binärer Modus →
  könnte als ℂ² modelliert werden, aber die Relation ist trivial
- Mutationssequenzen können nicht-kommutativ sein (A→B ≠ B→A auf der
  Landscape) → dies könnte SU(2)-Holonomie auf dem Meta-Graphen motivieren

**Bewertung:** SU(2) auf der Meta-Ebene ist *konzeptionell möglich*,
aber aktuell *nicht strukturell erzwungen*. Die Nicht-Kommutativität
von Mutationssequenzen ist real, aber ob sie SU(2)-Darstellung *braucht*
(vs. allgemeinere nicht-abelsche Struktur), ist eine offene Forschungsfrage.

**Empfehlung:** SU(2) auf Meta-Ebene nicht voreilig implementieren.
Erst prüfen, ob Mutationssequenzen *empirisch* zyklische Phaseneffekte
zeigen (z.B. nach 3 Mutationen A→B→C→A: ist die Landscape-Qualität
eine andere als vor den Mutationen?).

---

## 7. M_H — Aktueller Stand und nächster Schritt

**Alter Stand:** M_H = 1/(1+κ) oder exp(−κ) mit κ aus Holonomie → RETIRED (redundant mit Θ).

**Neuer Stand (M_H Adjudication v1):**
- M_H = graduated overlap functional
- Misst: wie stark wird Transition x→y durch co-realisierte Nachbar-Transitionen unterstützt
- Neighborhood T(x,y) = {z : x→z ∈ E, z→y ∈ E, z ∉ {x,y}} (forward-directed 2-hop support)
- Aggregation: overlap(x→y) = Σ_{z∈T} √(v(x,z) · v(z,y))
- Range: [0.2, 1.0] — floor 0.2 weil Canon §3.4 sagt "stability requires non-zero overlap"
- 45 Domains geprüft: >35 trivial (M_H=1.0, korrekt), <10 non-trivial

**Canon-Verankerung:** Ontodynamics §3.4 — „Gradual Overlap. Connections
possess degree. Overlap is graduated, not binary. Stability requires
non-zero overlap."

**Was fehlt:** Code-Implementierung. Die Formel steht, die Testdomäne
(Custom Overlap Differentiator) ist definiert, aber `landscape.py`
berechnet M_H noch immer als 1.0.

---

## 8. Korrektur-Kandidaten

Aufgrund dieser Tiefenprüfung identifiziere ich folgende Stellen, die
*nicht falsch* sind, aber *klarer dokumentiert* oder *explizit gemacht*
werden sollten:

### 8.1 Rate-Abweichung

| Aspekt | Canon | Code | Risiko |
|--------|-------|------|--------|
| v-Definition | v = Δ/R | argmin S = argmin(Δ·R) | Bei variablem Δ: andere Ordnung |
| transition_field | v = Δ/R | v = Δ · M_H · exp(−S) | Nichtlineare Transformation |

**Empfehlung:** In der Canon Alignment als *operationelle Konkretisierung*
dokumentieren, nicht als Widerspruch. Kein Code-Refactoring nötig — die
exp-Form hat bessere Konvergenz-Eigenschaften.

### 8.2 Decay ↔ Irreversibility

| Canon | Code | Risiko |
|-------|------|--------|
| „Non-invertible" | ρ < 1 → Abschwächung | Verletzung im strengen Sinne |

**Empfehlung:** Decay als *operationellen Approximations-Parameter*
klassifizieren. Canon-Treue wäre ρ=1 (kein Decay) — aber ρ=1
macht das System operationell instabil (alte Erfahrung dominiert).
Die Approximation ist *notwendig*, und die Spur wird *nie null*.

### 8.3 Finite Rate — fehlende Implementierung

Der Canon (§5.4) fordert eine *maximale Realisierungsrate*. Im Code
gibt es nur den Floor R≥1e-10, der eine implizite Obergrenze erzeugt.
Es existiert kein `v_max`-Parameter oder Check.

**Empfehlung:** Nicht implementieren als künstliches Limit. Das Floor
auf R ist ausreichend. Dokumentieren, dass die Canon-Forderung durch
das R-Floor implizit erfüllt ist.

---

## 9. Arbeitspunkte für Stufe 4

Sortiert nach Priorität:

| # | Arbeitspunkt | Typ | Priorität | Abhängigkeit |
|---|-------------|-----|-----------|--------------|
| 4a | **Identity Invariant** — definieren und implementieren | Konzept + Code | HOCH | Keine |
| 4b | **Mutation-Strategy-Adaptation** — MutationHistory → propose-Strategie | Code | MITTEL | 4a |
| 4c | **M_H Overlap-Functional** implementieren | Code | MITTEL | Keine |
| 4d | **Rate-Abweichung** in Canon Alignment dokumentieren | Doku | NIEDRIG | Keine |
| 4e | **SU(2) Meta-Exploration** — Meta-Graph-Zyklen prüfen | Forschung | NIEDRIG | 4b |

---

## 10. Status

**Status:** Deep Review v1 — konzeptionelle Tiefenprüfung abgeschlossen
**Version:** v1
**Relation zum Canon:** Kritische aber bestätigende Prüfung — keine
kanonischen Verstöße gefunden, aber drei Stellen expliziter
Dokumentationsbedarf (Rate, Decay, Finite Rate)
**Relation zur Synthese-Note:** Kompatibel; ergänzt um Rate-Analyse
und Decay-Spannung
**Relation zu Bridge 4:** Stufe 1–3 bestätigt geschlossen; Stufe 4
decomposed in 5 Arbeitspunkte (4a–4e)

---

*Ende der Tiefenprüfung.*
