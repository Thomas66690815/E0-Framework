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


# ──────────────────────────────────────────────
# Response Parsing
# ──────────────────────────────────────────────

def _parse_json_response(
    text: str,
    required_keys: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Extract JSON from LLM response, tolerant of markdown fences.

    Args:
        text: Raw LLM response string.
        required_keys: If given, validates that every key is present in the
            parsed dict.  Raises LLMResponseError on missing keys.

    Raises LLMResponseError if the response cannot be parsed or is
    structurally invalid.
    """
    raw = text
    text = text.strip()
    # Strip markdown code fences
    m = re.search(r"```(?:json)?\s*\n?(.*?)\n?\s*```", text, re.DOTALL)
    if m:
        text = m.group(1).strip()
    try:
        data = json.loads(text)
    except (json.JSONDecodeError, ValueError) as exc:
        raise LLMResponseError(
            f"LLM returned invalid JSON: {exc}",
            raw_response=raw,
        ) from exc

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
    ):
        self.config = config or LLMConfig()
        self._call = call_fn or openai_call

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

        return LandscapeProposal(states=states, edges=edges)

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
