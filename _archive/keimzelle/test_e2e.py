"""
E₀ Keimzelle — End-to-End Test
Simuliert den ersten Start programmatisch.
"""

import yaml
from keimzelle.storage import Storage
from keimzelle.llm_adapter import LLMAdapter
from keimzelle.models import Session
from keimzelle.nodes import create_a3_light, create_theta_light, create_kappa_light
from keimzelle.rounds import KoKognition, create_initial_delta
from keimzelle.onboarding import setup_network, create_first_session

# Config laden
with open("config.yml", "r") as f:
    config = yaml.safe_load(f)

llm_cfg = config["llm"]
adapter = LLMAdapter(
    provider=llm_cfg["provider"],
    api_key=llm_cfg["api_key"],
    base_url=llm_cfg.get("base_url", ""),
    model=llm_cfg["model"],
)

# Verbindungstest
print("Teste LLM-Verbindung...", end=" ", flush=True)
if adapter.test_connection():
    print("OK")
else:
    print("FEHLER — API nicht erreichbar")
    exit(1)

# Storage (in-memory für Test)
storage = Storage(":memory:")

# Netzwerk einrichten
human, a3, theta, kappa = setup_network(storage, "E₀-Test", llm_cfg["model"])
print(f"Netzwerk: E₀-Test")
print(f"Knoten: {human.name}, {a3.name}, {theta.name}, {kappa.name}")

# Session + Delta
session = create_first_session(storage, "E₀-Test", "Wie verändert KI die Arbeitswelt?")
delta = create_initial_delta(storage, session, "Wie verändert KI die Arbeitswelt?", human.id)
print(f"Delta: {delta.content}")

# Eine Phase: Öffnen
print("\n" + "=" * 60)
print("  Phase 1: Öffnen")
print("=" * 60)

engine = KoKognition(storage, adapter)
notes = engine.run_phase(session, delta, [theta, kappa])

for note in notes:
    node = storage.get_node(note.author_node_id)
    name = node.name if node else "?"
    print(f"\n{'─' * 60}")
    print(f"  [{name}]")
    print(f"{'─' * 60}")
    # Zeige erste 500 Zeichen
    content = note.content
    if len(content) > 500:
        print(content[:500] + "...")
    else:
        print(content)

print(f"\n--- TEST BESTANDEN: {len(notes)} Notes erzeugt ---")
