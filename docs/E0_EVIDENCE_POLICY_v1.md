# E₀ Evidence Policy v1

**Status:** Verbindlich für strategische und empirische Claims ab ARC-M / WP-0
**Ledger:** [`E0_EVIDENCE_LEDGER_v1.json`](E0_EVIDENCE_LEDGER_v1.json)
**Zweck:** Eine Aussage darf nicht dadurch stärker erscheinen, dass sie in mehreren
Dokumenten wiederholt wird.

## 1. Eine Quelle der Wahrheit

Das JSON-Ledger ist die verbindliche Quelle für den Evidenzstatus strategisch
relevanter Aussagen. README, Papers, Reports, `bootstrap.json` und Roadmaps dürfen
Claims erklären, aber nicht eigenständig ihren Status erhöhen.

Ein Zähler wie „6× bestätigt“ ist ohne sechs benannte Evidence-IDs kein Beleg.
Wiederholungen desselben Experiments, derselben Domänenfamilie oder derselben
Implementierung sind keine unabhängigen Bestätigungen.

## 2. Getrennte Achsen

### Claim-Status

| Status | Bedeutung |
|---|---|
| `open` | Noch nicht entschieden oder nicht ausreichend geprüft |
| `supported_internal` | Durch repo-eigene Analyse oder Experimente gestützt |
| `mixed_internal` | Interne Befunde zeigen Unterstützung und relevante Gegenbefunde |
| `contradicted_internal` | Durch repo-eigene Befunde geschwächt oder widerlegt |
| `supported_external` | Durch eine unabhängige Replikation gestützt |
| `falsified` | Vorab definierte Falsifikationsbedingung eingetreten |
| `decision` | Governance-/Produktentscheidung; keine empirische Erkenntnis |

### Replikationsgrad

| Grad | Bedeutung |
|---|---|
| `none` | Idee, Analyse oder noch nicht ausgeführtes Design |
| `executable` | Ausführbarer Code vorhanden, Ergebnis aber nicht im Quick-Protokoll gepinnt |
| `same_repo` | Im aktuellen Repository reproduzierbar |
| `independent` | Von unabhängiger Partei oder unabhängiger Implementierung repliziert |

### Datenherkunft

`synthetic_designed`, `external_observational`, `mixed` oder `not_applicable`.
Ein externer Datensatz erhöht die Realitätsnähe, ist aber noch keine unabhängige
Replikation, wenn Adapter, Auswertung und Interpretation aus diesem Repository
stammen.

## 3. Mindestfelder pro Claim

Jeder Claim enthält:

- eine enge, falsifizierbare oder klar als Entscheidung markierte Aussage,
- einen expliziten Geltungsbereich,
- Claim-Status, Replikationsgrad und Datenherkunft,
- konkrete Code-/Dokumentquellen,
- ausführbare Befehle, soweit vorhanden,
- Rohdatenartefakte oder ausdrücklich `[]`, wenn sie fehlen,
- bekannte Grenzen und Confounder,
- Datum und Commit der letzten Prüfung.

## 4. Regeln für Statusänderungen

1. Nur neue Evidenz ändert einen empirischen Status; Textwiederholung tut es nicht.
2. `supported_external` erfordert eine benannte unabhängige Replikation.
3. Ein neuer Benchmark muss Rohresultate maschinenlesbar speichern.
4. Positive Ergebnisse und Gegenbefunde werden im selben Claim oder über
   `related_claims` verbunden.
5. README- und Paper-Claims müssen auf eine Ledger-ID verweisen.
6. `bootstrap.json` darf Arbeitskontext enthalten, ist aber kein Evidence Store.
7. Strategische Gates werden vor dem entscheidenden Lauf präregistriert.
8. Änderungen am Ledger werden zusammen mit dem zugehörigen Code, Report oder
   Audit committed.

## 5. G1-spezifische Kausalablation

Der Geometrie-/Amplitude-Wert darf nicht nur als „Overlay an/aus“ geprüft werden.
Mindestens folgende Varianten sind bei identischem Suchhorizont und Budget nötig:

1. Historisierung ohne Lookahead,
2. phasenfreier Lookahead,
3. identischer Lookahead mit `Θ = 0`,
4. U(1)-Phase,
5. vollständige Geometrie-/Overlay-Konfiguration.

Nur so lässt sich unterscheiden, ob ein Vorteil von Historisierung, Tiefensuche,
Gating, Pfadaggregation oder tatsächlicher Phaseninterferenz stammt.

## 6. Archivierungsregel

Archiviert wird nach Status, nicht nach Alter:

- ersetzte Roadmaps, Bewertungen und abgelöste Erklärdokumente dürfen ins Archiv,
- Code, Rohdaten und Reproduktionsartefakte hinter aktiven Claims bleiben auffindbar,
- archivierte Dokumente erhalten einen Hinweis auf den Nachfolger,
- ein Repo-Split darf erst erfolgen, wenn Claim- und Provenienzverweise erhalten
  bleiben.
