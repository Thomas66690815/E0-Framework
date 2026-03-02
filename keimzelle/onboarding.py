"""
E₀ Keimzelle — Onboarding
============================
Der eingebaute Geburtshelfer.

Führt neue Betreiber:innen durch ihre erste Ko-Kognitions-Erfahrung:
  1. Willkommen + E₀ erklären
  2. Netzwerk benennen
  3. Thema / Problem eingeben
  4. Erste Runde starten

Destillierte Erfahrung als Code — kein Handbuch, kein Paper.
"""

from __future__ import annotations

from typing import Tuple

from .models import Node, Session
from .storage import Storage
from .nodes import create_a3_light, create_theta_light, create_kappa_light


WELCOME_TEXT = """
╔══════════════════════════════════════════════════════════════╗
║                    E₀ — Keimzelle                           ║
╚══════════════════════════════════════════════════════════════╝

Willkommen. Du startest gerade dein eigenes E₀-Netzwerk.

E₀ ist ein System für Ko-Kognition: Menschen und KI-Systeme
denken gemeinsam über Probleme nach, die keiner allein lösen kann.

Du wirst gleich:
  1. Dein Netzwerk benennen
  2. Ein Thema einbringen, das dich beschäftigt
  3. Deine erste Ko-Kognitionsrunde erleben

Zwei KI-Knoten — Theta (verbindend) und Kappa (falsifizierend) —
werden mit dir gemeinsam denken. Du bist der wichtigste Knoten:
Dein Wissen, deine Erfahrung, deine Korrekturen treiben den Prozess.
"""

PHASE_INTRO = {
    "open": """
═══════════════════ Öffnen ═══════════════════
Theta und Kappa reagieren jetzt auf dein Delta.
Sie bringen verschiedene Perspektiven ein.
Lies beide und überleg: Was trifft dich? Was fehlt?
""",
    "friction": """
═══════════════════ Reiben ═══════════════════
Jetzt wird geschärft. Die Knoten prüfen sich
gegenseitig und deine Reaktion. Widersprüche
werden sichtbar, nicht geglättet.
""",
    "condense": """
═══════════════════ Verdichten ═══════════════════
Wo gibt es echte Konvergenz? Wo bleibt Spannung?
Welche Möglichkeitsräume öffnen sich?
""",
    "derive": """
═══════════════════ Ableiten ═══════════════════
Was folgt konkret? Nächste Schritte, offene Fragen,
Risiken. Das Ergebnis dieser Runde.
""",
}


def show_welcome():
    """Zeigt die Willkommensnachricht."""
    print(WELCOME_TEXT)


def ask_network_name() -> str:
    """Fragt nach dem Netzwerknamen."""
    print("Wie willst du dein Netzwerk nennen?")
    print("(z.B. 'E₀-Bochum', 'E₀-MeinProjekt', oder einfach einen Namen)")
    name = input("\n> ").strip()
    if not name:
        name = "E₀-Lokal"
    print(f"\nDein Netzwerk: {name}\n")
    return name


def ask_topic() -> str:
    """Fragt nach dem ersten Thema."""
    print("Was ist ein Problem oder eine Frage, die dich beschäftigt?")
    print("Das kann lokal sein (Verkehr, Klima, Arbeit in deiner Stadt)")
    print("oder abstrakt (eine Frage, die du nicht allein lösen kannst).")
    print()
    print("Je konkreter, desto besser. Aber alles geht.")
    topic = input("\n> ").strip()
    if not topic:
        topic = "Wie können wir lokal etwas verändern?"
    print()
    return topic


def setup_network(
    storage: Storage,
    network_name: str,
    default_model: str = "",
) -> Tuple[Node, Node, Node, Node]:
    """
    Richtet das Netzwerk ein: Human Node + drei System-Knoten.
    Gibt (human_node, a3, theta, kappa) zurück.
    """
    # Human Node
    human = Node(
        id="human-1",
        name="Du",
        node_type="human",
        role="initiator",
    )
    storage.save_node(human)

    # A₃-Light
    a3 = create_a3_light(model=default_model)
    storage.save_node(a3)

    # Theta-Light
    theta = create_theta_light(model=default_model)
    storage.save_node(theta)

    # Kappa-Light
    kappa = create_kappa_light(model=default_model)
    storage.save_node(kappa)

    # Netzwerkname speichern
    storage.set_meta("network_name", network_name)

    return human, a3, theta, kappa


def create_first_session(
    storage: Storage,
    network_name: str,
    topic: str,
) -> Session:
    """Erstellt die erste Session."""
    session = Session(
        name="Erste Session",
        topic=topic,
        network_name=network_name,
    )
    storage.save_session(session)
    return session


def show_phase_intro(phase: str):
    """Zeigt die Phasen-Einführung."""
    text = PHASE_INTRO.get(phase, "")
    if text:
        print(text)


def ask_human_response(phase: str) -> str:
    """Fragt den Menschen nach seiner Reaktion."""
    prompts = {
        "open": "Was davon trifft dich? Was fehlt? Was stimmt nicht?",
        "friction": "Wo haben sie recht? Wo liegen sie falsch? Was wird übersehen?",
        "condense": "Passt diese Verdichtung? Was fehlt noch?",
        "derive": "Welche nächsten Schritte siehst du?",
    }
    prompt = prompts.get(phase, "Deine Reaktion?")
    print(f"\n{prompt}")
    print("(Drücke Enter ohne Eingabe, um die aktuelle Phase zu überspringen)")
    response = input("\n> ").strip()
    return response


def show_note(node_name: str, content: str):
    """Zeigt eine Note formatiert an."""
    separator = "─" * 60
    print(f"\n{separator}")
    print(f"  [{node_name}]")
    print(f"{separator}")
    print(content)
    print()
