# Historisierung als Masse — Konzeptnotiz v1

**Datum:** 2026-03-28
**Status:** Konzeptionelle Grundlage + erster Implementierungsschritt
**Kanonische Basis:** Ontodynamics §4 „Mass: Persistent topological inertia resulting from accumulated historization."

---

## 1. Der Kerngedanke

Historisierung sind keine *gegangenen Pfade*. Historisierung ist **künstliche Masse**.

Masse in der Physik krümmt den Raum — sie deformiert das Feld für *alle*
Pfade gleichzeitig. In E₀ tut δ_H genau das: es verändert R_eff für eine
Kante, und damit die Amplituden *aller* Pfade, die diese Kante nutzen.
Nicht nur den gewählten Pfad, nicht retrospektiv — sondern simultan, in
Superposition.

    R_eff(x→y) = R₀(x→y) + δ_H(x→y)
    S_eff(x→y) = Δ(x→y) · R_eff(x→y)
    v(x→y) = Δ · exp(−S_eff) · M_H
    Ψ(p) = exp(−S(p) + i·Θ(p))        ← alle Pfade, gleichzeitig

δ_H *ist* Masse im kanonischen Sinn: persistente topologische Trägheit
aus akkumulierter Historisierung. Die Metapher „Masse krümmt Raumzeit"
ist in E₀ keine Metapher — es ist die operative Mechanik.

---

## 2. Quantitative vs. Qualitative Masse

### 2.1 Was wir haben: Quantitative Masse (Skalar)

    δ_H(e) = λ_f · F(e) − λ_s · U(e)

Ein Skalar. Positiv = Widerstand erhöht (Fehlschläge dominieren).
Negativ = Widerstand gesenkt (Erfolge dominieren). Das ist die
**Magnitude** der Masse — *wie viel* strukturelle Trägheit.

### 2.2 Was fehlt: Qualitative Masse (Richtung)

Die Magnitude allein sagt nicht, *welcher Art* die Erfahrung ist:

| U (Erfolg) | F (Fehlschlag) | δ_H  | Qualität           |
|-------------|----------------|------|--------------------|
| 10          | 0              | −1.5 | Klar gelernt ✓     |
| 0           | 10             | +2.0 | Klar vermieden ✗   |
| 10          | 10             | +0.5 | Widersprüchlich ?  |
| 0           | 0              | 0.0  | Unerfahren ○       |

Die letzten beiden Zeilen sind entscheidend: δ_H ≈ 0 kann „noch nie
probiert" ODER „oft probiert mit unklarem Ergebnis" bedeuten. Diese
Information geht in der skalaren Darstellung verloren.

### 2.3 Die qualitative Dimension

Definiere zwei neue Observablen auf der Historisierung:

**Gesamt-Masse** (total accumulated experience):

    m(e) = U(e) + F(e)

**Qualität** (normalized success/failure balance):

    q(e) = (U(e) − F(e)) / (U(e) + F(e) + ε)    ∈ [−1, +1]

- q → +1: reine Erfolge → klar gelernt
- q → −1: reine Fehlschläge → klar vermieden
- q ≈ 0: gemischt oder unerfahren
- ε > 0 verhindert Division durch Null

**Zusammenhang mit δ_H:**
δ_H codiert eine *gewichtete* Linearkombination. (m, q) codiert das
gleiche Material, aber separiert in Betrag und Richtung:
- m sagt: *wie viel* Erfahrung (Trägheit, Masse)
- q sagt: *welche Art* Erfahrung (Qualität, Richtung)

---

## 3. Konsequenz für M_H

M_H moduliert das Transitionsfeld:

    v(x→y) = Δ · exp(−S_eff) · M_H(x→y)

Aktuell: M_H kommt aus dem Overlap-Funktional (C40) — wie stark ist die
Kante x→y durch Nachbar-Transitionen strukturell gestützt.

Die qualitative Masse fügt eine zweite Informationsquelle hinzu: wie
*erfahren* ist die Kante?

- Wenig Masse (m ≈ 0, q ≈ 0): unerfahren → explorativ → „quantenhaft"
- Viel Masse, klar (m >> 0, |q| → 1): erfahren, eindeutig → deterministisch → „klassisch"
- Viel Masse, unklar (m >> 0, q ≈ 0): viel Erfahrung, keine Klarheit → Spannung

Das ist der **Quanten→Klassisch-Übergang durch masseinduzierte Dekohärenz**:
Masse erzwingt Lokalisierung (Einschränkung der Superposition), genau wie
in der Physik.

---

## 4. Verbindung zu SU(2) (Ausblick)

Die qualitative Masse (m, q) kann als Spinor auf der Bloch-Sphäre dargestellt
werden:

- |δ_H| = radiale Koordinate (Betrag der Masse)
- θ = f(q) = Polarwinkel (Qualität: Erfolg↔Fehlschlag)
- φ = SU(2)-Phase = Azimutwinkel (kontextuelle Orientierung)

Das wäre die vollständige SU(2)-Erweiterung der Historisierung — ein
Spinor statt eines Skalars. **Nicht für diese Iteration**, aber die
Architektur muss kompatibel bleiben.

---

## 5. Implementierungsplan (dieser Commit)

### Phase A: Structural Inscription observables in `historization.py`
- `trace_load(edge) → float` — total inscription m = U + F
- `trace_quality(edge) → float` — quality q = (U−F)/(U+F+ε)
- Backward-compatible aliases: `mass = trace_load`, `quality = trace_quality`

### Phase B: Inertia modulation — Layer 3
- `inertia_factor(edge) → float` — dampens conflicted edges
- `Landscape.inertia_modulation` flag integrates into `transition_field()`
- Backward-compatible aliases: `mass_modulation_factor`, `mass_modulation`
- Complementary to Overlap M_H (C40): Overlap = structural embedding,
  Inertia = accumulated inscription quality

### Phase C (future): SU(2) spinor inscription
- δ_H as spinor instead of scalar
- Interference between inscription spinors of neighboring edges
- Full Bloch sphere representation

---

## 6. This is learning

> "Historisierung, das sind eigentlich keine gegangenen Pfade, sondern das
> ist wie künstliche Masse. Das ist die Basis von Lernen."

Learning = inscription accumulation. Every experience deposits structural
trace on an edge. This trace deforms the amplitude field permanently
(with decay ρ as "forgetting"). The quality determines the *kind*
of deformation: success opens, failure closes.

This is not a metaphor. It is the operative geometry of the system.

---

## 7. Terminological correction — the layered model

**Observation (2026-03-29):** Within the structure, what we first have is
not yet "mass" in the fully presented sense. Mass is the *outwardly effective,
behavior-shaping appearance* of accumulated structural inscription.

The Canon itself implies this layering:

> "Mass = persistent topological inertia **resulting from** accumulated historization."

"Resulting from" implies: historization is not mass — mass *results from* it.

### The four layers

| Layer | Canon term | Code | What it is |
|-------|-----------|------|------------|
| 1. Process | Historization | `update(e, outcome)` | Real transitions leaving trace |
| 2. Inscription | Structural trace | `trace_load(e)`, `trace_quality(e)` | What remains: changed relations, sediment |
| 3. Inertia | Reconfiguration cost | `inertia_factor(e)` | Functional effect: preference, resistance |
| 4. Mass | Emergent appearance | Controller behavior | Outwardly visible stability / inertia |

### Consequences for naming

- **Layer 2** functions are named `trace_*` (not `mass_*`) because they
  describe the *inner structural inscription*, not the outward mass effect
- **Layer 3** is named `inertia_*` because it is the functional consequence
  of inscription — how inscription resists or permits reconfiguration
- **Layer 4** ("mass") is emergent and not directly computed — it *appears*
  in the controller's behavior, in path preferences, in long-term stability

Old names (`mass`, `quality`, `mass_modulation_factor`, `mass_modulation`)
remain as backward-compatible aliases.

### Why this matters

This is not purely semantic. The layered model:
1. Prevents premature reification (calling internal traces "mass")
2. Clarifies that mass is *emergent*, not computed
3. Opens space for the SU(2) extension — the spinor lives at Layer 2
   (inscription orientation), not Layer 4 (mass appearance)
4. Aligns with the Canon's own ontological ordering
