"""
E₀ LandscapeBootstrapper (C299-C300)
======================================
Converts domain knowledge (natural language chunks) into a stable E₀ Landscape.

Design principles:
    1. Phase separation — Bootstrap THEN Navigate (never interleave).
       After finalize() the Landscape is frozen. All Historization
       accumulated during navigation is valid against a stable structure.

    2. Option B: guided extraction.
       The caller specifies CATEGORIES of states (e.g. "decision point",
       "information state"). The LLM extracts ONLY states of those types.
       Controllable and predictable. Option A (freeform) can be built on
       top later by passing a single broad category.

    3. Validation before build (GT-2 Blind Trust Trap prevention).
       LLM output passes a schema check before any Landscape modification.
       Invalid JSON raises BootstrapValidationError immediately.
       Invalid edges are skipped with a reason recorded — no silent failure.

    4. Partial-valid builds allowed.
       If some edges are malformed but others are valid, the valid subset
       is used. The caller can inspect schema.skipped_edges for diagnostics.

    5. InteractiveBootstrapSession — multistep chunk collection.
       add_chunk() accumulates text; finalize() makes the single LLM call.
       This is the "chat-style" bootstrap flow. Only one LLM call per session.

─────────────────────────────────────────────────────────────
Key types:
    BootstrapValidationError  — raised on unrecoverable schema errors
    BootstrapEdgeSpec         — one validated edge from LLM output
    BootstrapSchema           — validated, ready-to-build landscape spec
    BootstrapResult           — Landscape + diagnostics

Key classes:
    LandscapeBootstrapper        — single call: chunks → Landscape
    InteractiveBootstrapSession  — multistep: add_chunk() → finalize()

─────────────────────────────────────────────────────────────
Usage (single call):
    from e0_controller.landscape_bootstrapper import LandscapeBootstrapper
    from e0_controller.llm_adapter import LLMConfig

    bs = LandscapeBootstrapper(
        categories=["decision point", "information state"],
        config=LLMConfig(),
    )
    result = bs.bootstrap(
        chunks=["Customer profile: ...", "Competitor analysis: ..."],
        start="INTEL_GAP",
        goal="OFFER_SUBMITTED",
    )
    # result.landscape is a stable Landscape, ready for E0Turn
    session = E0Turn(result.landscape, port)

Usage (multistep):
    session = InteractiveBootstrapSession(
        categories=["decision point", "information state"],
        config=LLMConfig(),
    )
    session.add_chunk("Customer profile: ...")
    session.add_chunk("Competitor analysis: ...")
    result = session.finalize(start="INTEL_GAP", goal="OFFER_SUBMITTED")
    landscape = result.landscape
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from .landscape import Landscape
from .llm_adapter import LLMCallFn, LLMConfig, openai_call


# ── Errors ────────────────────────────────────────────────────────────────────

class BootstrapValidationError(Exception):
    """Raised when LLM output violates the bootstrap schema.

    Attributes:
        errors:  List of specific validation error messages.
        raw:     Raw LLM response (for diagnostics).
    """

    def __init__(
        self, message: str, errors: List[str], raw: str = ""
    ) -> None:
        super().__init__(message)
        self.errors: List[str] = errors
        self.raw: str = raw


# ── Data types ────────────────────────────────────────────────────────────────

@dataclass
class BootstrapEdgeSpec:
    """One edge as returned by the LLM, after validation.

    Fields map 1:1 to the JSON schema the LLM must produce.
    """
    source: str
    target: str
    delta: float       # Δ structural difference, clamped to [0.0, 1.0]
    resistance: float  # R₀ base resistance, clamped to [0.0, 2.0]
    label: str = ""    # human-readable description of the transition


@dataclass
class BootstrapSchema:
    """Validated, ready-to-build Landscape specification.

    Built by LandscapeBootstrapper._validate_and_parse().
    All fields are guaranteed internally consistent.

    Fields:
        states:          All unique state names (derived from valid edges).
        edges:           Validated BootstrapEdgeSpecs.
        start:           Start state — present in states.
        goal:            Goal state — present in states.
        domain_summary:  One-line domain description from LLM.
        skipped_edges:   Edges that failed validation: (raw_dict, reason).
        warnings:        Non-fatal structural issues (e.g. missing path).
    """
    states: List[str]
    edges: List[BootstrapEdgeSpec]
    start: str
    goal: str
    domain_summary: str = ""
    skipped_edges: List[Tuple[Any, str]] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


@dataclass
class BootstrapResult:
    """Result of one bootstrap call.

    Fields:
        landscape:    Ready-to-use E₀ Landscape. Treat as frozen after
                      this point — do not add edges during navigation.
        schema:       The validated BootstrapSchema used to build it.
        raw_response: Raw LLM JSON string (for logging/diagnostics).
        llm_tokens:   Token count from LLM call (0 if unavailable).
    """
    landscape: Landscape
    schema: BootstrapSchema
    raw_response: str = ""
    llm_tokens: int = 0


# ── Prompts ───────────────────────────────────────────────────────────────────

# System prompt — guides the LLM to produce the exact JSON schema.
# {categories_str}, {start}, {goal}, {max_states} are filled per call.
_SYSTEM_PROMPT = """\
You are an E0 Landscape Extractor. Extract a decision graph from the domain \
knowledge provided.

You will receive:
  - CATEGORIES: the types of states to extract (ONLY these types).
  - KNOWLEDGE CHUNKS: domain texts to analyse.
  - START and GOAL: the required start and goal states.

Output exactly one JSON object:

{{
  "domain_summary": "<one sentence describing this decision domain>",
  "edges": [
    {{
      "source": "STATE_NAME",
      "target": "STATE_NAME",
      "delta": 0.5,
      "resistance": 0.8,
      "label": "what changes during this transition"
    }}
  ]
}}

Constraints:
1. Extract ONLY states matching the CATEGORIES: {categories_str}.
2. State names: UPPER_SNAKE_CASE, max 30 chars, no spaces.
3. delta: float 0.0-1.0. Higher = more structural change required.
4. resistance: float 0.0-2.0. Higher = more effort / cost / risk.
5. "{start}" and "{goal}" MUST appear in the graph.
6. The graph MUST contain at least one path from "{start}" to "{goal}".
7. Maximum {max_states} distinct states.
8. Include only edges grounded in the provided knowledge. Do NOT invent.
9. Output ONLY the JSON object. No markdown. No explanation outside JSON.
"""

_USER_PROMPT = """\
CATEGORIES: {categories_str}
START: {start}
GOAL: {goal}

KNOWLEDGE CHUNKS:
{chunks_text}
"""


# ── Core Bootstrapper ─────────────────────────────────────────────────────────

class LandscapeBootstrapper:
    """Converts domain knowledge chunks into a stable E₀ Landscape.

    Args:
        categories:          Types of states to extract (Option B guidance).
                             Example: ["decision point", "information state"]
                             Passed verbatim to the LLM prompt.
        config:              LLMConfig. Defaults to LLMConfig() if None.
        call_fn:             LLM backend. Defaults to openai_call.
                             Override for testing: pass a function
                             (system, user, config) -> str.
        max_states:          Max states in extracted Landscape (default 12).
        default_delta:       Fallback delta if LLM omits it (default 0.5).
        default_resistance:  Fallback resistance if LLM omits it (default 1.0).
    """

    def __init__(
        self,
        categories: List[str],
        config: Optional[LLMConfig] = None,
        call_fn: Optional[LLMCallFn] = None,
        max_states: int = 12,
        default_delta: float = 0.5,
        default_resistance: float = 1.0,
    ) -> None:
        if not categories:
            raise ValueError(
                "categories must not be empty — "
                "Option B requires at least one category to guide extraction"
            )
        self._categories = list(categories)
        self._config = config or LLMConfig()
        self._call_fn: LLMCallFn = call_fn or openai_call
        self._max_states = max_states
        self._default_delta = default_delta
        self._default_resistance = default_resistance

    # ── Public API ────────────────────────────────────────────────────────────

    def bootstrap(
        self,
        chunks: List[str],
        start: str,
        goal: str,
    ) -> BootstrapResult:
        """Build a Landscape from knowledge chunks.

        Args:
            chunks:  Domain knowledge strings. Concatenated and sent to LLM.
            start:   Start state name (will be normalised to UPPER_SNAKE_CASE).
            goal:    Goal state name (will be normalised to UPPER_SNAKE_CASE).

        Returns:
            BootstrapResult with .landscape ready for E0Turn.

        Raises:
            ValueError:               If chunks is empty.
            BootstrapValidationError: If LLM output is structurally invalid
                                      and no valid landscape can be built.
        """
        if not chunks:
            raise ValueError("chunks must not be empty")

        categories_str = ", ".join(self._categories)
        chunks_text = "\n\n---\n\n".join(
            f"[Chunk {i + 1}]\n{chunk.strip()}"
            for i, chunk in enumerate(chunks)
        )

        system = _SYSTEM_PROMPT.format(
            categories_str=categories_str,
            start=_normalise(start),
            goal=_normalise(goal),
            max_states=self._max_states,
        )
        user = _USER_PROMPT.format(
            categories_str=categories_str,
            start=_normalise(start),
            goal=_normalise(goal),
            chunks_text=chunks_text,
        )

        raw = self._call_fn(system, user, self._config)
        schema = self._validate_and_parse(raw, start, goal)
        landscape = self._build_landscape(schema)

        return BootstrapResult(
            landscape=landscape,
            schema=schema,
            raw_response=raw,
        )

    # ── Validation ────────────────────────────────────────────────────────────

    def _validate_and_parse(
        self, raw: str, start: str, goal: str
    ) -> BootstrapSchema:
        """Parse and validate raw LLM JSON → BootstrapSchema.

        Validation tiers:
            Fatal (raise BootstrapValidationError):
                V1: valid JSON
                V2: 'edges' key present and list
                V3: at least one edge passes edge validation

            Per-edge (skip invalid, record in skipped_edges):
                V4: source and target are non-empty strings
                V5: no self-loops

            Soft warnings (added to schema.warnings):
                W1: start / goal absent from extracted graph
                W2: no reachable path from start to goal
        """
        warnings: List[str] = []

        # V1: valid JSON
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise BootstrapValidationError(
                f"LLM returned invalid JSON: {exc}",
                errors=[f"JSONDecodeError: {exc}"],
                raw=raw,
            ) from exc

        if not isinstance(data, dict):
            raise BootstrapValidationError(
                "LLM response is JSON but not a dict",
                errors=["Expected JSON object at root"],
                raw=raw,
            )

        domain_summary = str(data.get("domain_summary", ""))

        # V2: edges list
        raw_edges = data.get("edges")
        if not isinstance(raw_edges, list):
            raise BootstrapValidationError(
                "LLM response missing 'edges' list",
                errors=["'edges' key absent or not a list"],
                raw=raw,
            )

        # Per-edge validation
        valid_edges: List[BootstrapEdgeSpec] = []
        skipped: List[Tuple[Any, str]] = []

        for raw_edge in raw_edges:
            if not isinstance(raw_edge, dict):
                skipped.append((raw_edge, "not a dict"))
                continue

            src_raw = raw_edge.get("source", "")
            tgt_raw = raw_edge.get("target", "")

            # V4: source/target
            if not isinstance(src_raw, str) or not src_raw.strip():
                skipped.append((raw_edge, "missing or empty 'source'"))
                continue
            if not isinstance(tgt_raw, str) or not tgt_raw.strip():
                skipped.append((raw_edge, "missing or empty 'target'"))
                continue

            src = _normalise(src_raw)
            tgt = _normalise(tgt_raw)

            # V5: self-loop
            if src == tgt:
                skipped.append((raw_edge, f"self-loop on '{src}'"))
                continue

            # delta / resistance — use defaults on bad values (not fatal)
            delta = _safe_float(raw_edge.get("delta"), self._default_delta)
            resistance = _safe_float(
                raw_edge.get("resistance"), self._default_resistance
            )
            delta = max(0.0, min(1.0, delta))
            resistance = max(0.0, min(2.0, resistance))
            label = str(raw_edge.get("label", ""))

            valid_edges.append(
                BootstrapEdgeSpec(
                    source=src,
                    target=tgt,
                    delta=delta,
                    resistance=resistance,
                    label=label,
                )
            )

        # V3: at least one valid edge
        if not valid_edges:
            raise BootstrapValidationError(
                f"No valid edges after validation ({len(raw_edges)} raw edges)",
                errors=[f"All edges failed: {[s for _, s in skipped]}"],
                raw=raw,
            )

        # Collect all unique states (order-preserving)
        seen: Dict[str, None] = {}
        for edge in valid_edges:
            seen.setdefault(edge.source, None)
            seen.setdefault(edge.target, None)

        start_norm = _normalise(start)
        goal_norm = _normalise(goal)

        # W1: start / goal absent
        if start_norm not in seen:
            seen[start_norm] = None
            warnings.append(
                f"start={start_norm!r} absent from extracted edges — "
                "added as isolated state"
            )
        if goal_norm not in seen:
            seen[goal_norm] = None
            warnings.append(
                f"goal={goal_norm!r} absent from extracted edges — "
                "added as isolated state"
            )

        # W2: reachability
        if not _has_path(valid_edges, start_norm, goal_norm):
            warnings.append(
                f"No path from {start_norm!r} to {goal_norm!r} — "
                "E0 may not reach the goal"
            )

        return BootstrapSchema(
            states=list(seen.keys()),
            edges=valid_edges,
            start=start_norm,
            goal=goal_norm,
            domain_summary=domain_summary,
            skipped_edges=skipped,
            warnings=warnings,
        )

    # ── Build ─────────────────────────────────────────────────────────────────

    def _build_landscape(self, schema: BootstrapSchema) -> Landscape:
        """Build a Landscape from a validated BootstrapSchema."""
        ls = Landscape()
        for state in schema.states:
            ls.add_state(state)
        for edge in schema.edges:
            ls.add_edge(
                edge.source,
                edge.target,
                delta=edge.delta,
                resistance=edge.resistance,
                label=edge.label,
            )
        return ls


# ── Interactive Session ───────────────────────────────────────────────────────

class InteractiveBootstrapSession:
    """Multistep bootstrap — collect chunks, then call finalize() once.

    This is the "chat-style" interface:

        session = InteractiveBootstrapSession(categories=[...])
        session.add_chunk("Customer profile: ...")     # step 1
        session.add_chunk("Competitor analysis: ...")  # step 2
        session.add_chunk("Own product strengths: ...") # step 3
        result = session.finalize(start="...", goal="...")
        landscape = result.landscape   # frozen, ready for E0Turn

    Phase contract:
        - Only one LLM call happens (at finalize()).
        - After finalize(), add_chunk() raises RuntimeError.
        - The returned Landscape must not be modified after finalize().

    Properties:
        chunks:       List[str] — chunks added so far (read-only copy)
        chunk_count:  int
        is_final:     bool — True after finalize()
        result:       Optional[BootstrapResult] — None before finalize()
    """

    def __init__(
        self,
        categories: List[str],
        config: Optional[LLMConfig] = None,
        call_fn: Optional[LLMCallFn] = None,
        max_states: int = 12,
        default_delta: float = 0.5,
        default_resistance: float = 1.0,
    ) -> None:
        self._bootstrapper = LandscapeBootstrapper(
            categories=categories,
            config=config,
            call_fn=call_fn,
            max_states=max_states,
            default_delta=default_delta,
            default_resistance=default_resistance,
        )
        self._chunks: List[str] = []
        self._is_final: bool = False
        self._result: Optional[BootstrapResult] = None

    # ── Chunk management ──────────────────────────────────────────────────────

    def add_chunk(self, text: str) -> int:
        """Add a knowledge chunk to this session.

        Args:
            text: Domain knowledge string. Empty/whitespace-only is ignored.

        Returns:
            Number of chunks accumulated so far.

        Raises:
            RuntimeError: After finalize() has been called.
        """
        if self._is_final:
            raise RuntimeError(
                "Cannot add chunks after finalize() — session is frozen. "
                "Create a new InteractiveBootstrapSession for a new domain."
            )
        stripped = text.strip() if text else ""
        if stripped:
            self._chunks.append(stripped)
        return len(self._chunks)

    def finalize(self, start: str, goal: str) -> BootstrapResult:
        """Build the Landscape from all accumulated chunks (single LLM call).

        Args:
            start: Start state name.
            goal:  Goal state name.

        Returns:
            BootstrapResult with .landscape ready for E0Turn.

        Raises:
            RuntimeError:             No chunks added, or called twice.
            BootstrapValidationError: LLM output invalid.
        """
        if self._is_final:
            raise RuntimeError(
                "finalize() already called. Access .result for the result."
            )
        if not self._chunks:
            raise RuntimeError(
                "No chunks added. Call add_chunk() at least once."
            )

        self._result = self._bootstrapper.bootstrap(
            chunks=self._chunks,
            start=start,
            goal=goal,
        )
        self._is_final = True
        return self._result

    # ── Properties ────────────────────────────────────────────────────────────

    @property
    def chunks(self) -> List[str]:
        return list(self._chunks)

    @property
    def chunk_count(self) -> int:
        return len(self._chunks)

    @property
    def is_final(self) -> bool:
        return self._is_final

    @property
    def result(self) -> Optional[BootstrapResult]:
        return self._result


# ── Helpers ───────────────────────────────────────────────────────────────────

def _normalise(name: str) -> str:
    """Normalise a state name: strip, upper, spaces→underscore."""
    return name.strip().upper().replace(" ", "_").replace("-", "_")


def _safe_float(value: Any, default: float) -> float:
    """Convert value to float; return default on failure."""
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _has_path(edges: List[BootstrapEdgeSpec], start: str, goal: str) -> bool:
    """BFS reachability: is goal reachable from start via the edge list?"""
    if start == goal:
        return True
    adjacency: Dict[str, List[str]] = {}
    for edge in edges:
        adjacency.setdefault(edge.source, []).append(edge.target)

    visited = {start}
    queue = [start]
    while queue:
        node = queue.pop(0)
        for neighbor in adjacency.get(node, []):
            if neighbor == goal:
                return True
            if neighbor not in visited:
                visited.add(neighbor)
                queue.append(neighbor)
    return False
