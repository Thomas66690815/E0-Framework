"""
C41 — Stochastic Exploration Policy
======================================
Controls which HybridMode to use per iteration in Session.iterate().

Canon basis:  Born sampling (P ∝ I) provides stochastic exploration
that can discover paths argmax misses (see ADR-0007, C22).  But once
the landscape is well-explored (historization built), deterministic
argmax converges faster.

The ExplorationPolicy encodes this explore→exploit transition:

    warmup=0 : always use exploit_mode (default, backward-compatible)
    warmup=N : Born sampling for iterations 1..N, then exploit_mode

Adaptive extension: when convergence_threshold > 0, the policy can
switch from explore→exploit early if mean residual tension drops
below the threshold before warmup exhaustion.

Integration point:  Session.iterate(..., exploration_policy=policy)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, TYPE_CHECKING

from .controller import HybridMode

if TYPE_CHECKING:
    from .residual_tension import ResidualTensionMap


@dataclass(frozen=True)
class PolicyDecision:
    """What mode to use for this iteration, and why."""
    mode: HybridMode
    phase: str          # "warmup" | "exploit" | "converged"
    iteration: int


@dataclass(frozen=True)
class ExplorationPolicy:
    """Controls explore→exploit mode switching across iterations.

    Parameters
    ----------
    warmup : int
        Number of initial iterations using explore_mode (Born sampling).
        0 means no warmup — always use exploit_mode.
    explore_mode : HybridMode
        Mode during warmup phase (default: BORN_SAMPLING).
    exploit_mode : HybridMode
        Mode after warmup phase (default: AMPLITUDE_ON_DISAGREE).
    convergence_threshold : float
        If > 0 and mean residual tension drops below this during
        warmup, switch to exploit early.  0 = disabled (default).
    """
    warmup: int = 0
    explore_mode: HybridMode = HybridMode.BORN_SAMPLING
    exploit_mode: HybridMode = HybridMode.AMPLITUDE_ON_DISAGREE
    convergence_threshold: float = 0.0

    def decide(
        self,
        iteration: int,
        prev_map: Optional["ResidualTensionMap"] = None,
    ) -> PolicyDecision:
        """Determine the mode for the given iteration.

        Parameters
        ----------
        iteration : int
            Current iteration number (1-based).
        prev_map : ResidualTensionMap, optional
            Tension map from the previous iteration (for convergence check).
        """
        if self.warmup <= 0:
            return PolicyDecision(self.exploit_mode, "exploit", iteration)

        # Early convergence: tension already low → switch to exploit
        if (
            self.convergence_threshold > 0
            and prev_map is not None
            and prev_map.mean_residual < self.convergence_threshold
        ):
            return PolicyDecision(self.exploit_mode, "converged", iteration)

        # Within warmup window
        if iteration <= self.warmup:
            return PolicyDecision(self.explore_mode, "warmup", iteration)

        # Past warmup
        return PolicyDecision(self.exploit_mode, "exploit", iteration)

    @property
    def label(self) -> str:
        """Human-readable policy description."""
        if self.warmup <= 0:
            return f"fixed({self.exploit_mode.value})"
        parts = f"born×{self.warmup}→{self.exploit_mode.value}"
        if self.convergence_threshold > 0:
            parts += f"|conv<{self.convergence_threshold}"
        return parts

    # ── Convenience constructors ──

    @staticmethod
    def fixed(mode: HybridMode = HybridMode.AMPLITUDE_ON_DISAGREE) -> "ExplorationPolicy":
        """Always use the same mode (no warmup)."""
        return ExplorationPolicy(warmup=0, exploit_mode=mode)

    @staticmethod
    def born_warmup(
        warmup: int = 3,
        *,
        convergence_threshold: float = 0.0,
    ) -> "ExplorationPolicy":
        """Born sampling for first N iterations, then argmax."""
        return ExplorationPolicy(
            warmup=warmup,
            convergence_threshold=convergence_threshold,
        )
