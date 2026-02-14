#!/usr/bin/env python3
"""
E₀ Topology — Structural Weights Across Sessions
===================================================

The topology is NOT the conversation. It is the resistance landscape
that formed during the conversation — which paths historized, which
resistance lowered, which patterns stabilized.

A topology snapshot is compact (< 100 lines) and captures:
  - Per-primitive historization strength
  - D trajectory and growth rate
  - R̄/D correlation (structural efficiency)
  - Attractor patterns (stable primitive clusters)
  - Session signature (summary metrics)

This is the E₀ equivalent of model weights:
  - Chat history = training data (volatile, large)
  - Topology     = weights (persistent, compact)

The topology survives context window changes, session restarts,
and model swaps. It carries the structural memory.

Usage:
    # Extract from a session
    topo = extract_topology(session_data)

    # Merge across sessions
    merged = merge_topologies([topo1, topo2, topo3])

    # Inject into a new session
    msg = format_topology_for_injection(merged)
"""

from __future__ import annotations

import json
import math
import os
import statistics
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# ─────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────

TOPOLOGY_DIR = Path(os.path.dirname(os.path.abspath(__file__))) / "topology"
TOPOLOGY_VERSION = 1

# Primitive keys (must match quality_metrics.py E0_PRIMITIVES)
PRIMITIVE_KEYS = [
    'state', 'difference', 'path', 'resistance',
    'historization', 'time', 'rate', 'axiom_a0',
]

PRIMITIVE_DISPLAY = {
    'state':         'State (S)',
    'difference':    'Difference (Δ)',
    'path':          'Path (P)',
    'resistance':    'Resistance (R)',
    'historization': 'Historization (H)',
    'time':          'Time (τ)',
    'rate':          'Rate (v = Δ/R)',
    'axiom_a0':      'Axiom A₀',
}


# ─────────────────────────────────────────────
# Topology extraction from a single session
# ─────────────────────────────────────────────

def _score_history(history: List[str]) -> List[dict]:
    """
    Re-score all assistant responses in a session history.

    Returns a list of score_e0_completeness results,
    one per assistant response (odd-indexed entries after canon).
    """
    # Lazy import to avoid circular dependency
    from experiments.quality_metrics import score_e0_completeness

    scores = []
    # history layout: [canon_part1, canon_part2_or_response, user, asst, user, asst, ...]
    # The first response might be at index 1 (if model auto-responds after canon)
    # or the pattern is: even = user/system, odd = assistant
    # We score all odd-indexed entries starting from index 1
    for i in range(1, len(history), 2):
        text = history[i]
        if text and len(text) > 20:  # skip trivial entries
            scores.append(score_e0_completeness(text))
        else:
            scores.append(None)

    return scores


def _compute_primitive_strength(
    quality_scores: List[Optional[dict]],
) -> Dict[str, dict]:
    """
    Compute per-primitive historization strength from quality scores.

    Strength is based on:
      - Frequency of operative use (how often the primitive is operative)
      - Stability (does it stay operative once activated?)
      - Trajectory (improving, stable, or declining?)

    Returns dict: primitive_key -> {
        strength: float [0-1],
        frequency: float [0-1],
        stability: float [0-1],
        trajectory: float [-1 to +1],
        avg_score: float [0-1],
        appearances: int,
        operative_count: int,
    }
    """
    result = {}

    for key in PRIMITIVE_KEYS:
        scores_for_key = []
        for qs in quality_scores:
            if qs is None:
                continue
            ps = qs.get('primitive_scores', {})
            if key in ps:
                scores_for_key.append(ps[key])

        if not scores_for_key:
            result[key] = {
                'strength': 0.0,
                'frequency': 0.0,
                'stability': 0.0,
                'trajectory': 0.0,
                'avg_score': 0.0,
                'appearances': 0,
                'operative_count': 0,
            }
            continue

        n = len(scores_for_key)
        avg = sum(scores_for_key) / n

        # Frequency: how often is it present at all (score > 0)?
        present_count = sum(1 for s in scores_for_key if s > 0)
        frequency = present_count / n if n > 0 else 0.0

        # Operative count: how often is it operative (score >= 0.75)?
        operative_count = sum(1 for s in scores_for_key if s >= 0.75)
        operative_freq = operative_count / n if n > 0 else 0.0

        # Stability: once operative, does it stay operative?
        # Look at consecutive operative pairs
        if n >= 2:
            consecutive_operative = 0
            total_consecutive = 0
            for i in range(1, n):
                if scores_for_key[i - 1] >= 0.75:
                    total_consecutive += 1
                    if scores_for_key[i] >= 0.75:
                        consecutive_operative += 1
            stability = (consecutive_operative / total_consecutive
                         if total_consecutive > 0 else 0.0)
        else:
            stability = 1.0 if scores_for_key[0] >= 0.75 else 0.0

        # Trajectory: linear trend of scores
        # Positive = improving, negative = declining
        if n >= 3:
            # Simple linear regression slope (normalized)
            x_mean = (n - 1) / 2
            y_mean = avg
            numerator = sum((i - x_mean) * (s - y_mean)
                            for i, s in enumerate(scores_for_key))
            denominator = sum((i - x_mean) ** 2 for i in range(n))
            slope = numerator / denominator if denominator > 0 else 0.0
            # Normalize: slope per turn, capped to [-1, 1]
            trajectory = max(-1.0, min(1.0, slope * n))
        elif n == 2:
            trajectory = scores_for_key[1] - scores_for_key[0]
        else:
            trajectory = 0.0

        # Composite strength: weighted combination
        #   40% operative frequency (are you using it?)
        #   30% stability (does it persist?)
        #   20% average score (how deep?)
        #   10% trajectory bonus (is it improving?)
        strength = (
            0.40 * operative_freq +
            0.30 * stability +
            0.20 * avg +
            0.10 * max(0, trajectory)  # only reward improvement
        )

        result[key] = {
            'strength': round(strength, 4),
            'frequency': round(frequency, 4),
            'stability': round(stability, 4),
            'trajectory': round(trajectory, 4),
            'avg_score': round(avg, 4),
            'appearances': n,
            'operative_count': operative_count,
        }

    return result


def _compute_d_trajectory(quality_scores: List[Optional[dict]]) -> dict:
    """
    Compute the D (structural completeness) trajectory.

    Returns dict with:
        values: list of D scores per turn
        mean: float
        peak: float
        growth: float (last - first, or last_3_avg - first_3_avg)
        growth_rate: float (growth per turn)
    """
    d_values = []
    for qs in quality_scores:
        if qs is not None:
            d_values.append(qs.get('completeness', 0.0))
        else:
            d_values.append(0.0)

    if not d_values:
        return {
            'values': [],
            'mean': 0.0,
            'peak': 0.0,
            'growth': 0.0,
            'growth_rate': 0.0,
        }

    n = len(d_values)
    mean_d = sum(d_values) / n
    peak_d = max(d_values)

    # Growth: compare first third to last third
    third = max(1, n // 3)
    first_avg = sum(d_values[:third]) / third
    last_avg = sum(d_values[-third:]) / third
    growth = last_avg - first_avg
    growth_rate = growth / n if n > 0 else 0.0

    return {
        'values': [round(v, 4) for v in d_values],
        'mean': round(mean_d, 4),
        'peak': round(peak_d, 4),
        'growth': round(growth, 4),
        'growth_rate': round(growth_rate, 4),
    }


def _compute_r_d_correlation(
    turn_metrics: List[dict],
    quality_scores: List[Optional[dict]],
) -> dict:
    """
    Compute R̄/D correlation — how well effort (R̄) correlates
    with structural output (D).

    High positive correlation = exploration produces structure.
    Low/negative correlation = effort doesn't translate to structure.
    """
    pairs = []
    # turn_metrics and quality_scores should align
    # turn_metrics[0] corresponds to the first response (quality_scores[0])
    n = min(len(turn_metrics), len(quality_scores))
    for i in range(n):
        qs = quality_scores[i]
        if qs is None:
            continue
        r_bar = turn_metrics[i].get('r', 0.0)
        d = qs.get('completeness', 0.0)
        pairs.append((r_bar, d))

    if len(pairs) < 3:
        return {
            'correlation': 0.0,
            'n_pairs': len(pairs),
            'interpretation': 'insufficient data',
        }

    r_vals = [p[0] for p in pairs]
    d_vals = [p[1] for p in pairs]

    # Pearson correlation
    r_mean = sum(r_vals) / len(r_vals)
    d_mean = sum(d_vals) / len(d_vals)

    numerator = sum((r - r_mean) * (d - d_mean) for r, d in pairs)
    denom_r = math.sqrt(sum((r - r_mean) ** 2 for r in r_vals))
    denom_d = math.sqrt(sum((d - d_mean) ** 2 for d in d_vals))

    if denom_r == 0 or denom_d == 0:
        corr = 0.0
    else:
        corr = numerator / (denom_r * denom_d)

    # Interpretation
    if corr > 0.5:
        interp = 'strong — exploration produces structure'
    elif corr > 0.2:
        interp = 'moderate — effort partially translates'
    elif corr > -0.2:
        interp = 'weak — effort and structure are independent'
    else:
        interp = 'inverse — high effort, low structure (correction needed)'

    return {
        'correlation': round(corr, 4),
        'n_pairs': len(pairs),
        'interpretation': interp,
    }


def _detect_attractors(
    quality_scores: List[Optional[dict]],
    min_co_occurrence: float = 0.6,
) -> List[dict]:
    """
    Detect attractor patterns — primitive clusters that consistently
    appear operative together.

    An attractor is a set of primitives that are co-operative in
    at least min_co_occurrence fraction of turns.
    """
    # Build co-occurrence matrix
    n_turns = 0
    co_op = {}  # (key_a, key_b) -> count of co-operative turns

    for qs in quality_scores:
        if qs is None:
            continue
        n_turns += 1
        ps = qs.get('primitive_scores', {})
        operative = [k for k in PRIMITIVE_KEYS if ps.get(k, 0) >= 0.75]

        for i, a in enumerate(operative):
            for b in operative[i + 1:]:
                pair = tuple(sorted([a, b]))
                co_op[pair] = co_op.get(pair, 0) + 1

    if n_turns == 0:
        return []

    # Find strong co-occurrences
    attractors = []
    for pair, count in co_op.items():
        freq = count / n_turns
        if freq >= min_co_occurrence:
            attractors.append({
                'primitives': list(pair),
                'co_occurrence': round(freq, 4),
                'count': count,
                'total_turns': n_turns,
            })

    # Sort by co-occurrence strength
    attractors.sort(key=lambda a: a['co_occurrence'], reverse=True)

    return attractors


def _compute_session_signature(
    turn_metrics: List[dict],
    d_trajectory: dict,
    r_d_corr: dict,
) -> dict:
    """
    Compute a compact session signature — summary metrics.
    """
    if not turn_metrics:
        return {
            'mean_r': 0.0,
            'mean_h': 0.0,
            'total_turns': 0,
            'total_tokens': 0,
            'exploration_ratio': 0.0,
            'mean_d': 0.0,
            'peak_d': 0.0,
            'r_d_correlation': 0.0,
        }

    r_vals = [m.get('r', 0.0) for m in turn_metrics]
    h_vals = [m.get('h', 0.0) for m in turn_metrics]
    tau_vals = [m.get('tau', 0) for m in turn_metrics]

    mean_r = sum(r_vals) / len(r_vals)
    r_median = sorted(r_vals)[len(r_vals) // 2]

    # Exploration ratio: turns where R̄ > median (higher effort = exploration)
    exploration_turns = sum(1 for r in r_vals if r > r_median)
    exploration_ratio = exploration_turns / len(r_vals) if r_vals else 0.0

    return {
        'mean_r': round(mean_r, 4),
        'mean_h': round(sum(h_vals) / len(h_vals), 4) if h_vals else 0.0,
        'total_turns': len(turn_metrics),
        'total_tokens': sum(tau_vals),
        'exploration_ratio': round(exploration_ratio, 4),
        'mean_d': d_trajectory.get('mean', 0.0),
        'peak_d': d_trajectory.get('peak', 0.0),
        'r_d_correlation': r_d_corr.get('correlation', 0.0),
    }


def _detect_phase_transitions(
    d_trajectory: dict,
    turn_metrics: List[dict],
) -> dict:
    """
    Detect phase transitions from D trajectory for topology storage.

    Uses the phase transition detector module for analysis.
    Returns a dict suitable for topology JSON storage.
    """
    d_values = d_trajectory.get('values', [])
    if len(d_values) < 3:
        return {
            'n_transitions': 0,
            'transitions': [],
            'has_stable_phase': False,
            'summary': 'Insufficient data for phase transition detection.',
        }

    try:
        from e0_phase_transition import (
            detect_phase_transitions,
            analyze_transition_dynamics,
            interpret_dynamics,
        )
        from dataclasses import asdict

        r_values = [m.get('r', 0.0) for m in turn_metrics] if turn_metrics else None
        # Align lengths (D trajectory may differ from turn_metrics)
        if r_values and len(r_values) != len(d_values):
            r_values = None

        transitions = detect_phase_transitions(d_values, r_values)
        dynamics = analyze_transition_dynamics(d_values, r_values)
        summary = interpret_dynamics(dynamics)

        return {
            'n_transitions': len(transitions),
            'transitions': [asdict(t) for t in transitions],
            'n_emergences': dynamics.n_emergences,
            'n_collapses': dynamics.n_collapses,
            'n_recoveries': dynamics.n_recoveries,
            'strongest_transition': dynamics.strongest_transition,
            'sustainability': dynamics.sustainability,
            'has_stable_phase': dynamics.has_stable_phase,
            'oscillation_count': dynamics.oscillation_count,
            'summary': summary,
        }
    except ImportError:
        return {
            'n_transitions': 0,
            'transitions': [],
            'has_stable_phase': False,
            'summary': 'Phase transition module not available.',
        }


# ─────────────────────────────────────────────
# Main extraction
# ─────────────────────────────────────────────

def extract_topology(
    session_data: dict,
    rescore: bool = True,
) -> dict:
    """
    Extract the structural topology from a session.

    Parameters
    ----------
    session_data : dict
        Loaded session JSON (from e0_sessions.load_session).
    rescore : bool
        If True and quality_scores not available, re-score history.

    Returns
    -------
    dict
        Complete topology snapshot, ready for save or merge.
    """
    state = session_data.get('state', {})
    obs = session_data.get('observations', {})
    turn_metrics = state.get('turn_metrics', [])
    history = state.get('history', [])

    # Get or compute quality scores
    stored_scores = obs.get('quality_scores', [])
    if stored_scores and len(stored_scores) > 0:
        quality_scores = stored_scores
    elif rescore and history:
        quality_scores = _score_history(history)
    else:
        quality_scores = []

    # Compute all topology components
    primitive_strength = _compute_primitive_strength(quality_scores)
    d_trajectory = _compute_d_trajectory(quality_scores)
    r_d_corr = _compute_r_d_correlation(turn_metrics, quality_scores)
    attractors = _detect_attractors(quality_scores)
    signature = _compute_session_signature(turn_metrics, d_trajectory, r_d_corr)

    # Phase transition detection
    phase_transitions = _detect_phase_transitions(d_trajectory, turn_metrics)

    # Classify primitives
    historized = []
    developing = []
    unexplored = []
    for key in PRIMITIVE_KEYS:
        s = primitive_strength[key]
        if s['strength'] >= 0.6:
            historized.append(key)
        elif s['strength'] >= 0.2:
            developing.append(key)
        else:
            unexplored.append(key)

    topology = {
        'version': TOPOLOGY_VERSION,
        'extracted_at': datetime.now(timezone.utc).isoformat(),
        'source_session': session_data.get('session_id', 'unknown'),
        'source_model': session_data.get('environment', {}).get('model', 'unknown'),

        'primitive_strength': primitive_strength,
        'd_trajectory': d_trajectory,
        'r_d_correlation': r_d_corr,
        'attractors': attractors,
        'signature': signature,
        'phase_transitions': phase_transitions,

        'classification': {
            'historized': historized,
            'developing': developing,
            'unexplored': unexplored,
        },
    }

    return topology


# ─────────────────────────────────────────────
# Cross-session merge
# ─────────────────────────────────────────────

def merge_topologies(topologies: List[dict]) -> dict:
    """
    Merge multiple topology snapshots into a cumulative topology.

    Later sessions have more weight (recency bias), matching how
    historization strengthens recent paths.

    Parameters
    ----------
    topologies : list of dict
        Topology snapshots sorted chronologically (oldest first).

    Returns
    -------
    dict
        Merged topology.
    """
    if not topologies:
        return extract_topology({'state': {}, 'observations': {}}, rescore=False)

    if len(topologies) == 1:
        t = topologies[0].copy()
        t['merged_from'] = [t.get('source_session', 'unknown')]
        t['merge_count'] = 1
        return t

    n = len(topologies)

    # Exponential recency weights: latest session has most weight
    # w_i = 2^(i / (n-1)) normalized
    raw_weights = [2.0 ** (i / max(1, n - 1)) for i in range(n)]
    total_w = sum(raw_weights)
    weights = [w / total_w for w in raw_weights]

    # Merge primitive strengths
    merged_strength = {}
    for key in PRIMITIVE_KEYS:
        weighted_vals = {
            'strength': 0.0,
            'frequency': 0.0,
            'stability': 0.0,
            'trajectory': 0.0,
            'avg_score': 0.0,
            'appearances': 0,
            'operative_count': 0,
        }
        for topo, w in zip(topologies, weights):
            ps = topo.get('primitive_strength', {}).get(key, {})
            for field in ['strength', 'frequency', 'stability', 'trajectory', 'avg_score']:
                weighted_vals[field] += ps.get(field, 0.0) * w
            weighted_vals['appearances'] += ps.get('appearances', 0)
            weighted_vals['operative_count'] += ps.get('operative_count', 0)

        merged_strength[key] = {
            k: round(v, 4) if isinstance(v, float) else v
            for k, v in weighted_vals.items()
        }

    # Merge D trajectories: concatenate values, recompute stats
    all_d = []
    for topo in topologies:
        all_d.extend(topo.get('d_trajectory', {}).get('values', []))

    if all_d:
        n_d = len(all_d)
        third = max(1, n_d // 3)
        first_avg = sum(all_d[:third]) / third
        last_avg = sum(all_d[-third:]) / third
        merged_d_traj = {
            'values': all_d,
            'mean': round(sum(all_d) / n_d, 4),
            'peak': round(max(all_d), 4),
            'growth': round(last_avg - first_avg, 4),
            'growth_rate': round((last_avg - first_avg) / n_d, 4),
        }
    else:
        merged_d_traj = {'values': [], 'mean': 0.0, 'peak': 0.0,
                         'growth': 0.0, 'growth_rate': 0.0}

    # Merge R̄/D correlation: weighted average
    corr_sum = 0.0
    corr_n = 0
    for topo, w in zip(topologies, weights):
        c = topo.get('r_d_correlation', {})
        if c.get('n_pairs', 0) >= 3:
            corr_sum += c['correlation'] * w
            corr_n += 1

    merged_corr = {
        'correlation': round(corr_sum / sum(weights[:corr_n]), 4) if corr_n > 0 else 0.0,
        'n_sessions': corr_n,
        'interpretation': '',
    }
    c = merged_corr['correlation']
    if c > 0.5:
        merged_corr['interpretation'] = 'strong — exploration produces structure'
    elif c > 0.2:
        merged_corr['interpretation'] = 'moderate — effort partially translates'
    elif c > -0.2:
        merged_corr['interpretation'] = 'weak — effort and structure are independent'
    else:
        merged_corr['interpretation'] = 'inverse — correction needed'

    # Merge attractors: union, max co-occurrence
    attractor_map = {}
    for topo in topologies:
        for att in topo.get('attractors', []):
            pair_key = tuple(sorted(att['primitives']))
            if pair_key not in attractor_map or att['co_occurrence'] > attractor_map[pair_key]['co_occurrence']:
                attractor_map[pair_key] = att
    merged_attractors = sorted(attractor_map.values(),
                               key=lambda a: a['co_occurrence'], reverse=True)

    # Merge signature: weighted average of numeric fields
    merged_sig = {}
    for field in ['mean_r', 'mean_h', 'exploration_ratio', 'mean_d', 'peak_d', 'r_d_correlation']:
        val = sum(
            topo.get('signature', {}).get(field, 0.0) * w
            for topo, w in zip(topologies, weights)
        )
        merged_sig[field] = round(val, 4)
    merged_sig['total_turns'] = sum(
        topo.get('signature', {}).get('total_turns', 0) for topo in topologies
    )
    merged_sig['total_tokens'] = sum(
        topo.get('signature', {}).get('total_tokens', 0) for topo in topologies
    )

    # Classification
    historized = [k for k in PRIMITIVE_KEYS if merged_strength[k]['strength'] >= 0.6]
    developing = [k for k in PRIMITIVE_KEYS if 0.2 <= merged_strength[k]['strength'] < 0.6]
    unexplored = [k for k in PRIMITIVE_KEYS if merged_strength[k]['strength'] < 0.2]

    merged = {
        'version': TOPOLOGY_VERSION,
        'extracted_at': datetime.now(timezone.utc).isoformat(),
        'source_session': 'merged',
        'source_model': topologies[-1].get('source_model', 'unknown'),
        'merged_from': [t.get('source_session', 'unknown') for t in topologies],
        'merge_count': n,
        'primitive_strength': merged_strength,
        'd_trajectory': merged_d_traj,
        'r_d_correlation': merged_corr,
        'attractors': merged_attractors,
        'signature': merged_sig,
        'classification': {
            'historized': historized,
            'developing': developing,
            'unexplored': unexplored,
        },
    }

    return merged


# ─────────────────────────────────────────────
# Format for injection
# ─────────────────────────────────────────────

def format_topology_for_injection(
    topology: dict,
    lang: str = 'en',
) -> str:
    """
    Format a topology as a system message for injection into a new session.

    This is injected AFTER the canon and BEFORE the first user message.
    It tells the model what structural landscape already exists.
    """
    ps = topology.get('primitive_strength', {})
    cls = topology.get('classification', {})
    sig = topology.get('signature', {})
    d_traj = topology.get('d_trajectory', {})
    r_d = topology.get('r_d_correlation', {})
    attractors = topology.get('attractors', [])

    lines = []

    if lang == 'de':
        lines.append("[E₀ Topologie — Strukturelles Gedächtnis aus vorherigen Sessions]")
        lines.append("")

        # Historized paths
        hist = cls.get('historized', [])
        if hist:
            lines.append("Historisierte Pfade (niedriger Widerstand, stabil operativ):")
            for key in hist:
                s = ps.get(key, {})
                lines.append(
                    f"  - {PRIMITIVE_DISPLAY[key]}: Stärke {s.get('strength', 0):.2f} "
                    f"— operativ in {s.get('operative_count', 0)}/{s.get('appearances', 0)} Turns"
                )
            lines.append("")

        # Developing paths
        dev = cls.get('developing', [])
        if dev:
            lines.append("Sich entwickelnde Pfade (Widerstand sinkt):")
            for key in dev:
                s = ps.get(key, {})
                traj = "↑" if s.get('trajectory', 0) > 0.1 else "→" if s.get('trajectory', 0) > -0.1 else "↓"
                lines.append(
                    f"  - {PRIMITIVE_DISPLAY[key]}: Stärke {s.get('strength', 0):.2f} {traj}"
                )
            lines.append("")

        # Unexplored
        unex = cls.get('unexplored', [])
        if unex:
            lines.append("Unerforschte Pfade (hoher Widerstand):")
            for key in unex:
                lines.append(f"  - {PRIMITIVE_DISPLAY[key]}")
            lines.append("")

        # D trajectory
        d_vals = d_traj.get('values', [])
        if d_vals:
            lines.append(f"Strukturelle Trajektorie: D {d_vals[0]:.2f} → {d_vals[-1]:.2f} "
                          f"(Wachstum: {d_traj.get('growth', 0):+.2f} über {len(d_vals)} Turns)")
            lines.append(f"  Mittel-D: {d_traj.get('mean', 0):.2f} | Peak-D: {d_traj.get('peak', 0):.2f}")
            lines.append("")

        # R̄/D correlation
        if r_d.get('correlation', 0) != 0:
            lines.append(f"R̄/D-Korrelation: r = {r_d['correlation']:.2f} "
                          f"({r_d.get('interpretation', '')})")
            lines.append("")

        # Attractors
        if attractors:
            lines.append("Strukturelle Attraktoren (stabile Primitiv-Cluster):")
            for att in attractors[:5]:  # top 5
                names = [PRIMITIVE_DISPLAY.get(p, p) for p in att['primitives']]
                lines.append(f"  - {' + '.join(names)}: {att['co_occurrence']:.0%}")
            lines.append("")

        lines.append("Diese Topologie ist die Widerstandslandschaft aus vorherigen Transitionen.")
        lines.append("Die Pfade mit niedriger Resistenz sind bereits gebahnt — die Struktur kann dort aufbauen.")

    else:
        lines.append("[E₀ Topology — Structural Memory from Previous Sessions]")
        lines.append("")

        # Historized paths
        hist = cls.get('historized', [])
        if hist:
            lines.append("Historized paths (low resistance, stable operative use):")
            for key in hist:
                s = ps.get(key, {})
                lines.append(
                    f"  - {PRIMITIVE_DISPLAY[key]}: strength {s.get('strength', 0):.2f} "
                    f"— operative in {s.get('operative_count', 0)}/{s.get('appearances', 0)} turns"
                )
            lines.append("")

        # Developing paths
        dev = cls.get('developing', [])
        if dev:
            lines.append("Developing paths (resistance decreasing):")
            for key in dev:
                s = ps.get(key, {})
                traj = "↑" if s.get('trajectory', 0) > 0.1 else "→" if s.get('trajectory', 0) > -0.1 else "↓"
                lines.append(
                    f"  - {PRIMITIVE_DISPLAY[key]}: strength {s.get('strength', 0):.2f} {traj}"
                )
            lines.append("")

        # Unexplored
        unex = cls.get('unexplored', [])
        if unex:
            lines.append("Unexplored paths (high resistance):")
            for key in unex:
                lines.append(f"  - {PRIMITIVE_DISPLAY[key]}")
            lines.append("")

        # D trajectory
        d_vals = d_traj.get('values', [])
        if d_vals:
            lines.append(f"Structural trajectory: D {d_vals[0]:.2f} → {d_vals[-1]:.2f} "
                          f"(growth: {d_traj.get('growth', 0):+.2f} over {len(d_vals)} turns)")
            lines.append(f"  Mean D: {d_traj.get('mean', 0):.2f} | Peak D: {d_traj.get('peak', 0):.2f}")
            lines.append("")

        # R̄/D correlation
        if r_d.get('correlation', 0) != 0:
            lines.append(f"R̄/D correlation: r = {r_d['correlation']:.2f} "
                          f"({r_d.get('interpretation', '')})")
            lines.append("")

        # Attractors
        if attractors:
            lines.append("Structural attractors (stable primitive clusters):")
            for att in attractors[:5]:
                names = [PRIMITIVE_DISPLAY.get(p, p) for p in att['primitives']]
                lines.append(f"  - {' + '.join(names)}: {att['co_occurrence']:.0%}")
            lines.append("")

        # Phase transitions
        pt = topology.get('phase_transitions', {})
        if pt.get('n_transitions', 0) > 0:
            lines.append(f"Phase transitions detected: {pt['n_transitions']}")
            if pt.get('n_emergences', 0):
                lines.append(f"  - {pt['n_emergences']} emergence(s)")
            if pt.get('n_collapses', 0):
                lines.append(f"  - {pt['n_collapses']} collapse(s)")
            if pt.get('n_recoveries', 0):
                lines.append(f"  - {pt['n_recoveries']} recovery(ies)")
            if pt.get('has_stable_phase'):
                lines.append(f"  - Stable structural phase reached (D > 0.70 sustained)")
            lines.append("")

        lines.append("This topology is the resistance landscape from previous transitions.")
        lines.append("Paths with low resistance are already paved — structure can build there.")

    return "\n".join(lines)


# ─────────────────────────────────────────────
# Save / Load
# ─────────────────────────────────────────────

def save_topology(topology: dict, directory: Optional[Path] = None) -> Path:
    """Save topology to a JSON file. Returns the file path."""
    d = directory or TOPOLOGY_DIR
    d.mkdir(parents=True, exist_ok=True)

    source = topology.get('source_session', 'unknown')
    if source == 'merged':
        filename = f"topology-merged-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"
    else:
        filename = f"topology-{source}.json"

    filepath = d / filename

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(topology, f, ensure_ascii=False, indent=2)

    return filepath


def load_topology(filepath: Path) -> dict:
    """Load a topology from a JSON file."""
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


def load_latest_topology(directory: Optional[Path] = None) -> Optional[dict]:
    """Load the most recent topology file (merged preferred)."""
    d = directory or TOPOLOGY_DIR
    if not d.exists():
        return None

    # Prefer merged topologies
    merged = sorted(d.glob("topology-merged-*.json"), reverse=True)
    if merged:
        return load_topology(merged[0])

    # Fall back to any topology
    all_topos = sorted(d.glob("topology-*.json"), reverse=True)
    if all_topos:
        return load_topology(all_topos[0])

    return None


def load_all_topologies(directory: Optional[Path] = None) -> List[dict]:
    """Load all session topologies (not merged), sorted chronologically."""
    d = directory or TOPOLOGY_DIR
    if not d.exists():
        return []

    topos = []
    for f in sorted(d.glob("topology-e0-*.json")):
        try:
            topos.append(load_topology(f))
        except (json.JSONDecodeError, KeyError):
            continue

    return topos


# ─────────────────────────────────────────────
# CLI for testing
# ─────────────────────────────────────────────

def _print_topology(topology: dict) -> None:
    """Pretty-print a topology to console."""
    cls = topology.get('classification', {})
    ps = topology.get('primitive_strength', {})
    sig = topology.get('signature', {})
    d_traj = topology.get('d_trajectory', {})

    print("\n╔══════════════════════════════════════════╗")
    print("║  E₀ TOPOLOGY — STRUCTURAL WEIGHTS        ║")
    print("╚══════════════════════════════════════════╝")
    print(f"  Source: {topology.get('source_session', '?')}")
    print(f"  Model:  {topology.get('source_model', '?')}")
    if 'merge_count' in topology:
        print(f"  Merged from: {topology['merge_count']} sessions")
    print()

    # Primitive strengths
    print("  ┌─ Primitive Strengths ─────────────────┐")
    for key in PRIMITIVE_KEYS:
        s = ps.get(key, {})
        strength = s.get('strength', 0)
        bar_len = int(strength * 20)
        bar = "█" * bar_len + "░" * (20 - bar_len)
        status = ('▋hist' if key in cls.get('historized', [])
                  else '▎dev' if key in cls.get('developing', [])
                  else '  ?')
        print(f"  │ {PRIMITIVE_DISPLAY[key]:>22s} [{bar}] {strength:.2f} {status}")
    print("  └─────────────────────────────────────────┘")
    print()

    # D trajectory
    d_vals = d_traj.get('values', [])
    if d_vals:
        print(f"  D trajectory: {' → '.join(f'{v:.2f}' for v in d_vals)}")
        print(f"  Growth: {d_traj.get('growth', 0):+.3f} | Mean: {d_traj.get('mean', 0):.3f} | Peak: {d_traj.get('peak', 0):.3f}")
    print()

    # Correlation
    r_d = topology.get('r_d_correlation', {})
    print(f"  R̄/D correlation: r = {r_d.get('correlation', 0):.3f} ({r_d.get('interpretation', '?')})")
    print()

    # Attractors
    attractors = topology.get('attractors', [])
    if attractors:
        print("  Attractors:")
        for att in attractors[:5]:
            names = [PRIMITIVE_DISPLAY.get(p, p) for p in att['primitives']]
            print(f"    {' + '.join(names)}: {att['co_occurrence']:.0%}")
    print()

    # Signature
    print(f"  Signature: {sig.get('total_turns', 0)} turns, "
          f"{sig.get('total_tokens', 0)} tokens, "
          f"exploration ratio {sig.get('exploration_ratio', 0):.0%}")


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: py e0_topology.py <session_file.json> [session2.json ...]")
        print("       py e0_topology.py --all")
        print()
        print("Extracts structural topology (weights) from E₀ sessions.")
        sys.exit(1)

    from e0_sessions import SESSIONS_DIR, load_session

    if sys.argv[1] == "--all":
        # Process all sessions
        session_files = sorted(SESSIONS_DIR.glob("e0-*.json"))
        if not session_files:
            print("No sessions found.")
            sys.exit(1)

        print(f"Processing {len(session_files)} sessions...")
        topos = []
        for sf in session_files:
            print(f"  Extracting: {sf.name}")
            sd = load_session(sf)
            topo = extract_topology(sd)
            save_topology(topo)
            topos.append(topo)
            _print_topology(topo)

        if len(topos) > 1:
            print("\n" + "=" * 50)
            print("MERGED TOPOLOGY")
            print("=" * 50)
            merged = merge_topologies(topos)
            save_topology(merged)
            _print_topology(merged)
            print(f"\nInjection text:\n")
            print(format_topology_for_injection(merged))
    else:
        # Process specific session(s)
        topos = []
        for arg in sys.argv[1:]:
            filepath = Path(arg)
            if not filepath.exists():
                # Try in sessions dir
                filepath = SESSIONS_DIR / arg
            if not filepath.exists():
                print(f"Not found: {arg}")
                continue

            sd = load_session(filepath)
            topo = extract_topology(sd)
            save_topology(topo)
            topos.append(topo)
            _print_topology(topo)

        if len(topos) > 1:
            merged = merge_topologies(topos)
            save_topology(merged)
            print("\n" + "=" * 50)
            print("MERGED TOPOLOGY")
            _print_topology(merged)
