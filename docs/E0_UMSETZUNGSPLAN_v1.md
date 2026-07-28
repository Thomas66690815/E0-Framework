# E₀ Umsetzungsplan v1 — Konsolidierung & Entscheidung

**Status:** Verbindlich (ARC-M, ab C320)
**Datum:** 2026-07-27
**Grundlage:** [E0_EVIDENCE_LEDGER_v1.json](E0_EVIDENCE_LEDGER_v1.json) (verbindlicher Claim-Status), [E0_EVIDENCE_POLICY_v1.md](E0_EVIDENCE_POLICY_v1.md), [E0_PAPER_AUDIT_v1.md](E0_PAPER_AUDIT_v1.md), [E0_STRUCTURAL_CONTRADICTIONS_v1.md](E0_STRUCTURAL_CONTRADICTIONS_v1.md) (SC-11), [C185_TRAFFIC_VALIDATION_REPORT_v1.md](research/C185_TRAFFIC_VALIDATION_REPORT_v1.md), C319-Regimebefund
**Pflege:** WP-Status in diesem Dokument aktualisieren; Gate-Ergebnisse zusätzlich in `bootstrap.json → strategic_plan`.

---

## 0. Kurzfassung

Der intern reproduzierte Wert von E₀ konzentriert sich bisher auf Historisierung und Revisit-Handling (~600 LOC, `lean/reliability_memory`). Ob dies auch der dominante allgemeine Produktwert ist, bleibt eine strategische Hypothese. Der Interferenz-/Geometrie-Layer hat theoretische Substanz, aber keinen kausal isolierten praktischen Mehrwert: C185 zeigt einen kleinen gated Overlay-Effekt, trennt Phase jedoch nicht von Lookahead und Gating. Skalierung bis N≈225/500 existiert für den historisierenden Controller, nicht für die Geometrie-/Pfadfamilienberechnung. Standard-Baselines existieren im Repo; unabhängige Replikation und großskalige faire Vergleiche fehlen. Konsequenz:

1. **Als Produktkandidaten härten**, was intern trägt (lean-Pakete).
2. **Ein Entscheidungsexperiment** statt weiterer Features: kausale Ablation + Skalierung + gehärtete Standard-Baselines.
3. **Gate G1** entscheidet datenbasiert über die Zukunft des Geometrie-Layers.
4. **Feature-Freeze** für Layer 5–14 bis G1.

Geschätzter Gesamtumfang bis Phase 5: **15–25 Commits**.

---

## 1. Ausgangslage

| Kategorie | Befund | Quelle |
|---|---|---|
| **Intern gestützt** | Historisierung + Revisit-Handling schlagen memoryless Greedy auf den entworfenen Trap-/Cycle-Domänen | `E0-HIST-TRAPS-001` |
| **Gemischt/offen** | Historisierung ist der allgemein dominante Produktwert; der bisherige „6×“-Zähler ist keine unabhängige Evidence Map | `E0-HIST-DOMINANCE-001` |
| **Intern gestützt, eng begrenzt** | C185: gated Overlay (conf ≥ 0.85) +4,2–6 % Trips über E₀ greedy; ungated schlechter. Phasenursache nicht isoliert | `E0-OVERLAY-C185-001`, `E0-PHASE-CAUSAL-001` |
| **Intern gestützt, eng begrenzt** | C319-Beispiele bleiben bei typischen Gewichten überwiegend konstruktiv; Auslöschung erscheint erst im wrapped Regime | `E0-GEOMETRY-REGIME-001` |
| **Vorhanden** | Historisierungs-/Revisit-Skalierungsbenchmarks bis N≈225/500 | `E0-SCALE-HIST-001` |
| **Offen (existenziell)** | Geometrie-/Amplitude-Wert und Laufzeit bei N≥100; Pfad-Enumeration O(paths) | `E0-SCALE-GEOMETRY-001`, SC-11 |
| **Vorhanden, aber intern** | A*, BFS, Q-Learning, ε-Greedy, Random und Greedy; faire großskalige Referenzvergleiche und unabhängige Replikation fehlen | `E0-BASELINES-001`, `E0-EXTERNAL-REPLICATION-001` |
| **Fehlt** | Ablationen für Layer 5–14 (Dream, Sleep-Wake, Multiverse, Self-Graph, …) gegen simplere Alternativen | Audit §6.3.4 |
| **Bekannte Grenzen** | F3 (Branching ≥ 3), F4 (non-Markov Credit Assignment), River-City (stale memory −29 %), GT-8 (Partial Residual) | C272, C185, bootstrap |

---

## 2. Leitentscheidungen (ab sofort gültig)

- **L1 — Produkt vs. Forschung:** Produktkandidaten sind die lean-Pakete (`reliability_memory`, `structural_geometry`). Das Framework (`e0_controller/`, `server/`) ist bis Gate G1 Forschungsträger und Quellcode-Lieferant für lean-Extraktionen. Dies ist eine Governance-Entscheidung (`E0-PRODUCT-LEAN-001`), kein empirischer Befund.
- **L2 — Feature-Freeze Layer 5–14:** Reflexion, Multiverse, LLM-Integration-Ausbau, Observation, Dream, Entropy, Sleep-Wake, Curriculum, Communication, Session-Runner: nur noch Bugfixes. Entsperrung einzelner Mechanismen **nur per Ablation**: messbarer Mehrwert gegen eine simplere Alternative (z. B. periodischer Reset, k-means, Replay) auf ≥ 2 Domänen.
- **L3 — Plan-Bindung:** Jeder Commit ist einem Work Package (WP-x.y) zuordenbar. Kein WP → kein Commit (erst Plan bewusst ändern, dann arbeiten).
- **L4 — Claims-Disziplin:** Kein AGI-Framing. Positionierung: *„Lernender Kantenkosten-Speicher mit gated Lookahead für Graph-Navigation unter Unsicherheit."* Jeder strategische README-/Paper-Claim verweist auf eine Ledger-ID und von dort auf Benchmark- und Rohdatenartefakte.

---

## 3. Phasen und Work Packages

### Phase 0 — Evidence Reconciliation (vor Repo-Split und G1)

| WP | Inhalt | Akzeptanzkriterium | Status |
|---|---|---|---|
| **WP-0.1** | Evidence Policy + maschinenlesbares Claim-Ledger; Aussage-Status, Replikationsgrad und Datenherkunft trennen | Strategische C320-Claims besitzen eindeutige IDs, Scope, Quellen, Befehle und Grenzen; JSON validiert | done C321 |
| **WP-0.2** | Repository-Abgleich: C270/C273, A*/Q-Learning, Scaling, BPI2017 und bestehendes Reproduktionsprotokoll in Plan/Bootstrap richtig einordnen | Keine „fehlt"-Aussage widerspricht vorhandenem Code; Historisierungs- und Geometrie-Skalierung getrennt | done C321 |
| **WP-0.3** | G1-Protokoll präregistrieren: Metriken, Seeds, Budgets, Tuning/Holdout, Rohdatenformat und Kausalablation | Protokoll ist vor dem ersten G1-Ergebnis eingefroren; fünf Ablationsstufen ausführbar spezifiziert | done C322 |
| **WP-0.4** | Archiv-/Repo-Statusinventur ohne Verschieben: active, research, frozen, superseded, archive-candidate | Jede Top-Level-Komponente und strategische Doku hat Status und Nachfolger; Split-Entscheidung bleibt bis G1 vertagt | offen |

### Phase 1 — Lean-Pakete produktisieren (parallel zu Phase 2 möglich)

| WP | Inhalt | Akzeptanzkriterium | Status |
|---|---|---|---|
| **WP-1.1** | Packaging: eigenes `pyproject.toml` je Paket, `pip install -e` fähig, SemVer 0.x, eigenes README je Paket | Frischer Clone → `pip install -e lean/reliability_memory` → Tests grün; dito structural_geometry | offen |
| **WP-1.2** | PyPI-Veröffentlichung (Namen sichern, z. B. `e0-reliability-memory`) | `pip install e0-reliability-memory` funktioniert. **Nutzer-Entscheidung erforderlich** (externe Publikation) | offen |
| **WP-1.3** | End-to-End-Beispiel mit echtem Nutzwert: Tool-Call-Reliability-Sidecar für LLM-Agenten (MCP-Server existiert; fehlt: lauffähiges Beispiel + Kurzdoku) | Beispiel < 100 Zeilen Nutzercode, läuft ohne Framework-Installation | offen |
| **WP-1.4** | Game-AI-Beispielprojekt, das `structural_geometry` als Bibliothek konsumiert (Influence-Map-Vergleich, an GAME_AI.md anschließend) | Eigenständiges Skript/Repo-Ordner, nur lean-Import | offen |

### Phase 2 — Entscheidungsexperiment (die eigentliche Priorität)

| WP | Inhalt | Akzeptanzkriterium | Status |
|---|---|---|---|
| **WP-2.1** | Bestehende Harnesses (`benchmark_scaling`, `benchmark_sota`, `reproduce.py`) konsolidieren und um Domänengeneratoren erweitern: Trap-Grids inkl. TRAP_GRID-Redesign, nicht-stationäre Graphen, N = 100/500/1000; festes WP-0.3-Protokoll | Ein Befehl erzeugt reproduzierbar Domänen, Environment-Manifest und maschinenlesbare Rohdaten | offen |
| **WP-2.2** | Vorhandene Baselines auditieren und härten: A*/BFS/Q-Learning/ε-Greedy/Random; ergänzen um UCB1, D*-Lite (mit Karte, obere Referenz), Random-Restart-Greedy. Literaturparameter, identische Budgets, keine Strohmänner | Jede relevante Baseline läuft auf allen WP-2.1-Domänen; Abweichungen von Referenzverfahren dokumentiert | offen |
| **WP-2.3** | Kausalablation bei identischem Horizont/Budget: (a) Historisierung ohne Lookahead, (b) phasenfreier Lookahead, (c) Lookahead mit Θ=0, (d) U(1)-Phase, (e) vollständige Geometrie/Overlay-Konfiguration | Alle fünf Varianten auf allen Domänen; Phase, Lookahead, Pfadaggregation und Gate getrennt auswertbar | offen |
| **WP-2.4** | Skalierungslauf + Report `docs/research/E0_DECISION_BENCHMARK_v1.md` — positive und negative Resultate, Effektgrößen und Unsicherheit berichten | Vollständige Tabellen + Rohdatenbundle; Gate-G1-Kriterien darauf anwendbar | offen |
| **WP-2.5** | Vorhandenes C184b/BPI2017-Audit als Ausgangspunkt; neue held-out Case-Level-Vorhersage bzw. Empfehlung ohne Outcome-Leakage | Train/Test-Trennung, Accuracy/Calibration gegen Ground Truth und einfache Baselines im Report | offen |

### Phase 3 — Gate G1 (Entscheidung, vorab festgelegte Kriterien)

Die Kriterien stehen **vor** dem Experiment fest, um Post-hoc-Rationalisierung auszuschließen:

- **G1-A (Geometrie-Layer):** Zeigt die kausal isolierte Phase/Geometrie gegenüber dem besten einfacheren Equal-Budget-Control einen vorab definierten Mehrwert (Managementschwelle: median ≥ 10 %, Unsicherheitsintervall schließt 0 aus) auf ≥ 2 Holdout-Domänenklassen bei N ≥ 100 → Geometrie bleibt Produktbestandteil (→ Phase 4a). Sonst → Forschungs-Freeze (→ Phase 4b).
- **G1-B (Historisierung vs. Baselines):** Ist Historization-only unter identischem Interaktions- und Rechenbudget auf den vorab gewählten Primärmetriken mindestens so gut wie der Baseline-Median → Positionierung halten. Liegen Standardverfahren robust vorn → lean-Pakete repositionieren als *leichtgewichtige, erklärbare, trainingsfreie Alternative* mit dokumentierten Trade-offs; keine Überlegenheits-Claims.
- **Dokumentation:** Gate-Entscheid mit Datum, Ledger-IDs, Zahlen, Unsicherheit und Begründung hier, im Evidence Ledger **und** in `bootstrap.json → strategic_plan.gate_g1`.

### Phase 4a / 4b — je nach Gate

- **4a (Geometrie besteht):** `structural_geometry` voll produktisieren (Packaging-Feinschliff, Doku, weitere Game-AI-Beispiele), Geometrie-Paper extern einreichen.
- **4b (Geometrie besteht nicht):** Geometrie-Code einfrieren (bleibt im Repo, klar als Forschung markiert); volle Energie auf `reliability_memory`-Adoption.

### Phase 5 — Außendarstellung und Reproduzierbarkeit

| WP | Inhalt | Akzeptanzkriterium | Status |
|---|---|---|---|
| **WP-5.1** | README-Umbau: Claims an Benchmark-Artefakte koppeln, AGI-Blueprint nach `_archive/`, „When to use"-Sektion mit ehrlichen Alternativen (Q-Learning etc.) | Kein Claim ohne Beleg-Link | offen |
| **WP-5.2** | Kurzes eigenständiges Paper (6–10 Seiten): nur Historisierungs-Mechanismus + F3/F4-Grenzen + G1-Benchmark-Ergebnisse. Extern einreichen (arXiv/Workshop). **Nutzer-Entscheidung bei Einreichung** | Eingereichtes Manuskript | offen |
| **WP-5.3** | Bestehendes `reproduce.py`/`REPRODUCTION.md` auf G1 erweitern: ein Befehl reproduziert Tabellen und persistiert Environment-Manifest + Rohdaten | `README`-Abschnitt „Reproduce our numbers"; Ledger verweist auf unveränderliche Artefakte | offen |

---

## 4. Nicht-Ziele (bis G1 entschieden ist)

- Keine neuen Layer, keine neuen Mechanismen in Layer 5–14.
- Keine neuen Domänen-Demos, keine UI-/Studio-Ausbauten.
- Keine neuen Papers zu Layer-5–14-Mechanismen (P7–P10 aus dem Audit: aufgeschoben).
- Keine GT-8-Implementierung (Partial Residual) — dokumentiert lassen; nur relevant, falls der Framework-Kern nach G1 Produktcharakter behält.
- Kein weiteres „E₀ lernt E₀" (Selbstvalidierung erhöht den geschlossenen Erkenntniskreislauf, den Phase 2/5 gerade aufbrechen sollen).

---

## 5. Reihenfolge und Aufwand

```
WP-0.1 → WP-0.2 → WP-0.3    ──┐  Evidenzrahmen vor erstem G1-Lauf
             WP-0.4          ──┘  Statusinventur, noch kein Repo-Split
WP-1.1 (Packaging)          ──┐  parallelisierbar
WP-2.1 → WP-2.2 → WP-2.3    ──┤  Kernpfad (Priorität)
WP-2.4 (+ WP-2.5)           ──┘
        ↓
     Gate G1
        ↓
Phase 4a oder 4b → Phase 5 (WP-5.1 → WP-5.2/5.3)
WP-1.3 / WP-1.4: jederzeit einschiebbar (klein, unabhängig)
```

Grobschätzung: Phase 0 ≈ 1–3 Commits, Phase 1 ≈ 4–6, Phase 2 ≈ 5–8, Phase 4 ≈ 2–4, Phase 5 ≈ 3–5. Die Schätzung wird nach WP-0.4 neu kalibriert.

---

## 6. Erfolgskriterien des Gesamtplans (Horizont ~3 Monate)

1. **G1 ist entschieden** — mit Zahlen, nicht mit Meinung.
2. **README-/Paper-Claims == Ledger-IDs == Benchmark-Belege** (kein strategischer Claim ohne Scope und Artefakt).
3. **Erste externe Nutzung** der lean-Pakete sichtbar (Traffic/Clones/Issues/Installs).
4. **Ein extern eingereichtes Paper** (WP-5.2) — der erste Schritt aus dem Selbstvalidierungs-Kreislauf.

---

## 7. Pflege

- Nach jedem Commit: WP-Status-Spalte hier aktualisieren (offen → in Arbeit → done C{N}).
- Nach Gate G1: Ergebnisblock unter Phase 3 eintragen + `bootstrap.json → strategic_plan.gate_g1` setzen.
- Claim-Status ändert sich ausschließlich im Evidence Ledger und nur zusammen mit neuer Evidenz.
- Planänderungen sind erlaubt, aber explizit: neue Zeile im folgenden Änderungslog.

| Datum | Änderung |
|---|---|
| 2026-07-28 | WP-0.3 abgeschlossen: `E0-G1-v1` präregistriert vier Domänenfamilien × drei Größen × 30 Holdout-Seeds, gleiche Interaktionsbudgets, fünf kausale Ablationen, faire Baselines, Statistik-, Fehler- und Freeze-Regeln; Holdout noch nicht ausgeführt |
| 2026-07-27 | v1 erstellt (Strategie-Pivot nach Nützlichkeits-Reviews) |
| 2026-07-28 | WP-0 Evidence Reconciliation ergänzt; vorhandene C270/C273-Benchmarks, BPI2017 und Reproduktion berücksichtigt; Historisierungs- vs. Geometrie-Skalierung sowie Overlay- vs. Phasenursache getrennt |
