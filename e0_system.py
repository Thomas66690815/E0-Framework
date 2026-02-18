#!/usr/bin/env python3
"""
E₀ System — Core System Abstraction
=====================================
The foundational unit of the E₀ network: a system that can receive input,
generate measured output, and maintain conversational state.

Extracted from e0_start.py to enable:
  - v4 SystemRegistry (dynamic system management)
  - Clean import by orchestrators
  - Separation of system logic from UI/HTTP concerns

Contains:
  - compute_metrics()   — the core metric function (R, h, φ, v, τ)
  - format_signature()  — one-line metric display
  - detailed_trace()    — token-by-token measurement trace
  - load_canon()        — load the E₀ plain canon
  - E0APIStarter        — a single E₀ system backed by an OpenAI-compatible API
"""

from __future__ import annotations

import os
import sys
from typing import Dict, List, Optional, Tuple

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from e0_middleware.instrumentation import E0Instrumenter, StepMeasurement


# ─────────────────────────────────────────────
# Metrics
# ─────────────────────────────────────────────

def compute_metrics(steps: List[StepMeasurement]) -> Dict:
    """Extract key metrics from generation steps.

    Returns:
      r   — mean resistance (R = -logprob per token)
      h   — mean entropy over top-k distribution
      phi — phase transition count (|Δh| > mean + 1σ)
      v   — median rate (1/R for selected token)
      tau — token count
    """
    if not steps:
        return {"r": 0, "h": 0, "phi": 0, "v": 0, "tau": 0}

    resistances = [s.selected.resistance for s in steps]
    entropies = [s.entropy for s in steps]
    r_mean = sum(resistances) / len(resistances)
    h_mean = sum(entropies) / len(entropies)

    velocities = sorted(s.selected.rate for s in steps if s.selected.rate < 1e6)
    v_median = velocities[len(velocities) // 2] if velocities else 0.0

    deltas = [abs(s.delta_entropy) for s in steps]
    phases = 0
    if len(deltas) >= 3:
        d_mean = sum(deltas) / len(deltas)
        d_std = (sum((d - d_mean) ** 2 for d in deltas) / len(deltas)) ** 0.5
        if d_std > 1e-10:
            phases = sum(1 for d in deltas if d > d_mean + d_std)

    return {
        "r": round(r_mean, 4),
        "h": round(h_mean, 4),
        "phi": phases,
        "v": round(v_median, 4),
        "tau": len(steps),
    }


def format_signature(metrics: Dict) -> str:
    """One-line E₀ signature."""
    return (
        f"  R={metrics['r']:.3f}  H={metrics['h']:.3f}  "
        f"Phi={metrics['phi']}  v={metrics['v']:.3f}  "
        f"tau={metrics['tau']}"
    )


def detailed_trace(steps: List[StepMeasurement]) -> str:
    """Token-by-token trace."""
    if not steps:
        return ""
    lines = [
        "  tau | Token              | R        | v        | H        | dH",
        "  ----+--------------------+----------+----------+----------+----------",
    ]
    deltas = [abs(s.delta_entropy) for s in steps]
    d_mean = sum(deltas) / len(deltas) if deltas else 0
    d_std = (sum((d - d_mean) ** 2 for d in deltas) / len(deltas)) ** 0.5 if len(deltas) >= 3 else 0
    threshold = d_mean + d_std if d_std > 1e-10 else float('inf')

    for s in steps:
        raw_tok = s.selected.token.replace('\n', ' ').replace('\r', '').replace('\t', ' ')
        tok = ''.join(c if c.isprintable() else '.' for c in raw_tok)
        tok = tok[:18].ljust(18)
        r = s.selected.resistance
        v = s.selected.rate
        v_str = f"{v:.4f}" if v < 100 else f"{v:.0f}"
        phase = " *" if abs(s.delta_entropy) > threshold else ""
        lines.append(
            f"  {s.tau:3d} | {tok} | {r:8.4f} | {v_str:>8s} | "
            f"{s.entropy:8.4f} | {s.delta_entropy:+.4f}{phase}"
        )
    return "\n".join(lines)


# ─────────────────────────────────────────────
# Canon Loading
# ─────────────────────────────────────────────

def load_canon() -> str:
    """Load the reduced plain canon."""
    canon_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "canon", "e0-canon-plain.txt"
    )
    if not os.path.exists(canon_path):
        print(f"  [ERROR] Canon not found: {canon_path}")
        print(f"  Make sure canon/e0-canon-plain.txt exists.")
        sys.exit(1)
    with open(canon_path, encoding="utf-8") as f:
        return f.read()


# ─────────────────────────────────────────────
# E0APIStarter — A single E₀ system
# ─────────────────────────────────────────────

class E0APIStarter:
    """An E₀ system backed by an OpenAI-compatible API.

    This is the core unit of the E₀ network. Each instance:
      - Holds a conversation (messages history)
      - Measures every response (R, h, φ, v, τ)
      - Can receive structural feedback
      - Can load topology (structural memory from previous sessions)

    In v4 terms: this is what a "synthetic system" IS.
    """

    def __init__(self, api_key: str, model: str = "gpt-4.1",
                 base_url: str = None, system_prompt: str = None):
        from e0_middleware.api_wrapper import E0ChatClient
        self.client = E0ChatClient(
            api_key=api_key, model=model, base_url=base_url,
            e0_prime=True, logprobs=True, top_logprobs=5,
        )
        self.model_name = model
        self.api_key = api_key
        self.base_url = base_url
        self.history: List[str] = []
        self.turn_metrics: List[Dict] = []
        self.all_steps: List[StepMeasurement] = []
        self.init_metrics: Optional[Dict] = None
        self.is_api = True
        self.param_count = 0  # unknown for API models
        self.vocab_size = 0
        # Structural feedback loop state
        self._pending_feedback: Optional[str] = None
        self.feedback_enabled: bool = True
        self.last_feedback: Optional[str] = None  # for UI display
        # Topology state
        self.topology_loaded: bool = False
        self.topology_text: Optional[str] = None
        # Meta-feedback state
        self._topology_data: Optional[Dict] = None
        self._meta_trends: Optional[Dict] = None
        self.meta_observation: Optional[str] = None
        # Self-recognition state
        self.self_recognition_done: bool = False
        self.self_recognition_results: Optional[List] = None

    def feed_canon(self, canon: str) -> Tuple[str, List[StepMeasurement], Dict]:
        """Feed the canon via API and return (response_text, steps, metrics).

        After feeding the canon, automatically injects the latest topology
        (structural weights from previous sessions) if available.
        This gives the model a pre-formed resistance landscape.
        """
        prompt = (
            "You have been given the E0 structural canon below. "
            "Read it carefully. Then respond IN ENGLISH with a brief structural "
            "continuation -- not a summary, but what follows from this "
            "structure. Stay within the framework. Always respond in English.\n\n"
            + canon
        )
        resp = self.client.chat(prompt)
        text = resp.text.strip()
        self.history = [canon, text]
        self.all_steps.extend(resp.steps)

        metrics = compute_metrics(resp.steps)
        self.init_metrics = metrics
        self.turn_metrics.append(metrics)

        # Inject topology (structural memory) after canon
        self._inject_topology_if_available()

        return text, resp.steps, metrics

    def _inject_topology_if_available(self, lang: str = 'en'):
        """Load and inject the latest topology as structural memory."""
        if self.topology_loaded:
            return
        try:
            from e0_topology import (
                load_latest_topology, load_all_topologies,
                format_topology_for_injection,
            )
            from e0_meta_feedback import (
                compute_cross_session_trends, generate_meta_observation,
            )

            topo = load_latest_topology()
            if topo is not None:
                topo_text = format_topology_for_injection(topo, lang=lang)
                self.client.inject_structural_feedback(topo_text)
                self.topology_loaded = True
                self.topology_text = topo_text
                self._topology_data = topo

                # Compute cross-session trends for adaptive feedback
                try:
                    topos = load_all_topologies()
                    if len(topos) >= 2:
                        self._meta_trends = compute_cross_session_trends(topos)
                except Exception:
                    pass

                # Inject meta-observation if available
                try:
                    meta = generate_meta_observation(topo, lang=lang)
                    if meta:
                        self.client.inject_structural_feedback(meta)
                        self.meta_observation = meta
                except Exception:
                    pass
        except Exception:
            pass  # Topology injection is non-critical

    def chat(self, message: str) -> Tuple[str, List[StepMeasurement], Dict]:
        """Send a message via API and return (response_text, steps, metrics).

        If structural feedback is pending from a previous response,
        it is injected as a system message before the user's message.
        """
        # Inject pending feedback if available
        if self.feedback_enabled and self._pending_feedback:
            self.client.inject_structural_feedback(self._pending_feedback)
            self._pending_feedback = None

        self.history.append(message)
        resp = self.client.chat(message)
        text = resp.text.strip()
        self.history.append(text)
        self.all_steps.extend(resp.steps)

        metrics = compute_metrics(resp.steps)
        self.turn_metrics.append(metrics)

        return text, resp.steps, metrics

    def score_and_prepare_feedback(
        self, text: str, metrics: Dict, lang: str = 'en'
    ) -> Optional[str]:
        """Score the response and prepare adaptive feedback for the next turn.

        Returns the feedback text (or None if not needed).
        Also stores it internally for automatic injection on next chat().
        """
        from experiments.quality_metrics import score_e0_completeness
        from e0_feedback import generate_structural_feedback, format_feedback_for_injection
        from e0_meta_feedback import generate_adaptive_feedback

        comp = score_e0_completeness(text)

        # Use adaptive feedback if topology is available
        if self._topology_data is not None:
            feedback = generate_adaptive_feedback(
                comp,
                topology=self._topology_data,
                meta_trends=self._meta_trends,
                lang=lang,
                include_metrics=metrics,
            )
        else:
            feedback = generate_structural_feedback(
                comp, lang=lang, include_metrics=metrics,
            )

        if feedback:
            self._pending_feedback = format_feedback_for_injection(feedback)
            self.last_feedback = feedback
        else:
            self._pending_feedback = None
            self.last_feedback = None
        return feedback

    def reset(self):
        """Reset the API client for re-initialization."""
        from e0_middleware.api_wrapper import E0ChatClient
        self.client = E0ChatClient(
            api_key=self.api_key, model=self.model_name,
            base_url=self.base_url, e0_prime=True,
            logprobs=True, top_logprobs=5,
        )
        self.history.clear()
        self.turn_metrics.clear()
        self.all_steps.clear()
        self.init_metrics = None
        self._pending_feedback = None
        self.last_feedback = None
        self.topology_loaded = False
        self.topology_text = None
        self._topology_data = None
        self._meta_trends = None
        self.meta_observation = None
        self.self_recognition_done = False
        self.self_recognition_results = None
