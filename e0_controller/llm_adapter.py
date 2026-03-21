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
    model: str = "gpt-4o-mini"
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
        max_tokens=config.max_tokens,
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

Transition: {source} → {target}
Task: {task}

Perform the work implied by this transition and report the outcome.

Respond with exactly this JSON (no other text):
{{
  "outcome": "<SUCCESS|FAILURE|PARTIAL>",
  "result": "<what was accomplished or why it failed>",
  "confidence": <float between 0.0 and 1.0>
}}"""


# ──────────────────────────────────────────────
# Response Parsing
# ──────────────────────────────────────────────

def _parse_json_response(text: str) -> Dict[str, Any]:
    """Extract JSON from LLM response, tolerant of markdown fences.

    Raises LLMResponseError if the response cannot be parsed.
    """
    raw = text
    text = text.strip()
    # Strip markdown code fences
    m = re.search(r"```(?:json)?\s*\n?(.*?)\n?\s*```", text, re.DOTALL)
    if m:
        text = m.group(1).strip()
    try:
        return json.loads(text)
    except (json.JSONDecodeError, ValueError) as exc:
        raise LLMResponseError(
            f"LLM returned invalid JSON: {exc}",
            raw_response=raw,
        ) from exc


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
        data = _parse_json_response(raw)

        delta = float(data["delta"])
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
        data = _parse_json_response(raw)

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

        Returns:
            TransitionResult with outcome, result text, and confidence.
        """
        ctx = self._format_context(memos_summary) if memos_summary else "{}"
        prompt = EXECUTE_TRANSITION_PROMPT.format(
            context=ctx,
            source=source,
            target=target,
            task=task,
        )

        raw = self._call(SYSTEM_PROMPT, prompt, self.config)
        data = _parse_json_response(raw)

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

    # Type for dynamic summary provider: () → summary dict
    SummaryProvider = Callable[[], Optional[Dict[str, Any]]]

    def as_execute_fn(
        self,
        task_map: Dict[str, str],
        memos_summary: Optional[Dict[str, Any]] = None,
        summary_provider: Optional[SummaryProvider] = None,
    ) -> Callable[[str, str], Outcome]:
        """
        Return a callback compatible with E0Controller's execute_fn.

        Args:
            task_map: Dict mapping "source→target" to task descriptions.
            memos_summary: Static MemOS summary (used if summary_provider is None).
            summary_provider: Callable that returns a fresh summary per call.
                Preferred over static memos_summary for multi-step runs.

        Returns:
            Callable (source, target) → Outcome
        """
        def execute(source: str, target: str) -> Outcome:
            key = f"{source}→{target}"
            task = task_map.get(key, f"Transition from {source} to {target}")
            # Dynamic summary takes precedence
            summary = summary_provider() if summary_provider else memos_summary
            result = self.execute_transition(source, target, task, summary)
            return result.outcome
        return execute
