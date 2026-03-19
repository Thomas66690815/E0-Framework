"""
E₀ Instrumentation — Measuring E₀ Primitives on Real LLM Output
=================================================================
Takes raw logprobs / token probabilities from any LLM API
and computes E₀ primitives in real-time:

  Token probability  →  Resistance (R = -log(p), R=∞ for masked)
  Probability delta  →  Difference (Δ between token distributions)
  Top-k ordering     →  Rate (v = Δ/R, which tokens are 'enforced')
  Cache growth       →  Historization (τ advances with each token)
  Entropy change     →  Structural stability measure

No model weights needed. Only the OUTPUT distribution.
This works with:
  - OpenAI API (logprobs=True)
  - Anthropic API (if logprobs available)
  - HuggingFace (full logit access)
  - Any system that exposes token probabilities
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from e0_core.primitives import State, Path, Historization, HistorizationEvent


# ─────────────────────────────────────────────
# Token as E₀ State
# ─────────────────────────────────────────────

@dataclass
class TokenMeasurement:
    """
    E₀ measurement of a single token in context.

    Every token the LLM considers is a State.
    Its probability determines its Resistance.
    The selected token is the realized transition.
    """
    token: str
    logprob: float          # log-probability from model
    probability: float      # exp(logprob)
    resistance: float       # E₀ R = -logprob (higher R = harder to reach)
    rank: int               # position in probability ranking

    @property
    def rate(self) -> float:
        """v = Δ/R — but at token level, Δ is implicitly 1 (one step)."""
        if self.resistance <= 0:
            return float('inf')
        return 1.0 / self.resistance

    def __repr__(self) -> str:
        return (
            f"Token('{self.token}' | p={self.probability:.4f} "
            f"R={self.resistance:.4f} rank={self.rank})"
        )


# ─────────────────────────────────────────────
# Step Measurement — one generation step
# ─────────────────────────────────────────────

@dataclass
class StepMeasurement:
    """
    E₀ measurement of one complete generation step.

    Contains the full transition landscape:
    all candidates, the winner, and derived E₀ metrics.
    """
    tau: int                                # τ — position in sequence
    selected: TokenMeasurement              # the realized transition
    candidates: List[TokenMeasurement]      # all considered tokens
    entropy: float                          # H(distribution) — structural stability
    delta_entropy: float                    # ΔH from previous step
    top_rate_ratio: float                   # v_1 / v_2 — collapse risk indicator

    # E₀ derived metrics
    avg_resistance: float                   # R̄ across candidates
    resistance_spread: float                # σ(R) — landscape roughness
    historization_depth: int                # how many prior tokens in context

    @property
    def is_collapse_risk(self) -> bool:
        """Guard 1: Is the top token absorbing too much probability mass?"""
        return self.top_rate_ratio > 10.0

    @property
    def is_low_trace(self) -> bool:
        """Guard 3: Is this token providing minimal structural change?"""
        return abs(self.delta_entropy) < 0.01 and self.selected.probability > 0.9

    @property
    def structural_stability(self) -> str:
        """Qualitative assessment of the transition landscape."""
        if self.entropy > 3.0:
            return "HIGH_Δ"        # Many viable paths — high difference
        elif self.entropy > 1.5:
            return "BALANCED"       # Healthy transition space
        elif self.entropy > 0.5:
            return "NARROWING"      # Paths are consolidating
        else:
            return "CONVERGED"      # Near-deterministic — low Δ remaining

    def __repr__(self) -> str:
        return (
            f"Step(τ={self.tau} | '{self.selected.token}' "
            f"p={self.selected.probability:.4f} "
            f"H={self.entropy:.3f} | {self.structural_stability})"
        )


# ─────────────────────────────────────────────
# E₀ Instrumenter — The measurement engine
# ─────────────────────────────────────────────

class E0Instrumenter:
    """
    Instruments LLM output with E₀ primitives.

    Feed it token logprobs from any source.
    It computes all E₀ metrics in real-time.

    Usage:
        instrumenter = E0Instrumenter()

        # For each generation step, feed logprobs:
        measurement = instrumenter.measure_step(
            logprobs={"the": -0.5, "a": -1.2, "an": -2.1, ...},
            selected_token="the"
        )

        # Get E₀ metrics:
        print(measurement.entropy)          # structural stability
        print(measurement.selected.resistance)  # R of chosen path
        print(measurement.is_collapse_risk)  # guard check

        # Full session report:
        print(instrumenter.report())
    """

    def __init__(self):
        self.steps: List[StepMeasurement] = []
        self._prev_entropy: float = 0.0

    @property
    def tau(self) -> int:
        """Current time = number of realized transitions."""
        return len(self.steps)

    def _logprob_to_resistance(self, logprob: float) -> float:
        """
        R = -log(p)

        This is the EXACT structural mapping:
          - High probability → low R → easy path
          - Low probability  → high R → hard path
          - Zero probability → R = ∞  → path blocked

        This isn't an analogy. -log(p) IS the information-theoretic
        cost of selecting this token. Cost IS resistance.
        """
        return -logprob if logprob < 0 else 1e-10

    def _compute_entropy(self, probs: List[float]) -> float:
        """
        Shannon entropy of the distribution.

        High entropy = many viable paths (high Δ, unstable)
        Low entropy  = few viable paths (low Δ, converging)
        Zero entropy = only one path (deterministic, Δ→0)

        This IS the E₀ 'landscape roughness' — how much
        unresolved difference exists in the transition space.
        """
        h = 0.0
        for p in probs:
            if p > 0:
                h -= p * math.log2(p)
        return h

    def measure_step(
        self,
        logprobs: Dict[str, float],
        selected_token: str,
    ) -> StepMeasurement:
        """
        Measure one generation step through the E₀ lens.

        Args:
            logprobs: Dict mapping token → log-probability
            selected_token: The token that was actually generated

        Returns:
            StepMeasurement with full E₀ metrics
        """
        # Build token measurements
        candidates: List[TokenMeasurement] = []
        sorted_tokens = sorted(logprobs.items(), key=lambda x: x[1], reverse=True)

        for rank, (token, lp) in enumerate(sorted_tokens):
            prob = math.exp(lp) if lp > -50 else 0.0
            r = self._logprob_to_resistance(lp)
            candidates.append(TokenMeasurement(
                token=token,
                logprob=lp,
                probability=prob,
                resistance=r,
                rank=rank,
            ))

        # Find the selected token
        selected = None
        for c in candidates:
            if c.token == selected_token:
                selected = c
                break
        if selected is None:
            # Token wasn't in logprobs — create with minimal info
            selected = TokenMeasurement(
                token=selected_token, logprob=-1.0,
                probability=0.37, resistance=1.0, rank=-1,
            )

        # Entropy
        probs = [c.probability for c in candidates]
        total_p = sum(probs)
        if total_p > 0:
            probs_norm = [p / total_p for p in probs]
        else:
            probs_norm = probs
        entropy = self._compute_entropy(probs_norm)
        delta_entropy = entropy - self._prev_entropy

        # Rate ratio (collapse indicator)
        if len(candidates) >= 2:
            v1 = candidates[0].rate
            v2 = candidates[1].rate
            top_rate_ratio = v1 / v2 if v2 > 0 else float('inf')
        else:
            top_rate_ratio = 1.0

        # Resistance landscape stats
        resistances = [c.resistance for c in candidates if not math.isinf(c.resistance)]
        avg_r = sum(resistances) / len(resistances) if resistances else float('inf')
        if len(resistances) > 1:
            mean_r = avg_r
            spread = math.sqrt(
                sum((r - mean_r) ** 2 for r in resistances) / len(resistances)
            )
        else:
            spread = 0.0

        step = StepMeasurement(
            tau=self.tau,
            selected=selected,
            candidates=candidates,
            entropy=entropy,
            delta_entropy=delta_entropy,
            top_rate_ratio=top_rate_ratio,
            avg_resistance=avg_r,
            resistance_spread=spread,
            historization_depth=self.tau,
        )

        self._prev_entropy = entropy
        self.steps.append(step)
        return step

    # ─────────────────────────────────────────
    # Session-level E₀ analysis
    # ─────────────────────────────────────────

    def detect_phase_transitions(self) -> List[Tuple[int, str]]:
        """
        Detect structural phase transitions in the generation.

        A phase transition is a sudden change in the resistance
        landscape — the model shifts from one 'mode' to another.

        In E₀ terms: the topology of the accessible state space
        reconfigures. This is visible as entropy jumps.
        """
        transitions = []
        for i in range(1, len(self.steps)):
            dh = abs(self.steps[i].delta_entropy)
            if dh > 1.0:
                direction = "OPENING" if self.steps[i].delta_entropy > 0 else "CLOSING"
                transitions.append((
                    self.steps[i].tau,
                    f"Phase transition at τ={self.steps[i].tau}: "
                    f"ΔH={self.steps[i].delta_entropy:+.3f} — "
                    f"state space {direction}"
                ))
        return transitions

    def resistance_trajectory(self) -> List[float]:
        """R̄ over time — shows how the landscape evolves."""
        return [s.avg_resistance for s in self.steps]

    def entropy_trajectory(self) -> List[float]:
        """H over time — shows structural stability evolution."""
        return [s.entropy for s in self.steps]

    def convergence_profile(self) -> Dict[str, any]:
        """
        Overall convergence analysis.

        Answers: Is the model converging (Δ→0)?
        Is it stuck (high R, no movement)?
        Is it collapsing (one path dominating)?
        """
        if not self.steps:
            return {"status": "NO_DATA"}

        recent = self.steps[-5:] if len(self.steps) >= 5 else self.steps
        avg_entropy = sum(s.entropy for s in recent) / len(recent)
        avg_collapse_risk = sum(
            1 for s in recent if s.is_collapse_risk
        ) / len(recent)
        entropy_trend = (
            (recent[-1].entropy - recent[0].entropy) / len(recent)
            if len(recent) > 1 else 0.0
        )

        if avg_entropy < 0.3:
            status = "CONVERGED"
        elif avg_collapse_risk > 0.5:
            status = "COLLAPSING"
        elif entropy_trend < -0.3:
            status = "CONVERGING"
        elif entropy_trend > 0.3:
            status = "DIVERGING"
        else:
            status = "EXPLORING"

        return {
            "status": status,
            "avg_entropy": avg_entropy,
            "entropy_trend": entropy_trend,
            "collapse_risk": avg_collapse_risk,
            "tau": self.tau,
            "phase_transitions": len(self.detect_phase_transitions()),
        }

    def report(self) -> str:
        """Full E₀ instrumentation report."""
        lines = [
            "═══ E₀ Instrumentation Report ═══",
            f"  τ (tokens generated): {self.tau}",
        ]

        if not self.steps:
            lines.append("  No data yet.")
            return "\n".join(lines)

        # Convergence profile
        profile = self.convergence_profile()
        lines += [
            f"  Status: {profile['status']}",
            f"  Avg entropy:  {profile['avg_entropy']:.4f}",
            f"  Entropy trend: {profile['entropy_trend']:+.4f}",
            f"  Collapse risk: {profile['collapse_risk']:.2%}",
            f"  Phase transitions: {profile['phase_transitions']}",
            "",
            "  Step-by-step:",
        ]

        for step in self.steps:
            flags = []
            if step.is_collapse_risk:
                flags.append("⚠COLLAPSE")
            if step.is_low_trace:
                flags.append("⚠LOW_TRACE")
            flag_str = " " + " ".join(flags) if flags else ""

            lines.append(
                f"    τ={step.tau:3d} | '{step.selected.token:>12s}' "
                f"p={step.selected.probability:.4f} "
                f"R={step.selected.resistance:.3f} "
                f"H={step.entropy:.3f} "
                f"[{step.structural_stability}]{flag_str}"
            )

        # Phase transitions
        phases = self.detect_phase_transitions()
        if phases:
            lines += ["", "  Phase Transitions:"]
            for _, desc in phases:
                lines.append(f"    {desc}")

        return "\n".join(lines)
