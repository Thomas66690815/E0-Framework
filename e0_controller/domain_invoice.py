"""
E₀ Controller — Phase 1b Domain: Rechnungsprüfung
=====================================================
Synthetisch-realistische Domäne für Controller-Validierung.

Prüft: Historisierung, Dead-ends, Escalation, Failure-Learning,
       operative Metriken, Generalisierung über Mini-Domain hinaus.

Zustände (10):
    RECEIVED        — Rechnung eingegangen
    PDF_LOADED      — PDF erfolgreich geladen
    DATA_EXTRACTED  — Rechnungsdaten extrahiert (Betrag, Datum, Lieferant)
    CUSTOMER_FOUND  — Kunde im System identifiziert
    AMOUNT_OK       — Betrag stimmt mit Bestellung überein
    CONTRACT_MATCH  — Vertrag gefunden und zugeordnet
    POLICY_OK       — Richtlinienprüfung bestanden
    APPROVED        — Rechnung freigegeben (Ziel)
    REJECTED        — Rechnung abgelehnt (endgültig)
    HUMAN_REVIEW    — Manuelle Prüfung (Escalation-Senke)

Topologie:
    RECEIVED ──→ PDF_LOADED ──→ DATA_EXTRACTED ──→ CUSTOMER_FOUND
                      │                │                  │
                      ↓                ↓                  ↓
                  REJECTED      HUMAN_REVIEW         AMOUNT_OK
                                                         │
                                                    CONTRACT_MATCH
                                                         │
                                                     POLICY_OK
                                                         │
                                                     APPROVED

Eigenschaften:
    - 17 Edges mit realistischen Δ/R₀
    - Deterministische Kanten (PDF laden, Betrag prüfen)
    - Unsichere Kanten (Vertrags-Matching, Richtlinienprüfung)
    - Dead-end: REJECTED (keine Ausgangskanten)
    - Escalation-Senke: HUMAN_REVIEW (keine Ausgangskanten → erzwingt Escalation)
    - Failure-prone: DATA_EXTRACTED→CUSTOMER_FOUND (Kunde oft nicht gefunden)
    - Recovery: HUMAN_REVIEW→CUSTOMER_FOUND (nach manueller Prüfung)
"""

from __future__ import annotations

from e0_controller.primitives import Edge, Outcome
from e0_controller.landscape import Landscape


def build_invoice_landscape() -> Landscape:
    """
    Rechnungsprüfungs-Landscape.

    Δ = Strukturelle Differenz (wie verschieden sind die States).
    R₀ = Basaler Widerstand (wie schwer ist der Übergang).

    Niedrig Δ + Niedrig R₀ = einfacher, glatter Übergang
    Hoch Δ + Hoch R₀ = schwieriger, strukturell anderer Schritt
    """
    L = Landscape()

    # ── Hauptpfad (Happy Path) ──
    # RECEIVED → PDF_LOADED: Datei laden, technisch einfach
    L.add_edge("RECEIVED", "PDF_LOADED",
               delta=0.2, resistance=0.3)         # S₀ = 0.06

    # PDF_LOADED → DATA_EXTRACTED: OCR/Parsing, mittel
    L.add_edge("PDF_LOADED", "DATA_EXTRACTED",
               delta=0.4, resistance=0.8)          # S₀ = 0.32

    # DATA_EXTRACTED → CUSTOMER_FOUND: Kunden-Lookup, unsicher
    L.add_edge("DATA_EXTRACTED", "CUSTOMER_FOUND",
               delta=0.5, resistance=1.2)          # S₀ = 0.60

    # CUSTOMER_FOUND → AMOUNT_OK: Betragsvalidierung, deterministisch
    L.add_edge("CUSTOMER_FOUND", "AMOUNT_OK",
               delta=0.2, resistance=0.4)          # S₀ = 0.08

    # AMOUNT_OK → CONTRACT_MATCH: Vertragszuordnung, mittel-schwer
    L.add_edge("AMOUNT_OK", "CONTRACT_MATCH",
               delta=0.5, resistance=1.0)          # S₀ = 0.50

    # CONTRACT_MATCH → POLICY_OK: Richtlinien, mittel
    L.add_edge("CONTRACT_MATCH", "POLICY_OK",
               delta=0.3, resistance=0.7)          # S₀ = 0.21

    # POLICY_OK → APPROVED: Freigabe, fast trivial
    L.add_edge("POLICY_OK", "APPROVED",
               delta=0.1, resistance=0.2)          # S₀ = 0.02

    # ── Fehler-/Alternativpfade ──

    # PDF_LOADED → REJECTED: PDF unlesbar / korrupt
    L.add_edge("PDF_LOADED", "REJECTED",
               delta=0.8, resistance=0.5)          # S₀ = 0.40

    # DATA_EXTRACTED → HUMAN_REVIEW: Daten unklar, manuelle Prüfung
    L.add_edge("DATA_EXTRACTED", "HUMAN_REVIEW",
               delta=0.6, resistance=1.5)          # S₀ = 0.90

    # CUSTOMER_FOUND → HUMAN_REVIEW: Mehrdeutige Kundenzuordnung
    L.add_edge("CUSTOMER_FOUND", "HUMAN_REVIEW",
               delta=0.5, resistance=1.8)          # S₀ = 0.90

    # AMOUNT_OK → REJECTED: Betrag passt nicht (zu starke Abweichung)
    L.add_edge("AMOUNT_OK", "REJECTED",
               delta=0.7, resistance=1.0)          # S₀ = 0.70

    # CONTRACT_MATCH → HUMAN_REVIEW: Vertrag unklar
    L.add_edge("CONTRACT_MATCH", "HUMAN_REVIEW",
               delta=0.4, resistance=2.0)          # S₀ = 0.80

    # POLICY_OK → REJECTED: Policy-Verstoß
    L.add_edge("POLICY_OK", "REJECTED",
               delta=0.6, resistance=0.8)          # S₀ = 0.48

    # ── Recovery-Pfade (nach HUMAN_REVIEW) ──

    # HUMAN_REVIEW → CUSTOMER_FOUND: Mensch klärt Kunden
    L.add_edge("HUMAN_REVIEW", "CUSTOMER_FOUND",
               delta=0.3, resistance=2.5)          # S₀ = 0.75

    # HUMAN_REVIEW → DATA_EXTRACTED: Mensch korrigiert Daten
    L.add_edge("HUMAN_REVIEW", "DATA_EXTRACTED",
               delta=0.4, resistance=3.0)          # S₀ = 1.20

    # HUMAN_REVIEW → REJECTED: Mensch lehnt ab
    L.add_edge("HUMAN_REVIEW", "REJECTED",
               delta=0.3, resistance=3.0)          # S₀ = 0.90

    # ── Dead-ends ──
    # REJECTED und APPROVED haben keine Ausgangskanten.
    L.add_state("REJECTED")
    L.add_state("APPROVED")

    return L


# ──────────────────────────────────────────────
# Outcome-Szenarien (deterministische Execution-Callbacks)
# ──────────────────────────────────────────────

def happy_path(source: str, target: str) -> Outcome:
    """Alles klappt. Für Baseline-Messung."""
    return Outcome.SUCCESS


def realistic_outcomes(source: str, target: str) -> Outcome:
    """
    Realistische Fehlerverteilung:
    - DATA_EXTRACTED → CUSTOMER_FOUND: oft Probleme (FAILURE)
    - CONTRACT_MATCH → POLICY_OK: manchmal unklar (PARTIAL)
    - HUMAN_REVIEW → *: immer SUCCESS (Mensch schafft es)
    - Alles andere: SUCCESS
    """
    if source == "DATA_EXTRACTED" and target == "CUSTOMER_FOUND":
        return Outcome.FAILURE
    if source == "CONTRACT_MATCH" and target == "POLICY_OK":
        return Outcome.PARTIAL
    return Outcome.SUCCESS


def harsh_outcomes(source: str, target: str) -> Outcome:
    """
    Schwieriger Fall: Viele Fehler.
    - Extraction → Customer: FAILURE
    - Customer → Amount: PARTIAL
    - Contract → Policy: FAILURE
    - Alles andere: SUCCESS
    """
    if source == "DATA_EXTRACTED" and target == "CUSTOMER_FOUND":
        return Outcome.FAILURE
    if source == "CUSTOMER_FOUND" and target == "AMOUNT_OK":
        return Outcome.PARTIAL
    if source == "CONTRACT_MATCH" and target == "POLICY_OK":
        return Outcome.FAILURE
    return Outcome.SUCCESS


def learning_scenario(source: str, target: str, attempt: list) -> Outcome:
    """
    Lernfähiges Szenario: Erste N Versuche auf einer Kante scheitern,
    danach klappt es. Simuliert reales Lernen.

    Usage: Pass a mutable list as counter. Edge-specific.
    """
    key = f"{source}→{target}"
    # Track attempts per edge
    if not hasattr(learning_scenario, "_counts"):
        learning_scenario._counts = {}
    counts = learning_scenario._counts
    counts[key] = counts.get(key, 0) + 1

    # DATA_EXTRACTED → CUSTOMER_FOUND: first 3 fail, then OK
    if source == "DATA_EXTRACTED" and target == "CUSTOMER_FOUND":
        return Outcome.FAILURE if counts[key] <= 3 else Outcome.SUCCESS

    # CONTRACT_MATCH → POLICY_OK: first 2 partial, then OK
    if source == "CONTRACT_MATCH" and target == "POLICY_OK":
        return Outcome.PARTIAL if counts[key] <= 2 else Outcome.SUCCESS

    return Outcome.SUCCESS


def reset_learning_scenario():
    """Reset the learning scenario counter."""
    if hasattr(learning_scenario, "_counts"):
        learning_scenario._counts = {}


# ──────────────────────────────────────────────
# Testfall-Generatoren
# ──────────────────────────────────────────────

INVOICE_CASES = {
    "standard_invoice": {
        "desc": "Normale Rechnung, alle Daten korrekt",
        "execute_fn": happy_path,
        "expected_goal": "APPROVED",
        "start": "RECEIVED",
    },
    "realistic_invoice": {
        "desc": "Typische Rechnung — Kunde oft nicht gefunden",
        "execute_fn": realistic_outcomes,
        "expected_goal": "APPROVED",
        "start": "RECEIVED",
    },
    "harsh_invoice": {
        "desc": "Schwieriger Fall — mehrere Fehler",
        "execute_fn": harsh_outcomes,
        "expected_goal": None,  # may not reach APPROVED
        "start": "RECEIVED",
    },
    "start_from_review": {
        "desc": "Rechnung beginnt bei manueller Prüfung",
        "execute_fn": happy_path,
        "expected_goal": "APPROVED",
        "start": "HUMAN_REVIEW",
    },
    "rejected_dead_end": {
        "desc": "Start bei REJECTED — Dead-end, muss eskalieren",
        "execute_fn": happy_path,
        "expected_goal": None,
        "start": "REJECTED",
    },
}
