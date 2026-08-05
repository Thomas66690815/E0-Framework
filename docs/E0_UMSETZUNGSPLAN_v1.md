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
| **WP-0.4** | Archiv-/Repo-Statusinventur ohne Verschieben: active, research, frozen, superseded, archive-candidate | Jede Top-Level-Komponente und strategische Doku hat Status und Nachfolger; Split-Entscheidung bleibt bis G1 vertagt | done C323 |

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
| **WP-2.1** | Bestehende Harnesses (`benchmark_scaling`, `benchmark_sota`, `reproduce.py`) konsolidieren und um Domänengeneratoren erweitern: Trap-Grids inkl. TRAP_GRID-Redesign, nicht-stationäre Graphen, N = 100/500/1000; festes WP-0.3-Protokoll | Ein Befehl erzeugt reproduzierbar Domänen, Environment-Manifest und maschinenlesbare Rohdaten | done C324 |
| **WP-2.2** | Vorhandene Baselines auditieren und härten: A*/BFS/Q-Learning/ε-Greedy/Random; ergänzen um UCB1, D*-Lite (mit Karte, obere Referenz), Random-Restart-Greedy. Literaturparameter, identische Budgets, keine Strohmänner | Jede relevante Baseline läuft auf allen WP-2.1-Domänen; Abweichungen von Referenzverfahren dokumentiert | done C325 |
| **WP-2.3** | Kausalablation bei identischem Horizont/Budget: (a) Historisierung ohne Lookahead, (b) phasenfreier Lookahead, (c) Lookahead mit Θ=0, (d) U(1)-Phase, (e) vollständige Geometrie/Overlay-Konfiguration | Alle fünf Varianten auf allen Domänen; Phase, Lookahead, Pfadaggregation und Gate getrennt auswertbar | done C326 |
| **WP-2.4** | Skalierungslauf + Report `docs/research/E0_DECISION_BENCHMARK_v1.md` — positive und negative Resultate, Effektgrößen und Unsicherheit berichten | Vollständige Tabellen + Rohdatenbundle; Gate-G1-Kriterien darauf anwendbar | in Arbeit C328 (bounded Actions-Lauf bereit; Push/Dispatch ausstehend) |
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
| 2026-07-27 | v1 erstellt (Strategie-Pivot nach Nützlichkeits-Reviews) |
| 2026-07-28 | WP-0 Evidence Reconciliation ergänzt; vorhandene C270/C273-Benchmarks, BPI2017 und Reproduktion berücksichtigt; Historisierungs- vs. Geometrie-Skalierung sowie Overlay- vs. Phasenursache getrennt |
| 2026-07-28 | WP-0.3 abgeschlossen: `E0-G1-v1` präregistriert vier Domänenfamilien × drei Größen × 30 Holdout-Seeds, gleiche Interaktionsbudgets, fünf kausale Ablationen, faire Baselines, Statistik-, Fehler- und Freeze-Regeln; Holdout noch nicht ausgeführt |
| 2026-07-28 | WP-0.4 abgeschlossen: 27/27 getrackte Top-Level-Einträge und strategische Dokumente statusgeführt; keine Verschiebung, kein Löschen, kein neues Repo vor Gate G1 plus WP-1.1-Paketnachweis |
| 2026-07-28 | WP-2.1 abgeschlossen: vier exakte N-Domänengeneratoren, keyed Outcome-Schedule, reproduzierbares Development-Harness und 20 Schutz-/Invarianztests; 120/120 Development-Instanzen validiert. Keine Holdout-Ausführung, keine Methodenresultate, kein G1-Befund |
| 2026-07-28 | WP-2.2 abgeschlossen: acht protokollgebundene Adapter, einheitliche FAILURE-/Budget-Semantik, eingefrorene globale Konfigurationen und dokumentierte Abweichungen; 960/960 Development-Kompatibilitätsläufe, 0 Fehler. A*/D*-Lite explizit karteninformiert und vom G1-B-Comparator ausgeschlossen; BFS nur Test-Oracle. Kein Holdout-Zugriff, kein Methodenranking, kein G1-Befund |
| 2026-07-28 | WP-2.3 abgeschlossen: fünf protokollgebundene E₀-Ablationen, gemeinsame B–E-Kandidaten/Pfadfamilie/Override-Regel, eingefrorene globale Operationalisierung und 32 Schutz-/Kausaltests; 600/600 bounded Development-Kompatibilitätsläufe, 0 Path-Cap-Treffer. Vollbudget-Development-Lauf und Control-Auswahl bleiben WP-2.4. Kein Holdout-Zugriff, kein Ranking, kein G1-Befund |
| 2026-07-28 | WP-2.4 gestartet: wiederaufnehmbarer Fresh-Process-Runner für 1.560 Vollbudget-Development-Replikate, atomare Rohdaten-/Episodenartefakte, deterministische Control-Auswahl und gepaarte stratifizierte Bootstrap-Auswertung; 23 Schutz-/Artefakttests. Vollauf und Ergebnis-Freeze bleiben ausstehend. Kein Holdout-Zugriff, kein G1-Befund |
| 2026-07-29 | C327-Vollauf nach 196/1.560 Shards kontrolliert beendet: Timeouts wurden erst nach unbeschränkter Rückkehr bewertet, N=500-Replikate liefen stundenlang. Zwischenstand als Engineering-Evidenz separiert. C328 setzt 60-s-Episodenfristen an Entscheidungsgrenzen und 1.800-s-Replikatgrenze per killbarem Kindprozess durch; deterministische 240-Job-Actions-Matrix (6–7 Replikate/Job, max. 20 parallel) lokal vorbereitet. Kein Push, kein Holdout-Zugriff, kein G1-Befund |
| 2026-08-04 | WP-2.4 abgeschlossen (C332): korrigierter Vollauf 30526724307 (1.560/1.560 Replikate, 0 Infrastrukturfehler) verifiziert und vor Artefakt-Ablauf (13.08.) byte-identisch retiniert. Alle drei Development-Diagnostiken berichtet: G1-A 0,0 überall (Mechanismus-Neutralität, C331); Phasen-Attribution D vs. C 0,0; G1-B erstmals berichtet — A_HIST gesamt −0,199 [CI −0,206; −0,192] gegen Baseline-Median, nur wall_grid (+0,260) erfüllt die Familienkriterien. Kein Holdout-Zugriff, kein Gate-Ergebnis; Holdout-Lebenszyklus ist Nutzer-Entscheidung |
| 2026-08-05 | Gate G1-v1 GESCHLOSSEN (C333, Nutzer-Entscheidung): negativ auf Development-Evidenz, Holdout bleibt dauerhaft ungeöffnet, kein formales Holdout-PASS/FAIL. Konsequenzen: P4b Research-Freeze Geometrie, WP-2.5 ungeführt geschlossen, Override-Gate v2 dauerhaft geparkt, kein G1-v2. Abschlussbogen: WP-5.1 (C334), WP-5.2 (C335), WP-6.1/6.2 finales reliability_memory-Entscheidungsexperiment. Siehe docs/E0_G1_CLOSURE_v1.md |
| 2026-08-05 | WP-5.1 abgeschlossen (C334): README auf Ledger-gestützte Claims umgestellt — negatives G1-Ergebnis prominent, Geometrie als research-frozen markiert, Override-Gate- und Historisierungs-Claims auf Ledger-IDs gescoped, Zahlen korrigiert (7.166 Tests/181 Dateien), AGI-Blueprint nach _archive/canon/ verschoben. Keine Überlegenheits-Claims mehr im README |
| 2026-08-05 | WP-5.2 Entwurf abgeschlossen (C335): Abschluss-Paper PAPER11_CLOSURE_MANUSCRIPT_v1.md — präregistriertes Negativergebnis mit Mechanismus-Diagnose (Gate nie erreicht, Gradient-Regime, D≡E-Äquivalenz), wall_grid-Nische, Methodenteil (Preregistrierung/Ledger/Audit/Infrastruktur-Regress). EINREICHUNG = NUTZER-ENTSCHEIDUNG |
| 2026-08-05 | WP-6.1 abgeschlossen (C336): E0-WP6-RELMEM-v1 präregistriert — finales reliability_memory-Entscheidungsexperiment: 3 Regime (persistent/Drift/Kontext) × 30 gepaarte Seeds × 4 Arme (MEMORY/NO_MEMORY/STICKY/ORACLE), Shipped-Defaults ohne Tuning, eingefrorene PASS/FAIL-Kriterien inkl. Sticky-Vergleich (Verlieren gegen die Ein-Zeilen-Heuristik = FAIL). PASS→gepflegte Bibliothek, FAIL→Vollarchiv. WP-6.2-Ausführung erst nach Nutzer-Review des Designs |
| 2026-08-05 | WP-6-Design vom Nutzer FREIGEGEBEN; WP-6.2a (C337): Harness implementiert — seeded Umgebung, 4 Arme, eingefrorene Statistik/Kriterien, SHA-256-gebundenes Testobjekt, 22 No-Outcome-Contract-Tests. Kein präregistriertes Ergebnis in C337 |
| 2026-08-05 | WP-6.2b abgeschlossen (C338): 360/360 Replikate am Execution-Commit 16929d4e. VERDICT: PASS — MEMORY +48 % (R1), +54 % (R2), +11 % (R3) gegen NO_MEMORY; gegen STICKY +2,6 % (R1, Pflicht-Doku-Note „Sticky fängt den Großteil des Werts") und +5,0 % (R2, CI klar positiv — echter Differenzierer ist Drift-Robustheit); kontext-gekeyte STICKY schlägt kontextfreien Store in R3 um 19,2 % (Doku-Guidance: Kontext in den State-Key). Abschlussbogen endet im Zweig GEPFLEGTE BIBLIOTHEK. Artefakte mit SHA-256-Manifest retiniert; deterministischer Re-Run byte-identisch |
| 2026-08-05 | WP-5.2 v2 (C339): Abschluss-Paper um das ausgeführte WP-6-Ergebnis ergänzt (Abstract, Beitrag 6, §9, Limitations, Conclusion, Data Availability); arXiv-LaTeX-Quelle unter docs/papers/arxiv/PAPER11_v1/. NUTZER-ENTSCHEIDUNG: Einreichung bei arXiv (cs.AI) freigegeben; Upload läuft über den Account des Nutzers |
