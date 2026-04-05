"""
E₀ Perception Ontology (C158)
==============================
A learnable landscape domain encoding human perception primitives.

E0 does not know how humans perceive. This module teaches it — via the
Bootstrapper — a small set of Gestalt and language primitives as a
landscape domain. E0 can then build trace_load/quality on perception
nodes through normal historization, learning which perceptual strategies
work for communicating with a human peer.

Two sub-domains:
  - Visual primitives (proximity, emphasis, hierarchy, ...)
  - Language primitives (assertion, question, uncertainty, ...)

The perception landscape uses sparse directional edges encoding
"this perception modality naturally supports that one" (e.g.,
emphasis → contrast: highlighting differences requires emphasis).

See docs/E0_HUMAN_COMMUNICATION_DESIGN_v1.md §2 Layer 1.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from .bootstrapper import bootstrap_landscape, EdgeSpec, validate_spec
from .landscape import Landscape
from .primitives import Edge


# ──────────────────────────────────────────────
# 1. Perception Primitives
# ──────────────────────────────────────────────

class PerceptionKind(Enum):
    """Classification of perception primitives."""
    VISUAL = "visual"
    LANGUAGE = "language"


VISUAL_PRIMITIVES = [
    "proximity",    # spatial closeness = relatedness
    "emphasis",     # size, contrast, color = importance
    "hierarchy",    # nesting = structural subordination
    "sequence",     # ordering = time or causality
    "grouping",     # boundary, similarity = category
    "contrast",     # difference = distinction
    "density",      # information per unit area
    "motion",       # change over time = dynamics
    "label",        # textual annotation = naming
    "absence",      # deliberate omission = what is NOT shown
]

LANGUAGE_PRIMITIVES = [
    "assertion",    # stating a fact
    "question",     # requesting input
    "uncertainty",  # hedging / expressing doubt
    "reference",    # pointing to prior context
    "enumeration",  # listing items
]

ALL_PRIMITIVES = VISUAL_PRIMITIVES + LANGUAGE_PRIMITIVES


def primitive_kind(name: str) -> PerceptionKind:
    """Return the kind (visual/language) of a named primitive."""
    if name in VISUAL_PRIMITIVES:
        return PerceptionKind.VISUAL
    if name in LANGUAGE_PRIMITIVES:
        return PerceptionKind.LANGUAGE
    raise ValueError(f"Unknown perception primitive: {name!r}")


# ──────────────────────────────────────────────
# 2. Default Domain Spec
# ──────────────────────────────────────────────

# Sparse directed edges encoding natural perceptual support relationships.
# Each edge: (source, target, delta, resistance, initial_U, initial_F, confidence)
# High confidence (0.9) = well-established Gestalt principle.
# Medium confidence (0.7) = reasonable but context-dependent.
# Low confidence (0.5) = hypothesis — E0 must learn if this holds.

_DEFAULT_EDGES: List[Dict[str, Any]] = [
    # Visual → Visual (Gestalt support)
    {"from": "proximity",  "to": "grouping",   "delta": 0.3, "resistance": 0.5,
     "initial_U": 7.0, "initial_F": 1.0, "confidence": 0.9},
    {"from": "emphasis",   "to": "contrast",   "delta": 0.4, "resistance": 0.5,
     "initial_U": 6.0, "initial_F": 2.0, "confidence": 0.8},
    {"from": "hierarchy",  "to": "grouping",   "delta": 0.3, "resistance": 0.6,
     "initial_U": 6.0, "initial_F": 1.5, "confidence": 0.8},
    {"from": "sequence",   "to": "motion",     "delta": 0.3, "resistance": 0.5,
     "initial_U": 5.0, "initial_F": 1.0, "confidence": 0.7},
    {"from": "contrast",   "to": "emphasis",   "delta": 0.3, "resistance": 0.5,
     "initial_U": 5.0, "initial_F": 2.0, "confidence": 0.7},
    {"from": "density",    "to": "absence",    "delta": 0.5, "resistance": 0.8,
     "initial_U": 4.0, "initial_F": 2.0, "confidence": 0.7},
    {"from": "label",      "to": "hierarchy",  "delta": 0.2, "resistance": 0.4,
     "initial_U": 5.0, "initial_F": 1.0, "confidence": 0.8},
    {"from": "grouping",   "to": "proximity",  "delta": 0.3, "resistance": 0.5,
     "initial_U": 6.0, "initial_F": 1.5, "confidence": 0.8},
    {"from": "absence",    "to": "emphasis",   "delta": 0.4, "resistance": 0.6,
     "initial_U": 4.0, "initial_F": 2.0, "confidence": 0.6},
    {"from": "motion",     "to": "sequence",   "delta": 0.3, "resistance": 0.5,
     "initial_U": 5.0, "initial_F": 1.5, "confidence": 0.7},

    # Language → Visual (how speech acts shape perception)
    {"from": "assertion",  "to": "label",      "delta": 0.3, "resistance": 0.5,
     "initial_U": 5.0, "initial_F": 1.0, "confidence": 0.8},
    {"from": "question",   "to": "emphasis",   "delta": 0.4, "resistance": 0.6,
     "initial_U": 4.0, "initial_F": 1.5, "confidence": 0.7},
    {"from": "uncertainty","to": "contrast",   "delta": 0.4, "resistance": 0.7,
     "initial_U": 4.0, "initial_F": 2.5, "confidence": 0.6},
    {"from": "reference",  "to": "sequence",   "delta": 0.3, "resistance": 0.5,
     "initial_U": 5.0, "initial_F": 1.0, "confidence": 0.7},
    {"from": "enumeration","to": "grouping",   "delta": 0.3, "resistance": 0.5,
     "initial_U": 5.0, "initial_F": 1.0, "confidence": 0.8},

    # Visual → Language (perception informs speech act choice)
    {"from": "emphasis",   "to": "assertion",  "delta": 0.3, "resistance": 0.6,
     "initial_U": 4.0, "initial_F": 1.5, "confidence": 0.6},
    {"from": "absence",    "to": "uncertainty","delta": 0.4, "resistance": 0.7,
     "initial_U": 3.0, "initial_F": 2.0, "confidence": 0.5},
    {"from": "hierarchy",  "to": "enumeration","delta": 0.3, "resistance": 0.5,
     "initial_U": 5.0, "initial_F": 1.0, "confidence": 0.7},

    # Language → Language (speech act flow)
    {"from": "question",   "to": "uncertainty","delta": 0.3, "resistance": 0.4,
     "initial_U": 5.0, "initial_F": 1.0, "confidence": 0.8},
    {"from": "assertion",  "to": "reference",  "delta": 0.2, "resistance": 0.4,
     "initial_U": 5.0, "initial_F": 1.0, "confidence": 0.7},
]


def default_perception_spec() -> Dict[str, Any]:
    """Return the default perception domain spec for bootstrapping."""
    return {
        "nodes": list(ALL_PRIMITIVES),
        "edges": list(_DEFAULT_EDGES),
    }


# ──────────────────────────────────────────────
# 3. Perception Profile
# ──────────────────────────────────────────────

@dataclass(frozen=True)
class PerceptionProfile:
    """Snapshot of a single perception primitive's state.

    Extracted from the perception landscape's historization traces.
    """
    name: str
    kind: PerceptionKind
    trace_load: float      # total inscription (U+F)
    quality: float         # directional balance [-1, +1]
    outgoing_edges: int    # connectivity
    avg_outgoing_quality: float  # mean quality on outgoing edges

    @property
    def strength(self) -> float:
        """Effective perception strength: load × quality (clamped ≥ 0).

        A primitive with high trace_load and high quality is strongly
        reinforced. Negative quality (failed perceptions) clamp to 0.
        """
        return self.trace_load * max(0.0, self.quality)


@dataclass(frozen=True)
class PerceptionSnapshot:
    """Complete snapshot of the perception landscape state."""
    profiles: List[PerceptionProfile]
    total_load: float
    visual_load: float
    language_load: float

    def by_name(self, name: str) -> PerceptionProfile:
        """Look up a profile by primitive name."""
        for p in self.profiles:
            if p.name == name:
                return p
        raise KeyError(f"No profile for {name!r}")

    def ranked(self, kind: Optional[PerceptionKind] = None) -> List[PerceptionProfile]:
        """Return profiles ranked by strength (descending).

        If kind is given, filter to that kind only.
        """
        subset = self.profiles if kind is None else [
            p for p in self.profiles if p.kind == kind
        ]
        return sorted(subset, key=lambda p: p.strength, reverse=True)

    def top(self, n: int = 3, kind: Optional[PerceptionKind] = None) -> List[PerceptionProfile]:
        """Return the top-n strongest perception primitives."""
        return self.ranked(kind)[:n]


# ──────────────────────────────────────────────
# 4. Perception Domain
# ──────────────────────────────────────────────

class PerceptionDomain:
    """Manages the perception landscape as a learnable domain.

    Build via ``build_perception_domain()`` or ``from_spec()``.
    The underlying landscape is a normal E0 Landscape — all standard
    operations (historization, inertia, trace queries) work on it.
    """

    def __init__(self, landscape: Landscape, primitives: List[str]) -> None:
        self._landscape = landscape
        self._primitives = list(primitives)

    @property
    def landscape(self) -> Landscape:
        return self._landscape

    @property
    def primitives(self) -> List[str]:
        return list(self._primitives)

    @property
    def visual_primitives(self) -> List[str]:
        return [p for p in self._primitives if p in VISUAL_PRIMITIVES]

    @property
    def language_primitives(self) -> List[str]:
        return [p for p in self._primitives if p in LANGUAGE_PRIMITIVES]

    def profile(self, name: str) -> PerceptionProfile:
        """Extract the current profile for a single primitive."""
        if name not in self._primitives:
            raise KeyError(f"Unknown primitive: {name!r}")
        hist = self._landscape.historization
        outgoing = [e for e in self._landscape.edges if e.source == name]
        loads = [hist.trace_load(e) for e in outgoing]
        quals = [hist.trace_quality(e) for e in outgoing]
        total_load = sum(loads)
        avg_quality = sum(quals) / len(quals) if quals else 0.0
        # Node-level load/quality: sum across all outgoing edges
        all_edges = [e for e in self._landscape.edges
                     if e.source == name or e.target == name]
        node_U = sum(hist._effective_traces(e)[0] for e in all_edges)
        node_F = sum(hist._effective_traces(e)[1] for e in all_edges)
        node_load = node_U + node_F
        node_quality = (node_U - node_F) / (node_U + node_F + 1e-12)
        return PerceptionProfile(
            name=name,
            kind=primitive_kind(name),
            trace_load=node_load,
            quality=node_quality,
            outgoing_edges=len(outgoing),
            avg_outgoing_quality=avg_quality,
        )

    def snapshot(self) -> PerceptionSnapshot:
        """Extract a complete perception snapshot."""
        profiles = [self.profile(p) for p in self._primitives]
        total = sum(p.trace_load for p in profiles)
        vis = sum(p.trace_load for p in profiles
                  if p.kind == PerceptionKind.VISUAL)
        lang = sum(p.trace_load for p in profiles
                   if p.kind == PerceptionKind.LANGUAGE)
        return PerceptionSnapshot(
            profiles=profiles,
            total_load=total,
            visual_load=vis,
            language_load=lang,
        )

    def suggest_perception(self, n: int = 3,
                           kind: Optional[PerceptionKind] = None
                           ) -> List[str]:
        """Suggest the top-n perception primitives to use right now.

        Based on current strength (trace_load × quality). High strength
        means E0 has evidence that this perception mode works.
        """
        snap = self.snapshot()
        return [p.name for p in snap.top(n, kind)]


# ──────────────────────────────────────────────
# 5. Builder Functions
# ──────────────────────────────────────────────

def build_perception_domain(
    spec: Optional[Dict[str, Any]] = None,
) -> PerceptionDomain:
    """Build a perception domain from a spec (or use the default).

    The default spec contains 15 perception primitives with 20 sparse
    directed edges encoding Gestalt support relationships.

    Args:
        spec: Optional custom domain spec. If None, uses the default
              perception ontology.

    Returns:
        A PerceptionDomain wrapping an initialized Landscape.
    """
    if spec is None:
        spec = default_perception_spec()
    landscape = bootstrap_landscape(spec)
    primitives = list(spec["nodes"])
    return PerceptionDomain(landscape, primitives)


def from_landscape(landscape: Landscape,
                   primitives: Optional[List[str]] = None
                   ) -> PerceptionDomain:
    """Wrap an existing landscape as a PerceptionDomain.

    Useful when the perception landscape has been evolved through
    historization and should be re-wrapped (e.g., after session restore).

    Args:
        landscape: An already-initialized landscape.
        primitives: List of primitive names. If None, uses all states
                    in the landscape.
    """
    if primitives is None:
        primitives = sorted(landscape.states)
    return PerceptionDomain(landscape, primitives)
