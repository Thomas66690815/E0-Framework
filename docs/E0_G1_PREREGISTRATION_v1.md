# E₀ Gate G1 — Präregistrierung v1

**Protocol ID:** `E0-G1-v1`
**Status:** Präregistriertes Design; noch keine Holdout-Ausführung
**Datum:** 2026-07-28
**Maschinenlesbar:** [`E0_G1_PROTOCOL_v1.json`](E0_G1_PROTOCOL_v1.json)
**Evidence Policy:** [`E0_EVIDENCE_POLICY_v1.md`](E0_EVIDENCE_POLICY_v1.md)

## 1. Zweck und Entscheidungsfragen

G1 ist kein weiterer Demonstrator. Es beantwortet zwei vorab festgelegte
Entscheidungsfragen:

- **G1-A:** Liefert die kausal isolierte Geometrie-/Phasenkomponente praktischen
  Mehrwert gegenüber dem besten einfacheren Equal-Interaction-Control, und bleibt
  dieser Mehrwert bei `N >= 100` praktisch berechenbar?
- **G1-B:** Ist Historisierung ohne Lookahead auf denselben Holdout-Instanzen
  gegenüber fair trainierten Standard-Baselines kompetitiv?

Diese Präregistrierung legt Domänen, Splits, Budgets, Ablationen, Metriken,
Statistik und Abbruchregeln vor dem ersten Holdout-Ergebnis fest.

## 2. Was bestehende Benchmarks nicht leisten

Vorhandener Code wird wiederverwendet, aber nicht ungeprüft als G1-Evidenz
übernommen:

- `benchmark_scaling.py` testet den historisierenden Greedy-Controller bis
  ungefähr 500 Knoten, nicht die Amplitude-/Pfadfamilienberechnung.
- `benchmark_sota.py` gibt Q-Learning bisher nur einen einzelnen
  Navigationslauf. Das ist kein fairer Training-/Evaluationsvergleich.
- C185 vergleicht Overlay an/aus, isoliert aber Phase nicht von Lookahead,
  kohärenter Pfadaggregation und Gating.
- A* und D*-Lite besitzen Kartenwissen. Sie sind obere Referenzen, keine
  gleichinformierten Wettbewerbs-Baselines.

## 3. Experimentelle Einheit und Splits

Eine experimentelle Einheit ist:

`domain_family × scale × generator_seed × method`

Alle Methoden erhalten dieselbe erzeugte Instanz, dieselben Outcome-Sequenzen und
dasselbe maximale Interaktionsbudget. Methoden-RNG und Environment-RNG sind
getrennt.

### Entwicklung

- Generator-Seeds: `0..9`
- Nur diese Seeds dürfen für Debugging, Hyperparameterwahl und die Auswahl des
  primären einfacheren G1-A-Controls verwendet werden.
- Es gilt eine globale Konfiguration je Methode; keine domänen- oder
  größenspezifische Handoptimierung.

### Holdout

- Generator-Seeds: `1000..1029` — 30 gepaarte Replikate je Zelle.
- Outcome-Seed: `200000 + generator_seed`
- Policy-Seed: `300000 + generator_seed`
- Stochastische Outcomes werden gegen
  `(generator_seed, episode_index, edge_id, edge_attempt_index)` geschlüsselt.
  Methoden dürfen keinen gemeinsam fortlaufenden Environment-RNG verbrauchen:
  divergierende Aktionsfolgen würden sonst unterschiedliche Zufallsereignisse
  verschieben statt dieselben aktionsgebundenen Potential Outcomes abzurufen.
- Nach dem ersten Lesen eines Holdout-Ergebnisses dürfen Konfigurationen,
  Generatoren, Metriken und Gate-Regeln nicht mehr geändert werden. Eine
  semantische Änderung erfordert Protokoll v2; v1 bleibt vollständig berichtet.

## 4. Domänenfamilien

Alle Familien werden bei Zielgrößen `N = 100, 500, 1000` erzeugt. Der Generator
darf die exakte Knotenzahl geringfügig überschreiten, muss aber Ziel- und
tatsächliche Größe protokollieren.

1. **`wall_grid`** — Gradient führt gegen eine Wand; eine erfolgreiche Route
   erfordert einen gerichteten Umweg. Statische Kontrollfamilie.
2. **`trap_grid_v2`** — neu zu implementierender Trap-Grid-Generator. Ein Trap
   muss semantisch echt sein: lokal attraktiver Eintritt, nachgelagerter
   FAILURE/Dead-End oder messbarer Rückkehrpreis. Ein bloß unattraktiver
   Diagonalweg zählt nicht.
3. **`decoy_dag`** — parallele Pfade; 40 % scheitern erst bei 70–90 % ihrer
   Tiefe. Prüft spätes Credit Assignment ohne Zyklen.
4. **`nonstationary_parallel`** — mindestens zwei alternative Korridore. Nach
   der Hälfte der Evaluations-Episoden tauschen erfolgreiche und fehlschlagende
   Korridore ihre Rollen. Prüft Anpassung statt bloßer Endleistung.

Die Generator-Invarianten werden in WP-2.1 getestet. Eine Verletzung macht die
betroffene Instanz infrastrukturell ungültig; sie darf nicht still ersetzt
werden.

## 5. Interaktionsprotokoll

Jede Methode startet pro Replikat mit leerem Lernzustand.

- **Adaptation:** 10 Episoden
- **Evaluation:** 20 Episoden; nur diese Episoden gehen in G1 ein
- **Maximale Schritte je Episode:** `4 × actual_N`
- **Wall-Time-Cap:** 60 Sekunden je Episode und 1.800 Sekunden je Replikat
- **Peak-RSS-Cap:** 4 GiB je isoliertem Methoden-Worker
- Zielerreichung oder struktureller Dead-End beendet eine Episode.
- Position und episodischer Executor-Zustand werden je Episode zurückgesetzt;
  gelernter Zustand bleibt innerhalb des Replikats erhalten.
- Lernen bleibt auch während der Evaluation aktiv, weil Historisierung und die
  verglichenen Bandit/RL-Verfahren als kontinuierlich lernende Systeme geprüft
  werden.
- `nonstationary_parallel` schaltet unmittelbar vor Evaluations-Episode 11 um.
- Interaktionsbudget ist identisch. Wall-Time und Speicher werden gemessen, aber
  nicht in zusätzliche Interaktionen umgerechnet.

## 6. Fünf kausale E₀-Ablationen

Alle Lookahead-Varianten verwenden dieselben Kandidaten, dieselbe enumerierte
Pfadmenge, Horizont `h = 3`, `confidence >= 0.85`, maximale Imbalance `3.0` und
dieselbe Override-Regel. So bleibt nur der jeweils benannte Mechanismus
unterschiedlich.

| ID | Variante | Isolierte Frage |
|---|---|---|
| `A_HIST` | Historisierung + Revisit, kein Lookahead | Trägt die Memory-Basis allein? |
| `B_INCOHERENT` | Pfade enumerieren; je Aktion `Σ exp(-2S(p))` | Was bringt Lookahead ohne kohärente Kreuzterme? |
| `C_THETA_ZERO` | `|Σ exp(-S(p))|²` mit `Θ=0` | Was bringt kohärente Pfadmasse ohne Phasendifferenz? |
| `D_U1_PHASE` | identisch zu C, mit tatsächlicher U(1)-Phase | Was bringt Phase kausal gegenüber Θ=0? |
| `E_FULL_GEOMETRY` | vollständiger `structural_geometry`-Pfad | Was bringt der gesamte Geometrie-Stack? |

Pro Entscheidung dürfen höchstens 100.000 Pfade expandiert werden. Ein Treffer
des Caps wird protokolliert und zählt als Laufzeit-/Skalierungsfehler, nicht als
Grund, die Instanz auszuschließen.

## 7. Baselines

### Gleichinformierte Wettbewerbs-Baselines für G1-B

- Tabulares Q-Learning
- UCB1 auf Kanten
- Random-Restart-Greedy

Sie erhalten dasselbe Adaptations-/Evaluationsbudget wie `A_HIST`.
Hyperparameter werden in WP-2.2 aus Literatur plus Entwicklungs-Seeds gewählt
und vor Holdout-Zugriff in `frozen_configs.json` gespeichert.

### Diagnostische Baselines

- Memoryless Greedy
- ε-Greedy
- Uniform Random

### Karteninformierte obere Referenzen

- A*
- D*-Lite

A* und D*-Lite werden berichtet, aber wegen ihres zusätzlichen Kartenwissens
nicht in den G1-B-Baseline-Median aufgenommen.

## 8. Metriken

### Primärmetrik

Für jede Evaluations-Episode:

```text
success_adjusted_efficiency =
    oracle_cost / max(observed_cost, oracle_cost)   wenn Ziel erreicht
    0                                               sonst
```

Die Metrik liegt in `[0,1]`, bestraft Nichterreichen ohne Survivor Bias und
belohnt erfolgreiche, kurze Navigation. `oracle_cost` wird vom
karteninformierten Evaluator berechnet, nicht an gleichinformierte Methoden
weitergegeben.

### Sekundärmetriken

- Zielrate
- Schritte und Gesamtkosten
- Regret gegenüber dem Oracle
- Revisit- und FAILURE-Zahl
- Post-Switch-Recovery-Episoden
- Wall-Time und Peak-RSS
- expandierte Pfade, Path-Cap-Treffer
- Overrides und Override-Erfolg
- Phase-Regime-Zähler (`gradient`, `interfering`, `wrapped`)

## 9. Statistik

- Paarung über identische Generator-/Outcome-Seeds.
- 10.000 gepaarte Bootstrap-Resamples, Seed `20260728`.
- Resampling-Einheit ist die Domäneninstanz, stratifiziert nach Familie und
  Größe; Episoden werden nicht als unabhängige Replikate ausgegeben.
- Zunächst wird je `family × scale` über die 30 Generator-Seeds gemittelt. Ein
  Familienwert ist anschließend das ungewichtete Mittel der drei Zellwerte für
  `N=100,500,1000`; damit erhält jede präregistrierte Größe dasselbe Gewicht.
- 95-%-Konfidenzintervalle; Effektgrößen und Rohwerte werden gemeinsam
  berichtet.
- Keine optionale Beendigung und kein Entfernen negativer Seeds.
- Explorative Auswertungen werden klar als explorativ markiert und verändern
  G1 nicht.

## 10. Vorab festgelegte Gate-Regeln

### G1-A — Geometrie

Das primäre einfachere Control wird **vor Holdout-Zugriff** auf Entwicklungs-Seeds
als bestes von `A_HIST`, `B_INCOHERENT`, `C_THETA_ZERO` gewählt; bei Gleichstand
gewinnt die schnellere Variante. Primäres Treatment ist `E_FULL_GEOMETRY`.

Eine Domänenfamilie qualifiziert sich, wenn über `N=100/500/1000`:

1. der relative Lift der mittleren `success_adjusted_efficiency` mindestens
   10 % beträgt,
2. die untere Grenze des gepaarten 95-%-Intervalls der absoluten Differenz über
   0 liegt,
3. die Zielrate nicht um mehr als 2 Prozentpunkte sinkt,
4. der Effekt bei `N=1000` nicht das Vorzeichen wechselt.

Wenn das Control im Mittel unter `0.05` liegt, ersetzt ein absoluter Gewinn von
mindestens `0.10` das relative 10-%-Kriterium.

G1-A besteht nur, wenn:

- mindestens zwei der vier Familien qualifizieren,
- bei `N=1000` weniger als 5 % der Läufe Path-Cap/Timeout erreichen,
- die mediane Wall-Time von E höchstens 10× die des gewählten Controls beträgt.

`D_U1_PHASE` gegen `C_THETA_ZERO` ist die vorab festgelegte
Phasen-Attributionsprüfung. Für D gegen C gelten dieselben Familien- und
Gesamtregeln wie oben, lediglich Treatment und Control werden ersetzt. Besteht
nur E, nicht aber D gegen C, darf ein Produktwert des vollständigen Stacks, aber
kein praktischer Interferenz-/Phasenwert behauptet werden.

### G1-B — Historisierung

Pro gepaarter Instanz ist der Comparator der Median aus Q-Learning, UCB1 und
Random-Restart-Greedy. Eine Familie gilt als kompetitiv, wenn:

1. der Punktschätzer von `A_HIST` mindestens dem Comparator entspricht,
2. die untere 95-%-Intervallgrenze der absoluten Differenz größer als `-0.05`
   ist,
3. die Zielrate nicht mehr als 10 Prozentpunkte schlechter ist.

G1-B besteht bei mindestens drei von vier Familien, sofern bei `N=1000` keine
Familie einen Zielraten-Rückstand von mehr als 20 Prozentpunkten zeigt.

## 11. Fehler-, Timeout- und Änderungsregeln

- Algorithmischer Timeout, Path-Cap, NaN oder Speicherüberschreitung:
  gültiges negatives Ergebnis, Episode erhält Primärscore 0.
  Die festen Zeit- und RSS-Grenzen stehen im Interaktionsprotokoll.
- Infrastrukturfehler außerhalb der Methode: gesamte
  `method × family × scale`-Zelle nach Fix mit denselben Seeds erneut ausführen;
  fehlerhaftes Artefakt aufbewahren.
- Sind mehr als 10 % aller geplanten Zellen infrastrukturell ungültig, lautet
  das Gate-Ergebnis `UNDECIDED`, nicht PASS oder FAIL.
- Semantische Änderungen nach Holdout-Zugriff erzeugen Protokoll v2. Ergebnisse
  aus v1 bleiben sichtbar.

## 12. Rohdaten und Reproduktion

WP-2.x muss unter `artifacts/g1/E0-G1-v1/` erzeugen:

- `manifest.json` — Commit, Protokollhash, Plattform, Python/Dependency-Versionen
- `frozen_configs.json` — endgültige Methodenkonfigurationen
- `raw_runs.jsonl` — eine Zeile je experimenteller Einheit
- `episodes.jsonl.gz` — Evaluations-Episoden
- `summary.json` — ausschließlich aus Rohdaten abgeleitete Gate-Zusammenfassung
- `environment.json` — CPU, RAM, OS und Timerauflösung

Jeder Rohdatensatz enthält mindestens Protocol-ID, Commit, Run-ID, Familie,
Ziel-/Ist-N, Seeds, Methode, Config-Hash, Budgetverbrauch, Ergebnis, alle
Primär-/Sekundärmetriken und Fehlerstatus.

## 13. Freeze-Erklärung

Mit C322 ist das **Design** präregistriert. Holdout-Ergebnisse existieren zu
diesem Zeitpunkt nicht. WP-2.1 bis WP-2.3 dürfen fehlende Implementierung bauen
und auf Entwicklungs-Seeds prüfen. Vor dem ersten Holdout-Lauf werden lediglich
konkrete Literatur-Hyperparameter und der auf Development gewählte
G1-A-Control-Name in `frozen_configs.json` ergänzt; Gate-Regeln und
Holdout-Seeds bleiben unverändert.
