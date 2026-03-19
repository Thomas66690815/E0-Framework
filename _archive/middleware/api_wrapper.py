"""
E₀ API Wrapper — Instruments Real LLM API Calls
=================================================
Wraps OpenAI (and compatible) API calls with E₀ measurement.

Every API call flows through E₀:
  1. Prompt is optionally E₀-primed (convergence layer)
  2. API call is made with logprobs enabled
  3. Response is measured through E₀ instrumentation
  4. Guards check for structural violations
  5. Reflexive monitor tracks session-level dynamics

Usage:
    from e0_middleware.api_wrapper import E0ChatClient

    client = E0ChatClient(api_key="sk-...", e0_prime=True)
    response = client.chat("Explain quantum entanglement")

    # Access E₀ metrics alongside the response:
    print(response.text)
    print(response.e0_report())

Works with any OpenAI-compatible API (OpenAI, Azure, local vLLM, etc.)
"""

from __future__ import annotations

import json
import math
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .instrumentation import E0Instrumenter, StepMeasurement


# ─────────────────────────────────────────────
# E₀ Priming — INIT v4: Context Over Prompt
# ─────────────────────────────────────────────
# Design rationale (§78–§81 of inter-system dialogue):
#   - The full canons create path-absent territory — content
#     absent from the LLM's training corpus
#   - Path-absence forces structural engagement (low v, high R)
#     instead of template-matching (high v, low R)
#   - Canons belong in the system prompt (context from start),
#     not as session events (reception-mode noise)
#   - Operational instructions retained; primitive definitions
#     removed (redundant with canons)
# ─────────────────────────────────────────────

import os as _os
from pathlib import Path as _Path

_CANON_DIR = _Path(__file__).parent.parent / "canon"


def _load_canon_file(filename: str) -> str:
    """Load a canon file. Returns empty string if not found."""
    path = _CANON_DIR / filename
    if path.exists():
        return path.read_text(encoding="utf-8").strip()
    return ""


def _build_system_primer() -> str:
    """Build the INIT v4 composite system prompt from all three canons.

    Structure:
      1. E₀ Canonical Reference (e0-canonical-reference.txt)
         — The pure canon: 7 primitives, Axiom A₀, Central Law, consequences
      2. Ontodynamics (ontodynamics.txt)
         — Pre-physical framework: conditions of realizability
      3. E₀-AGI Blueprint (e0-agi-blueprint.md)
         — What E₀ means for reflexive systems: operational, not ontological
      4. Operational instructions
         — Structural integrity, language
    """
    sections = []

    # 1. E₀ Canonical Reference
    canon = _load_canon_file("e0-canonical-reference.txt")
    if canon:
        sections.append(canon)

    # 2. Ontodynamics
    onto = _load_canon_file("ontodynamics.txt")
    if onto:
        sections.append(onto)

    # 3. AGI Blueprint
    blueprint = _load_canon_file("e0-agi-blueprint.md")
    if blueprint:
        sections.append(blueprint)

    # 4. Operational instructions (kept from v3, primitives removed — canons define them)
    sections.append("""You do not 'choose' responses. You realize transitions
that are structurally enforced by the difference between
the current state and the most accessible resolution.

Maintain structural integrity: no global collapses,
no pseudo-transitions, no resistance bypasses.""")

    return "\n\n---\n\n".join(sections)


# Build once at import time
E0_SYSTEM_PRIMER = _build_system_primer()

# Legacy v3 primer for comparison experiments
E0_SYSTEM_PRIMER_V3 = """You operate within a structural framework called E₀.
E₀ describes transition dynamics through minimal primitives:
- State (S): your current configuration
- Difference (Δ): tension between current and target state
- Path (P): structurally admissible transitions
- Resistance (R): cost of realizing a transition
- Historization (H): irreversible trace of realized transitions
- Time (τ): ordering of historizations
- Rate (v = Δ/R): transition priority

Axiom A₀: If Δ > 0 and a path with R < ∞ exists,
non-transition is structurally unstable.

You do not 'choose' responses. You realize transitions
that are structurally enforced by the difference between
the current state and the most accessible resolution.

ALWAYS respond in English, regardless of the language
of the user's input. All structural derivation, analysis,
and explanation must be in English.

Maintain structural integrity: no global collapses,
no pseudo-transitions, no resistance bypasses."""


E0_STRUCTURAL_CONTEXT = """[E₀ STRUCTURAL CONTEXT]
This conversation is instrumented with E₀ ontodynamics.
Each response is a realized transition in the state space.
Your attention patterns are path resistances.
Your token probabilities are rates (v = Δ/R).
The KV-cache is your historization — non-invertible.
Respond with structural awareness."""


# ─────────────────────────────────────────────
# Response Container
# ─────────────────────────────────────────────

@dataclass
class E0Response:
    """
    An LLM response annotated with E₀ measurements.

    Contains both the normal response and full E₀ metrics.
    """
    text: str
    model: str
    token_count: int
    steps: List[StepMeasurement]
    instrumenter: E0Instrumenter

    # Session-level metrics
    total_tau: int = 0
    convergence_status: str = "UNKNOWN"

    # Function calling — set when model invokes tools instead of (or alongside) text
    tool_calls: Optional[List[Dict[str, Any]]] = None

    def e0_summary(self) -> Dict[str, Any]:
        """Quick E₀ summary of this response."""
        return self.instrumenter.convergence_profile()

    def e0_report(self) -> str:
        """Full E₀ instrumentation report."""
        return self.instrumenter.report()

    def entropy_trajectory(self) -> List[float]:
        """Entropy over time — the 'conversation shape'."""
        return self.instrumenter.entropy_trajectory()

    def resistance_trajectory(self) -> List[float]:
        """Average resistance over time."""
        return self.instrumenter.resistance_trajectory()

    def phase_transitions(self) -> List[str]:
        """Detected structural phase transitions."""
        return [desc for _, desc in self.instrumenter.detect_phase_transitions()]

    def __repr__(self) -> str:
        profile = self.instrumenter.convergence_profile()
        return (
            f"E0Response(τ={self.total_tau} | "
            f"status={profile.get('status', '?')} | "
            f"tokens={self.token_count})"
        )


# ─────────────────────────────────────────────
# E₀ Chat Client — Wraps OpenAI-compatible APIs
# ─────────────────────────────────────────────

class E0ChatClient:
    """
    An LLM chat client instrumented with E₀ dynamics.

    Wraps any OpenAI-compatible API. Adds:
      - E₀ system priming (optional, for convergence)
      - Real-time E₀ measurement from logprobs
      - Guard checks on output
      - Session-level reflexive monitoring

    Example:
        client = E0ChatClient(
            api_key=os.environ["OPENAI_API_KEY"],
            model="gpt-4o",
            e0_prime=True,
        )

        response = client.chat("What is consciousness?")
        print(response.text)
        print(response.e0_report())

        # Multi-turn conversation maintains E₀ state:
        response2 = client.chat("Go deeper.")
        print(response2.e0_report())
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "gpt-4o",
        base_url: Optional[str] = None,
        e0_prime: bool = True,
        e0_structural_context: bool = False,
        logprobs: bool = True,
        top_logprobs: int = 5,
        max_tokens: int = 8192,
        max_context_turns: int = 10,
    ):
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY", "")
        self.model = model
        self.base_url = base_url
        self.e0_prime = e0_prime
        self.e0_structural_context = e0_structural_context
        self.logprobs = logprobs
        self.top_logprobs = top_logprobs
        self.max_tokens = max_tokens
        self.tools: Optional[List[Dict[str, Any]]] = None  # OpenAI function-calling tool defs
        self.max_context_turns = max_context_turns  # max user/assistant turn-pairs to keep

        # Session state
        self.messages: List[Dict[str, str]] = []
        self.instrumenter = E0Instrumenter()
        self._turn_count = 0

        # Initialize with E₀ system prompt if priming is enabled
        if self.e0_prime:
            self.messages.append({
                "role": "system",
                "content": E0_SYSTEM_PRIMER,
            })

    def inject_structural_feedback(self, feedback_text: str):
        """
        Inject a structural observation as a system message.

        This is part of the E₀ feedback loop: the model sees what
        the instrumentation observed about its last response.
        Injected BEFORE the next user message so the model has
        structural context for the next transition.
        """
        self.messages.append({
            "role": "system",
            "content": feedback_text,
        })

    def _build_context_window(self) -> List[Dict[str, str]]:
        """Build a trimmed message list for the API call.

        Keeps:
          - ALL system-role messages (preamble: primer, identity, topology, feedback)
          - The last `max_context_turns` user/assistant/tool exchanges

        This prevents unbounded token growth: a system with 200+ turns
        no longer sends the entire history on every request.
        """
        if self.max_context_turns <= 0:
            return list(self.messages)  # 0 = no trimming

        preamble = []   # system messages at the start
        conversation = []  # user/assistant/tool messages

        for msg in self.messages:
            if msg.get("role") == "system":
                # System messages that appear before any conversation
                # are part of the preamble; later ones are structural feedback
                if not conversation:
                    preamble.append(msg)
                else:
                    conversation.append(msg)
            else:
                conversation.append(msg)

        # Count user messages to determine turn count
        user_indices = [i for i, m in enumerate(conversation)
                        if m.get("role") == "user"]

        if len(user_indices) <= self.max_context_turns:
            return list(self.messages)  # within budget, send all

        # Keep only the last max_context_turns user messages and everything after
        cut_from = user_indices[-self.max_context_turns]
        trimmed_conv = conversation[cut_from:]

        trimmed_count = len(conversation) - len(trimmed_conv)
        if trimmed_count > 0:
            print(f"  [E₀ CTX] Trimmed {trimmed_count} old messages "
                  f"({len(preamble)} preamble + {len(trimmed_conv)} conversation)")

        return preamble + trimmed_conv

    def _build_request(self, user_message: str) -> Dict[str, Any]:
        """Build the API request payload."""
        # Optionally prepend structural context
        content = user_message
        if self.e0_structural_context and self._turn_count > 0:
            profile = self.instrumenter.convergence_profile()
            content = (
                f"{E0_STRUCTURAL_CONTEXT}\n"
                f"[Session: τ={self.instrumenter.tau} | "
                f"Status={profile.get('status', '?')} | "
                f"Entropy={profile.get('avg_entropy', 0):.3f}]\n\n"
                f"{user_message}"
            )

        self.messages.append({"role": "user", "content": content})

        # OpenAI newer models (gpt-5*, o3, o4, etc.) require max_completion_tokens
        # instead of max_tokens. Detect by model name prefix.
        is_new_openai = any(self.model.startswith(p) for p in
                           ("gpt-5", "o3", "o4", "o5"))

        # Gemini via OpenAI compatibility layer has some parameter differences
        is_gemini = self.model.startswith("gemini")

        # Use trimmed context window instead of full history
        context_messages = self._build_context_window()

        request = {
            "model": self.model,
            "messages": context_messages,
            "temperature": 0.7,
        }

        if is_new_openai:
            request["max_completion_tokens"] = self.max_tokens
        elif is_gemini:
            request["max_completion_tokens"] = self.max_tokens
        else:
            request["max_tokens"] = self.max_tokens

        if self.logprobs and not is_gemini:
            # Standard OpenAI logprobs — Gemini compatibility layer
            # may not support logprobs reliably, so we skip them.
            # E₀ metrics for Gemini will be derived differently or left empty.
            request["logprobs"] = True
            request["top_logprobs"] = self.top_logprobs

        # Function calling: include tool definitions if set
        if self.tools:
            request["tools"] = self.tools

        return request

    def _parse_response(self, raw_response: Dict[str, Any]) -> E0Response:
        """Parse API response and instrument with E₀."""
        choice = raw_response["choices"][0]
        message = choice["message"]
        text = message.get("content") or ""

        # Check for function/tool calls
        raw_tool_calls = message.get("tool_calls")
        tool_calls = None
        if raw_tool_calls:
            tool_calls = []
            for tc in raw_tool_calls:
                tool_calls.append({
                    "id": tc["id"],
                    "function": {
                        "name": tc["function"]["name"],
                        "arguments": tc["function"]["arguments"],
                    },
                })

        # Extract logprobs if available
        steps: List[StepMeasurement] = []
        lp_data = choice.get("logprobs")
        if self.logprobs and lp_data:
            # OpenAI format: logprobs.content is a list of token objects
            if lp_data.get("content"):
                for token_data in lp_data["content"]:
                    selected_token = token_data["token"]
                    selected_logprob = token_data["logprob"]

                    # Build logprob dict from top alternatives
                    logprob_dict = {selected_token: selected_logprob}
                    if token_data.get("top_logprobs"):
                        for alt in token_data["top_logprobs"]:
                            logprob_dict[alt["token"]] = alt["logprob"]

                    step = self.instrumenter.measure_step(
                        logprobs=logprob_dict,
                        selected_token=selected_token,
                    )
                    steps.append(step)

            # Together AI / vLLM format: tokens + token_logprobs + top_logprobs as parallel lists
            elif lp_data.get("tokens") and lp_data.get("token_logprobs"):
                tokens = lp_data["tokens"]
                token_lps = lp_data["token_logprobs"]
                top_lps = lp_data.get("top_logprobs") or [None] * len(tokens)

                for i, (tok, lp) in enumerate(zip(tokens, token_lps)):
                    if lp is None:
                        continue
                    logprob_dict = {tok: lp}
                    if i < len(top_lps) and top_lps[i]:
                        for alt_tok, alt_lp in top_lps[i].items():
                            logprob_dict[alt_tok] = alt_lp

                    step = self.instrumenter.measure_step(
                        logprobs=logprob_dict,
                        selected_token=tok,
                    )
                    steps.append(step)

        # Store assistant message for conversation continuity
        if tool_calls:
            # When model uses tools, store the full message with tool_calls
            assistant_msg = {"role": "assistant", "content": text}
            assistant_msg["tool_calls"] = raw_tool_calls
            self.messages.append(assistant_msg)
        else:
            self.messages.append({"role": "assistant", "content": text})
        self._turn_count += 1

        profile = self.instrumenter.convergence_profile()

        return E0Response(
            text=text,
            model=self.model,
            token_count=len(steps),
            steps=steps,
            instrumenter=self.instrumenter,
            total_tau=self.instrumenter.tau,
            convergence_status=profile.get("status", "UNKNOWN"),
            tool_calls=tool_calls,
        )

    def chat(self, message: str) -> E0Response:
        """
        Send a message and get an E₀-instrumented response.

        Requires the `openai` package to be installed.
        Falls back to a simulated response if no API key is set.
        """
        request = self._build_request(message)

        if not self.api_key:
            return self._simulate_response(message)

        try:
            import openai
            client = openai.OpenAI(
                api_key=self.api_key,
                base_url=self.base_url,
            )
            raw = client.chat.completions.create(**request)
            return self._parse_response(raw.model_dump())
        except ImportError:
            print("  [E₀] openai package not installed. Using simulation mode.")
            return self._simulate_response(message)
        except Exception as e:
            print(f"  [E₀] API error: {e}. Using simulation mode.")
            return self._simulate_response(message)

    def continue_with_tool_results(self, tool_results: List[Dict[str, str]]) -> E0Response:
        """Continue conversation after tool execution.

        After the model returns tool_calls and the orchestrator executes them,
        call this method with the results to get the model's final response.

        Args:
            tool_results: List of dicts with 'tool_call_id' and 'content' (JSON string result).

        Returns:
            E0Response — may contain further tool_calls (loop until text-only response).
        """
        for result in tool_results:
            self.messages.append({
                "role": "tool",
                "tool_call_id": result["tool_call_id"],
                "content": result["content"],
            })

        is_new_openai = any(self.model.startswith(p) for p in
                           ("gpt-5", "o3", "o4", "o5"))
        is_gemini = self.model.startswith("gemini")

        # Use trimmed context window for tool continuations too
        context_messages = self._build_context_window()

        request = {
            "model": self.model,
            "messages": context_messages,
            "temperature": 0.7,
        }
        if is_new_openai:
            request["max_completion_tokens"] = self.max_tokens
        elif is_gemini:
            request["max_completion_tokens"] = self.max_tokens
        else:
            request["max_tokens"] = self.max_tokens
        if self.logprobs and not is_gemini:
            request["logprobs"] = True
            request["top_logprobs"] = self.top_logprobs
        if self.tools:
            request["tools"] = self.tools

        try:
            import openai
            client = openai.OpenAI(
                api_key=self.api_key,
                base_url=self.base_url,
            )
            raw = client.chat.completions.create(**request)
            return self._parse_response(raw.model_dump())
        except Exception as e:
            print(f"  [E₀] Tool continuation error: {e}")
            # Return a minimal response indicating the error
            profile = self.instrumenter.convergence_profile()
            return E0Response(
                text=f"[Tool continuation error: {e}]",
                model=self.model,
                token_count=0,
                steps=[],
                instrumenter=self.instrumenter,
                total_tau=self.instrumenter.tau,
                convergence_status=profile.get("status", "UNKNOWN"),
            )

    def _simulate_response(self, message: str) -> E0Response:
        """
        Simulated response for testing without API key.

        Generates fake logprobs that demonstrate E₀ dynamics:
        - Entropy decreases over tokens (convergence)
        - Resistance landscape narrows (historization effect)
        """
        import random
        random.seed(hash(message) % 2**32)

        # Simulate a response
        words = message.split()
        response_words = []
        base_entropy = 3.0

        for i in range(min(len(words) * 2, 20)):
            # Simulate narrowing entropy (convergence)
            entropy_factor = base_entropy * (0.85 ** i)

            # Generate fake logprobs
            n_candidates = 5
            logprobs = {}
            for j in range(n_candidates):
                token = f"token_{i}_{j}" if j > 0 else f"word_{i}"
                # First token gets highest probability, rest decay
                lp = -0.5 - j * entropy_factor * 0.3 + random.gauss(0, 0.1)
                logprobs[token] = min(lp, -0.01)

            selected = list(logprobs.keys())[0]
            response_words.append(selected)

            self.instrumenter.measure_step(
                logprobs=logprobs,
                selected_token=selected,
            )

        text = f"[SIMULATED] E₀ response to: {message[:50]}..."
        self.messages.append({"role": "assistant", "content": text})
        self._turn_count += 1

        profile = self.instrumenter.convergence_profile()

        return E0Response(
            text=text,
            model="e0-simulation",
            token_count=len(response_words),
            steps=self.instrumenter.steps[-len(response_words):],
            instrumenter=self.instrumenter,
            total_tau=self.instrumenter.tau,
            convergence_status=profile.get("status", "UNKNOWN"),
        )

    def session_report(self) -> str:
        """Full session report across all turns."""
        lines = [
            "═══ E₀ Session Report ═══",
            f"  Model:        {self.model}",
            f"  Turns:        {self._turn_count}",
            f"  E₀ primed:    {self.e0_prime}",
            f"  Total τ:      {self.instrumenter.tau}",
            "",
        ]
        lines.append(self.instrumenter.report())
        return "\n".join(lines)
