# E₀ Repository-Statusinventur v1

**Inventory ID:** `E0-REPO-STATUS-v1`
**Stand:** 2026-07-28
**Basis:** Commit `b605e7f` (C322)
**Maschinenlesbar:** [`E0_REPOSITORY_STATUS_v1.json`](E0_REPOSITORY_STATUS_v1.json)

## 1. Entscheidung

WP-0.4 ist eine Inventur, keine Aufräumaktion:

- Es wird jetzt **kein neues Repository** eröffnet.
- Es wird nichts verschoben, gelöscht oder physisch archiviert.
- `e0_controller/` bleibt bis Gate G1 der Forschungs-Träger.
- `lean/` enthält die beiden Produktkandidaten. Ein späterer Repo-Split ist
  möglich, aber weder durch den aktuellen Umfang noch allein durch einen
  positiven G1-Ausgang automatisch gerechtfertigt.
- Ein Lean-Paket darf erst dann in ein eigenes Repo wechseln, wenn Gate G1 und
  WP-1.1 eine tragfähige Paketgrenze zeigen und ein eigener Release-Zyklus,
  Verantwortungsbereich oder externer Nutzungsgrund besteht.

Damit ist die Antwort auf die Ordnungsfrage vorerst: **ein Repo, explizite
Lebenszyklusgrenzen, keine voreilige physische Trennung**.

## 2. Statusbegriffe

| Status | Bedeutung | Erlaubte Änderung |
|---|---|---|
| `active` | Aktuelle Autorität, Produktkandidat oder notwendige Infrastruktur | Geplante Pflege innerhalb eines WP |
| `research` | Experimenteller Träger; kein Produkt- oder Evidenzstatus | Nur gemapptes Forschungs-/G1-WP |
| `frozen` | Bleibt lesbar und ausführbar, wird aber nicht ausgebaut | Korrektur, Kompatibilität, Testfix |
| `superseded` | Historisch behalten; benannter Nachfolger ist maßgeblich | Nur Verweis-/Kompatibilitätsfix |
| `archive-candidate` | Später planbar aus der aktiven Oberfläche zu entfernen | Jetzt keine Bewegung; eigener späterer Beschluss |

`archive-candidate` heißt nicht „wertlos“ und nicht „darf gelöscht werden“. Es
heißt nur: Der Pfad hat keinen aktuellen operativen Auftrag mehr und besitzt
einen benannten Nachfolger oder Zielzustand.

## 3. Vollständige Top-Level-Inventur

Der Scope ist der getrackte Root-Bestand aus `git ls-tree HEAD`. Ignorierte
Caches, Secrets, Builds und Laufzeitausgaben sind keine Architekturkomponenten.

| Pfad | Status | Rolle | Nachfolger / Grenze |
|---|---|---|---|
| `.env.example` | `active` | Nicht-geheime Konfigurationsvorlage | Kein Nachfolger |
| `.github/` | `active` | CI | Aktive Tests und Python-Versionen |
| `.gitignore` | `active` | Secret-/Artefaktgrenze | Kein Nachfolger |
| `AGENT_BUILDER_GUIDE.md` | `active` | Integrationsleitfaden | Darf eingefrorene Mechanismen nicht reaktivieren |
| `AGENT_REFERENCE.md` | `active` | Implementierungsreferenz | Empirische Aussagen verweisen auf das Ledger |
| `CHANGELOG.md` | `active` | Änderungshistorie | Keine Evidenzautorität |
| `GAME_AI.md` | `active` | Geometry-Anwendungsleitfaden | Produktwert bleibt von G1-A abhängig |
| `LICENSE` | `active` | Lizenzautorität | Änderung nur durch Nutzerentscheidung |
| `README.md` | `active` | Öffentlicher Einstieg | Evidenz-Umbau in WP-5.1 |
| `REPRODUCTION.md` | `active` | Bestehende Schnellreproduktion | Erweiterung in WP-5.3; nicht der G1-Runner |
| `_archive/` | `frozen` | Historische Referenz | Keine Imports oder aktuelle Claims |
| `bootstrap.json` | `active` | Arbeitsgedächtnis und Pointer | Claim-Status kommt aus dem Ledger |
| `canon/` | `frozen` | Konzeptuelle/historische Texte | Empirie: Ledger; AGI-Blueprint ist Archivkandidat |
| `client/` | `superseded` | Alte React/Cytoscape-UI | `server/static/index.html` |
| `docs/` | `active` | Dokumentationscontainer | Untergruppen behalten getrennte Status |
| `e0_controller/` | `research` | G1-Forschungs-Träger | Post-G1: behalten, verengen oder einfrieren |
| `e0_session_e0-session.txt` | `archive-candidate` | Generierte Beispielausgabe | Künftig ungetrackte Laufzeitausgabe |
| `lean/` | `active` | Zwei Produktkandidaten | Eigene Repos frühestens nach G1 + WP-1.1 |
| `learning_state.json` | `frozen` | Zustand alter Selbstlern-/Explorationspfade | Bestehende Persistenzschnittstellen |
| `memos/` | `frozen` | Seeds, Beispiele und Session-/Dream-Zustand | Später ggf. echte Fixtures oder externer Runtime-Speicher |
| `memos_interference/` | `archive-candidate` | Historisches Demo-Sessionartefakt | C185-Report und künftige G1-Rohdaten |
| `pyproject.toml` | `active` | Kanonische Build-/Dependency-Konfiguration | In WP-1.1 gegen Paketgrenzen prüfen |
| `reproduce.py` | `active` | Schnellreproduktionskommando | WP-5.3-Artefaktworkflow |
| `requirements.txt` | `superseded` | Nicht-kanonische Kompatibilitätsliste | `pyproject.toml` + explizite CI-Dependencies |
| `scenarios/` | `frozen` | Session-Runner-Szenarien | G1 verwendet eigene Domänengeneratoren |
| `server/` | `frozen` | Domain Studio, statische UI und Demos | Bugfixes ja, Ausbau vor G1 nein |
| `tools/` | `active` | Repository-Pflegewerkzeuge | Nur aktive Governance-/Reproduktionsaufgaben |

### Wichtige Untergrenzen

- In `e0_controller/` sind G1-Harness, notwendiger Controller-Kern und Tests
  `research`. Reflexion, Multiverse, LLM-Erweiterungen, Observation, Dream,
  Entropy, Sleep-Wake, Curriculum, Communication und Session Runner bleiben
  gemäß Feature Freeze eingefroren.
- `lean/reliability_memory` ist ein aktiver Produktkandidat.
- `lean/structural_geometry` ist ein aktiver Produktkandidat mit offenem
  Produktentscheid: G1-A bestimmt Produktisierung oder Research Freeze.
- `server/`, `client/`, `memos/` und `scenarios/` werden nicht als alternative
  G1-Ausführungspfade benutzt.

## 4. Strategische Dokumentordnung

### Aktuelle Autoritäten

| Thema | Autorität |
|---|---|
| Arbeitsreihenfolge und WPs | `docs/E0_UMSETZUNGSPLAN_v1.md` |
| Evidenzregeln | `docs/E0_EVIDENCE_POLICY_v1.md` |
| Claim-Status | `docs/E0_EVIDENCE_LEDGER_v1.json` |
| Gate-G1-Design | `docs/E0_G1_PROTOCOL_v1.json` + Präregistrierung |
| Repository-Lebenszyklus | dieses Dokument + JSON-Inventur |
| Architektur | `docs/ARCHITECTURE.md` |
| Formel-Code-Zuordnung | `docs/E0_MATH_IMPL_MAPPING_v1.md` |
| Tests | `docs/E0_TEST_REGISTRY_v2.md` |
| Schnellreproduktion | `REPRODUCTION.md` + `reproduce.py` |

Diese Autoritäten sind absichtlich getrennt. Der Bootstrap darf zum Beispiel den
Claim-Status zusammenfassen, ihn aber nicht überschreiben.

### Herabgestufte oder eingefrorene Strategiedokumente

| Pfad / Gruppe | Status | Nachfolger / Verwendung |
|---|---|---|
| `docs/E0_EVIDENCE_AND_FALSIFICATION_STATUS_v1.md` | `superseded` | Claim-Status: Evidence Ledger |
| `docs/E0_PAPER_AUDIT_v1.md` | `superseded` | Historischer Audit-Input; Ledger ist aktuell |
| `docs/E0_STRUCTURAL_CONTRADICTIONS_v1.md` | `research` | Offene Fragen fließen in Ledger/G1 |
| `docs/E0_LAYER_AUDIT_v1.md` | `research` | Snapshot; Code/Tests und diese Inventur sind aktueller |
| `docs/E0_ARC_H_PLAN_v1.md` | `frozen` | Wiederaufnahme nur als Post-G1-WP |
| `docs/E0_HUMAN_AI_COLLABORATION_REPORT_v1.md` | `research` | Prozessbericht, keine Leistungsevidenz |
| `canon/e0-agi-blueprint.md` | `archive-candidate` | Geplanter Umzug in WP-5.1 |
| übrige Canon-Texte | `frozen` | Konzepttexte; keine empirische Autorität |
| `docs/research/**` | `research` | Claim-Promotion ausschließlich über das Ledger |
| `docs/archive/**` | `frozen` | Historische Referenz |
| `docs/papers/**` | `frozen` | Post-G1-Paper in WP-5.2 |

Ausnahmen innerhalb der Papers:

- `E0_FORMAL_PAPER_DRAFT_v1.md` → durch v2 ersetzt.
- `E0_PUBLICATION_OUTLINE_v1.md` → durch `E0_PUBLICATION_DRAFT_v1.md` ersetzt.
- `PAPER1_SKELETON_v1.md` und `PAPER2_SKELETON_v1.md` → durch ihre Manuskripte
  ersetzt.
- `related-work-research-report.md` bleibt `research`.

## 5. Was mit lokalen Artefakten geschieht

Im Arbeitsverzeichnis sichtbare Pfade wie `.env`, `.pytest_cache/`,
`__pycache__/`, `e0_framework.egg-info/`, `client/node_modules/`,
`client/dist/`, `data/`, `provenance/` und generierte `e0_session_*.html`
gehören nicht zur getrackten Architektur. Sie werden weder zu Komponenten
erklärt noch als Evidenz gezählt. Ihre Behandlung folgt `.gitignore`.

## 6. Repo-Split-Gate

Vor einem neuen Repo müssen nach G1 vier Bedingungen gemeinsam erfüllt sein:

1. Eine stabile, getestete Paketgrenze existiert.
2. Das Paket benötigt einen eigenen Release-Zyklus oder Verantwortungsbereich.
3. Ein realer Nutzer-/Integrationspfad profitiert von der Trennung.
4. Migration von History, Issues, Dokumentation und CI ist geplant.

Wenn diese Bedingungen nicht gemeinsam erfüllt sind, bleibt das Monorepo die
einfachere und ehrlichere Ordnung. Ein positiver G1-Effekt allein ist kein
Organisationsargument.

## 7. Review-Regel

Die Inventur wird neu versioniert bei:

- Gate-G1-Entscheid,
- Abschluss von WP-1.1,
- jedem Vorschlag zu Verschieben, Löschen, Publizieren oder Repo-Split,
- oder wenn ein benannter Nachfolger nicht mehr existiert.

Bis dahin ist sie eine Lifecycle-Grenze, keine Einladung zur Bereinigung.
