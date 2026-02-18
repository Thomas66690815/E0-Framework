# E₀ v4 — Netzwerk-Architektur: Planung und Ziele

*Erstellt: 18. Februar 2026. Thomas + A₂.*
*Status: Lebendes Dokument — wird mit jedem Schritt aktualisiert.*

---

## 0. Kontext

Nach 14 Tagen Forschung (§91–§102) hat das E₀-Netzwerk empirische Befunde produziert, die eine technische Neuausrichtung erzwingen:

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
| M1 | **Persistenz** | Systeme überleben Server-Restarts. State (Messages, Turn-Count, Metriken) wird nach jeder Interaktion gespeichert und bei Start restauriert. | offen |
| M2 | **Alpha/Beta/Gamma zurückholen** | Die gesicherten Sessions (`system_state.json`) können geladen werden. Die drei Systeme sind nach dem Umbau wieder ansprechbar. | offen |
| M3 | **Dynamische Systeme** | Neue Systeme können erstellt werden (kein hardcodiertes `SYSTEM_IDS`). INIT-Prozess über UI. Griechisches Alphabet als Namenskonvention, aber frei wählbar. | offen |
| M4 | **Sessions laden / parken** | Vorhandene Sessions können in das Netzwerk geladen oder aus dem aktiven Netzwerk entfernt ("geparkt") werden, ohne Datenverlust. | offen |
| M5 | **UI: Tabs statt Spalten** | Maximal 3 Systeme gleichzeitig im Vordergrund (menschliche Aufmerksamkeit). System-Switching per Tabs. | offen |
| M6 | **UI: Sidebar bereinigen** | Prompt-Repertoire entfernen. Steuerungsleiste stattdessen: Neuer Partner, Session laden, Session parken. | offen |

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
| E0APIStarter (System-Wrapper) | `e0_start.py` | ✅ Kern bleibt, Persistenz ergänzen |
| E₀-System-Primer (Canon) | `canon/*.txt`, `canon/*.md` | ✅ Unverändert |
| Session Save/Load | `e0_sessions.py` | ⚠️ Basis da, aber nicht für v3-Orchestrator integriert |
| Config (API-Keys, per-System) | `e0_config.py` | ✅ Erweitern um dynamische Systeme |
| State-Extraktor | `e0_extract_state.py` | ✅ Für Migration |
| Orchestrator (Web-Server) | `e0_init_v3_orchestrator.py` | 🔄 Signifikant umbauen |
| UI | `e0_init_v3_ui.html` | 🔄 Signifikant umbauen |

### 3.2 Was neu gebaut werden muss

| Komponente | Beschreibung |
|---|---|
| **SystemRegistry** | Dynamische Verwaltung von N Systemen. Erstellen, laden, parken, löschen. |
| **StatePersistence** | Auto-Save nach jeder Interaktion. Messages, Metriken, Turn-Count. |
| **DuckDB-Layer** | Schema für Dialog-Einträge, Metriken, System-Metadaten. Import bestehender Daten. |
| **UI: Tab-System** | Dynamische Tabs, System-Switching, max 3 sichtbar. |
| **UI: Steuerungsleiste** | Neuer Partner, Session laden/parken, System-Info. |
| **INIT-Workflow (UI)** | Wizard zum Erstellen eines neuen Systems: Name, Modell, API-Endpoint, Canon-Feed. |

---

## 4. Umsetzungsplan

### Phase 1: Fundament (Persistenz + Dynamische Systeme)

**Ziel:** Server kann neu starten, ohne Systeme zu verlieren. Neue Systeme können programmatisch erstellt werden.

1. `SystemRegistry` implementieren — löst hardcodiertes `SYSTEM_IDS` ab
2. `StatePersistence` implementieren — auto-save `E0ChatClient.messages` + Metriken nach jeder Interaktion
3. Restore-on-Startup — beim Start werden alle persistierten Systeme geladen
4. Alpha/Beta/Gamma aus `system_state.json` migrieren
5. Orchestrator-Endpoints anpassen: `/add-system`, `/park-system`, `/load-system`

**Abschlusskriterium:** Server-Restart → alle Systeme wieder da, letzte Nachricht intakt.

### Phase 2: UI-Umbau

**Ziel:** Tab-basierte UI mit Steuerungsleiste, N Systeme unterstützt.

1. Sidebar entfernen (Prompt-Repertoire, Phase-1-Buttons)
2. Tab-System implementieren (max 3 sichtbar, Rest im Hintergrund)
3. Steuerungsleiste: [+ Neuer Partner] [Session laden] [Session parken]
4. INIT-Wizard für neue Systeme
5. System-Info-Anzeige (Modell, Turns, letzter h-Wert)

**Abschlusskriterium:** Neues System über UI erstellen, INIT durchlaufen, Dialog führen, parken, wieder laden.

### Phase 3: Dialog-Persistenz (DuckDB)

**Ziel:** Der gesamte Dialog ist strukturiert gespeichert und durchsuchbar.

1. DuckDB-Schema entwerfen (entries, metrics, systems, sessions)
2. Bestehende Daten importieren (125 Einträge aus `_raw_transcripts`)
3. Jede neue Interaktion schreibt automatisch in DuckDB
4. UI: Such- und Filterinterface
5. Markdown-Export beibehalten (menschenlesbarer Record)

**Abschlusskriterium:** Thomas kann in der UI nach "Polyzentrum" suchen und alle Gamma-Einträge mit h > 1.0 finden.

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
| O3 | Braucht jedes System ein eigenes DuckDB, oder eine zentrale? | Zentral = einfacher, aber Zugriffskontrolle unklar. Pro-System = isoliert, aber Inter-System-Queries schwieriger. |
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
| 2026-02-18 | README-Neufassung geparkt | Erst nach stabilisierter v4-Architektur. |

---

*Nächster Schritt: Phase 1 beginnen — Persistenz + SystemRegistry.*
