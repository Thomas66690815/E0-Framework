# E₀ Memo: Amplituden-Masse-Falle (Beipackzettel-Finding)

**Datum:** 2026-03-27  
**Kontext:** Erster Real-World-Durchlauf mit Ibuprofen-Beipackzettel  
**Commit:** `36d4381`  
**Status:** Bestätigtes Phänomen, reproduzierbar

---

## Befund

Bei der `simple`-Summationsgeometrie bevorzugt die Amplitudenberechnung
Zustände mit mehr ausgehenden Kanten — unabhängig davon, ob diese Kanten
zum Ziel führen.

**Mechanismus:**
```
I(a) = |Σ Ψ(p)|²    wobei p ∈ Paths(a)
```
Mehr Pfade ab einer Aktion `a` → mehr Terme in der Summe → i.d.R. höhere
Intensität `I(a)`.

**Konkretes Beispiel:**

| Aktion           | Ausgehende Kanten | I(simple) | Führt zu GESUND? |
|------------------|:-----------------:|:---------:|:----------------:|
| MAGEN_REIZUNG    | 2 (MAGENULKUS, ABSETZEN) | hoch | Nein |
| BESSERUNG        | 1 (GESUND)               | niedrig | **Ja** |

Die `simple`-Amplitude überschreibt den Greedy-Controller und zieht ihn
in Richtung MAGEN_REIZUNG — das medizinische Gegenteil der Empfehlung.

## Lösung

`goal_reaching`-Geometrie gewichtet Pfade, die das Ziel enthalten, und
eliminiert dieses Problem. Der Controller findet dann:

    KOPFSCHMERZ → PARACETAMOL → BESSERUNG → GESUND  (3 Schritte, Σ=0.32)

statt

    KOPFSCHMERZ → IBU_400 → KEINE_WIRKUNG → IBU_800 → MAGEN_REIZUNG → ABSETZEN → Loop  (20 Schritte)

## Design-Entscheidung

- **Default bleibt `simple`**: Korrekter Default für explorative Runs ohne Ziel.
- **Session.run() warnt**: Wenn `goal` gesetzt ist aber `hybrid_geometry != "goal_reaching"`,
  wird ein `UserWarning` ausgegeben.
- **Kein automatischer Override**: Die Geometrie-Wahl hat Konsequenzen, und der
  Nutzer soll diese bewusst treffen.

## Zirkularitäts-Einschränkung

Die Δ/R₀-Werte wurden von Hand gesetzt und iteriert. Das Phänomen der
Amplituden-Masse-Falle ist *strukturell* real (folgt aus |ΣΨ|² über
unterschiedlich verzweigte Teilgraphen), aber die pharmakologische
Interpretation erfordert eine nicht-zirkuläre Validierung:

→ LLM-gestützter Landscape-Bau, bei dem die Δ/R₀ vom LLM geschätzt werden,
  ohne dass der Experimentator die Werte kennt oder steuert.
