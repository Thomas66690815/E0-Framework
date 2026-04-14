"""
E₀ Controller — LLM Adapter (Phase 3a)
========================================
Structured interface between the E₀ controller stack and an OpenAI-compatible LLM.

The adapter does NOT replace the controller. It provides three semantic functions
that the controller cannot do deterministically:

    1. extract_delta()      — LLM estimates Δ(x,y) from natural language
    2. propose_states()     — LLM suggests reachable states from a description
    3. execute_transition() — LLM performs the work of a transition and reports outcome

The adapter receives a MemOS summary (from summarize_for_llm()) as context,
so the LLM always sees the current E₀ state, not raw chat history.

Architecture: A3 Hybrid
    - Python Controller: deterministic S_eff, path selection, historization
    - LLM: semantic understanding, Δ-estimation, natural-language execution
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

from .primitives import Outcome


class LLMResponseError(Exception):
    """Raised when the LLM returns unparseable or invalid output."""
    def __init__(self, message: str, raw_response: str = ""):
        super().__init__(message)
        self.raw_response = raw_response


# ──────────────────────────────────────────────
# Configuration
# ──────────────────────────────────────────────

@dataclass
class LLMConfig:
    """Configuration for the LLM connection."""
    model: str = "gpt-5.4-mini"
    temperature: float = 0.2
    max_tokens: int = 1024
    api_key: Optional[str] = None

    def resolve_api_key(self) -> str:
        """Return API key from config, env, or .env file."""
        if self.api_key:
            return self.api_key

        # Check environment
        key = os.environ.get("OPENAI_API_KEY")
        if key:
            return key

        # Try .env file in cwd
        env_path = os.path.join(os.getcwd(), ".env")
        if os.path.exists(env_path):
            with open(env_path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("OPENAI_API_KEY="):
                        return line.split("=", 1)[1].strip()

        raise RuntimeError(
            "No API key found. Set OPENAI_API_KEY in environment or .env file."
        )


# ──────────────────────────────────────────────
# LLM Call Abstraction
# ──────────────────────────────────────────────

# Type for pluggable LLM backends (for testing / alternative providers)
LLMCallFn = Callable[[str, str, LLMConfig], str]


def openai_call(system: str, user: str, config: LLMConfig) -> str:
    """Call OpenAI API. Requires `openai` package."""
    import openai
    client = openai.OpenAI(api_key=config.resolve_api_key())
    response = client.chat.completions.create(
        model=config.model,
        temperature=config.temperature,
        max_completion_tokens=config.max_tokens,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    )
    return response.choices[0].message.content or ""


# ──────────────────────────────────────────────
# Prompt Templates
# ──────────────────────────────────────────────

SYSTEM_PROMPT = """\
You are the semantic interface of the E₀ reasoning controller.

E₀ is a transition framework built from three primitives:
- Δ (difference): how structurally different two states are (0 = identical, 1 = maximal)
- R (resistance): how difficult a transition is to execute (modified by history)
- H (historization): success/failure traces that alter future resistance

From these, E₀ derives:
- Tension S = Δ · R_eff — the integration burden of a transition
- Coherence C = exp(−S) — how structurally open a transition is (high = easy)
- Transition field v = Δ · M_H · exp(−S) — directional transition capacity
- Connection ω — antisymmetric phase from the rotational component of v
- Path phase Θ = Σω — accumulated orientation along a path
- Path amplitude Ψ = exp(−S) · exp(iΘ) — complex path representation
- Intensity I = |Ψ|² — structural weight of a path family

The controller selects transitions by minimizing S_eff (greedy) or by
comparing amplitude-derived intensities across path families (hybrid mode).
When greedy and amplitude disagree, the amplitude choice can override.

M_H is the topological modulation factor: M_H = 1/(1+κ), where κ is the
local edge curvature from face holonomies. High curvature damps transitions.
When curvature_modulation is off (default), M_H = 1.

You receive structured state information from the E₀ runtime:
- current_state: where the system is now
- admissible_neighbors: reachable states with tension/coherence data
- edge_history: success/failure traces for edges in the neighborhood
- runtime: recent path and escalation context

Your role is to provide structured, parseable responses.
Always respond in the exact JSON format requested. No markdown, no explanation outside the JSON."""

EXTRACT_DELTA_PROMPT = """\
Estimate the structural difference Δ(x, y) between two states.

Δ measures how structurally different two states are:
- 0.0 = identical (no transition needed)
- 0.1–0.3 = minor difference (simple, mechanical step)
- 0.3–0.6 = moderate difference (requires non-trivial work)
- 0.6–0.9 = major difference (fundamentally different)
- 1.0 = maximal difference

Context from E₀ runtime:
{context}

Estimate Δ for this transition:
  source: {source}
  target: {target}
  description: {description}

Respond with exactly this JSON (no other text):
{{"delta": <float between 0.0 and 1.0>, "reasoning": "<one sentence>"}}"""

PROPOSE_STATES_PROMPT = """\
Given the current E₀ state, propose reachable next states.

Context from E₀ runtime:
{context}

Current state: {current_state}
Task description: {description}

Propose 2-5 reachable states. Each state should be a short, uppercase identifier
(like DATA_EXTRACTED, CUSTOMER_FOUND) with a brief description.

Respond with exactly this JSON (no other text):
{{"states": [{{"name": "<STATE_NAME>", "description": "<what this state means>", "estimated_delta": <float>}}]}}"""

EXECUTE_TRANSITION_PROMPT = """\
Execute the transition from source to target state.

Context from E₀ runtime:
{context}
{scenario_block}
Transition: {source} → {target}
Task: {task}

Perform the work implied by this transition using the source material provided.
Ground your output in the scenario content. Do not invent facts not present in the source.

Respond with exactly this JSON (no other text):
{{
  "outcome": "<SUCCESS|FAILURE|PARTIAL>",
  "result": "<what was accomplished or why it failed>",
  "confidence": <float between 0.0 and 1.0>
}}"""


ESTIMATE_RESISTANCE_PROMPT = """\
Estimate the structural resistance R₀ for a transition between two states.

R₀ measures how difficult a transition is to execute, independent of history:
- 0.1–0.3 = easy (routine, well-understood step)
- 0.3–0.7 = moderate (requires some effort or judgment)
- 0.7–1.5 = hard (complex, error-prone, requires expertise)
- 1.5–3.0 = very hard (likely to fail, deep expertise needed)
- 3.0+    = extremely difficult (near-impossible, research-level)

Context from E₀ runtime:
{context}

Estimate R₀ for this transition:
  source: {source}
  target: {target}
  description: {description}

Respond with exactly this JSON (no other text):
{{"resistance": <float > 0>, "reasoning": "<one sentence>"}}"""


BUILD_LANDSCAPE_PROMPT = """\
Given a task description, design the complete state graph for an E₀ controller.

An E₀ landscape consists of:
- States: discrete milestones (UPPER_CASE identifiers)
- Edges: directed transitions between states, each with:
  - delta: structural difference Δ ∈ [0,1] (how different source and target are)
  - resistance: base difficulty R₀ > 0 (how hard the transition is)

Rules:
- First state must be the starting point
- Last state must be the goal
- Include both happy path and at least one error/recovery path
- Keep it bounded: 5–15 states, 8–25 edges
- State names must be UPPER_CASE with underscores

Context from E₀ runtime:
{context}
{scenario_block}
Task: {task}
Start state: {start}
{goal}

Respond with exactly this JSON (no other text):
{{
  "states": ["STATE_A", "STATE_B", ...],
  "edges": [
    {{"source": "STATE_A", "target": "STATE_B", "delta": 0.4, "resistance": 0.8, "description": "what this transition does"}},
    ...
  ]
}}"""


REBUILD_LANDSCAPE_PROMPT = """\
The previous E₀ landscape for this task produced structural problems.
Redesign the state graph based on the diagnostic evidence below.

An E₀ landscape consists of:
- States: discrete milestones (UPPER_CASE identifiers)
- Edges: directed transitions between states, each with:
  - delta: structural difference Δ ∈ [0,1]
  - resistance: base difficulty R₀ > 0

Previous landscape:
  States: {old_states}
  Edges: {old_edges}

Structural diagnostic:
{diagnostic_block}

Rules:
- You MUST restructure the topology, not just tweak edge weights
- Address every problem listed in the diagnostic
- Keep start state "{start}" and goal state "{goal}"
- Include error/recovery paths
- Keep it bounded: 5–15 states, 8–25 edges
- State names must be UPPER_CASE with underscores

{scenario_block}
Task: {task}

Respond with exactly this JSON (no other text):
{{
  "states": ["STATE_A", "STATE_B", ...],
  "edges": [
    {{"source": "STATE_A", "target": "STATE_B", "delta": 0.4, "resistance": 0.8, "description": "what this transition does"}},
    ...
  ]
}}"""

PROPOSE_DOMAIN_GRAPH_PROMPT = """\
Given a domain description, design a complete E₀ domain graph.

An E₀ domain graph defines the decision landscape for a specific domain:
- Nodes: distinct states or milestones (UPPER_CASE identifiers)
- Edges: directed transitions, each with structural parameters AND
  your confidence estimate for each edge.

Edge parameters:
- delta: structural difference Δ ∈ [0,1] (how different source and target are)
- resistance: base difficulty R₀ > 0 (how hard the transition is)
- initial_U: expected number of successes on this edge (≥ 0)
    High initial_U means you expect this transition to succeed often.
- initial_F: expected number of failures on this edge (≥ 0)
    High initial_F means you expect this transition to fail often.
- confidence: how sure you are about your U/F estimates ∈ [0,1]
    1.0 = certain, 0.5 = moderate guess, 0.0 = pure speculation.
    Low confidence makes E0 cautious (high inertia) on that edge.

Guidelines:
- Use UPPER_CASE identifiers with underscores for node names
- Keep the graph bounded: 4–12 nodes, 6–20 edges
- Include both forward paths and recovery/fallback edges
- For well-understood transitions: high initial_U, low initial_F, high confidence
- For uncertain transitions: moderate initial_U and initial_F, low confidence
- For risky transitions: low initial_U, high initial_F, moderate confidence
- No self-loops (an edge cannot go from a node to itself)

Context from E₀ runtime:
{context}

Domain description: {description}

Respond with exactly this JSON (no other text):
{{
  "nodes": ["STATE_A", "STATE_B", ...],
  "edges": [
    {{"from": "STATE_A", "to": "STATE_B", "delta": 0.4, "resistance": 0.8, "initial_U": 5.0, "initial_F": 1.0, "confidence": 0.7}},
    ...
  ]
}}"""

SYNTHESIZE_ANSWER_PROMPT = """\
You are synthesizing an answer based on structural evidence from E₀ navigation.

E₀ navigated its knowledge landscape to answer a question. Below is the
evidence trail: the sequence of concepts visited, their descriptions,
the types of connections between them, and navigation quality metrics.

Your job: synthesize a coherent, informative answer to the question using
ONLY the evidence provided. Do not invent facts. If the evidence is
insufficient, say so honestly.

Question: {question}

Navigation path (concepts visited in order):
{path_evidence}

Navigation metrics:
  Steps: {steps}
  Domain crossings: {domain_crossings}
  Coverage change: {coverage_delta}

Respond with exactly this JSON (no other text):
{{
  "answer": "Your synthesized answer as a clear paragraph (2-5 sentences).",
  "confidence": 0.7,
  "key_concepts": ["concept1", "concept2", "concept3"],
  "evidence_sufficient": true
}}"""

# ──────────────────────────────────────────────
# Response Parsing
# ──────────────────────────────────────────────

def _parse_json_response(
    text: str,
    required_keys: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Extract JSON from LLM response with robust fallback parsing.

    Handles common LLM failure modes:
      1. Clean JSON — parse directly
      2. Markdown code fences — strip ```json ... ```
      3. Preamble/postamble text — extract first { ... last }
      4. Trailing commas — remove before parsing
      5. Single-line // comments — strip before parsing

    Args:
        text: Raw LLM response string.
        required_keys: If given, validates that every key is present in the
            parsed dict.  Raises LLMResponseError on missing keys.

    Raises LLMResponseError if the response cannot be parsed or is
    structurally invalid.
    """
    raw = text
    text = text.strip()

    # Strategy 1: direct parse (fast path)
    data = _try_json_loads(text)

    # Strategy 2: strip markdown code fences
    if data is None:
        m = re.search(r"```(?:json)?\s*\n?(.*?)\n?\s*```", text, re.DOTALL)
        if m:
            data = _try_json_loads(m.group(1).strip())

    # Strategy 3: extract first { ... last } (handles preamble/postamble)
    if data is None:
        first_brace = text.find("{")
        last_brace = text.rfind("}")
        if first_brace != -1 and last_brace > first_brace:
            candidate = text[first_brace:last_brace + 1]
            data = _try_json_loads(candidate)

    # Strategy 4: fix trailing commas and re-try strategies 1-3
    if data is None:
        cleaned = _fix_json_quirks(text)
        data = _try_json_loads(cleaned)
        if data is None:
            first_brace = cleaned.find("{")
            last_brace = cleaned.rfind("}")
            if first_brace != -1 and last_brace > first_brace:
                candidate = cleaned[first_brace:last_brace + 1]
                data = _try_json_loads(candidate)

    if data is None:
        raise LLMResponseError(
            f"LLM returned invalid JSON (all parsing strategies failed)",
            raw_response=raw,
        )

    if not isinstance(data, dict):
        raise LLMResponseError(
            f"Expected JSON object, got {type(data).__name__}",
            raw_response=raw,
        )

    if required_keys:
        missing = [k for k in required_keys if k not in data]
        if missing:
            raise LLMResponseError(
                f"LLM response missing required keys: {missing}",
                raw_response=raw,
            )

    return data


def _try_json_loads(text: str) -> Optional[Dict[str, Any]]:
    """Try json.loads, return None on failure instead of raising."""
    try:
        result = json.loads(text)
        return result if isinstance(result, dict) else None
    except (json.JSONDecodeError, ValueError):
        return None


def _fix_json_quirks(text: str) -> str:
    """Fix common LLM JSON quirks: trailing commas, // comments."""
    # Remove single-line // comments (but not inside strings)
    text = re.sub(r'(?m)^\s*//.*$', '', text)
    text = re.sub(r'(?<=\S)\s*//[^"]*$', '', text, flags=re.MULTILINE)
    # Remove trailing commas before } or ]
    text = re.sub(r',\s*([}\]])', r'\1', text)
    return text


_STATE_NAME_RE = re.compile(r"^[A-Z][A-Z0-9_]{0,49}$")


def _normalize_state_name(name: str) -> str:
    """Normalize a proposed state name to UPPER_SNAKE_CASE."""
    name = name.strip().upper().replace(" ", "_").replace("-", "_")
    # Collapse multiple underscores
    name = re.sub(r"_+", "_", name).strip("_")
    return name


# ──────────────────────────────────────────────
# Structured Response Types
# ──────────────────────────────────────────────

@dataclass
class DeltaEstimate:
    """LLM's estimate of Δ(x, y)."""
    delta: float
    reasoning: str


@dataclass
class ProposedState:
    """A state proposed by the LLM."""
    name: str
    description: str
    estimated_delta: float


@dataclass
class TransitionResult:
    """LLM's report of executing a transition."""
    outcome: Outcome
    result: str
    confidence: float


@dataclass
class ResistanceEstimate:
    """LLM's estimate of R₀(x, y)."""
    resistance: float
    reasoning: str


@dataclass
class LandscapeProposal:
    """LLM's proposed landscape for a task."""
    states: List[str]
    edges: List[Dict[str, Any]]  # [{source, target, delta, resistance, description}]


# ──────────────────────────────────────────────
# E0LLMAdapter — Core Class
# ──────────────────────────────────────────────

class E0LLMAdapter:
    """
    Structured LLM interface for the E₀ controller.

    The adapter translates between the controller's formal state
    (MemOS summary) and natural-language LLM interaction.

    Usage:
        adapter = E0LLMAdapter()                         # uses openai_call
        adapter = E0LLMAdapter(call_fn=my_mock_fn)       # for testing
        adapter = E0LLMAdapter(config=LLMConfig(model="gpt-4o"))
    """

    def __init__(
        self,
        config: Optional[LLMConfig] = None,
        call_fn: Optional[LLMCallFn] = None,
        provenance: Optional["ProvenanceLog"] = None,
    ):
        self.config = config or LLMConfig()
        base_call = call_fn or openai_call
        if provenance is not None:
            self._call = provenance.wrap_call_fn(base_call)
            self._provenance = provenance
        else:
            self._call = base_call
            self._provenance = None

    def _format_context(self, memos_summary: Dict[str, Any]) -> str:
        """Format MemOS summary as compact context string for prompts."""
        return json.dumps(memos_summary, indent=2, ensure_ascii=False)

    # ── 1. Extract Δ ──

    def extract_delta(
        self,
        source: str,
        target: str,
        description: str,
        memos_summary: Optional[Dict[str, Any]] = None,
    ) -> DeltaEstimate:
        """
        Ask LLM to estimate structural difference Δ(x, y).

        Args:
            source: Source state name.
            target: Target state name.
            description: Natural-language description of the transition.
            memos_summary: Output from E0MemoryOS.summarize_for_llm().

        Returns:
            DeltaEstimate with delta (float) and reasoning (str).
        """
        ctx = self._format_context(memos_summary) if memos_summary else "{}"
        prompt = EXTRACT_DELTA_PROMPT.format(
            context=ctx,
            source=source,
            target=target,
            description=description,
        )

        raw = self._call(SYSTEM_PROMPT, prompt, self.config)
        data = _parse_json_response(raw, required_keys=["delta"])

        try:
            delta = float(data["delta"])
        except (TypeError, ValueError) as exc:
            raise LLMResponseError(
                f"Invalid delta value: {data['delta']!r}", raw_response=raw,
            ) from exc
        delta = max(0.0, min(1.0, delta))  # clamp to [0, 1]

        return DeltaEstimate(
            delta=delta,
            reasoning=data.get("reasoning", ""),
        )

    # ── 2. Propose States ──

    def propose_states(
        self,
        current_state: str,
        description: str,
        memos_summary: Optional[Dict[str, Any]] = None,
    ) -> List[ProposedState]:
        """
        Ask LLM to propose reachable next states from a task description.

        Args:
            current_state: Current state name.
            description: What the user wants to accomplish.
            memos_summary: Output from E0MemoryOS.summarize_for_llm().

        Returns:
            List of ProposedState objects.
        """
        ctx = self._format_context(memos_summary) if memos_summary else "{}"
        prompt = PROPOSE_STATES_PROMPT.format(
            context=ctx,
            current_state=current_state,
            description=description,
        )

        raw = self._call(SYSTEM_PROMPT, prompt, self.config)
        data = _parse_json_response(raw, required_keys=["states"])

        states = []
        seen: set = set()
        for s in data.get("states", []):
            name = _normalize_state_name(s.get("name", ""))
            if not name or not _STATE_NAME_RE.match(name):
                continue  # skip invalid names
            if name in seen:
                continue  # skip duplicates
            seen.add(name)
            delta = float(s.get("estimated_delta", 0.5))
            delta = max(0.0, min(1.0, delta))
            states.append(ProposedState(
                name=name,
                description=s.get("description", ""),
                estimated_delta=delta,
            ))
        return states

    # ── 3. Execute Transition ──

    def execute_transition(
        self,
        source: str,
        target: str,
        task: str,
        memos_summary: Optional[Dict[str, Any]] = None,
        scenario_block: str = "",
    ) -> TransitionResult:
        """
        Ask LLM to perform the work of a transition.

        The LLM receives the E₀ context and reports whether the
        transition succeeded, failed, or partially completed.

        Args:
            source: Source state name.
            target: Target state name.
            task: Description of what needs to happen.
            memos_summary: Output from E0MemoryOS.summarize_for_llm().
            scenario_block: Pre-formatted scenario context string.

        Returns:
            TransitionResult with outcome, result text, and confidence.
        """
        ctx = self._format_context(memos_summary) if memos_summary else "{}"
        sc_block = f"\nScenario context:\n{scenario_block}\n" if scenario_block else ""
        prompt = EXECUTE_TRANSITION_PROMPT.format(
            context=ctx,
            scenario_block=sc_block,
            source=source,
            target=target,
            task=task,
        )

        raw = self._call(SYSTEM_PROMPT, prompt, self.config)
        data = _parse_json_response(raw, required_keys=["outcome"])

        outcome_str = data.get("outcome", "FAILURE").upper()
        outcome_map = {
            "SUCCESS": Outcome.SUCCESS,
            "FAILURE": Outcome.FAILURE,
            "PARTIAL": Outcome.PARTIAL,
        }
        outcome = outcome_map.get(outcome_str, Outcome.FAILURE)

        confidence = float(data.get("confidence", 0.5))
        confidence = max(0.0, min(1.0, confidence))

        return TransitionResult(
            outcome=outcome,
            result=data.get("result", ""),
            confidence=confidence,
        )

    # ── Convenience: execute_fn for E0Controller ──

    # ── 4. Estimate Resistance ──

    def estimate_resistance(
        self,
        source: str,
        target: str,
        description: str,
        memos_summary: Optional[Dict[str, Any]] = None,
    ) -> ResistanceEstimate:
        """
        Ask LLM to estimate base resistance R₀(x, y).

        The LLM provides a qualitative assessment which is returned as
        a float > 0. Values are floored at 0.01 (resistance is never zero).

        Args:
            source: Source state name.
            target: Target state name.
            description: What this transition involves.
            memos_summary: Output from E0MemoryOS.summarize_for_llm().

        Returns:
            ResistanceEstimate with resistance (float) and reasoning (str).
        """
        ctx = self._format_context(memos_summary) if memos_summary else "{}"
        prompt = ESTIMATE_RESISTANCE_PROMPT.format(
            context=ctx,
            source=source,
            target=target,
            description=description,
        )

        raw = self._call(SYSTEM_PROMPT, prompt, self.config)
        data = _parse_json_response(raw, required_keys=["resistance"])

        try:
            resistance = float(data["resistance"])
        except (TypeError, ValueError) as exc:
            raise LLMResponseError(
                f"Invalid resistance value: {data['resistance']!r}",
                raw_response=raw,
            ) from exc
        resistance = max(0.01, resistance)  # floor: R₀ > 0 always

        return ResistanceEstimate(
            resistance=resistance,
            reasoning=data.get("reasoning", ""),
        )

    # ── 5. Build Landscape ──

    def build_landscape(
        self,
        task: str,
        start: str,
        goal: str,
        goals: Optional[Set[str]] = None,
        memos_summary: Optional[Dict[str, Any]] = None,
        scenario_block: str = "",
    ) -> LandscapeProposal:
        """
        Ask LLM to design a complete state graph for a task.

        The LLM proposes states and directed edges with Δ and R₀ values.
        Returns a LandscapeProposal that can be materialized into a Landscape.

        Args:
            task: Natural-language description of the overall task.
            start: Name of the starting state.
            goal: Name of the primary goal state.
            goals: Optional set of additional goal states.  When provided,
                the prompt tells the LLM about all goal states.
            memos_summary: Output from E0MemoryOS.summarize_for_llm().
            scenario_block: Pre-formatted scenario context string.

        Returns:
            LandscapeProposal with states and edges.
        """
        all_goals = {goal}
        if goals:
            all_goals |= goals

        ctx = self._format_context(memos_summary) if memos_summary else "{}"
        sc_block = f"\nScenario context:\n{scenario_block}\n" if scenario_block else ""

        if len(all_goals) > 1:
            goal_line = "Goal states: " + ", ".join(sorted(all_goals)) + " (the task completes when ANY of these is reached)"
        else:
            goal_line = f"Goal state: {goal}"

        prompt = BUILD_LANDSCAPE_PROMPT.format(
            context=ctx,
            scenario_block=sc_block,
            task=task,
            start=start,
            goal=goal_line,
        )

        raw = self._call(SYSTEM_PROMPT, prompt, self.config)
        data = _parse_json_response(raw, required_keys=["states", "edges"])

        # Normalize states
        states = []
        seen: set = set()
        for s in data.get("states", []):
            name = _normalize_state_name(str(s))
            if name and _STATE_NAME_RE.match(name) and name not in seen:
                seen.add(name)
                states.append(name)

        # Ensure start and all goals are included
        for required in [start] + sorted(all_goals):
            norm = _normalize_state_name(required)
            if norm not in seen:
                states.append(norm)
                seen.add(norm)

        # Normalize edges
        edges = []
        for e in data.get("edges", []):
            src = _normalize_state_name(str(e.get("source", "")))
            tgt = _normalize_state_name(str(e.get("target", "")))
            if not src or not tgt or src not in seen or tgt not in seen:
                continue  # skip edges with unknown states

            delta = float(e.get("delta", 0.5))
            delta = max(0.0, min(1.0, delta))
            resistance = float(e.get("resistance", 1.0))
            resistance = max(0.01, resistance)

            edges.append({
                "source": src,
                "target": tgt,
                "delta": delta,
                "resistance": resistance,
                "description": e.get("description", ""),
            })

        proposal = LandscapeProposal(states=states, edges=edges)

        if self._provenance is not None:
            self._provenance.record_proposal(proposal)

        return proposal

    # ── 6. Rebuild Landscape (Structural Reflection) ──

    def rebuild_landscape(
        self,
        task: str,
        start: str,
        goal: str,
        old_proposal: LandscapeProposal,
        diagnostic: "StructuralDiagnostic",
        goals: Optional[Set[str]] = None,
        scenario_block: str = "",
    ) -> LandscapeProposal:
        """Ask LLM to redesign a landscape based on structural diagnostics.

        Unlike build_landscape(), this provides the LLM with the old
        topology and a diagnostic of what went wrong.  The LLM is
        instructed to restructure — not tweak parameters.

        Args:
            task: Natural-language description of the overall task.
            start: Name of the starting state.
            goal: Name of the primary goal state.
            old_proposal: The previous LandscapeProposal.
            diagnostic: StructuralDiagnostic from reflection.
            goals: Optional set of additional goal states.
            scenario_block: Pre-formatted scenario context string.

        Returns:
            New LandscapeProposal with restructured topology.
        """
        from .reflection import StructuralDiagnostic

        # Format old landscape
        old_states_str = ", ".join(old_proposal.states)
        old_edges_lines = []
        for e in old_proposal.edges:
            old_edges_lines.append(
                f"  {e['source']} → {e['target']} "
                f"(Δ={e.get('delta', '?')}, R₀={e.get('resistance', '?')}, "
                f"{e.get('description', '')})"
            )
        old_edges_str = "\n".join(old_edges_lines) if old_edges_lines else "(none)"

        # Format diagnostic
        diag_lines = []
        if diagnostic.dead_states:
            diag_lines.append(f"Dead states (never visited): {', '.join(diagnostic.dead_states)}")
        if diagnostic.loop_states:
            diag_lines.append(f"Loop states (bidirectional edges): {', '.join(diagnostic.loop_states)}")
        if diagnostic.chronic_issues:
            for dim, count in diagnostic.chronic_issues.items():
                diag_lines.append(f"Chronic {dim} issue: triggered in {count} recent runs")
        if diagnostic.plateau_evidence:
            diag_lines.append(f"Plateau: {diagnostic.plateau_evidence}")
        if diagnostic.parameter_bounds_hit:
            for bound_info in diagnostic.parameter_bounds_hit:
                diag_lines.append(f"Parameter bound: {bound_info}")
        if not diag_lines:
            diag_lines.append("General structural inadequacy detected")
        diag_block = "\n".join(f"  - {line}" for line in diag_lines)

        sc_block = f"\nScenario context:\n{scenario_block}\n" if scenario_block else ""

        all_goals = {goal}
        if goals:
            all_goals |= goals

        prompt = REBUILD_LANDSCAPE_PROMPT.format(
            old_states=old_states_str,
            old_edges=old_edges_str,
            diagnostic_block=diag_block,
            start=start,
            goal=goal,
            scenario_block=sc_block,
            task=task,
        )

        raw = self._call(SYSTEM_PROMPT, prompt, self.config)
        data = _parse_json_response(raw, required_keys=["states", "edges"])

        # Normalize states (same logic as build_landscape)
        states = []
        seen: set = set()
        for s in data.get("states", []):
            name = _normalize_state_name(str(s))
            if name and _STATE_NAME_RE.match(name) and name not in seen:
                seen.add(name)
                states.append(name)

        for required in [start] + sorted(all_goals):
            norm = _normalize_state_name(required)
            if norm not in seen:
                states.append(norm)
                seen.add(norm)

        # Normalize edges
        edges = []
        for e in data.get("edges", []):
            src = _normalize_state_name(str(e.get("source", "")))
            tgt = _normalize_state_name(str(e.get("target", "")))
            if not src or not tgt or src not in seen or tgt not in seen:
                continue

            delta = float(e.get("delta", 0.5))
            delta = max(0.0, min(1.0, delta))
            resistance = float(e.get("resistance", 1.0))
            resistance = max(0.01, resistance)

            edges.append({
                "source": src,
                "target": tgt,
                "delta": delta,
                "resistance": resistance,
                "description": e.get("description", ""),
            })

        proposal = LandscapeProposal(states=states, edges=edges)

        if self._provenance is not None:
            self._provenance.record_proposal(proposal)

        return proposal

    # ── 7. Propose Domain Graph (C45) ──

    def propose_domain_graph(
        self,
        description: str,
        memos_summary: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Ask LLM to design a bootstrapper-compatible domain graph.

        Returns a spec dict that can be passed directly to
        ``bootstrapper.bootstrap_landscape(spec)``.

        Args:
            description: Natural-language description of the domain.
            memos_summary: Output from E0MemoryOS.summarize_for_llm().

        Returns:
            Dict with 'nodes' (list of str) and 'edges' (list of dicts
            with from/to/delta/resistance/initial_U/initial_F/confidence).

        Raises:
            LLMResponseError: If the LLM output is unparseable.
        """
        ctx = self._format_context(memos_summary) if memos_summary else "{}"
        prompt = PROPOSE_DOMAIN_GRAPH_PROMPT.format(
            context=ctx,
            description=description,
        )

        raw = self._call(SYSTEM_PROMPT, prompt, self.config)
        data = _parse_json_response(raw, required_keys=["nodes", "edges"])

        # Normalize nodes
        nodes = []
        seen: set = set()
        for n in data.get("nodes", []):
            name = _normalize_state_name(str(n))
            if name and _STATE_NAME_RE.match(name) and name not in seen:
                seen.add(name)
                nodes.append(name)

        # Normalize edges
        edges = []
        for e in data.get("edges", []):
            src = _normalize_state_name(str(e.get("from", "")))
            tgt = _normalize_state_name(str(e.get("to", "")))
            if not src or not tgt or src not in seen or tgt not in seen:
                continue
            if src == tgt:
                continue  # skip self-loops

            delta = float(e.get("delta", 0.5))
            delta = max(0.0, min(1.0, delta))
            resistance = float(e.get("resistance", 1.0))
            resistance = max(0.01, resistance)

            initial_U = float(e.get("initial_U", 0.0))
            initial_U = max(0.0, initial_U)
            initial_F = float(e.get("initial_F", 0.0))
            initial_F = max(0.0, initial_F)

            confidence = float(e.get("confidence", 1.0))
            confidence = max(0.0, min(1.0, confidence))

            edges.append({
                "from": src,
                "to": tgt,
                "delta": delta,
                "resistance": resistance,
                "initial_U": initial_U,
                "initial_F": initial_F,
                "confidence": confidence,
            })

        return {"nodes": nodes, "edges": edges}

    # ── 8. Synthesize Answer ──

    def synthesize_answer(
        self,
        question: str,
        path_evidence: str,
        steps: int = 0,
        domain_crossings: int = 0,
        coverage_delta: float = 0.0,
    ) -> Dict[str, Any]:
        """Synthesize a prose answer from E₀ navigation evidence.

        Args:
            question: the original question
            path_evidence: formatted string of visited concepts + descriptions
            steps: navigation step count
            domain_crossings: how many domain boundaries were crossed
            coverage_delta: coverage change during navigation

        Returns dict with: answer, confidence, key_concepts, evidence_sufficient.
        """
        prompt = SYNTHESIZE_ANSWER_PROMPT.format(
            question=question,
            path_evidence=path_evidence,
            steps=steps,
            domain_crossings=domain_crossings,
            coverage_delta=f"{coverage_delta:+.1%}",
        )
        raw = self._call(SYSTEM_PROMPT, prompt, self.config)
        data = _parse_json_response(raw, required_keys=["answer"])
        return {
            "answer": str(data.get("answer", "")),
            "confidence": float(data.get("confidence", 0.5)),
            "key_concepts": list(data.get("key_concepts", [])),
            "evidence_sufficient": bool(data.get("evidence_sufficient", True)),
        }

    def propose_and_bootstrap(
        self,
        description: str,
        memos_summary: Optional[Dict[str, Any]] = None,
    ) -> "Landscape":
        """Propose a domain graph and bootstrap it into a Landscape.

        Convenience pipeline: propose_domain_graph() → bootstrap_landscape().

        Args:
            description: Natural-language description of the domain.
            memos_summary: Output from E0MemoryOS.summarize_for_llm().

        Returns:
            An initialized Landscape with conservative historization.

        Raises:
            LLMResponseError: If the LLM output is unparseable.
            BootstrapError: If the proposed spec fails validation.
        """
        from .bootstrapper import bootstrap_landscape

        spec = self.propose_domain_graph(description, memos_summary)
        return bootstrap_landscape(spec)

    # ── Convenience: execute_fn for E0Controller ──

    # Type for dynamic summary provider: () → summary dict
    SummaryProvider = Callable[[], Optional[Dict[str, Any]]]
    # Type for live summary: (source) → summary dict
    LiveSummaryProvider = Callable[[str], Optional[Dict[str, Any]]]

    def as_execute_fn(
        self,
        task_map: Dict[str, str],
        memos_summary: Optional[Dict[str, Any]] = None,
        summary_provider: Optional[SummaryProvider] = None,
        live_summary: Optional[LiveSummaryProvider] = None,
        scenario_block: str = "",
        result_log: Optional[List["TransitionResult"]] = None,
    ) -> Callable[[str, str], Outcome]:
        """
        Return a callback compatible with E0Controller's execute_fn.

        Args:
            task_map: Dict mapping "source→target" to task descriptions.
            memos_summary: Static MemOS summary (used if summary_provider is None).
            summary_provider: Callable that returns a fresh summary per call.
                Preferred over static memos_summary for multi-step runs.
            live_summary: Callable (source_state) → summary dict.
                Uses the actual source state from each call to build context.
                Takes precedence over summary_provider and memos_summary.
            scenario_block: Pre-formatted scenario context string from
                ScenarioPacket.as_prompt_block(). Passed to every transition.
            result_log: If provided, each TransitionResult is appended here
                so callers can inspect the LLM's semantic output per step.

        Returns:
            Callable (source, target) → Outcome
        """
        def execute(source: str, target: str) -> Outcome:
            key = f"{source}→{target}"
            task = task_map.get(key, f"Transition from {source} to {target}")
            # Live summary (uses actual source) takes highest precedence
            if live_summary:
                summary = live_summary(source)
            elif summary_provider:
                summary = summary_provider()
            else:
                summary = memos_summary
            result = self.execute_transition(
                source, target, task, summary,
                scenario_block=scenario_block,
            )
            if result_log is not None:
                result_log.append(result)
            return result.outcome
        return execute


# ──────────────────────────────────────────────
# Landscape Materialization (Phase 3b)
# ──────────────────────────────────────────────

def materialize_landscape(proposal: LandscapeProposal) -> "Landscape":
    """
    Convert a LandscapeProposal into a concrete Landscape object.

    This bridges the LLM's semantic output back into the deterministic
    controller stack. Edges are created with the LLM-estimated Δ and R₀.
    """
    from .landscape import Landscape

    L = Landscape()
    for s in proposal.states:
        L.add_state(s)
    for e in proposal.edges:
        L.add_edge(e["source"], e["target"],
                   delta=e["delta"], resistance=e["resistance"])
    return L


def task_map_from_proposal(proposal: LandscapeProposal) -> Dict[str, str]:
    """
    Extract a task_map (for as_execute_fn) from a LandscapeProposal.

    Maps each "source→target" to the edge description provided by the LLM.
    """
    return {
        f"{e['source']}→{e['target']}": e.get("description", "")
        for e in proposal.edges
    }
