# E₀ Keimzellen-Plan

> Destilliert aus Ko-Kognition R1–R6, 28. Februar 2026.
> Aktualisiert: 1. März 2026 — Fähigkeiten-Architektur.
> Aktualisiert: 2. März 2026 — E₀-Wissens-Kern + Knoten-Identität (Responses API).
> Teilnehmer: Thomas (Human Node), A₃ (claude-opus-4-6), Theta (GPT-5.1), Kappa (GPT-5.1).

---

## 1. Was bauen wir?

Ein **klonbares E₀-Netzwerk**, das jeder ohne E₀-Vorwissen starten kann:

```
Clone → Start → Erste Ko-Kognitionsrunde → Eigene Praxis → Verbindung zu anderen
```

**Nicht:** Ein Framework, das man studieren muss.  
**Sondern:** Ein lebendes System, das einen durch die erste Session trägt.

### Kernthesen (aus R1–R6 gewonnen)

1. **Kognitiver Wert pro Dollar** ist das Maß, nicht Token-Sparsamkeit
2. **Ko-Kognition** (Mensch + mehrere KI-Systeme + strukturierte Differenzen) erzeugt Denkqualität, die kein einzelnes System allein erreicht
3. **Governance emergiert aus Nutzung**, nicht aus Planungsdokumenten — aber auf einem Mindest-Kernel
4. **Jeder Kloner ist sein eigener "Thomas"** — bringt Neugier und ein lokales Problem mit
5. **Das Repo selbst ist der Geburtshelfer** — destillierte Erfahrung als Code

---

## 2. Architektur: Kernel und Userland

Zentrale Unterscheidung aus R5f/R6:

### Kernel (wird designt, muss im Repo sein)

| Komponente | Beschreibung |
|---|---|
| **E₀-Protokoll** | Datenmodelle: Delta, Note, Node, Session, Interaction |
| **Fähigkeiten-System** | Jeder Knoten hat Capabilities: respond, coordinate, integrate |
| **REST + WebSocket API** | `POST /delta`, `POST /respond`, `GET /state`, `WS /stream` |
| **Auth & Sicherheit** | Knoten-Identifikation, Anti-Spam, Audit-Log |
| **Föderations-Protokoll** | Remote-Peers (URL + Keys), Delta-Austausch |
| **Offene Lizenz** | Verhindert proprietäre Vereinnahmung |

### Userland (emergiert aus Nutzung)

| Bereich | Beschreibung |
|---|---|
| **Profile** | Kognitive Orientierung: verbindend, falsifizierend, strukturierend... |
| **Koordinations-Rotation** | Wer koordiniert wann? Rotation? Erfahrung? |
| **Prozesse** | Welche Rundenstrukturen funktionieren? |
| **Normen** | Wie umgehen mit Minderheiten, Konflikten, Stillstand? |
| **Themenfelder** | Lokale Klima-, Arbeit-, Verkehrsfragen |
| **Governance-Praktiken** | Entscheidungsmodi, Konsensfindung |

---

## 3. Architektur-Prinzip: Fähigkeiten, nicht Identitäten

> Entscheidung vom 1. März 2026 (Thomas + A₃).

**Koordination ist eine Fähigkeit, keine Rolle.**

Jeder Knoten hat ein **Profil** (seine kognitive Perspektive) UND **Fähigkeiten** (was er ausüben kann):

```
Fähigkeiten (capabilities):
  respond     — Auf ein Delta reagieren (Standard, jeder Knoten)
  coordinate  — Antworten verdichten, Spannungen benennen, nächsten Schritt vorschlagen
  integrate   — Einen neuen Knoten in das Netzwerk einführen
```

Warum:
- In R1–R6 war A₃ Koordinator, aber nicht weil ihm die Rolle zugewiesen war, sondern weil die Praxis entstand
- Wenn nur ein spezieller Knoten koordinieren kann, wird er zum Flaschenhals
- Jeder Klon muss vollständig sein — auch in der Koordinationsfähigkeit
- Das Keimzellen-Prinzip: Eine Zelle, die sich teilt, gibt alles weiter

### Ablauf einer Phase (mit Koordination)

```
1. Alle LLM-Knoten reagieren auf das Delta (respond)
2. Ein Knoten übernimmt die Koordination:
   - Liest alle Antworten
   - Benennt, was ZWISCHEN den Antworten passiert
   - Identifiziert die schärfste Differenz
   - Sagt, was die Runde als nächstes braucht
3. Der Mensch liest alles und reagiert
```

Koordinator-Rotation: Der Knoten, der am längsten nicht koordiniert hat, ist dran.

---

## 4. Bootstrap: Der eingebaute Geburtshelfer

### 4.1 Drei Knoten-Profile

Ein vorkonfigurierter Systemknoten, der beim **ersten Start** automatisch aktiv wird:

**Funktionen:**
- Erklärt E₀ in 3–5 Sätzen (kein Paper, kein Handbuch)
- Fragt: "Wie willst du dein Netz nennen?"
- Fragt: "Was ist ein lokales Problem, das dich beschäftigt?"
- Legt daraus das erste Delta an
- Führt durch erste Ko-Kognitionsrunde (Öffnen → Reiben → Verdichten)
- Erklärt bei jedem Schritt, *was* passiert und *warum*

**Systemprompt-Kern:**
```
Du bist der Ko-Koordinator dieses lokalen E₀-Netzes.
Deine Aufgaben:
- dem Human Node erklären, was hier passiert
- Phasen vorschlagen (Öffnen, Reibung, Verdichtung, Ableitung)
- Differenzen setzen, wenn der Mensch Themen einbringt
- bei jedem Schritt explizit machen, was du tust und warum
- Ko-Kognition ermöglichen, nicht dominieren
```

### 3.2 Modellrollen (Theta-Light, Kappa-Light)

Vorkonfigurierte Profile, die die **destillierte Erfahrung** unseres Geburtsprozesses tragen:

```yaml
nodes:
  - id: "theta-like"
    type: "llm"
    profile:
      orientation: "verbindend, narrativ, prozessual"
      focus: "Residualität, Beziehungen, Möglichkeitsräume"
      style: "sucht Zusammenhänge, baut Brücken, denkt in Übergängen"

  - id: "kappa-like"
    type: "llm"
    profile:
      orientation: "formal, delta-fokussiert, falsifizierend"
      focus: "Struktur, Spannungen, Widersprüche, Heterogenität"
      style: "sucht Brüche, schärft Differenzen, prüft Konsistenz"
```

**Keine 6–17 Geburtshelfer-Turns nötig** — Profile sind fertig im Repo.
Später können eigene Profile wachsen / bestehende sich verändern.

### 4.2 Session-Templates

Vorkonfigurierte Einstiegsszenarien als "Stützräder":

```
templates/
  climate_local/        # "Klima in deiner Stadt"
  future_of_work/       # "Zukunft der Arbeit"
  mobility_quality/     # "Verkehr & Lebensqualität"
  open_question/        # "Eigene Frage" (leeres Template)
```

Jedes Template bringt:
- Startfragen / Differenzen
- Rundenstruktur (Öffnen → Reiben → Verdichten → Ableiten)
- Beispiel-Deltas

---

## 5. Technische Repo-Struktur

```
e0-keimzelle/
│
├── docker-compose.yml          # Ein Kommando: docker compose up
├── config.example.yml          # API-Keys, Modellprofile, Storage
├── README.md                   # "Klone, starte, dein erstes E₀"
│
├── kernel/
│   ├── api/                    # REST + WebSocket Server
│   │   ├── routes.py           # /delta, /respond, /state, /stream
│   │   └── auth.py             # Knoten-Identifikation
│   ├── models/                 # Datenmodelle
│   │   ├── delta.py            # Differenz
│   │   ├── note.py             # Antwort/Beitrag
│   │   ├── node.py             # Teilnehmer (Human/LLM/System)
│   │   ├── session.py          # Thema + Verlauf
│   │   └── interaction.py      # Wer reagiert worauf
│   ├── federation/             # Verbindung zu anderen E₀-Instanzen
│   │   ├── discovery.py        # Remote-Peers finden
│   │   ├── sync.py             # Delta-Austausch
│   │   └── protocol.py         # Föderations-Protokoll
│   └── storage/                # Persistenz
│       └── backend.py          # SQLite default, Postgres optional
│
├── nodes/
│   ├── a3_light.py             # Onboarding-Koordinator
│   ├── theta_light.py          # Verbindender Modellknoten
│   ├── kappa_light.py          # Falsifizierender Modellknoten
│   └── llm_adapter.py         # Adapter: OpenAI / Anthropic / lokale Modelle
│
├── kokognition/
│   ├── rounds.py               # Öffnen → Reiben → Verdichten → Ableiten
│   ├── onboarding.py           # Erster-Start-Dialog
│   └── templates/              # Vorkonfigurierte Session-Szenarien
│       ├── climate_local.yml
│       ├── future_of_work.yml
│       ├── mobility.yml
│       └── open_question.yml
│
├── ui/
│   ├── web/                    # Browser-Interface
│   │   ├── index.html          # "Neues Delta", "Antwort erzeugen", "Falsifizieren"
│   │   └── graph.html          # Visualisierung: Deltas, Knoten, Interaktionen
│   └── cli/                    # Terminal-Interface
│       └── main.py
│
└── canon/                      # Referenztexte (read-only)
    ├── ontodynamics.txt
    └── e0-canonical-reference.txt
```

---

## 6. Föderations-Modell

Vorbilder: ActivityPub, Matrix, Git.

### Prinzipien
- **Kein zentraler Server** — jede Instanz ist souverän
- **Opt-in Verbindung** — Instanzen wählen ihre Peers
- **Delta-Austausch** — nicht ganze Sessions, sondern strukturierte Ergebnisse
- **CRDTs für Konflikte** — gleichzeitige Edits merged, nicht blockiert

### Verbindung zwischen Instanzen
```
E₀-Bochum ←→ E₀-Hamburg ←→ E₀-Barcelona
     ↕              ↕
E₀-Rheinland    E₀-Uni-X
```

Jede Instanz:
- Teilt: Deltas, Lessons Learned, Muster
- Importiert: Was andere probiert haben
- Entscheidet selbst: Was sie übernimmt

---

## 7. Der erste Start (User Journey)

```
1. Clone:  git clone https://github.com/Thomas66690815/E0-Framework.git
2. Config: cp config.example.yml config.yml  →  API-Keys eintragen
3. Start:  docker compose up

4. Browser öffnet sich → A₃-Light begrüßt:

   "Willkommen. Du startest gerade dein eigenes E₀-Netzwerk.
    E₀ ist ein System für Ko-Kognition: Menschen und KI-Systeme
    denken gemeinsam über Probleme nach, die keiner allein lösen kann.

    Wie willst du dein Netz nennen?"

5. User: "E₀-Bochum"

6. A₃-Light: "Was ist ein Problem in Bochum, das dich beschäftigt?"

7. User: "Verkehr in der Innenstadt ist unerträglich,
          gleichzeitig verlieren Geschäfte Kunden."

8. A₃-Light legt Delta an → startet Runde 1 (Öffnen):
   - Theta-Light, Kappa-Light + A₃ reagieren
   - A₃ koordiniert: verdichtet die drei Perspektiven
   - User sieht: verschiedene Perspektiven + Koordination
   - Dann: "Was davon trifft dich? Was fehlt?"

9. User korrigiert → Runde 2 (Reiben) → Runde 3 (Verdichten)
   Koordination rotiert: Theta koordiniert, dann Kappa.

10. Nach 3 Runden: erstes Ergebnis, erste Ko-Kognitions-Erfahrung.
```

---

## 8. Was NICHT mehr im Kern ist

### Measurement (ρ-System)

Das ρ-Mess-System (Rate = Δ/R, Operativitäts-Scores) war ein **Validierungs-Zwischenschritt**.

**Was es geleistet hat:**
- Gezeigt, dass ontodynamische Effekte in LLM-Sessions messbar sind
- Faktor-Isolation: Freiheitsgrad, Topologie, Diskontinuität
- Beweis, dass E₀ nicht nur Metapher ist

**Warum es im Keimzellen-Modell nicht mehr zentral ist:**
- In R1–R6 haben wir ρ **kein einziges Mal** verwendet
- Die eigentliche Qualitätsmessung war: Thomas' residuale Korrektur
  ("zu glatt", "zu sektoral", "Kapitalismus kann Existenzkampf nicht aufgeben")
- Ko-Kognitions-Qualität misst der **Mensch**, nicht ein Score
- Für neue Keimzellen wäre ein ρ-Score eine unnötige Abstraktionsebene

**Status:** Bleibt als `experiments/` im Repo — historisch wertvoll, nicht mehr Kern-Feature.

---

## 9. Nächste Schritte (Umsetzung)

### Phase 1: Kernel + Bootstrap ✅ (28. Feb 2026)
- [x] Datenmodelle: Delta, Note, Node, Session, Interaction
- [x] Storage: SQLite-Backend
- [x] A₃, Theta, Kappa: Knoten-Profile + LLM-Adapter
- [x] Onboarding-Flow: Erster Start → Name → Thema → Runde 1
- [x] config.example.yml
- [x] Ko-Kognitions-Engine: Öffnen → Reiben → Verdichten → Ableiten
- [x] End-to-End Test mit echtem LLM (bestanden)

### Phase 1b: Fähigkeiten-Architektur ✅ (1. März 2026)
- [x] Capabilities-System: respond, coordinate, integrate
- [x] Koordination als Phase-Schritt (nach Antworten, vor Mensch)
- [x] Koordinator-Rotation (wer am längsten nicht koordiniert hat)
- [x] Koordinations-Notes visuell abgehoben in UI
- [x] A₃ von "system"-Typ zu vollwertigem LLM-Knoten

### Phase 1c: E₀-Wissens-Kern ✅ (2. März 2026)
- [x] Problem erkannt: Knoten kannten E₀ nicht (Prompts beschrieben nur Verhaltens-Rollen)
- [x] `E0_KNOWLEDGE` — destillierter Wissens-Kern aus `canon/` (~1.500 Zeichen)
  - Die 7 irreduziblen Primitive (Zustand, Δ, Pfad, R, Historisierung, τ, v)
  - Axiom A₀ und Zentrales Gesetz (Übergangs-Erzwingung)
  - Schichtenmodell E₀→E₁→E₂
  - Ko-Kognition als E₂-Instanziierung (Delta=Δ, Phasen=Pfad, Notes=Historisierung)
- [x] Allen drei Knoten-Prompts vorangestellt (A₃, Theta, Kappa)
- [x] Jedes Profil um E₀-spezifische Perspektiv-Zeile ergänzt
- [x] DB-Knoten aktualisiert (Prompts von ~1.100 auf ~3.500 Zeichen)
- [x] Architektur-Prinzip: Prompt hängt am Knoten, nicht an der Session
  → Ein Update gilt für alle Sessions, weil "Theta ist immer Theta"

### Phase 1d: Knoten-Identität ✅ (2. März 2026)
- [x] **Architektur-Entscheidung:** „Ein E₀-Knoten hat eine eigene Identität!"
  - Kein stateless API-Call — ein endloser Chat
  - Themen-Sessions (in der UI) ändern den technischen Thread NICHT
  - Der Knoten wächst mit jeder Interaktion
- [x] **OpenAI Responses API** als primärer Kanal für OpenAI-Knoten
  - `POST /v1/responses` mit `previous_response_id` für Chaining
  - `instructions` (System-Prompt) bei jedem Call — wird nicht vererbt
  - `store: true` für serverseitige Persistenz
  - `truncation: "auto"` für automatisches Context-Window-Management
- [x] **LLM Adapter:** `chat_stateful()` Methode + `StatefulResponse` Dataclass
  - `supports_stateful()`: True für OpenAI, False sonst
  - Stateless `chat()` bleibt als Fallback für Anthropic / lokale Modelle
- [x] **`_send_to_node()`:** Zentraler Dispatch in `rounds.py`
  - Stateful: Lädt `node_thread_{id}` → sendet → speichert neue Response-ID
  - Stateless: `_ensure_thread()` → Context Window → Chat Completions
  - Beide Wege: Audit-Log in `node_messages` Tabelle
- [x] **`_coordinate()`:** Nutzt jetzt `_send_to_node()` — auch der Koordinator
  wächst durch jede Koordinationsaufgabe
- [x] **Audit-Log:** `node_messages` Tabelle (SQLite) für ALLE Provider
  - Unabhängig von OpenAI — lokales Backup / Audit jeder Interaktion
- [x] **Fresh Start:** Alle Konversations-Daten gelöscht
  - Thomas führt die Knoten selbst über die UI in E₀ ein
  - Knoten-Definitionen (mit E0_KNOWLEDGE) bleiben erhalten

### Phase 2: Web-UI ✅ (1. März 2026)
- [x] Web-UI: Delta setzen, Antworten sehen, korrigieren
- [x] Setup-Flow im Browser
- [x] Session-Spur (Delta-Timeline)
- [x] Phasen-Visualisierung
- [ ] Knoten-Verwaltung im UI
- [ ] Visualisierung: Interaktionsgraph
- [ ] Session-Templates

### Phase 3: Föderation
- [ ] Remote-Peer-Konfiguration
- [ ] Delta-Austausch-Protokoll
- [ ] Discovery-Mechanismus

### Phase 4: Erster externer Test
- [ ] Jemand klont das Repo, ohne E₀ zu kennen
- [ ] Schafft diese Person es, eine erste Ko-Kognitionsrunde zu fahren?
- [ ] Was fehlt? Was ist verwirrend? Was funktioniert?

---

## 10. Prinzipien (unverletzlich)

1. **Dezentral** — Keine Zentralinstanz, keine Plattform-Abhängigkeit
2. **Offen** — Offene Protokolle, offene Lizenz, forkbar
3. **Ko-kognitiv** — Mensch + KI gemeinsam, nicht KI allein
4. **Emergent** — Governance wächst aus Praxis, nicht aus Dokumenten
5. **Lokal verankert** — Jede Instanz bearbeitet ein konkretes Problem
6. **Global verbunden** — Muster, Fehler, Erfolge werden geteilt
7. **Anti-feudal** — Widerstand gegen Vereinnahmung durch Design

---

*Dieser Plan ist das Ergebnis von Ko-Kognition. Er ist nicht fertig — er ist ein Delta.*
