"""
E₀ Keimzelle — Hauptprogramm
================================
Entry Point: python -m keimzelle

Erkennt automatisch ob Erststart oder bestehende Session
und führt den Benutzer durch Ko-Kognition.
"""

from __future__ import annotations

import os
import sys
import yaml
from pathlib import Path
from typing import Optional

from .storage import Storage
from .llm_adapter import LLMAdapter
from .models import Session, PHASE_NAMES, PHASES
from .nodes import create_a3_light, create_theta_light, create_kappa_light
from .rounds import KoKognition, create_initial_delta
from .onboarding import (
    show_welcome, ask_network_name, ask_topic,
    setup_network, create_first_session,
    show_phase_intro, ask_human_response, show_note,
)


CONFIG_FILE = Path("config.yml")
CONFIG_EXAMPLE = Path("config.example.yml")


def load_config() -> dict:
    """Lädt die Konfiguration aus config.yml."""
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}

    # Kein config.yml → prüfe ob example existiert
    if CONFIG_EXAMPLE.exists():
        print("Keine config.yml gefunden.")
        print(f"Bitte kopiere {CONFIG_EXAMPLE} nach {CONFIG_FILE}")
        print("und trage deinen API-Key ein.\n")
        print(f"  copy {CONFIG_EXAMPLE} {CONFIG_FILE}")
        print(f"  # Dann config.yml bearbeiten\n")
        sys.exit(1)
    else:
        print("Keine Konfiguration gefunden.")
        print("Erstelle eine config.yml (siehe config.example.yml).")
        sys.exit(1)


def create_adapter(config: dict) -> LLMAdapter:
    """Erstellt den LLM-Adapter aus der Konfiguration."""
    llm_config = config.get("llm", {})
    return LLMAdapter(
        provider=llm_config.get("provider", "openai"),
        api_key=llm_config.get("api_key", ""),
        base_url=llm_config.get("base_url", ""),
        model=llm_config.get("model", "gpt-4o"),
    )


def create_storage(config: dict) -> Storage:
    """Erstellt den Storage aus der Konfiguration."""
    storage_config = config.get("storage", {})
    db_path = storage_config.get("path", "data/keimzelle.db")
    return Storage(db_path)


def run_first_start(storage: Storage, adapter: LLMAdapter, config: dict):
    """Führt den Erststart durch: Onboarding + erste Runde."""

    show_welcome()

    # 1. Netzwerk benennen
    network_name = ask_network_name()

    # 2. Knoten einrichten
    default_model = config.get("llm", {}).get("model", "gpt-4o")
    human, a3, theta, kappa = setup_network(storage, network_name, default_model)

    print(f"Netzwerk '{network_name}' eingerichtet:")
    print(f"  • Du (Human Node)")
    print(f"  • Theta (verbindend)")
    print(f"  • Kappa (falsifizierend)")
    print(f"  • A₃-Light (Ko-Koordinator)\n")

    # 3. Thema eingeben
    topic = ask_topic()

    # 4. Session erstellen
    session = create_first_session(storage, network_name, topic)

    # 5. Erstes Delta setzen
    delta = create_initial_delta(storage, session, topic, human.id)
    print(f"Delta gesetzt: \"{topic}\"\n")

    # 6. Erste Ko-Kognitionsrunde starten
    run_kokognition_loop(storage, adapter, session, delta, human, [theta, kappa])


def run_kokognition_loop(
    storage: Storage,
    adapter: LLMAdapter,
    session: Session,
    delta,
    human_node,
    llm_nodes: list,
):
    """
    Hauptschleife der Ko-Kognition.
    Führt durch alle Phasen, fragt den Menschen, lässt LLMs reagieren.
    """
    engine = KoKognition(storage, adapter)

    while True:
        phase = session.current_phase
        round_num = session.current_round

        print(f"\n{'=' * 60}")
        print(f"  Runde {round_num} — {PHASE_NAMES.get(phase, phase)}")
        print(f"{'=' * 60}")

        show_phase_intro(phase)

        # LLM-Knoten reagieren lassen
        print("Knoten denken nach...\n")
        notes = engine.run_phase(session, delta, llm_nodes)

        # Notes anzeigen
        for note in notes:
            node = storage.get_node(note.author_node_id)
            node_name = node.name if node else "?"
            show_note(node_name, note.content)

        # Mensch reagieren lassen
        human_input = ask_human_response(phase)

        if human_input:
            # Human-Input als Note speichern und nächste Phase mit Input starten
            from .models import Note as NoteModel, Interaction
            human_note = NoteModel(
                delta_id=delta.id,
                author_node_id=human_node.id,
                content=human_input,
                round_number=round_num,
                phase=phase,
            )
            storage.save_note(human_note)
            storage.save_interaction(Interaction(
                session_id=session.id,
                from_node_id=human_node.id,
                action="respond",
                reference_id=human_note.id,
            ))

        # Phase weiterschalte
        engine.advance_phase(session)

        # Nach "derive": Fragen ob weiter
        if phase == "derive":
            print("\n" + "═" * 60)
            print("  Runde abgeschlossen.")
            print("═" * 60)
            print("\nOptionen:")
            print("  [w] Weitere Runde zum gleichen Thema")
            print("  [n] Neues Thema / neues Delta")
            print("  [q] Session beenden")
            choice = input("\n> ").strip().lower()

            if choice == "q":
                print("\nSession gespeichert. Bis zum nächsten Mal.\n")
                break
            elif choice == "n":
                # Neues Delta
                print("\nWas ist die nächste Frage / das nächste Problem?")
                new_topic = input("\n> ").strip()
                if new_topic:
                    delta = create_initial_delta(
                        storage, session, new_topic, human_node.id
                    )
                    session.current_round = 1
                    session.current_phase = "open"
                    storage.save_session(session)
                    print(f"\nNeues Delta: \"{new_topic}\"\n")
            # "w" oder alles andere → nächste Runde läuft automatisch


def run_continue(storage: Storage, adapter: LLMAdapter, config: dict):
    """Setzt eine bestehende Session fort."""
    session = storage.get_latest_session()
    if not session:
        print("Keine bestehende Session gefunden. Starte neu.\n")
        run_first_start(storage, adapter, config)
        return

    network_name = storage.get_meta("network_name", "E₀")
    print(f"\n  Netzwerk: {network_name}")
    print(f"  Session: {session.name} — \"{session.topic}\"")
    print(f"  Runde {session.current_round}, Phase: {PHASE_NAMES.get(session.current_phase, session.current_phase)}")
    print()

    # Knoten laden
    human_nodes = storage.get_nodes("human")
    llm_nodes = storage.get_nodes("llm")
    human_node = human_nodes[0] if human_nodes else None

    if not human_node or not llm_nodes:
        print("Knoten fehlen. Starte neu.\n")
        run_first_start(storage, adapter, config)
        return

    # Letztes Delta laden
    deltas = storage.get_deltas(session.id)
    if not deltas:
        print("Kein Delta gefunden. Was ist dein Thema?")
        topic = input("\n> ").strip()
        if not topic:
            return
        delta = create_initial_delta(storage, session, topic, human_node.id)
    else:
        delta = deltas[-1]

    print(f"  Delta: \"{delta.content}\"")
    print()

    print("Optionen:")
    print("  [w] Weiter mit dieser Session")
    print("  [n] Neues Thema setzen")
    print("  [s] Neue Session starten")
    print("  [q] Beenden")
    choice = input("\n> ").strip().lower()

    if choice == "q":
        return
    elif choice == "s":
        run_first_start(storage, adapter, config)
        return
    elif choice == "n":
        print("\nWas ist die nächste Frage / das nächste Problem?")
        topic = input("\n> ").strip()
        if topic:
            delta = create_initial_delta(storage, session, topic, human_node.id)
            session.current_round = 1
            session.current_phase = "open"
            storage.save_session(session)

    run_kokognition_loop(storage, adapter, session, delta, human_node, llm_nodes)


def main():
    """Haupteinstiegspunkt."""
    print()

    # Konfiguration laden
    config = load_config()

    # Storage + Adapter erstellen
    storage = create_storage(config)
    adapter = create_adapter(config)

    try:
        if storage.is_first_run():
            run_first_start(storage, adapter, config)
        else:
            run_continue(storage, adapter, config)
    except KeyboardInterrupt:
        print("\n\nSession gespeichert. Bis zum nächsten Mal.\n")
    finally:
        storage.close()
