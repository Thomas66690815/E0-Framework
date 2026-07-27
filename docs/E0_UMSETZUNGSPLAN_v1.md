# E₀ Umsetzungsplan v1 — Konsolidierung & Entscheidung

**Status:** Verbindlich (ARC-M, ab C320)
**Datum:** 2026-07-27
**Grundlage:** [E0_PAPER_AUDIT_v1.md](E0_PAPER_AUDIT_v1.md), [E0_STRUCTURAL_CONTRADICTIONS_v1.md](E0_STRUCTURAL_CONTRADICTIONS_v1.md) (SC-11), [C185_TRAFFIC_VALIDATION_REPORT_v1.md](research/C185_TRAFFIC_VALIDATION_REPORT_v1.md), C319-Befund (rein konstruktive Interferenz bei typischen Gewichten)
**Pflege:** WP-Status in diesem Dokument aktualisieren; Gate-Ergebnisse zusätzlich in `bootstrap.json → strategic_plan`.

---

## 0. Kurzfassung

Der belegte Wert von E₀ konzentriert sich auf die Historisierung (~600 LOC, `lean/reliability_memory`). Der Interferenz-/Geometrie-Layer hat theoretische Substanz, aber unbewiesenen praktischen Mehrwert (+4 % nur mit hartem Gate; keine Skalierungsbelege über N≈50; keine externen Baselines). Konsequenz:

1. **Produktisieren**, was trägt (lean-Pakete).
2. **Ein Entscheidungsexperiment** statt weiterer Features: Skalierung + externe Baselines.
3. **Gate G1** entscheidet datenbasiert über die Zukunft des Geometrie-Layers.
4. **Feature-Freeze** für Layer 5–14 bis G1.

Geschätzter Gesamtumfang bis Phase 5: **15–25 Commits**.

---

## 1. Ausgangslage

| Kategorie | Befund | Quelle |
|---|---|---|
| **Belegt** | Historisierung ist der dominante Mechanismus (6× bestätigt) | bootstrap working_principles, C262 |
| **Belegt** | Trap-Navigation ohne Karte (100 % vs. 0 % Greedy), volle Anpassung an Nicht-Stationarität (F2) | benchmark_gridworld, C272 |
| **Belegt** | Traffic: 2,3× Durchsatz vs. BFS; Amplitude-Override nur gated (conf ≥ 0.85) +4 % über reine Historisierung, ungated netto negativ | C185 |
| **Widerlegt/geschwächt** | Destruktive Interferenz bei typischen Gewichten: rein konstruktiv, Auslöschung bräuchte Phasenlücke ~π (jenseits stabilen Rankings) | C319 |
| **Offen (existenziell)** | Skalierung > N≈50 (SC-11); Pfad-Enumeration O(paths) | Audit §6.3, SC-11 |
| **Fehlt** | Externe Baselines (Q-Learning, UCB, D*-Lite, …) | Audit §6.3.2 |
| **Fehlt** | Ablationen für Layer 5–14 (Dream, Sleep-Wake, Multiverse, Self-Graph, …) gegen simplere Alternativen | Audit §6.3.4 |
| **Bekannte Grenzen** | F3 (Branching ≥ 3), F4 (non-Markov Credit Assignment), River-City (stale memory −29 %), GT-8 (Partial Residual) | C272, C185, bootstrap |

---

## 2. Leitentscheidungen (ab sofort gültig)

- **L1 — Produkt vs. Forschung:** Produkt sind die lean-Pakete (`reliability_memory`, `structural_geometry`). Das Framework (`e0_controller/`, `server/`) ist Forschungsträger und Quellcode-Lieferant für lean-Extraktionen — kein Produkt.
- **L2 — Feature-Freeze Layer 5–14:** Reflexion, Multiverse, LLM-Integration-Ausbau, Observation, Dream, Entropy, Sleep-Wake, Curriculum, Communication, Session-Runner: nur noch Bugfixes. Entsperrung einzelner Mechanismen **nur per Ablation**: messbarer Mehrwert gegen eine simplere Alternative (z. B. periodischer Reset, k-means, Replay) auf ≥ 2 Domänen.
- **L3 — Plan-Bindung:** Jeder Commit ist einem Work Package (WP-x.y) zuordenbar. Kein WP → kein Commit (erst Plan bewusst ändern, dann arbeiten).
- **L4 — Claims-Disziplin:** Kein AGI-Framing. Positionierung: *„Lernender Kantenkosten-Speicher mit gated Lookahead für Graph-Navigation unter Unsicherheit."* Jeder README-Claim verweist auf ein Benchmark-Artefakt.

---

## 3. Phasen und Work Packages

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
| **WP-2.1** | Benchmark-Harness: Domänengeneratoren (Trap-Grids inkl. TRAP_GRID-Redesign, nicht-stationäre Graphen, skalierende Topologien N = 100/500/1000), festes Protokoll (Seeds, Episodenzahl, Metriken: Zielrate, Schritte, Regret, Wall-Time) | Ein Befehl erzeugt reproduzierbar alle Domänen + Rohdaten | offen |
| **WP-2.2** | Externe Baselines: tabulares Q-Learning (ε-greedy), UCB1 auf Kanten, D*-Lite (mit Karte, als obere Referenz), Random-Restart-Greedy. Standard-Hyperparameter aus der Literatur, dokumentiert — keine geschwächten Strohmänner | Jede Baseline läuft auf allen WP-2.1-Domänen | offen |
| **WP-2.3** | E₀-Ablationsvarianten: (a) Historization-only (lean core), (b) + Amplitude gated 0.85, (c) + Amplitude voll | Alle drei auf allen Domänen, identisches Protokoll | offen |
| **WP-2.4** | Skalierungslauf + Report `docs/research/E0_DECISION_BENCHMARK_v1.md` — beide Richtungen berichten (Konvention aus C185 fortführen) | Report mit vollständigen Tabellen; Gate-G1-Kriterien darauf anwendbar | offen |
| **WP-2.5** | BPI2017-Realdaten-Validierung (aus IB-2 promoviert) als zweite Evidenzquelle neben synthetischen Domänen | Accuracy-Vergleich gegen Ground Truth im Report | offen |

### Phase 3 — Gate G1 (Entscheidung, vorab festgelegte Kriterien)

Die Kriterien stehen **vor** dem Experiment fest, um Post-hoc-Rationalisierung auszuschließen:

- **G1-A (Geometrie-Layer):** Behält Amplitude/Geometrie ≥ 10 % Mehrwert über Historization-only auf ≥ 2 Domänenklassen bei N ≥ 100 → Geometrie bleibt Produktbestandteil (→ Phase 4a). Sonst → Forschungs-Freeze (→ Phase 4b): Papers bleiben, Code wird nicht weiter produktisiert.
- **G1-B (Historisierung vs. Baselines):** Ist Historization-only kompetitiv (≥ Median der Baselines) → Positionierung halten. Liegen Q-Learning/UCB durchgängig vorn → lean-Pakete repositionieren als *leichtgewichtige, erklärbare, trainingsfreie Alternative* mit dokumentierten Trade-offs; keine Überlegenheits-Claims.
- **Dokumentation:** Gate-Entscheid mit Datum, Zahlen und Begründung hier **und** in `bootstrap.json → strategic_plan.gate_g1`.

### Phase 4a / 4b — je nach Gate

- **4a (Geometrie besteht):** `structural_geometry` voll produktisieren (Packaging-Feinschliff, Doku, weitere Game-AI-Beispiele), Geometrie-Paper extern einreichen.
- **4b (Geometrie besteht nicht):** Geometrie-Code einfrieren (bleibt im Repo, klar als Forschung markiert); volle Energie auf `reliability_memory`-Adoption.

### Phase 5 — Außendarstellung und Reproduzierbarkeit

| WP | Inhalt | Akzeptanzkriterium | Status |
|---|---|---|---|
| **WP-5.1** | README-Umbau: Claims an Benchmark-Artefakte koppeln, AGI-Blueprint nach `_archive/`, „When to use"-Sektion mit ehrlichen Alternativen (Q-Learning etc.) | Kein Claim ohne Beleg-Link | offen |
| **WP-5.2** | Kurzes eigenständiges Paper (6–10 Seiten): nur Historisierungs-Mechanismus + F3/F4-Grenzen + G1-Benchmark-Ergebnisse. Extern einreichen (arXiv/Workshop). **Nutzer-Entscheidung bei Einreichung** | Eingereichtes Manuskript | offen |
| **WP-5.3** | Reproduktionsprotokoll (Audit S3): ein Befehl reproduziert alle Benchmark-Tabellen des Reports | `README`-Abschnitt „Reproduce our numbers" | offen |

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
WP-1.1 (Packaging)          ──┐  parallelisierbar
WP-2.1 → WP-2.2 → WP-2.3    ──┤  Kernpfad (Priorität)
WP-2.4 (+ WP-2.5)           ──┘
        ↓
     Gate G1
        ↓
Phase 4a oder 4b → Phase 5 (WP-5.1 → WP-5.2/5.3)
WP-1.3 / WP-1.4: jederzeit einschiebbar (klein, unabhängig)
```

Grobschätzung: Phase 1 ≈ 4–6 Commits, Phase 2 ≈ 5–8, Phase 4 ≈ 2–4, Phase 5 ≈ 3–5. Gesamt 15–25 Commits.

---

## 6. Erfolgskriterien des Gesamtplans (Horizont ~3 Monate)

1. **G1 ist entschieden** — mit Zahlen, nicht mit Meinung.
2. **README-Claims == Benchmark-Belege** (kein Claim ohne Artefakt).
3. **Erste externe Nutzung** der lean-Pakete sichtbar (Traffic/Clones/Issues/Installs).
4. **Ein extern eingereichtes Paper** (WP-5.2) — der erste Schritt aus dem Selbstvalidierungs-Kreislauf.

---

## 7. Pflege

- Nach jedem Commit: WP-Status-Spalte hier aktualisieren (offen → in Arbeit → done C{N}).
- Nach Gate G1: Ergebnisblock unter Phase 3 eintragen + `bootstrap.json → strategic_plan.gate_g1` setzen.
- Planänderungen sind erlaubt, aber explizit: neue Zeile im folgenden Änderungslog.

| Datum | Änderung |
|---|---|
| 2026-07-27 | v1 erstellt (Strategie-Pivot nach Nützlichkeits-Reviews) |
