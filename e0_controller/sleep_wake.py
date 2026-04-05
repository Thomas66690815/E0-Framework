"""
Sleep–Wake Cycle (C121)
========================
Automatic rhythm between active navigation (wake) and passive
consolidation (dream). Closes the loop between Structural Entropy
(C114–C120) and Dream Mode (C109–C112).

The trigger is parameter-free:

    should_dream ⟺ T_s > μ

where T_s = structural temperature and μ = half-load constant
(the same μ used by inertia_factor, inscription_threshold,
and adaptive_mu).

Cycle:
    Wake:  Controller.run()  →  T_s rises  →  inscription slows
    Sleep: DreamObserver.dream_cycle()  →  decay lowers T_s
    Wake:  inscription resumes  →  new experience  →  T_s rises …

The SleepWakeCycle does NOT modify Controller or DreamObserver.
It only decides WHEN to call dream_cycle(), based on dream_pressure.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set

from .config import DEFAULTS
from .controller import E0Controller, RunTrace
from .dream_mode import DreamCycleResult, DreamObserver, make_dream_peer_fn
from .structural_entropy import (
    dream_pressure,
    should_dream,
    structural_temperature,
)


# ---------------------------------------------------------------------------
# Episode result
# ---------------------------------------------------------------------------

@dataclass
class WakePhase:
    """Result of a single wake phase (one controller run)."""
    domain: str
    trace: RunTrace
    T_s_before: float
    T_s_after: float
    pressure_after: float


@dataclass
class SleepPhase:
    """Result of a single sleep phase (dream cycles until pressure drops)."""
    dream_results: List[DreamCycleResult]
    T_s_before: float
    T_s_after: float
    pressure_before: float
    pressure_after: float


@dataclass
class EpisodeResult:
    """One full wake–sleep episode."""
    episode: int
    wake: WakePhase
    slept: bool
    sleep: Optional[SleepPhase] = None


# ---------------------------------------------------------------------------
# SleepWakeCycle
# ---------------------------------------------------------------------------

class SleepWakeCycle:
    """Orchestrates wake (controller) and sleep (dream) phases.

    Does not own controllers or dream observer — holds references only.
    The user registers domain controllers; the cycle decides when to
    dream based on dream_pressure.

    Usage:
        swc = SleepWakeCycle(dream_observer, mu=5.0)
        swc.register("chess", chess_controller, start="A", goal="B")
        swc.register("invoice", invoice_controller, start="X", goal="Y")

        results = swc.run(n_episodes=30, max_cycles_per_run=40)
        # → List[EpisodeResult] with automatic wake/sleep rhythm

    Parameters
    ----------
    observer : DreamObserver
        Must have the same domains registered. SleepWakeCycle checks
        dream_pressure on the observer's domain landscapes.
    mu : float
        Half-load constant. Same μ as everywhere. Default 5.0.
    max_dream_cycles : int
        Safety cap on dream cycles per sleep phase. Default 10.
    """

    def __init__(
        self,
        observer: DreamObserver,
        *,
        mu: float = DEFAULTS.mu,
        max_dream_cycles: int = DEFAULTS.max_dream_cycles,
    ):
        self._observer = observer
        self._mu = mu
        self._max_dream_cycles = max_dream_cycles
        self._controllers: Dict[str, E0Controller] = {}
        self._starts: Dict[str, str] = {}
        self._goals: Dict[str, Optional[str]] = {}
        self._episodes: List[EpisodeResult] = []

    # -- Registration -------------------------------------------------------

    def register(
        self,
        name: str,
        controller: E0Controller,
        start: str,
        goal: Optional[str] = None,
    ) -> None:
        """Register a domain controller for the wake phase."""
        self._controllers[name] = controller
        self._starts[name] = start
        self._goals[name] = goal

    @property
    def domain_names(self) -> List[str]:
        return list(self._controllers.keys())

    def wire_peer_fns(
        self,
        *,
        min_quality: float = 0.0,
        base_discount: float = 0.5,
    ) -> int:
        """Auto-create dream peer_fns for all registered controllers (C154).

        Each controller gets a peer_fn that consults dream equivalences
        (both edge-level and node-level) during overload.

        Must be called after all domains are registered.

        Returns number of controllers wired.
        """
        wired = 0
        for name, ctrl in self._controllers.items():
            goal = self._goals.get(name)
            peer = make_dream_peer_fn(
                self._observer,
                name,
                goal,
                min_quality=min_quality,
                base_discount=base_discount,
            )
            ctrl.peer_fn = peer
            wired += 1
        return wired

    @property
    def episodes(self) -> List[EpisodeResult]:
        return list(self._episodes)

    # -- Core loop ----------------------------------------------------------

    def run(
        self,
        n_episodes: int = 10,
        max_cycles_per_run: int = 50,
    ) -> List[EpisodeResult]:
        """Run n episodes of the sleep–wake cycle.

        Each episode:
        1. Wake: run each registered controller once
        2. Check: should_dream on any domain?
        3. Sleep: if yes, dream_cycle until pressure drops or cap reached

        Returns list of EpisodeResult for analysis.
        """
        results: List[EpisodeResult] = []

        for ep_i in range(n_episodes):
            # Wake phase — run each domain
            for name, ctrl in self._controllers.items():
                hist = ctrl.landscape.historization
                T_s_before = structural_temperature(hist)

                trace = ctrl.run(
                    self._starts[name],
                    goal=self._goals[name],
                    max_cycles=max_cycles_per_run,
                )

                T_s_after = structural_temperature(hist)
                p_after = dream_pressure(hist, self._mu)

                wake = WakePhase(
                    domain=name,
                    trace=trace,
                    T_s_before=T_s_before,
                    T_s_after=T_s_after,
                    pressure_after=p_after,
                )

                # Check if ANY domain wants to dream
                any_dream = self._any_should_dream()

                sleep_phase = None
                slept = False

                if any_dream:
                    sleep_phase = self._sleep()
                    slept = True

                episode = EpisodeResult(
                    episode=ep_i,
                    wake=wake,
                    slept=slept,
                    sleep=sleep_phase,
                )

                results.append(episode)
                self._episodes.append(episode)

        return results

    def _any_should_dream(self) -> bool:
        """Check if any registered domain has dream_pressure > 0.5."""
        for name in self._observer.domain_names:
            landscape = self._observer._domains.get(name)
            if landscape is None:
                continue
            if should_dream(landscape.historization, self._mu):
                return True
        return False

    def _sleep(self) -> SleepPhase:
        """Run dream cycles until pressure drops below threshold or cap."""
        # Snapshot pressure before sleep
        pressures_before = self._domain_pressures()
        p_before = max(pressures_before.values()) if pressures_before else 0.0
        T_s_before = max(
            (structural_temperature(la.historization)
             for la in self._observer._domains.values()),
            default=0.0,
        )

        dream_results: List[DreamCycleResult] = []

        for _ in range(self._max_dream_cycles):
            result = self._observer.dream_cycle()
            dream_results.append(result)

            # Stop if no domain wants to dream anymore
            if not self._any_should_dream():
                break

        # Snapshot after sleep
        pressures_after = self._domain_pressures()
        p_after = max(pressures_after.values()) if pressures_after else 0.0
        T_s_after = max(
            (structural_temperature(la.historization)
             for la in self._observer._domains.values()),
            default=0.0,
        )

        return SleepPhase(
            dream_results=dream_results,
            T_s_before=T_s_before,
            T_s_after=T_s_after,
            pressure_before=p_before,
            pressure_after=p_after,
        )

    def _domain_pressures(self) -> Dict[str, float]:
        """Current dream_pressure for each observed domain."""
        return {
            name: dream_pressure(la.historization, self._mu)
            for name, la in self._observer._domains.items()
        }

    # -- Query --------------------------------------------------------------

    def pressure_report(self) -> Dict[str, Dict[str, float]]:
        """Current T_s and dream_pressure per domain."""
        report: Dict[str, Dict[str, float]] = {}
        for name, la in self._observer._domains.items():
            T_s = structural_temperature(la.historization)
            p = dream_pressure(la.historization, self._mu)
            report[name] = {"T_s": T_s, "pressure": p}
        return report

    def summary(self) -> str:
        """Human-readable summary of the cycle history."""
        total = len(self._episodes)
        slept = sum(1 for e in self._episodes if e.slept)
        lines = [
            f"SleepWakeCycle — {total} episodes, {slept} sleep phases",
        ]
        for name, la in self._observer._domains.items():
            T_s = structural_temperature(la.historization)
            p = dream_pressure(la.historization, self._mu)
            lines.append(f"  {name}: T_s={T_s:.3f}, pressure={p:.3f}")
        return "\n".join(lines)
