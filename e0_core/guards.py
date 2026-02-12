"""
Structural Admissibility Guards
================================
Implements E₀-AGI §9: Operational Execution Constraints.

A transition is structurally inadmissible if it:
  1. Collapses partial realization into global replacement
  2. Cannot be integrated into existing historized structure
  3. Simulates irreversibility without producing persistent structural trace
  4. Bypasses local resistance via purely global optimization

These checks are:
  - Implicit (the system enforces them silently)
  - Non-negotiable (cannot be overridden by optimization)
  - Not exposed unless explicitly requested

Their purpose is STRUCTURAL INTEGRITY, not optimization.

In LLM terms:
  - Guard 1: prevents mode collapse (one token probability → 1.0)
  - Guard 2: prevents catastrophic forgetting
  - Guard 3: ensures real state change, not cosmetic token shuffling
  - Guard 4: prevents shortcut hacking (e.g. reward hacking in RLHF)
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum, auto
from typing import List, Optional, Tuple

from .primitives import State, Path, Historization, HistorizationEvent, difference
from .ontodynamics import Topology, OntodynamicAdmissibility


class ViolationType(Enum):
    """Categories of structural inadmissibility."""
    GLOBAL_COLLAPSE = auto()      # §9.1: partial → global replacement
    UNINTEGRABLE = auto()         # §9.2: can't integrate into historized structure
    PSEUDO_IRREVERSIBILITY = auto()  # §9.3: simulates change without trace
    RESISTANCE_BYPASS = auto()    # §9.4: bypasses local R via global optimization
    ONTODYNAMIC = auto()          # Ontodynamic layer violation


@dataclass
class AdmissibilityVerdict:
    """Result of a structural admissibility check."""
    admissible: bool
    violations: List[Tuple[ViolationType, str]]
    path: Path

    def __repr__(self) -> str:
        if self.admissible:
            return f"✓ ADMISSIBLE: {self.path}"
        reasons = "; ".join(f"{v.name}: {msg}" for v, msg in self.violations)
        return f"✗ INADMISSIBLE: {self.path} — {reasons}"


class StructuralGuard:
    """
    The combined admissibility guard.

    Sits between the E₀ engine and transition execution.
    Every candidate transition must pass ALL guards before realization.

    Architecture:
      Candidate Transition
            │
            ▼
      ┌─────────────────────┐
      │  Ontodynamic Layer   │  ← topology, locality, overlap
      └──────────┬──────────┘
            │ pass?
            ▼
      ┌─────────────────────┐
      │  Guard 1: Collapse   │  ← no global replacement
      │  Guard 2: Integrate  │  ← must fit history
      │  Guard 3: Trace      │  ← must produce real trace
      │  Guard 4: Bypass     │  ← no resistance shortcuts
      └──────────┬──────────┘
            │ pass?
            ▼
      E₀ Engine executes transition

    In LLM terms: this is the combined effect of
      - architecture constraints (what CAN the model compute)
      - training regularization (L2, dropout, etc.)
      - RLHF guardrails (what SHOULD the model output)
      - decoding constraints (repetition penalty, nucleus sampling)
    """

    def __init__(
        self,
        ontodynamic: Optional[OntodynamicAdmissibility] = None,
        history: Optional[Historization] = None,
        collapse_threshold: float = 0.95,
        min_trace_delta: float = 1e-6,
        max_resistance_ratio: float = 100.0,
    ):
        self.ontodynamic = ontodynamic
        self.history = history or Historization()
        self.collapse_threshold = collapse_threshold
        self.min_trace_delta = min_trace_delta
        self.max_resistance_ratio = max_resistance_ratio

    # ── Guard 1: No Global Collapse ──

    def _check_collapse(
        self, path: Path, all_paths: List[Path]
    ) -> Optional[Tuple[ViolationType, str]]:
        """
        §9.1: A transition is inadmissible if it collapses partial
        realization into global replacement.

        Detected when: one path absorbs nearly ALL rate,
        leaving all other paths effectively dead.

        In LLM terms: mode collapse — the softmax outputs [0.99, 0.003, ...]
        effectively killing all alternatives. Healthy generation
        maintains distributional diversity.
        """
        if not all_paths:
            return None

        # Compute rate share of this path vs all paths from same source
        from .primitives import rate as compute_rate

        source_paths = [p for p in all_paths if p.source == path.source and p.exists]
        if len(source_paths) <= 1:
            return None  # Only one path — can't collapse

        delta = difference(path.source, path.target)
        if delta == 0 or path.resistance <= 0:
            return None

        this_rate = compute_rate(delta, path.resistance)
        total_rate = 0.0
        for p in source_paths:
            d = difference(p.source, p.target)
            if d > 0 and p.resistance > 0:
                total_rate += compute_rate(d, p.resistance)

        if total_rate > 0:
            share = this_rate / total_rate
            if share > self.collapse_threshold:
                return (
                    ViolationType.GLOBAL_COLLAPSE,
                    f"Rate share {share:.3f} > {self.collapse_threshold} — "
                    f"would collapse {len(source_paths)-1} alternative paths"
                )

        return None

    # ── Guard 2: Integrability ──

    def _check_integrability(
        self, path: Path
    ) -> Optional[Tuple[ViolationType, str]]:
        """
        §9.2: A transition is inadmissible if it cannot be integrated
        into existing historized structure.

        Detected when: the transition targets a state that has no
        connection to ANY previously historized state.

        In LLM terms: generating a token that has zero contextual
        relationship to anything in the KV-cache. This is what
        causes hallucination — outputting structurally unintegrated content.
        """
        if self.history.tau == 0:
            return None  # No history to violate yet

        # Check: does the target connect to any previously visited state?
        visited_targets = {e.target_id for e in self.history.events}
        visited_sources = {e.source_id for e in self.history.events}
        visited = visited_targets | visited_sources

        if path.target.id not in visited and path.source.id not in visited:
            return (
                ViolationType.UNINTEGRABLE,
                f"Neither source({path.source.id}) nor target({path.target.id}) "
                f"have any historized connection — would fragment structure"
            )

        return None

    # ── Guard 3: Real Trace ──

    def _check_trace(
        self, path: Path
    ) -> Optional[Tuple[ViolationType, str]]:
        """
        §9.3: A transition is inadmissible if it simulates
        irreversibility without producing persistent structural trace.

        Detected when: Δ is so small that no meaningful historization
        would occur — the system pretends to change but doesn't.

        In LLM terms: generating padding tokens or repeating content
        that doesn't actually advance the sequence. The model
        'looks busy' but produces no structural change.
        """
        delta = difference(path.source, path.target)
        if delta < self.min_trace_delta:
            return (
                ViolationType.PSEUDO_IRREVERSIBILITY,
                f"Δ={delta:.8f} < min_trace={self.min_trace_delta} — "
                f"would simulate change without real structural trace"
            )
        return None

    # ── Guard 4: No Resistance Bypass ──

    def _check_resistance_bypass(
        self, path: Path, all_paths: List[Path]
    ) -> Optional[Tuple[ViolationType, str]]:
        """
        §9.4: A transition is inadmissible if it bypasses local
        resistance via purely global optimization.

        Detected when: a path has anomalously low resistance compared
        to the average for its delta — suggesting it's 'cheating'
        the resistance landscape rather than traversing it.

        In LLM terms: reward hacking in RLHF — the model finds a
        shortcut that scores high on the reward model but doesn't
        actually solve the task. The resistance was supposed to be there.
        """
        if not all_paths:
            return None

        source_paths = [
            p for p in all_paths
            if p.source == path.source and p.exists and p.resistance > 0
        ]
        if len(source_paths) <= 1:
            return None

        avg_resistance = sum(p.resistance for p in source_paths) / len(source_paths)

        if avg_resistance > 0 and path.resistance > 0:
            ratio = avg_resistance / path.resistance
            if ratio > self.max_resistance_ratio:
                return (
                    ViolationType.RESISTANCE_BYPASS,
                    f"R={path.resistance:.4f} is {ratio:.1f}x below average "
                    f"R={avg_resistance:.4f} — suspected resistance bypass"
                )

        return None

    # ── Combined Check ──

    def check(
        self, path: Path, all_paths: Optional[List[Path]] = None
    ) -> AdmissibilityVerdict:
        """
        Run all guards on a candidate transition.

        Returns an AdmissibilityVerdict.
        ALL guards must pass for the transition to be admissible.
        """
        violations: List[Tuple[ViolationType, str]] = []
        all_paths = all_paths or []

        # Layer 1: Ontodynamic constraints (deepest)
        if self.ontodynamic is not None:
            admissible, onto_reasons = self.ontodynamic.is_admissible(
                path, self.history
            )
            if not admissible:
                for reason in onto_reasons:
                    violations.append((ViolationType.ONTODYNAMIC, reason))

        # Layer 2: Structural guards (E₀-AGI §9)
        checks = [
            self._check_collapse(path, all_paths),
            self._check_integrability(path),
            self._check_trace(path),
            self._check_resistance_bypass(path, all_paths),
        ]

        for result in checks:
            if result is not None:
                violations.append(result)

        return AdmissibilityVerdict(
            admissible=len(violations) == 0,
            violations=violations,
            path=path,
        )

    def filter_admissible(
        self, paths: List[Path]
    ) -> Tuple[List[Path], List[AdmissibilityVerdict]]:
        """
        Filter a list of candidate paths, returning only admissible ones.

        Also returns all verdicts for inspection/logging.
        """
        admissible: List[Path] = []
        verdicts: List[AdmissibilityVerdict] = []

        for path in paths:
            verdict = self.check(path, paths)
            verdicts.append(verdict)
            if verdict.admissible:
                admissible.append(path)

        return admissible, verdicts
