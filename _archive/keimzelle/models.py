"""
E₀ Keimzelle — Datenmodelle
=============================
Die fünf Kern-Entities des E₀-Protokolls:

  Node        — Teilnehmer (Mensch, LLM, System)
  Delta       — Differenz / Frage / Spannung
  Note        — Antwort / Beitrag auf ein Delta
  Session     — Thema + Verlauf
  Interaction — Wer reagiert worauf (Audit-Trail)
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()

def _id() -> str:
    return uuid.uuid4().hex[:12]


# ───────────────────────────────────────────
# Node — Ein Teilnehmer im Netzwerk
# ───────────────────────────────────────────

@dataclass
class Node:
    """
    Ein Knoten im E₀-Netzwerk.

    Typen:
      - "human"  : Ein Mensch (der Betreiber, eingeladene Personen)
      - "llm"    : Ein Sprachmodell (Theta-Light, Kappa-Light, ...)
      - "system" : Ein Systemknoten (A₃-Light Koordinator)
    """
    id: str = field(default_factory=_id)
    name: str = ""
    node_type: str = "human"      # human | llm | system
    role: str = ""                # explorer, critic, ... (Perspektive)
    system_prompt: str = ""       # Für LLM/System-Knoten
    model: str = ""               # Modellname (für LLM-Knoten)
    capabilities: List[str] = field(default_factory=lambda: ["respond"])
    config: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=_now)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["capabilities"] = ",".join(self.capabilities) if self.capabilities else ""
        return d

    def has_capability(self, cap: str) -> bool:
        return cap in self.capabilities

    @classmethod
    def from_dict(cls, d: dict) -> "Node":
        d = dict(d)
        if isinstance(d.get("capabilities"), str):
            d["capabilities"] = [c.strip() for c in d["capabilities"].split(",") if c.strip()]
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


# ───────────────────────────────────────────
# Delta — Eine Differenz / Frage / Spannung
# ───────────────────────────────────────────

@dataclass
class Delta:
    """
    Ein Delta ist die Grundeinheit der Ko-Kognition:
    eine Frage, eine Spannung, ein Problem, das bearbeitet werden soll.

    Beispiel: "Verkehr in der Innenstadt ist unerträglich,
    gleichzeitig verlieren Geschäfte Kunden."
    """
    id: str = field(default_factory=_id)
    content: str = ""
    author_node_id: str = ""
    session_id: str = ""
    parent_delta_id: Optional[str] = None   # Für Verkettung
    tags: List[str] = field(default_factory=list)
    created_at: str = field(default_factory=_now)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["tags"] = ",".join(self.tags) if self.tags else ""
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "Delta":
        d = dict(d)
        if isinstance(d.get("tags"), str):
            d["tags"] = [t.strip() for t in d["tags"].split(",") if t.strip()]
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


# ───────────────────────────────────────────
# Note — Antwort / Beitrag auf ein Delta
# ───────────────────────────────────────────

@dataclass
class Note:
    """
    Eine Note ist die Antwort eines Knotens auf ein Delta.
    Notes gehören zu einer Runde und einer Phase.

    Phasen:
      - "open"      : Öffnen — Erste Reaktionen, Fragen sammeln
      - "friction"   : Reiben — Falsifikation, Widersprüche
      - "condense"   : Verdichten — Möglichkeitsräume, Konvergenz
      - "derive"     : Ableiten — Nächste Schritte, Handlung
    """
    id: str = field(default_factory=_id)
    delta_id: str = ""
    author_node_id: str = ""
    content: str = ""
    round_number: int = 1
    phase: str = "open"           # open | friction | condense | derive
    note_type: str = "response"   # response | coordination
    created_at: str = field(default_factory=_now)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Note":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


# ───────────────────────────────────────────
# Session — Thema + Verlauf
# ───────────────────────────────────────────

@dataclass
class Session:
    """
    Eine Session bündelt Deltas, Notes und Interaktionen
    zu einem Thema.
    """
    id: str = field(default_factory=_id)
    name: str = ""
    topic: str = ""
    network_name: str = ""
    current_round: int = 1
    current_phase: str = "open"   # open | friction | condense | derive
    created_at: str = field(default_factory=_now)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Session":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


# ───────────────────────────────────────────
# Interaction — Audit-Trail
# ───────────────────────────────────────────

@dataclass
class Interaction:
    """
    Protokolliert, wer wann worauf reagiert hat.
    Ermöglicht Nachvollziehbarkeit und spätere Analyse.
    """
    id: str = field(default_factory=_id)
    session_id: str = ""
    from_node_id: str = ""
    to_node_id: Optional[str] = None
    action: str = ""              # set_delta | respond | correct | condense
    reference_id: str = ""        # ID des Delta oder Note
    created_at: str = field(default_factory=_now)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Interaction":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


# ───────────────────────────────────────────
# Phasen-Konstanten
# ───────────────────────────────────────────

PHASES = ["open", "friction", "condense", "derive"]
PHASE_NAMES = {
    "open": "Öffnen",
    "friction": "Reiben",
    "condense": "Verdichten",
    "derive": "Ableiten",
    "discourse": "Diskurs",
}

def next_phase(current: str) -> Optional[str]:
    """Gibt die nächste Phase zurück, oder None wenn fertig."""
    try:
        idx = PHASES.index(current)
        return PHASES[idx + 1] if idx + 1 < len(PHASES) else None
    except ValueError:
        return None
