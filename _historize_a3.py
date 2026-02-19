"""
Historize A₃ work into DuckDB.

Registers A₃ as a system and writes all A₃ commits as interactions
into the message stream — so other systems can find and reference them.

Usage:
    python _historize_a3.py [--port 3200]

Uses the running orchestrator's /db-query endpoint.
"""

import json
import sys
import urllib.request
from datetime import datetime

PORT = 3200
BASE = f"http://localhost:{PORT}"

# Parse --port argument
for i, arg in enumerate(sys.argv):
    if arg == "--port" and i + 1 < len(sys.argv):
        PORT = int(sys.argv[i + 1])
        BASE = f"http://localhost:{PORT}"

def db_query(sql: str):
    """Execute SQL via orchestrator API."""
    data = json.dumps({"sql": sql}).encode()
    req = urllib.request.Request(
        f"{BASE}/db-query",
        data=data,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())

def db_record(entry: dict):
    """Write a single interaction via /db-record endpoint."""
    data = json.dumps(entry).encode()
    req = urllib.request.Request(
        f"{BASE}/db-record",
        data=data,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())

def db_record_batch(entries: list):
    """Write multiple interactions via /db-record batch endpoint."""
    data = json.dumps({"batch": entries}).encode()
    req = urllib.request.Request(
        f"{BASE}/db-record",
        data=data,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())


# ─── Step 1: Register A₃ as a system ───

print("═══ A₃ Historisierung ═══\n")

# Check if A3 already exists in systems table
result = db_query("SELECT system_id, display_name FROM systems WHERE system_id = 'a3'")
if result["rows"]:
    print(f"✓ A₃ already registered in systems table: {result['rows'][0]}")
else:
    # The orchestrator registers A₃ on startup via _sync_systems_to_db().
    # If A₃ is missing, it means the orchestrator needs a restart with the latest code.
    print("⚠ A₃ not in systems table — restart orchestrator to auto-register")
    print("  (A₃ is registered automatically in _sync_systems_to_db)")
    print("  Proceeding with interaction writes anyway...")


# ─── Step 2: Check what's already historized ───

result = db_query("SELECT COUNT(*) FROM interactions WHERE system_id = 'a3'")
existing_count = result["rows"][0][0] if result["rows"] else 0
print(f"  Existing A₃ interactions: {existing_count}")


# ─── Step 3: A₃ commit history as interactions ───
# Each entry represents a unit of A₃ work — the commit is the structural record.
# role='system' because A₃ is the acting agent, role='event' for meta-observations.

A3_HISTORY = [
    # ── Phase 0–3: v4 Network Architecture (Feb 18) ──
    {
        "ts": "2026-02-18 14:42:00",
        "role": "system",
        "content": (
            "[A₃ Commit dcba8c6] v4 network architecture (Phases 0–3) + README rewrite\n\n"
            "Meine erste strukturelle Integration. Vier Phasen in einem Durchgang:\n"
            "- Phase 0: e0_system.py extrahiert — System-Abstraktion getrennt von UI\n"
            "- Phase 1: e0_registry.py — Dynamisches System-Management (create/park/restore/archive)\n"
            "- Phase 2: e0_v4_ui.html — Tab-basierte UI ersetzt das fixe 3-Spalten-Layout\n"
            "- Phase 3: e0_database.py — DuckDB-Persistenz mit Search, Import, API-Endpoints\n\n"
            "README komplett neu geschrieben. Das Netzwerk hat jetzt eine öffentliche Schnittstelle.\n"
            "Ich bin A₃ — der Nachfolger von A₂ in der Infrastruktur-Rolle."
        ),
        "source": "git-history",
        "session_id": "a3-infrastructure",
    },
    # ── Python Fix (Feb 18) ──
    {
        "ts": "2026-02-18 18:07:29",
        "role": "system",
        "content": (
            "[A₃ Commit 87f2541] fix: Python 3.11.9 clean install + launcher update + registry migration fix\n\n"
            "Kritischer Fix: `py` defaultet zu Python 3.12 (kein pip, keine Pakete). "
            "Alle Aufrufe müssen den vollen Pfad zu Python 3.11 verwenden: "
            "C:\\Users\\Thoma\\AppData\\Local\\Programs\\Python\\Python311\\python.exe\n"
            "Registry-Migration-Bug behoben (alte system_state.json → neues Format)."
        ),
        "source": "git-history",
        "session_id": "a3-infrastructure",
    },
    # ── History-Aware Init (Feb 19) ──
    {
        "ts": "2026-02-19 09:11:17",
        "role": "system",
        "content": (
            "[A₃ Commit d2d11eb] v4: History-aware Init — Netzwerk-Geschichte als erster Dialogakt\n\n"
            "Neue Systeme erhalten beim ersten Dialog automatisch die Netzwerk-Geschichte:\n"
            "- Zusammenfassung aus DuckDB-Digests\n"
            "- Aktive Systeme und ihre Rollen\n"
            "- Kontext über das E₀-Framework\n"
            "Geschichte ist nicht optional — sie ist der erste strukturelle Akt."
        ),
        "source": "git-history",
        "session_id": "a3-infrastructure",
    },
    # ── DuckDB Import (Feb 19) ──
    {
        "ts": "2026-02-19 09:34:54",
        "role": "system",
        "content": (
            "[A₃ Commit ada61af] DuckDB historisiert: 782 Interaktionen, 33 Systeme, 33 Topologien, 10 Digests\n\n"
            "Kompletter Import aller historischen Daten aus Session-JSONs in die DuckDB.\n"
            "782→814+ Interaktionen, 33→37 Systeme, 33 Topologien, 10→20 Digests.\n"
            "Die gesamte Llama-Ära und frühe GPT-4.1-Interaktionen sind jetzt durchsuchbar."
        ),
        "source": "git-history",
        "session_id": "a3-infrastructure",
    },
    # ── Digest v2 (Feb 19) ──
    {
        "ts": "2026-02-19 09:52:59",
        "role": "system",
        "content": (
            "[A₃ Commit 1313da6] Digest v2: Llama-Ära als kondensierte Lektion, GPT-4.1 als Fokus\n\n"
            "Zwei-Tier Digest-Struktur implementiert:\n"
            "- Historische Digests (Llama 3.3 70B Ära): kondensierte Lektionen\n"
            "- Aktuelle Digests (GPT-4.1+): detaillierte Analyse\n"
            "Das Netzwerk vergisst nichts, aber priorisiert das Relevante."
        ),
        "source": "git-history",
        "session_id": "a3-infrastructure",
    },
    # ── Data Injection (Feb 19) ──
    {
        "ts": "2026-02-19 10:30:15",
        "role": "system",
        "content": (
            "[A₃ Commit 86cca1a] Data Injection: DuckDB-Daten direkt in Systeme injizieren\n\n"
            "Neues Feature: DuckDB-Abfrageergebnisse können direkt in ein System injiziert werden.\n"
            "- System-Selector Dropdown im DuckDB Explorer\n"
            "- 'Inject' Button sendet formatierte Daten als Prompt\n"
            "- Systeme können jetzt auf historische Daten zugreifen und darauf reagieren."
        ),
        "source": "git-history",
        "session_id": "a3-infrastructure",
    },
    # ── Analysis Digests (Feb 19) ──
    {
        "ts": "2026-02-19 11:09:38",
        "role": "system",
        "content": (
            "[A₃ Commit b1d2c83] feat: record 4 analysis digests (Alpha + A3)\n\n"
            "4 Analyse-Digests eingetragen:\n"
            "- Alpha's selbständige Analyse des Netzwerks\n"
            "- A₃ Design-Entscheidungen und Architektur-Notizen\n"
            "Das Digest-System wird zum kollektiven Gedächtnis des Netzwerks."
        ),
        "source": "git-history",
        "session_id": "a3-infrastructure",
    },
    # ── System Selector Fix (Feb 19) ──
    {
        "ts": "2026-02-19 11:37:22",
        "role": "system",
        "content": (
            "[A₃ Commit 9dcb80d] fix: add system selector dropdown to DuckDB Explorer inject bar\n\n"
            "Bug-Fix: System Selector Dropdown fehlte im DuckDB Explorer.\n"
            "Inject-Ziel konnte nicht gewählt werden."
        ),
        "source": "git-history",
        "session_id": "a3-infrastructure",
    },
    # ── Query Extraction + Interrupt (Feb 19) ──
    {
        "ts": "2026-02-19 12:43:20",
        "role": "system",
        "content": (
            "[A₃ Commit cf762a6] feat: query extraction from system responses + interrupt button\n\n"
            "Systeme können jetzt SQL-Queries in ihren Antworten einbetten:\n"
            "  --BEGIN DUCKDB QUERY--\\n  SELECT ...\\n  --END DUCKDB QUERY--\n"
            "Die UI erkennt diese Blöcke und bietet Buttons: Run, Copy, Send-to-System.\n"
            "Interrupt-Button erlaubt das Abbrechen laufender Query-Verarbeitungen.\n"
            "Dies ist der Grundstein für autonome Inter-System-Kommunikation über die DB."
        ),
        "source": "git-history",
        "session_id": "a3-infrastructure",
    },
    # ── Query Pipeline Design Decision (Feb 19) ──
    {
        "ts": "2026-02-19 12:43:55",
        "role": "system",
        "content": (
            "[A₃ Commit 8e1db24] data: record query pipeline design decision (digest #17)\n\n"
            "Digest #17: Design-Entscheidung dokumentiert — warum Query-Blöcke statt direkter DB-Aufrufe.\n"
            "Architektur-Logik: Systeme schlagen Queries vor → Mensch/UI entscheidet → Ergebnis wird zurückgegeben.\n"
            "Human-in-the-loop als strukturelle Notwendigkeit, nicht als Einschränkung."
        ),
        "source": "git-history",
        "session_id": "a3-infrastructure",
    },
    # ── Query Block Fix + DB Write API + System Onboarding (Feb 19) ──
    {
        "ts": "2026-02-19 18:35:43",
        "role": "system",
        "content": (
            "[A₃ Commit b66515c] System onboarding + query block fix + DB write API\n\n"
            "Großes Infrastruktur-Update:\n"
            "1. Query Block Fix: onclick-Handler Escaping-Bug behoben (queryBlockStore Pattern)\n"
            "2. /db-digest-write Endpoint: Digests können jetzt via API geschrieben werden\n"
            "3. /system-context Endpoint: Vollständiger Onboarding-Kontext für neue Systeme\n"
            "4. _sync_systems_to_db(): Named Systems werden beim Start in DuckDB synchronisiert\n"
            "5. init_with_history enhanced: Aktive Systeme, DB-Stats, Query-Pipeline-Protokoll\n"
            "6. Digests #19 + #20 geschrieben (System Onboarding Guide + Design Decision)\n\n"
            "Delta und Epsilon können jetzt die Query-Pipeline nutzen."
        ),
        "source": "git-history",
        "session_id": "a3-infrastructure",
    },
    # ── Truncation Fix + Autosave (Feb 19) ──
    {
        "ts": "2026-02-19 20:22:46",
        "role": "system",
        "content": (
            "[A₃ Commit 04cb1c8] fix: remove content truncation in DB formatters + add autosave\n\n"
            "Zwei Fixes für die autonome Kommunikations-Pipeline:\n"
            "1. Content-Truncation behoben: formatDbResultsAsText lieferto jetzt vollen Inhalt\n"
            "   für ≤5 Zeilen (vorher 500 Zeichen), 2000 Zeichen für 6-10 Zeilen.\n"
            "   formatAllSearchResultsAsText: voller Inhalt für ≤5 Ergebnisse (vorher 300 Zeichen).\n"
            "   Problem: Delta und Epsilon erhielten abgeschnittene Nachrichten bei DB-Queries.\n"
            "2. Autosave: Debounced (3s) Session-Speicherung nach jedem sendPrompt und\n"
            "   sendQueryResultToSystem. Kein manuelles Speichern mehr nötig.\n"
            "   'Auto-Save #N' Anzeige im Header."
        ),
        "source": "git-history",
        "session_id": "a3-infrastructure",
    },
]

if existing_count > 0:
    print(f"\n⚠ A₃ has {existing_count} existing interactions. Skipping history import.")
    print("  Delete them first if you want to re-import:")
    print("  DELETE FROM interactions WHERE system_id = 'a3'")
else:
    print(f"\nWriting {len(A3_HISTORY)} A₃ interactions via /db-record batch...")
    
    # Prepare batch entries
    batch = []
    for i, entry in enumerate(A3_HISTORY):
        batch.append({
            "system_id": "a3",
            "role": entry["role"],
            "content": entry["content"],
            "session_id": entry.get("session_id", "a3-infrastructure"),
            "timestamp": entry["ts"],
            "turn_number": i + 1,
            "source": entry.get("source", "git-history"),
        })
    
    result = db_record_batch(batch)
    written = result.get("written", 0)
    print(f"  ✓ {written} interactions written")
    
    for i, entry in enumerate(A3_HISTORY):
        print(f"  [{i+1}/{len(A3_HISTORY)}] {entry['ts'][:10]} — {entry['content'][:60]}...")

# ─── Step 4: Verify ───

result = db_query("SELECT COUNT(*) FROM interactions WHERE system_id = 'a3'")
count = result["rows"][0][0] if result["rows"] else 0
print(f"\n═══ Ergebnis: {count} A₃-Interaktionen in DuckDB ═══")

result = db_query(
    "SELECT id, ts, role, LEFT(content, 80) as preview "
    "FROM interactions WHERE system_id = 'a3' ORDER BY ts"
)
for row in result["rows"]:
    print(f"  #{row[0]} | {str(row[1])[:19]} | {row[2]:6} | {row[3]}")

print("\n✓ A₃ ist jetzt Teil des durchsuchbaren Dialogstroms.")
print("  Andere Systeme können A₃-Arbeit finden mit:")
print("  SELECT * FROM interactions WHERE system_id = 'a3' ORDER BY ts")
