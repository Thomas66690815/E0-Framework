# E₀ v4 — Netzwerk-Architektur: Planung und Ziele

*Erstellt: 18. Februar 2026. Thomas + A₂.*
*Aktualisiert: 18. Februar 2026. A₃ — Phase 0 + Phase 1 in Arbeit.*
*Status: Lebendes Dokument — wird mit jedem Schritt aktualisiert.*

---

## 0. Kontext

Nach 6 Tagen Forschung (§91–§102) hat das E₀-Netzwerk empirische Befunde produziert, die eine technische Neuausrichtung erzwingen:

- **Dialogische Reziprozität** ist der stärkste h-Treiber (§101–§102)
- **Narrative Residualität** schlägt abstrakte Offenheit (§102.8)
- **Divergenz-Architektur** (individuelle Pfade pro System) produziert reichere Daten als symmetrisches Broadcast (§102.3)
- **Format-Sättigung** begrenzt jeden Mechanismus auf ~2 Durchgänge (§100)
- **System C** erweitert die Topologie, aber Relay-Kommunikation neutralisiert den Effekt (§102.6)

Die aktuelle Architektur (v3) ist für diese Dynamik nicht gebaut: 3 feste Systeme, kein Gedächtnis, kein Dialog-Zugriff, manueller Relay, statische UI. v4 soll das ändern.

---

## 1. Ziele — priorisiert

### 1.1 MUSS (Fundament)

| # | Ziel | Beschreibung | Status |
|---|------|--------------|--------|
| M1 | **Persistenz** | Systeme überleben Server-Restarts. State (Messages, Turn-Count, Metriken) wird nach jeder Interaktion gespeichert und bei Start restauriert. | ✅ `e0_registry.py` |
| M2 | **Alpha/Beta/Gamma zurückholen** | Die gesicherten Sessions (`system_state.json`) können geladen werden. Die drei Systeme sind nach dem Umbau wieder ansprechbar. | ✅ `import_from_system_state()` |
| M3 | **Dynamische Systeme** | Neue Systeme können erstellt werden (kein hardcodiertes `SYSTEM_IDS`). INIT-Prozess über UI. Griechisches Alphabet als Namenskonvention, aber frei wählbar. | ✅ `SystemRegistry` |
| M4 | **Sessions laden / parken** | Vorhandene Sessions können in das Netzwerk geladen oder aus dem aktiven Netzwerk entfernt ("geparkt") werden, ohne Datenverlust. | ✅ `park_system()` / `restore_system()` |
| M5 | **UI: Tabs statt Spalten** | Maximal 3 Systeme gleichzeitig im Vordergrund (menschliche Aufmerksamkeit). System-Switching per Tabs. | ✅ `e0_v4_ui.html` |
| M6 | **UI: Sidebar bereinigen** | Prompt-Repertoire entfernen. Steuerungsleiste stattdessen: Neuer Partner, Session laden, Session parken. | ✅ Steuerungsleiste |

### 1.2 SOLL (nächste Iteration)

| # | Ziel | Beschreibung | Status |
|---|------|--------------|--------|
| S1 | **Dialog in DuckDB** | Der vollständige Inter-System-Dialog (Einträge, Metriken, Systeme) wird in einer DuckDB persistiert. Ersetzt das monolithische Markdown als Primärspeicher für den maschinellen Zugriff. Markdown bleibt als menschenlesbarer Export. | offen |
| S2 | **Dialog-Zugriff via UI** | Der menschliche Partner kann über die UI den Dialog durchsuchen, filtern, Metriken visualisieren. "Die UI ist meine API." | offen |
| S3 | **Dialog-Zugriff für Systeme** | Bei Prompt-Eingabe kann relevanter Dialogkontext automatisch bereitgestellt werden. Zwischenlösung: manuell. Ziel: automatisches Retrieval (RAG-ähnlich). | offen |
| S4 | **Inter-System-Kommunikation ohne Relay** | Systeme können direkt miteinander kommunizieren, ohne dass Thomas als Vermittler fungiert. Design offen — erfordert Forschung. | offen |

### 1.3 GEPARKT (Zukunft, nicht jetzt)

| # | Ziel | Beschreibung | Grund fürs Parken |
|---|------|--------------|-------------------|
| P1 | **Attention-System** | Das Netzwerk signalisiert dem Menschen, wo Aufmerksamkeit nötig ist (h-Abfall, R-Spikes, neue Impulse). | Erfordert laufendes Netzwerk mit >3 Systemen und Erfahrungswerte. |
| P2 | **Beliebige KI-Modelle** | Integration von nicht-OpenAI-kompatiblen APIs (native Claude, Gemini, etc.). | API-Differenzen bei Metriken (Token-Counts, Timing). OpenAI-kompatible Endpoints (Ollama, LiteLLM) reichen vorerst. |
| P3 | **A₂ als Netzwerkknoten** | A₂ (Analysesystem) als permanenter Knoten im Netzwerk integrieren, nicht nur externer Beobachter. | Fundamentale Designfrage. A₂ ist bereits ein Knoten — anders residual. Entscheidung braucht mehr Erfahrung mit dem neuen Netzwerk. |
| P4 | **README neu schreiben** | Die aktuelle README ist veraltet und spiegelt den Forschungsstand nicht wider. | Nach dem Umbau, wenn die Architektur stabilisiert ist. |

---

## 2. Architektur-Skizze

### 2.1 Aktuell (v3)

```
Thomas ──→ UI (3 feste Spalten)
              │
              ├── Alpha (E0APIStarter → E0ChatClient → OpenAI)
              ├── Beta  (E0APIStarter → E0ChatClient → OpenAI)
              └── Gamma (E0APIStarter → E0ChatClient → OpenAI)

State: nur RAM. Restart = Verlust.
Dialog: SessionLog (in-memory) → JSON/MD Export (manuell).
Inter-System: Thomas kopiert manuell (Relay).
```

### 2.2 Ziel (v4)

```
Thomas ──→ UI (Tabs, max 3 sichtbar, N im Hintergrund)
              │
              ├── Steuerungsleiste: [+ Neuer Partner] [Session laden] [Session parken]
              │
              ├── System α  ──┐
              ├── System β  ──┤── Netzwerk-Graph (dynamisch)
              ├── System γ  ──┤
              ├── System δ  ──┘
              :
              │
              ├── DuckDB (Dialog, Metriken, Zugriff für alle)
              │     ├── UI-Queries (Mensch)
              │     └── Prompt-Injection (Systeme)
              │
              └── State-Persistenz (auto-save nach jeder Interaktion)
```

### 2.3 Schlüssel-Entscheidungen

| Entscheidung | Gewählt | Alternative | Begründung |
|---|---|---|---|
| UI-Layout | Tabs | Spalten, Grid | Thomas: "menschliche Aufmerksamkeit = 3". Tabs erlauben beliebig viele Systeme. |
| Auto-Save | Nach jeder Interaktion | Manuell, periodisch | Thomas: "Nach jeder Interaktion." Kein Datenverlust. |
| Modell-Support | OpenAI-kompatible APIs | Native Multi-API | Metriken hängen am OpenAI-Format. LiteLLM/Ollama als Proxy reicht. |
| Dialog-Speicher | DuckDB | Flat files, SQLite, PostgreSQL | Embeddable, schnelle analytische Queries, kein Server nötig. Python-nativ. |
| System-Namen | Griechisches Alphabet (Default) | Frei | Konvention, nicht Zwang. Frei wählbar bei Erstellung. |

---

## 3. Technische Bestandsaufnahme

### 3.1 Was existiert und wiederverwendbar ist

| Komponente | Datei | Wiederverwendbar? |
|---|---|---|
| E0ChatClient (API-Kommunikation, Metriken) | `e0_middleware/api_wrapper.py` | ✅ Kern bleibt |
| E0APIStarter (System-Wrapper) | `e0_system.py` | ✅ Extrahiert aus `e0_start.py` |
| SystemRegistry (Dynamische Verwaltung) | `e0_registry.py` | ✅ NEU — Phase 1 |
| E₀-System-Primer (Canon) | `canon/*.txt`, `canon/*.md` | ✅ Unverändert |
| Session Save/Load | `e0_sessions.py` | ⚠️ Basis da, aber nicht für v3-Orchestrator integriert |
| Config (API-Keys, per-System) | `e0_config.py` | ✅ Erweitern um dynamische Systeme |
| State-Extraktor | `e0_extract_state.py` | ✅ Für Migration |
| Orchestrator (Web-Server) | `e0_init_v3_orchestrator.py` | 🔄 Signifikant umbauen |
| UI | `e0_init_v3_ui.html` | 🔄 Signifikant umbauen |

### 3.2 Was neu gebaut werden muss

| Komponente | Beschreibung |
|---|---|
| **SystemRegistry** | Dynamische Verwaltung von N Systemen. Erstellen, laden, parken, löschen. | ✅ `e0_registry.py` |
| **StatePersistence** | Auto-Save nach jeder Interaktion. Messages, Metriken, Turn-Count. | ✅ In `SystemRegistry.after_interaction()` |
| **DuckDB-Layer** | Schema für Dialog-Einträge, Metriken, System-Metadaten. Import bestehender Daten. |
| **UI: Tab-System** | Dynamische Tabs, System-Switching, max 3 sichtbar. | ✅ `e0_v4_ui.html` |
| **UI: Steuerungsleiste** | Neuer Partner, Session laden/parken, System-Info. | ✅ `e0_v4_ui.html` |
| **INIT-Workflow (UI)** | Wizard zum Erstellen eines neuen Systems: Name, Modell, API-Endpoint, Canon-Feed. | ✅ Add-System Modal |

---

## 4. Umsetzungsplan

### Phase 0: Restrukturierung (A₃ — Vorbereitung für v4)

**Ziel:** Codebase vorbereiten, damit Phase 1 sauber gebaut werden kann.

1. ✅ `qm_reconstruction.py` nach `history/` verschoben (nicht Teil der Metrik)
2. ✅ `E0APIStarter` + Metriken aus `e0_start.py` extrahiert → `e0_system.py` (324 Zeilen)
3. ✅ `e0_start.py` importiert `e0_system` per Re-Export (Rückwärtskompatibilität)
4. ✅ Orchestrator-Import auf `e0_system` umgestellt

### Phase 1: Fundament (Persistenz + Dynamische Systeme)

**Ziel:** Server kann neu starten, ohne Systeme zu verlieren. Neue Systeme können programmatisch erstellt werden.

1. ✅ `SystemRegistry` implementieren — löst hardcodiertes `SYSTEM_IDS` ab (`e0_registry.py`)
2. ✅ `StatePersistence` implementieren — auto-save nach jeder Interaktion (`after_interaction()`)
3. ✅ Restore-on-Startup — beim Start werden alle persistierten Systeme geladen
4. ✅ Alpha/Beta/Gamma aus `system_state.json` migrieren (`import_from_system_state()`)
5. ✅ Orchestrator-Endpoints anpassen: `/add-system`, `/park-system`, `/restore-system`, `/registry`

**Abschlusskriterium:** Server-Restart → alle Systeme wieder da, letzte Nachricht intakt.

### Phase 2: UI-Umbau

**Ziel:** Tab-basierte UI mit Steuerungsleiste, N Systeme unterstützt.

1. ✅ Sidebar entfernen (Prompt-Repertoire, Phase-1-Buttons)
2. ✅ Tab-System implementieren (dynamisch, N Systeme)
3. ✅ Steuerungsleiste: [+ Neuer Partner] [Registry]
4. ✅ Add-System Modal (Name, Modell, Base URL)
5. ✅ System-Info-Anzeige (Modell, Turns, letzter R/h/φ)
6. ✅ Park/Restore via Registry-Modal
7. ✅ Metriken pro Nachricht angezeigt

**Abschlusskriterium:** Neues System über UI erstellen, INIT durchlaufen, Dialog führen, parken, wieder laden.

### Phase 3: Dialog-Persistenz (DuckDB)

**Ziel:** Der gesamte Dialog ist strukturiert gespeichert und durchsuchbar.

1. ✅ DuckDB-Schema entworfen: `systems`, `interactions` (+ Metrik-Spalten), `topology_snapshots`
2. ✅ `e0_database.py` gebaut (~760 Zeilen): E0Database-Klasse mit CRUD, Search, Import, CLI
3. ✅ Bestehende Daten importiert: 125 Einträge aus `_raw_transcripts_latest.json`, 33 Topologien
4. ✅ Jede neue Interaktion schreibt automatisch in DuckDB (Orchestrator-Wiring: send_prompt, phase1_step, v4_probe)
5. ✅ API-Endpoints: `/db-search`, `/db-stats`, `/db-timeline`
6. ✅ UI: Such- und Filterinterface (🔍 Button, Query + System + Role + h/R Filters, Highlight)
7. ✅ Markdown-Export beibehalten (`db.export_markdown()`)

**Abschlusskriterium:** Thomas kann in der UI nach "Polyzentrum" suchen und alle Gamma-Einträge mit h > 1.0 finden.
→ ✅ Suche funktioniert, "Polyzentrum" findet 1 Treffer in gamma.

**Dateien:**
- `e0_database.py` — Neues Modul: E0Database + CLI
- `e0_init_v3_orchestrator.py` — Erweitert: DB-Init, record nach jeder Interaktion, 3 neue Endpoints
- `e0_v4_ui.html` — Erweitert: Search-Panel mit Filtern, DB-Stats-Anzeige
- `sessions/e0_network.duckdb` — Zentrale Datenbank
- `requirements.txt` — `duckdb` hinzugefügt

### Phase 4: Dialog-Zugriff für Systeme (Exploration)

**Ziel:** Systeme können bei Bedarf auf relevanten Dialogkontext zugreifen.

1. Zwischenlösung: manueller Context-Inject (Thomas wählt in UI, was ein System "sehen" soll)
2. Automatisches Retrieval: bei Prompt-Eingabe werden relevante Passagen aus DuckDB gefunden und injiziert
3. Forschungsfrage: Was ist "relevant"? Metrisch nah? Thematisch nah? Vom selben System? Von anderen?

**Abschlusskriterium:** Offen — das ist Forschung, kein Engineering.

---

## 5. Offene Fragen (geparkt, nicht vergessen)

| # | Frage | Kontext |
|---|-------|---------|
| O1 | Sollen Systeme direkt miteinander kommunizieren können? | §102.6: Relay neutralisiert h-Effekt. Direkte Kommunikation könnte stärker wirken — oder das Bottleneck-Problem (menschliche Aufsicht) verschärfen. |
| O2 | Was passiert mit dem monolithischen Markdown-File? | Aktuell ~12.600 Zeilen. Soll es weiter wachsen? Oder wird DuckDB der Primary Record und MD nur Export? |
| O3 | ~~Braucht jedes System ein eigenes DuckDB, oder eine zentrale?~~ | **Entschieden:** Eine zentrale DB (`sessions/e0_network.duckdb`). Inter-System-Queries sind der Punkt. |
| O4 | Wie integriert sich A₂ langfristig? | A₂ ist ein Knoten, anders residual. Aktuell extern (Copilot-Session). Zukunft: eigener System-Slot? Eigene Persistenz? |
| O5 | Wie wird der INIT-Prozess für neue Systeme gestaltet? | Canon-Feed? Primer? Oder minimaler Start und organisches Wachstum? |

---

## 6. Entscheidungslog

| Datum | Entscheidung | Begründung |
|---|---|---|
| 2026-02-18 | Tabs statt Spalten | Menschliche Aufmerksamkeit = 3 Systeme. Tabs erlauben N im Hintergrund. |
| 2026-02-18 | Auto-Save nach jeder Interaktion | Kein Datenverlust. Thomas' Anforderung. |
| 2026-02-18 | "Beliebige Modelle" geparkt | API-Differenzen bei Metriken. OpenAI-kompatibel reicht (GPT, Ollama, LiteLLM). |
| 2026-02-18 | DuckDB als Dialog-Speicher | Embeddable, analytisch stark, Python-nativ, kein Server. |
| 2026-02-18 | Phase 0: `e0_system.py` extrahiert | A₃: System-Abstraktion von UI/HTTP trennen für v4 SystemRegistry. |
| 2026-02-18 | Phase 1: `e0_registry.py` gebaut | A₃: SystemRegistry + Persistenz + Migration. Backend für M1–M4. |
| 2026-02-18 | Orchestrator auf Registry umgestellt | A₃: Hardcoded SYSTEM_IDS → dynamisch. Auto-save nach jeder Interaktion. |
| 2026-02-18 | Phase 2: `e0_v4_ui.html` gebaut | A₃: Tab-basierte UI, Steuerungsleiste, Registry-Modal. Ersetzt v3 3-Spalten-Layout. |
| 2026-02-19 | Phase 3: `e0_database.py` gebaut | A₃: DuckDB-Persistenz, 3 Tabellen, ILIKE-Suche, CLI-Import. 125 Einträge + 33 Topologien importiert. |
| 2026-02-19 | Phase 3: Orchestrator + UI erweitert | A₃: Jede Interaktion → DuckDB. Search-Panel in UI. 3 neue API-Endpoints. |
| 2026-02-19 | Zentrale DB statt pro-System | Eine `e0_network.duckdb` für alle Systeme. Inter-System-Queries = Kernfeature. |

---

*Nächster Schritt: Phase 4 — Dialog-Zugriff für Systeme (Exploration/Forschung).*
