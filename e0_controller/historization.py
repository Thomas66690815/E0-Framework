"""
E₀ Controller — Historization
==============================
Success/Failure trace management with separated learning rates.

Spec coverage: §17.1 (U/F Traces), §17.2 (δ_H correction), §17.3 (Clipping).

Core equations:
    U_t(e) = ρ_S · U_{t-1}(e) + 𝟙_success
    F_t(e) = ρ_F · F_{t-1}(e) + 𝟙_failure

Asymmetric decay (C79): ρ_S and ρ_F can differ. When ρ_F > ρ_S,
failures are remembered longer than successes — reflecting that errors
are asymmetrically informative (they reveal multiple blocked paths,
not just one). Default: ρ_S = ρ_F = ρ (symmetric, backward-compatible).
    δ_H(e) = λ_f · F_t(e) − λ_s · U_t(e)
    δ_H_clipped = clip(δ_H, -δ_max, δ_max)
    R_eff(e) = R₀(e) + δ_H_clipped(e)

Global decay (K2): All edges decay by ρ at every global time step τ, not
just when touched. Implemented as lazy catch-up: each edge stores τ_last
(when it was last written). On access, the stored traces are multiplied by
ρ^(τ − τ_last) to account for the missed decay steps. This is mathematically
identical to iterating all edges at every step, but O(1) per access.

Epistemic Trust (C186):
    E₀ doubts always. Historized knowledge is a hypothesis, not truth.
    trust(e) = exp(−staleness(e) / τ_doubt(e))
    where staleness = τ − τ_last(e)
    and τ_doubt(e) = τ_base / (1 − stability(e) + ε)
    stability(e) = confirmations(e) / (confirmations(e) + surprises(e) + 1)

    confirmations/surprises are ρ-decayed alongside U/F.
    A revisit "confirms" when the outcome matches the predicted direction
    (q > 0 → SUCCESS, q < 0 → FAILURE), else it "surprises".
    τ_base = median inter-visit interval (self-calibrating).

    Result: stable edges (always confirmed) → trust stays high.
    Volatile edges (often surprised) → trust decays fast.
    Stale edges (never revisited) → trust drifts toward 0.
    δ_H_trusted(e) = δ_H(e) · trust(e).

Surprise Dampening (C187):
    "The bridge was full" ≠ "the bridge is bad."
    When surprise_dampening=True, a surprising outcome (revisit where
    actual contradicts predicted direction) is inscribed with weight 0.5
    instead of 1.0.  This prevents transient events from overwriting
    stable knowledge.  First-visit edges are always inscribed at full
    weight (no expectation to violate).

    classify_experience() diagnoses the domain character from accumulated
    surprise/confirmation statistics:
        'stable'      — low surprise rate (< 30%), outcomes match predictions
        'volatile'    — high surprise rate (≥ 30%), many contradictions
        'exploratory' — insufficient revisit data

Note on PARTIAL outcomes: The canonical spec defines only SUCCESS and FAILURE.
PARTIAL (U += 0.5, F += 0.3) is a runtime convenience extension — operationally
useful but not derived from the minimal canonical core.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Tuple, Optional

from .primitives import Edge, Outcome
from .config import DEFAULTS


@dataclass
class TraceRecord:
    """Single historization event for audit trail."""
    tau: int
    edge: Edge
    outcome: Outcome
    r_eff_before: float
    r_eff_after: float
    predecessor: Optional[Edge] = None  # C176: previous edge in same run


@dataclass
class Historization:
    """
    Separated Success/Failure trace management.

    Successes lower effective resistance (path reinforcement).
    Failures raise effective resistance (path avoidance).
    Decay (ρ < 1) prevents permanent lock-in.
    Clipping (δ_max) ensures bounded dynamics.
    """

    # Learning parameters
    rho: float = DEFAULTS.rho
    lambda_s: float = DEFAULTS.lambda_s
    lambda_f: float = DEFAULTS.lambda_f
    delta_max: float = DEFAULTS.delta_max
    rho_s: Optional[float] = None  # success-trace decay (None → rho)
    rho_f: Optional[float] = None  # failure-trace decay (None → rho)

    # Internal state
    _U: Dict[Edge, float] = field(default_factory=dict)  # success traces
    _F: Dict[Edge, float] = field(default_factory=dict)  # failure traces
    _tau: int = 0
    _tau_last: Dict[Edge, int] = field(default_factory=dict)  # K2: last-update time per edge
    _log: List[TraceRecord] = field(default_factory=list)

    # Epistemic Trust (C186)
    _confirmations: Dict[Edge, float] = field(default_factory=dict)
    _surprises: Dict[Edge, float] = field(default_factory=dict)
    _inter_visit_intervals: List[int] = field(default_factory=list)  # recent intervals for τ_base

    # Surprise Dampening (C187)
    surprise_dampening: bool = False  # when True, surprising outcomes get weight 0.5

    # --- Lazy Global Decay (K2) ---

    def _effective_traces(self, edge: Edge) -> Tuple[float, float]:
        """
        Return (U, F) with lazy global decay applied.

        If an edge was last written at τ_last and current time is τ,
        the effective traces are ρ^(τ − τ_last) · stored values.
        This accounts for decay steps that occurred while the edge
        was not being directly updated.
        """
        u = self._U.get(edge, 0.0)
        f = self._F.get(edge, 0.0)
        if u == 0.0 and f == 0.0:
            return 0.0, 0.0
        tau_last = self._tau_last.get(edge, self._tau)
        gap = self._tau - tau_last
        if gap > 0:
            rs = self.rho_s if self.rho_s is not None else self.rho
            rf = self.rho_f if self.rho_f is not None else self.rho
            u *= rs ** gap
            f *= rf ** gap
        return u, f

    # --- Public API ---

    def update(self, edge: Edge, outcome: Outcome) -> None:
        """
        Update traces after executing a transition.

        §17.1: U_t(e) = ρ · U_{t-1}(e) + 𝟙_success
               F_t(e) = ρ · F_{t-1}(e) + 𝟙_failure

        K2: Lazy catch-up is applied before the standard formula,
        so edges that haven't been touched for k steps first decay
        by ρ^k, then the single-step ρ + signal is applied.

        C186: Epistemic trust — track confirmations/surprises on revisit.
        A revisit = τ − τ_last > 1 (not the immediately next step).
        Confirmation: outcome matches predicted direction (q > 0 → S, q < 0 → F).
        Surprise: outcome contradicts predicted direction.

        C187: Surprise dampening — surprising outcomes are inscribed with
        reduced weight.  "The bridge was full" ≠ "the bridge is bad."
        When surprise_dampening is True and a revisit surprises us,
        the inscription weight is halved (0.5 instead of 1.0).
        This prevents transient events (congestion, temporary blockage)
        from overwriting stable knowledge.
        """
        # Catch up missed decay steps (K2)
        u_prev, f_prev = self._effective_traces(edge)
        rs = self.rho_s if self.rho_s is not None else self.rho
        rf = self.rho_f if self.rho_f is not None else self.rho

        # C186/C187: track revisit confirmation/surprise + dampening
        tau_last = self._tau_last.get(edge, -1)
        gap = self._tau - tau_last if tau_last >= 0 else -1
        is_surprise = False
        if gap > 1 and (u_prev + f_prev) > 1e-12:
            # This is a revisit of a previously-experienced edge
            self._inter_visit_intervals.append(gap)
            # Keep only recent intervals (sliding window)
            if len(self._inter_visit_intervals) > 200:
                self._inter_visit_intervals = self._inter_visit_intervals[-100:]
            # Predict: existing q tells us what we expect
            q_prev = (u_prev - f_prev) / (u_prev + f_prev + 1e-12)
            predicted_success = q_prev >= 0.0
            actual_success = (outcome == Outcome.SUCCESS or
                              (outcome == Outcome.PARTIAL and q_prev >= 0.0))
            is_surprise = (predicted_success != actual_success)
            # Decay old confirmations/surprises (same ρ as traces)
            rho_trust = self.rho
            old_conf = self._confirmations.get(edge, 0.0) * rho_trust ** gap
            old_surp = self._surprises.get(edge, 0.0) * rho_trust ** gap
            if not is_surprise:
                self._confirmations[edge] = old_conf + 1.0
                self._surprises[edge] = old_surp
            else:
                self._confirmations[edge] = old_conf
                self._surprises[edge] = old_surp + 1.0

        # C187: Surprise dampening — transient events get reduced inscription
        w = 0.5 if (is_surprise and self.surprise_dampening) else 1.0

        if outcome == Outcome.SUCCESS:
            self._U[edge] = rs * u_prev + w
            self._F[edge] = rf * f_prev
        elif outcome == Outcome.FAILURE:
            self._U[edge] = rs * u_prev
            self._F[edge] = rf * f_prev + w
        else:  # PARTIAL (runtime extension, not canonical)
            self._U[edge] = rs * u_prev + 0.5 * w
            self._F[edge] = rf * f_prev + 0.3 * w

        self._tau += 1
        self._tau_last[edge] = self._tau

    def delta_H(self, edge: Edge) -> float:
        """
        Historization correction for an edge.

        §17.2: δ_H(e) = λ_f · F_t(e) − λ_s · U_t(e)
        §17.3: clipped to [-δ_max, +δ_max]

        Positive δ_H → resistance increases (failures dominate).
        Negative δ_H → resistance decreases (successes dominate).

        K2: Uses effective (lazily decayed) traces.
        """
        u, f = self._effective_traces(edge)
        raw = self.lambda_f * f - self.lambda_s * u
        return max(-self.delta_max, min(raw, self.delta_max))

    # --- Epistemic Trust (C186) ---

    def stability(self, edge: Edge) -> float:
        """
        How stable is the learned knowledge about this edge?

        stability(e) = confirmations / (confirmations + surprises + 1)

        Returns float in [0, 1):
            → 0: no revisit data, or every revisit surprised us
            → ~1: many confirmations, few surprises (stable environment)

        The +1 in the denominator is a Bayesian prior: without evidence,
        stability is 0 (maximum doubt).
        """
        c = self._confirmations.get(edge, 0.0)
        s = self._surprises.get(edge, 0.0)
        # Apply lazy decay to confirmation/surprise counts
        tau_last = self._tau_last.get(edge, self._tau)
        gap = self._tau - tau_last
        if gap > 0:
            decay = self.rho ** gap
            c *= decay
            s *= decay
        return c / (c + s + 1.0)

    def _tau_base(self) -> float:
        """Self-calibrating base doubt interval.

        Median inter-visit interval across all recently observed edges.
        Falls back to 10 when no revisit data exists (conservative default).
        """
        if not self._inter_visit_intervals:
            return 10.0
        sorted_ivs = sorted(self._inter_visit_intervals)
        mid = len(sorted_ivs) // 2
        if len(sorted_ivs) % 2 == 0:
            return (sorted_ivs[mid - 1] + sorted_ivs[mid]) / 2.0
        return float(sorted_ivs[mid])

    def trust(self, edge: Edge) -> float:
        """
        Epistemic trust: how much should we believe δ_H for this edge?

        trust(e) = exp(−staleness(e) / τ_doubt(e))

        where:
            staleness = τ − τ_last(e)
            τ_doubt(e) = τ_base / (1 − stability(e) + ε)

        Properties:
            - Just visited (staleness=0): trust = 1.0
            - Stable edge (high stability): τ_doubt large → trust decays slowly
            - Volatile edge (low stability): τ_doubt small → trust decays fast
            - Never-visited edge: trust = 1.0 (no basis for doubt)
            - Virgin edge (no traces): trust = 1.0

        Returns float in (0, 1].
        """
        u, f = self._effective_traces(edge)
        if u + f < 1e-12:
            return 1.0  # virgin edge — nothing to doubt
        tau_last = self._tau_last.get(edge, self._tau)
        staleness = self._tau - tau_last
        if staleness <= 0:
            return 1.0
        stab = self.stability(edge)
        tau_base = self._tau_base()
        # τ_doubt: stable edges → large (slow doubt), volatile → small (fast doubt)
        tau_doubt = tau_base / (1.0 - stab + 0.01)
        return math.exp(-staleness / tau_doubt)

    def delta_H_trusted(self, edge: Edge) -> float:
        """
        Doubt-aware historization correction.

        δ_H_trusted(e) = δ_H(e) · trust(e)

        Semantics: "I remember this edge was bad, but I'm not sure
        that's still true." As trust decays, the historization
        correction weakens, and the edge returns to its base resistance.
        """
        return self.delta_H(edge) * self.trust(edge)

    # --- Experience Classification (C187) ---

    def surprise_rate(self) -> float:
        """Global fraction of surprising revisits.

        Returns the ratio of total surprises to total revisit events
        across all edges.  High surprise_rate = volatile/competitive
        environment where outcomes contradict predictions.

        Returns float in [0, 1].  0.0 when no revisit data exists.
        """
        total_conf = sum(self._confirmations.values())
        total_surp = sum(self._surprises.values())
        total = total_conf + total_surp
        if total < 1e-12:
            return 0.0
        return total_surp / total

    def classify_experience(self) -> str:
        """Classify the domain character from accumulated experience.

        Uses surprise_rate and surprise distribution to determine
        what kind of environment the agent is navigating.

        Returns one of:
            'stable'      — low surprise_rate, outcomes match predictions
            'volatile'    — high surprise_rate, many contradictions
            'exploratory' — insufficient revisit data to classify

        This is E₀'s domain-awareness: "What kind of problem am I in?"
        The classification can inform strategy choices (overlay horizon,
        exploration policy, inscription parameters) across rounds.
        """
        total_conf = sum(self._confirmations.values())
        total_surp = sum(self._surprises.values())
        total = total_conf + total_surp
        if total < 3.0:
            return "exploratory"
        sr = total_surp / total
        if sr > 0.3:
            return "volatile"
        return "stable"

    def surprise_edges(self, top_k: int = 5) -> list:
        """Return edges with highest surprise counts.

        Useful for diagnosing WHERE surprises concentrate — if they
        cluster at few edges, those are bottlenecks/congestion points.
        If distributed, the domain is inherently stochastic.

        Returns list of (edge, surprise_count) sorted descending.
        """
        items = [(e, s) for e, s in self._surprises.items() if s > 1e-12]
        items.sort(key=lambda x: -x[1])
        return items[:top_k]

    def record(self, edge: Edge, outcome: Outcome,
               r_eff_before: float, r_eff_after: float,
               predecessor: Optional[Edge] = None) -> None:
        """Append to audit trail."""
        self._log.append(TraceRecord(
            tau=self._tau, edge=edge, outcome=outcome,
            r_eff_before=r_eff_before, r_eff_after=r_eff_after,
            predecessor=predecessor,
        ))

    def remove_edges(self, edges) -> None:
        """Clean up trace data for removed edges.

        Deletes _U, _F, _tau_last, _confirmations, _surprises entries.
        The _log is preserved — historical events remain as a record
        of what happened, even after the structure that produced them
        is gone.

        Does not modify _tau.
        """
        for e in edges:
            self._U.pop(e, None)
            self._F.pop(e, None)
            self._tau_last.pop(e, None)
            self._confirmations.pop(e, None)
            self._surprises.pop(e, None)

    # --- Inspection ---

    @property
    def tau(self) -> int:
        """Current time = number of historization events."""
        return self._tau

    @property
    def log(self) -> List[TraceRecord]:
        return list(self._log)

    def success_trace(self, edge: Edge) -> float:
        u, _ = self._effective_traces(edge)
        return u

    def failure_trace(self, edge: Edge) -> float:
        _, f = self._effective_traces(edge)
        return f

    def trace_load(self, edge: Edge) -> float:
        """
        Total accumulated structural inscription on an edge (Layer 2).

        trace_load(e) = U(e) + F(e)

        Layer model (Ontodynamics §4):
          1. Historization — the process (update/decay)
          2. Structural inscription — what remains (trace_load, trace_quality)
          3. Inertia — functional effect (inertia_factor)
          4. Mass — outward appearance (emergent, not computed here)

        trace_load = 0 → no inscription (virgin edge)
        trace_load > 0 → accumulated structural trace

        K2: Uses effective (lazily decayed) traces.
        """
        u, f = self._effective_traces(edge)
        return u + f

    # Backward-compatible alias
    mass = trace_load

    def trace_quality(self, edge: Edge) -> float:
        """
        Directional balance of accumulated structural inscription (Layer 2).

        q(e) = (U(e) − F(e)) / (U(e) + F(e) + ε)    ∈ (−1, +1)

        Not *how much* inscription, but *what kind*:
          q → +1 : pure success (clearly reinforced)
          q → −1 : pure failure (clearly avoided)
          q ≈  0 : mixed signals or no inscription

        Together (trace_load, trace_quality) decompose the structural
        inscription into magnitude and direction — the two dimensions
        that scalar δ_H conflates.

        K2: Uses effective (lazily decayed) traces.
        """
        u, f = self._effective_traces(edge)
        return (u - f) / (u + f + 1e-12)

    # Backward-compatible alias
    quality = trace_quality

    def inertia_factor(self, edge: Edge,
                       alpha: float = DEFAULTS.inertia_alpha,
                       mu: float = DEFAULTS.mu) -> float:
        """
        Inertia modulation factor from structural inscription (Layer 3).

        I(e) = 1 − α · (m/(m+μ)) · (1 − |q|)

        where m = trace_load(e), q = trace_quality(e).

        Layer model:
          Layer 2 (inscription) → m and q exist
          Layer 3 (inertia) → this function: how inscription resists change
          Layer 4 (mass) → emergent behavior visible from outside

        Dampens edges with high inscription but low clarity (conflicting
        experience). This captures information that the scalar δ_H
        loses: when U ≈ F, δ_H ≈ 0 looks like "no inscription", but
        m >> 0 with q ≈ 0 means "lots of contradictory inscription".

        Parameters
        ----------
        alpha : float
            Maximum dampening strength at full confusion.
            Default 0.5 → conflicted edge damped to 0.5× at saturation.
        mu : float
            Half-load reference. When m = μ, m_norm = 0.5.
            Default 5.0 → ~5 events for half-load.

        Returns
        -------
        float in (1 − alpha, 1.0]:
            1.0 when no inscription or clear quality (|q| → 1).
            Minimum when high inscription and fully contradictory (|q| ≈ 0).

        K2: Uses effective (lazily decayed) traces.
        """
        u, f = self._effective_traces(edge)
        m = u + f
        if m < 1e-12:
            return 1.0  # no inscription → neutral
        m_norm = m / (m + mu)
        q = (u - f) / (m + 1e-12)
        confusion = 1.0 - abs(q)
        return 1.0 - alpha * m_norm * confusion

    # Backward-compatible alias
    mass_modulation_factor = inertia_factor

    # --- Snapshot export/import (for MemOS) ---

    def to_snapshot_dict(self) -> dict:
        """Export internal state as plain dict for serialization."""
        return {
            "tau": self._tau,
            "rho": self.rho,
            "lambda_s": self.lambda_s,
            "lambda_f": self.lambda_f,
            "delta_max": self.delta_max,
            "rho_s": self.rho_s,
            "rho_f": self.rho_f,
            "U": {e: v for e, v in self._U.items()},
            "F": {e: v for e, v in self._F.items()},
            "tau_last": {e: v for e, v in self._tau_last.items()},
            "confirmations": {e: v for e, v in self._confirmations.items()},
            "surprises": {e: v for e, v in self._surprises.items()},
        }

    @classmethod
    def from_snapshot_dict(cls, d: dict, edge_parser) -> Historization:
        """Reconstruct from a snapshot dict.

        edge_parser: callable that converts a dict key back to an Edge.
        """
        H = cls(
            rho=d["rho"],
            lambda_s=d["lambda_s"],
            lambda_f=d["lambda_f"],
            delta_max=d["delta_max"],
            rho_s=d.get("rho_s"),
            rho_f=d.get("rho_f"),
        )
        H._tau = d["tau"]
        H._U = {edge_parser(k): v for k, v in d["U"].items()}
        H._F = {edge_parser(k): v for k, v in d["F"].items()}
        # K2: backward compat — old snapshots without tau_last
        if "tau_last" in d:
            H._tau_last = {edge_parser(k): v for k, v in d["tau_last"].items()}
        else:
            # Assume all edges were current at snapshot time
            all_edges = set(H._U.keys()) | set(H._F.keys())
            H._tau_last = {e: H._tau for e in all_edges}
        # C186: backward compat — old snapshots without trust data
        if "confirmations" in d:
            H._confirmations = {edge_parser(k): v for k, v in d["confirmations"].items()}
        if "surprises" in d:
            H._surprises = {edge_parser(k): v for k, v in d["surprises"].items()}
        return H

    def summary(self) -> Dict[str, float]:
        """Quick overview of historization state (with lazy decay applied)."""
        all_edges = set(self._U.keys()) | set(self._F.keys())
        total_u = 0.0
        total_f = 0.0
        for e in all_edges:
            u, f = self._effective_traces(e)
            total_u += u
            total_f += f
        return {
            "tau": self._tau,
            "edges_touched": len(all_edges),
            "total_U": total_u,
            "total_F": total_f,
        }

    def strategy_profile(
        self,
        edges: Optional[List[Edge]] = None,
        *,
        top_n: int = 0,
    ) -> List[Tuple[Edge, float, float]]:
        """Extract learned strategy as ranked (edge, quality, load) triples.

        Returns edges sorted by trace_quality (descending), filtered to
        those with trace_load > 0 (at least one observation).

        This answers: "What did E₀ learn?"

        Parameters
        ----------
        edges : list of Edge, optional
            Edges to inspect.  If None, uses all edges that have
            been touched (non-zero U or F).
        top_n : int
            If > 0, return only the top N entries.  0 = all.

        Returns
        -------
        list of (Edge, trace_quality, trace_load) sorted by quality desc.
        """
        if edges is None:
            edges = list(set(self._U.keys()) | set(self._F.keys()))
        ranked = []
        for e in edges:
            load = self.trace_load(e)
            if load < 1e-12:
                continue
            ranked.append((e, self.trace_quality(e), load))
        ranked.sort(key=lambda x: x[1], reverse=True)
        if top_n > 0:
            ranked = ranked[:top_n]
        return ranked

    # --- Context Sensitivity (C176) ---

    def context_quality(
        self,
        edge: Edge,
    ) -> Dict[Optional[Edge], Tuple[float, float]]:
        """Compute trace quality of an edge conditioned on predecessor.

        Returns a dict mapping predecessor_edge → (quality, count):
            quality = (U − F) / (U + F + ε) for events from that predecessor
            count   = number of events from that predecessor

        Predecessor None means "first step in a run" (no prior edge).

        Uses the audit log, not the live traces (which aggregate across
        all predecessors). This is intentional: the conditioned view
        reveals what the aggregated view hides.
        """
        EPS = 1e-12
        # Collect events: predecessor → (U_count, F_count)
        contexts: Dict[Optional[Edge], List[float]] = {}
        for rec in self._log:
            if rec.edge != edge:
                continue
            pred = rec.predecessor
            if pred not in contexts:
                contexts[pred] = [0.0, 0.0]
            if rec.outcome == Outcome.SUCCESS:
                contexts[pred][0] += 1.0
            elif rec.outcome == Outcome.FAILURE:
                contexts[pred][1] += 1.0
            elif rec.outcome == Outcome.PARTIAL:
                contexts[pred][0] += 0.5
                contexts[pred][1] += 0.3

        result: Dict[Optional[Edge], Tuple[float, float]] = {}
        for pred, (u, f) in contexts.items():
            q = (u - f) / (u + f + EPS)
            result[pred] = (q, u + f)
        return result

    def context_sensitivity(
        self,
        edge: Edge,
    ) -> float:
        """Measure how much an edge's quality depends on predecessor context.

        Returns a value in [0, 2]:
            0.0 = quality is identical regardless of predecessor (context-free)
            2.0 = maximum divergence (q=+1 from one pred, q=-1 from another)

        Computed as max quality range across all observed predecessor contexts.
        Requires at least 2 distinct predecessors; returns 0.0 otherwise.

        This is E₀'s structural analog of causal sensitivity:
        high context_sensitivity means the edge's success depends on
        HOW you arrived, not just WHERE you are.
        """
        cq = self.context_quality(edge)
        if len(cq) < 2:
            return 0.0
        qualities = [q for q, count in cq.values() if count >= 1.0]
        if len(qualities) < 2:
            return 0.0
        return max(qualities) - min(qualities)
