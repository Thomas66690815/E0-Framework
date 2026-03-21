"""
E₀ Controller — Scenario Loader
=================================
Loads Scenario Packets (JSON) per the schema in
scenarios/SCENARIO_PACKET_SCHEMA_v0.1.md.

A Scenario Packet is the **domain-content carrier** the LLM receives
as semantic source material.  It is NOT the landscape, NOT the MemOS
snapshot, NOT the controller state.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


REQUIRED_FIELDS = [
    "scenario_id", "domain", "title", "source_text",
    "objective", "required_outputs",
]


@dataclass
class ScenarioPacket:
    """Validated scenario packet ready for injection into E₀ prompts."""

    scenario_id: str
    domain: str
    title: str
    source_text: str
    objective: str
    required_outputs: List[str]

    # Optional fields
    known_constraints: List[str] = field(default_factory=list)
    evaluation_points: List[str] = field(default_factory=list)
    start_state: Optional[str] = None
    goal_state: Optional[str] = None
    expected_sections: List[str] = field(default_factory=list)
    notes: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def as_prompt_block(self) -> str:
        """Format the scenario as a prompt block for the LLM.

        Returns a text block containing the scenario context that
        should be injected into LLM prompts alongside the E₀ runtime
        context.
        """
        lines = [
            f"Scenario: {self.title}",
            f"Objective: {self.objective}",
            "",
            "Source Material:",
            self.source_text,
            "",
            f"Required Outputs: {', '.join(self.required_outputs)}",
        ]
        if self.known_constraints:
            lines.append(f"Constraints: {'; '.join(self.known_constraints)}")
        if self.expected_sections:
            lines.append(f"Expected Sections: {', '.join(self.expected_sections)}")
        return "\n".join(lines)


def load_scenario(path: str) -> ScenarioPacket:
    """Load and validate a scenario packet from a JSON file.

    Args:
        path: Path to the scenario JSON file.

    Returns:
        Validated ScenarioPacket.

    Raises:
        FileNotFoundError: If the file does not exist.
        ValueError: If required fields are missing.
    """
    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    missing = [k for k in REQUIRED_FIELDS if k not in data]
    if missing:
        raise ValueError(
            f"Scenario packet {path!r} missing required fields: {missing}"
        )

    return ScenarioPacket(
        scenario_id=data["scenario_id"],
        domain=data["domain"],
        title=data["title"],
        source_text=data["source_text"],
        objective=data["objective"],
        required_outputs=data["required_outputs"],
        known_constraints=data.get("known_constraints", []),
        evaluation_points=data.get("evaluation_points", []),
        start_state=data.get("start_state"),
        goal_state=data.get("goal_state"),
        expected_sections=data.get("expected_sections", []),
        notes=data.get("notes", ""),
        metadata=data.get("metadata", {}),
    )


def find_scenario(domain: str, scenarios_dir: str = "scenarios") -> Optional[str]:
    """Find the first scenario JSON file for a given domain.

    Args:
        domain: Domain name (e.g. 'competitor_brief').
        scenarios_dir: Base scenarios directory.

    Returns:
        Path to the first .json file found, or None.
    """
    domain_dir = os.path.join(scenarios_dir, domain)
    if not os.path.isdir(domain_dir):
        return None
    for fname in sorted(os.listdir(domain_dir)):
        if fname.endswith(".json"):
            return os.path.join(domain_dir, fname)
    return None
