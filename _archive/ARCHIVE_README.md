# _archive/ — Eingefrorener Code

**Stand:** 2026-03-19

Dieser Ordner enthält Code und Daten aus früheren Entwicklungsphasen des E₀-Frameworks.
Er wird **nicht mehr aktiv entwickelt** und dient ausschließlich als Referenz.

## Inhalt

| Ordner | Was | Warum eingefroren |
|---|---|---|
| `keimzelle/` | Multi-Agent Ko-Kognitions-System (3 LLM-Knoten, Server, UI) | Orchestrierung war Sackgasse — zu aufwändig, parallele Monologe |
| `middleware/` | E₀-Middleware (Decoding Guards, Instrumentation) | Nicht mehr benötigt für Controller-Architektur |
| `server/` | Root-Level Server-Dateien (e0_start.py, configs, etc.) | Waren für Keimzelle-Server, nicht für Controller |
| `ui/` | HTML-UIs (v3, v4, v5) und Shell-Skripte (.bat, .ps1) | Legacy-Interfaces |
| `scripts/` | Diagnose-/Test-Skripte (_check.py, _test_*.py, etc.) | Bezogen sich auf alte Architektur |
| `docs/` | Alte Projektdokumentation und Analysedokumente | Überholt durch E0_CONTROLLER_STATUS.md |
| `data/` | SQLite-DB, Experiments, Sessions, History, Profiles | Daten der Keimzelle-Phase |

## Aktive Entwicklung

Geht weiter in:
- `e0_controller/` — Neuer deterministischer E₀ Controller
- `e0_core/` — Kanonische Primitives (Read-Only-Referenz)
- `canon/` — Kanonische Texte (unveränderlich)
