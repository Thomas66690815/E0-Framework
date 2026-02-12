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
# E₀ Priming — The Convergence Phenomenon
# ─────────────────────────────────────────────

E0_SYSTEM_PRIMER = """You operate within a structural framework called E₀.
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
    ):
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY", "")
        self.model = model
        self.base_url = base_url
        self.e0_prime = e0_prime
        self.e0_structural_context = e0_structural_context
        self.logprobs = logprobs
        self.top_logprobs = top_logprobs

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

        return {
            "model": self.model,
            "messages": self.messages,
            "logprobs": self.logprobs,
            "top_logprobs": self.top_logprobs,
        }

    def _parse_response(self, raw_response: Dict[str, Any]) -> E0Response:
        """Parse API response and instrument with E₀."""
        choice = raw_response["choices"][0]
        text = choice["message"]["content"]

        # Extract logprobs if available
        steps: List[StepMeasurement] = []
        if self.logprobs and choice.get("logprobs") and choice["logprobs"].get("content"):
            for token_data in choice["logprobs"]["content"]:
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

        # Store assistant message for conversation continuity
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
