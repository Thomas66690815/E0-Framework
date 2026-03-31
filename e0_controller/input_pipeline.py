"""InputPipeline — unified entry point for creating Landscapes.

Supports three input channels:
  1. Structured JSON spec → Bootstrapper → Landscape
  2. Unstructured text → LLMAdapter → Bootstrapper → Landscape
  3. Canon name → CanonLoader → Landscape

Part of Layer B (Service Layer).  C83.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from e0_controller.bootstrapper import bootstrap_landscape, BootstrapError
from e0_controller.canon_loader import (
    CanonLandscape,
    load_canon,
    list_canons,
)
from e0_controller.landscape import Landscape


@dataclass
class PipelineResult:
    """Result of input processing — Landscape + provenance."""
    landscape: Landscape
    source: str                       # "json" | "text" | "canon"
    canon_name: Optional[str] = None  # if source == "canon"
    spec_used: Optional[dict] = None  # the bootstrap spec that was used


class InputPipeline:
    """Creates Landscapes from various input formats."""

    def from_json(self, spec: dict) -> PipelineResult:
        """Create Landscape from structured DomainSpec JSON.

        Raises BootstrapError on validation failure.
        """
        landscape = bootstrap_landscape(spec)
        return PipelineResult(
            landscape=landscape,
            source="json",
            spec_used=spec,
        )

    def from_text(self, description: str, *, api_key: Optional[str] = None) -> PipelineResult:
        """Create Landscape from unstructured text via LLM.

        Requires the openai package and a valid API key.

        Raises:
            LLMResponseError: If LLM output is unparseable.
            BootstrapError: If generated spec is invalid.
        """
        from e0_controller.llm_adapter import E0LLMAdapter, LLMConfig

        config = LLMConfig()
        if api_key:
            config.api_key = api_key
        adapter = E0LLMAdapter(config)
        landscape = adapter.propose_and_bootstrap(description)
        return PipelineResult(
            landscape=landscape,
            source="text",
        )

    def from_canon(self, name: str) -> PipelineResult:
        """Create Landscape from a named canon.

        Raises FileNotFoundError if canon not found.
        """
        cl: CanonLandscape = load_canon(name)
        return PipelineResult(
            landscape=cl.landscape,
            source="canon",
            canon_name=name,
        )

    @staticmethod
    def available_canons() -> List[str]:
        """List available canon names."""
        return list_canons()
