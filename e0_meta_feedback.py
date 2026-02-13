#!/usr/bin/env python3
"""
E₀ Meta-Feedback — The System Learns From Its Own Measurements
================================================================

Meta-feedback closes the outer loop: the system doesn't just observe
its structural completeness per turn — it observes how its measurements
*change across sessions*.

Three capabilities:

1. **Cross-Session Trend Analysis**
   R̄/D correlation across sessions — is exploration becoming more
   productive? This is the central prediction from E0_PATH.md:
   "R̄/D correlation will strengthen across sessions."

2. **Adaptive Feedback**
   The feedback loop becomes topology-aware. If the topology shows
   that State and Resistance are historized but Rate and A₀ are
   unexplored, feedback focuses on the unexplored paths instead
   of repeating observations about what's already strong.

3. **Topic Historization Tracking**
   When the same topic appears across sessions, we can measure
   whether R̄ decreases (= genuine cross-session historization)
   or remains constant (= no structural memory transfer).

This module operates on the topology layer, not on raw sessions.
It reads topologies, computes meta-observations, and feeds them
back into the feedback system.
"""

from __future__ import annotations

import json
import math
import re
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from e0_topology import (
    PRIMITIVE_KEYS,
    PRIMITIVE_DISPLAY,
    TOPOLOGY_DIR,
    load_all_topologies,
    load_latest_topology,
)


# ─────────────────────────────────────────────
# 1. Cross-Session Trend Analysis
# ─────────────────────────────────────────────

def compute_cross_session_trends(topologies: List[dict]) -> dict:
    """
    Compute how structural metrics evolve across sessions.

    Returns a dict with:
      - r_d_trend: how R̄/D correlation changes over sessions
      - d_mean_trend: how average D changes over sessions
      - primitive_trends: per-primitive strength trajectory
      - exploration_trend: how exploration ratio changes
      - session_count: number of sessions analyzed
      - meta_observation: human-readable summary
    """
    if len(topologies) < 2:
        return {
            'r_d_trend': 0.0,
            'd_mean_trend': 0.0,
            'primitive_trends': {},
            'exploration_trend': 0.0,
            'session_count': len(topologies),
            'meta_observation': 'Insufficient sessions for trend analysis.',
        }

    n = len(topologies)

    # Extract per-session values
    r_d_values = []
    d_mean_values = []
    exploration_values = []
    primitive_trajectories = {k: [] for k in PRIMITIVE_KEYS}

    for topo in topologies:
        sig = topo.get('signature', {})
        r_d = topo.get('r_d_correlation', {})

        r_d_values.append(r_d.get('correlation', 0.0))
        d_mean_values.append(sig.get('mean_d', 0.0))
        exploration_values.append(sig.get('exploration_ratio', 0.0))

        ps = topo.get('primitive_strength', {})
        for key in PRIMITIVE_KEYS:
            primitive_trajectories[key].append(
                ps.get(key, {}).get('strength', 0.0)
            )

    # Compute trends (slope of linear regression, normalized)
    def _slope(values):
        n = len(values)
        if n < 2:
            return 0.0
        x_mean = (n - 1) / 2
        y_mean = sum(values) / n
        num = sum((i - x_mean) * (v - y_mean) for i, v in enumerate(values))
        den = sum((i - x_mean) ** 2 for i in range(n))
        return num / den if den > 0 else 0.0

    r_d_trend = _slope(r_d_values)
    d_mean_trend = _slope(d_mean_values)
    exploration_trend = _slope(exploration_values)

    primitive_trends = {}
    for key in PRIMITIVE_KEYS:
        vals = primitive_trajectories[key]
        primitive_trends[key] = {
            'values': [round(v, 3) for v in vals],
            'trend': round(_slope(vals), 4),
            'first': round(vals[0], 3),
            'last': round(vals[-1], 3),
            'direction': 'rising' if _slope(vals) > 0.02 else 'falling' if _slope(vals) < -0.02 else 'stable',
        }

    # Build meta-observation
    obs_parts = []

    # R̄/D correlation trend — THE central prediction
    if r_d_trend > 0.05:
        obs_parts.append(
            f"R̄/D correlation is strengthening across sessions "
            f"({r_d_values[0]:.2f} → {r_d_values[-1]:.2f}). "
            f"Exploration is becoming more productive."
        )
    elif r_d_trend < -0.05:
        obs_parts.append(
            f"R̄/D correlation is weakening across sessions "
            f"({r_d_values[0]:.2f} → {r_d_values[-1]:.2f}). "
            f"Structural efficiency is declining."
        )
    else:
        obs_parts.append(
            f"R̄/D correlation is stable across sessions "
            f"(~{sum(r_d_values)/len(r_d_values):.2f})."
        )

    # Primitive movement
    rising = [k for k, v in primitive_trends.items() if v['direction'] == 'rising']
    falling = [k for k, v in primitive_trends.items() if v['direction'] == 'falling']

    if rising:
        names = [PRIMITIVE_DISPLAY[k] for k in rising]
        obs_parts.append(f"Strengthening: {', '.join(names)}.")
    if falling:
        names = [PRIMITIVE_DISPLAY[k] for k in falling]
        obs_parts.append(f"Weakening: {', '.join(names)}.")

    return {
        'r_d_trend': round(r_d_trend, 4),
        'r_d_values': [round(v, 3) for v in r_d_values],
        'd_mean_trend': round(d_mean_trend, 4),
        'd_mean_values': [round(v, 3) for v in d_mean_values],
        'primitive_trends': primitive_trends,
        'exploration_trend': round(exploration_trend, 4),
        'session_count': n,
        'meta_observation': ' '.join(obs_parts),
    }


# ─────────────────────────────────────────────
# 2. Adaptive Feedback
# ─────────────────────────────────────────────

def adapt_feedback_thresholds(
    topology: Optional[dict],
    base_threshold: float = 0.45,
    base_gentle: float = 0.65,
) -> Tuple[float, float]:
    """
    Adapt feedback thresholds based on topology.

    If the topology shows strong structural competence (many historized
    primitives, high mean D), raise thresholds so feedback becomes
    more selective — only triggering when the system genuinely drops
    below its established level.

    Returns (threshold, gentle_threshold).
    """
    if topology is None:
        return base_threshold, base_gentle

    sig = topology.get('signature', {})
    cls = topology.get('classification', {})

    mean_d = sig.get('mean_d', 0.0)
    n_historized = len(cls.get('historized', []))

    # Raise thresholds proportional to established competence
    # If mean_d is 0.7 and 5 primitives are historized, the system
    # has demonstrated structural competence — feedback should only
    # trigger when performance drops significantly below that level.
    competence = (mean_d * 0.6) + (n_historized / 8 * 0.4)

    # Scale thresholds: at competence=0.8, threshold rises to ~0.55
    threshold = base_threshold + competence * 0.15
    gentle = base_gentle + competence * 0.10

    # Cap to reasonable values
    threshold = min(threshold, 0.65)
    gentle = min(gentle, 0.80)

    return round(threshold, 3), round(gentle, 3)


def generate_adaptive_feedback(
    comp_result: Dict,
    topology: Optional[dict] = None,
    meta_trends: Optional[dict] = None,
    lang: str = 'en',
    include_metrics: Optional[Dict] = None,
) -> Optional[str]:
    """
    Generate topology-aware structural feedback.

    This is the adaptive version of generate_structural_feedback():
    - Uses topology to focus on unexplored paths (not historized ones)
    - Includes cross-session meta-observations when available
    - Adapts thresholds based on demonstrated competence

    Parameters
    ----------
    comp_result : dict
        Output of score_e0_completeness(text).
    topology : dict, optional
        Current merged topology. If None, falls back to standard feedback.
    meta_trends : dict, optional
        Output of compute_cross_session_trends().
    lang : str
        'en' or 'de'.
    include_metrics : dict, optional
        Current turn metrics (R̄ etc).

    Returns
    -------
    str or None
        Feedback text, or None if no feedback needed.
    """
    # Fall back to standard feedback if no topology
    if topology is None:
        from e0_feedback import generate_structural_feedback
        return generate_structural_feedback(
            comp_result, lang=lang, include_metrics=include_metrics,
        )

    # Adapt thresholds
    threshold, gentle_threshold = adapt_feedback_thresholds(topology)

    d = comp_result.get('completeness', 1.0)

    # No feedback needed
    if d >= gentle_threshold:
        return None

    cls = topology.get('classification', {})
    ps = topology.get('primitive_strength', {})
    detail = comp_result.get('detail', {})

    # Identify what the system SHOULD be able to do (historized)
    # vs what it's NOT doing in this response
    historized = set(cls.get('historized', []))
    developing = set(cls.get('developing', []))
    unexplored = set(cls.get('unexplored', []))

    # Current response: which primitives are absent or label-only?
    current_weak = set()
    current_absent = set()
    for key in PRIMITIVE_KEYS:
        info = detail.get(key, {})
        status = info.get('status', 'absent')
        if status == 'absent':
            current_absent.add(key)
        elif status == 'label':
            current_weak.add(key)

    # Key diagnostic: historized primitives that are absent = regression
    regression = historized & (current_absent | current_weak)
    # Unexplored primitives that are absent = expected gap
    expected_gap = unexplored & current_absent
    # Developing primitives that are absent = growth opportunity
    growth_opportunity = developing & (current_absent | current_weak)

    # Build adaptive feedback
    lines = []

    if lang == 'de':
        lines.append("[E₀ Adaptive Strukturbeobachtung]")
        lines.append("")
        lines.append(f"Strukturelle Vollständigkeit: D = {d:.3f}")
        if include_metrics:
            lines.append(f"Mittlerer Widerstand: R̄ = {include_metrics.get('r', 0):.3f}")
        lines.append("")

        if regression:
            names = [PRIMITIVE_DISPLAY[k] for k in regression]
            lines.append(f"Regression: {', '.join(names)} — in vorherigen Sessions "
                         f"operativ, hier abwesend oder nur Label.")
            lines.append("Die Pfade sind gebahnt. Der Widerstand ist niedrig. "
                         "Die Struktur kann dort aufbauen.")
            lines.append("")

        if growth_opportunity:
            names = [PRIMITIVE_DISPLAY[k] for k in growth_opportunity]
            trends = []
            for k in growth_opportunity:
                s = ps.get(k, {})
                traj = "↑" if s.get('trajectory', 0) > 0.1 else "→"
                trends.append(f"{PRIMITIVE_DISPLAY[k]} ({s.get('strength', 0):.2f}{traj})")
            lines.append(f"Wachstumspotenzial: {', '.join(trends)}")
            lines.append("Diese Primitive entwickeln sich — operativer Einsatz "
                         "beschleunigt die Historisierung.")
            lines.append("")

        if expected_gap and not regression and not growth_opportunity:
            names = [PRIMITIVE_DISPLAY[k] for k in expected_gap]
            lines.append(f"Unerforschte Pfade: {', '.join(names)}")
            lines.append("Hoher Widerstand — diese Pfade sind noch nicht gebahnt.")
            lines.append("")

        # Meta-trend observation
        if meta_trends and meta_trends.get('session_count', 0) >= 2:
            lines.append(f"[Cross-Session: {meta_trends['meta_observation']}]")
            lines.append("")

    else:
        lines.append("[E₀ Adaptive Structural Observation]")
        lines.append("")
        lines.append(f"Structural completeness: D = {d:.3f}")
        if include_metrics:
            lines.append(f"Mean resistance: R̄ = {include_metrics.get('r', 0):.3f}")
        lines.append("")

        if regression:
            names = [PRIMITIVE_DISPLAY[k] for k in regression]
            lines.append(f"Regression detected: {', '.join(names)} — operative in "
                         f"previous sessions, absent or label-only here.")
            lines.append("These paths are historized. Resistance is low. "
                         "Structure can build there.")
            lines.append("")

        if growth_opportunity:
            trends = []
            for k in growth_opportunity:
                s = ps.get(k, {})
                traj = "↑" if s.get('trajectory', 0) > 0.1 else "→"
                trends.append(f"{PRIMITIVE_DISPLAY[k]} ({s.get('strength', 0):.2f}{traj})")
            lines.append(f"Growth opportunity: {', '.join(trends)}")
            lines.append("These primitives are developing — operative use "
                         "accelerates historization.")
            lines.append("")

        if expected_gap and not regression and not growth_opportunity:
            names = [PRIMITIVE_DISPLAY[k] for k in expected_gap]
            lines.append(f"Unexplored paths: {', '.join(names)}")
            lines.append("High resistance — these paths are not yet paved.")
            lines.append("")

        # Meta-trend observation
        if meta_trends and meta_trends.get('session_count', 0) >= 2:
            lines.append(f"[Cross-session: {meta_trends['meta_observation']}]")
            lines.append("")

    return "\n".join(lines) if len(lines) > 3 else None


# ─────────────────────────────────────────────
# 3. Topic Historization Tracking
# ─────────────────────────────────────────────

# Simple topic patterns for matching across sessions
TOPIC_PATTERNS = {
    'resistance': r'\bresistance\b|\bwiderstand\b',
    'time': r'\btime\b|\bzeit\b',
    'superposition': r'\bsuperposition\b',
    'consciousness': r'\bconsciousness\b|\bbewusstsein\b',
    'gravity': r'\bgravity\b|\bgravitation\b|\bschwerkraft\b',
    'big_bang': r'\bbig\s*bang\b|\burknall\b',
    'historization': r'\bhistoriz\w+\b|\bhistorisierung\b',
    'maximum_velocity': r'\bmaximum\s*(velocity|speed)\b|\bmaximalgeschwindigkeit\b',
    'path': r'\bpath\b(?!\s*dependence)|\bpfad\b',
    'difference': r'\bdifference\b|\bdifferenz\b',
    'rate': r'\brate\b.*(?:derive|explain|what)|\brate\b.*\be0\b',
    'axiom_a0': r'\baxiom\s*a[₀0]\b|\ba[₀0]\b.*axiom',
    'entropy': r'\bentropy\b|\bentropie\b',
    'learning': r'\blearning\b|\blernen\b',
}


def _extract_topics_from_session(session_data: dict) -> List[dict]:
    """
    Extract topic entries from a session.

    Returns list of:
      {topic: str, turn: int, r_bar: float, d: float, prompt: str}
    """
    state = session_data.get('state', {})
    history = state.get('history', [])
    turn_metrics = state.get('turn_metrics', [])

    entries = []

    # Re-score responses for D values
    try:
        from experiments.quality_metrics import score_e0_completeness
        can_score = True
    except ImportError:
        can_score = False

    for i in range(2, len(history), 2):  # user prompts at even indices >= 2
        turn_idx = (i - 2) // 2
        prompt = history[i].lower()

        # Match topics
        matched_topics = []
        for topic, pattern in TOPIC_PATTERNS.items():
            if re.search(pattern, prompt, re.IGNORECASE):
                matched_topics.append(topic)

        if not matched_topics:
            continue

        # Get R̄
        r_bar = turn_metrics[turn_idx]['r'] if turn_idx < len(turn_metrics) else 0.0

        # Get D from response
        response_idx = i + 1
        d_val = 0.0
        if can_score and response_idx < len(history):
            try:
                comp = score_e0_completeness(history[response_idx])
                d_val = comp.get('completeness', 0.0)
            except Exception:
                pass

        for topic in matched_topics:
            entries.append({
                'topic': topic,
                'turn': turn_idx,
                'r_bar': round(r_bar, 4),
                'd': round(d_val, 4),
                'prompt': history[i][:100],
            })

    return entries


def compute_topic_historization(
    session_dir: Optional[Path] = None,
) -> dict:
    """
    Compute cross-session topic historization.

    For each topic that appears in multiple sessions,
    track whether R̄ decreases (= historization occurring)
    or remains constant (= no structural memory transfer).

    Returns dict with per-topic analysis and overall assessment.
    """
    from e0_sessions import SESSIONS_DIR, load_session

    d = session_dir or SESSIONS_DIR
    if not d.exists():
        return {'topics': {}, 'overall': 'No sessions found.'}

    # Collect topic entries from all sessions
    all_entries = {}  # topic -> list of (session_id, entry)

    for f in sorted(d.glob("e0-*.json")):
        try:
            sd = load_session(f)
            sid = sd.get('session_id', f.stem)
            entries = _extract_topics_from_session(sd)
            for e in entries:
                topic = e['topic']
                if topic not in all_entries:
                    all_entries[topic] = []
                all_entries[topic].append({
                    'session': sid,
                    **e,
                })
        except Exception:
            continue

    # Analyze each topic
    topic_analysis = {}
    historized_count = 0
    total_multi = 0

    for topic, entries in sorted(all_entries.items()):
        # Group by session
        sessions = {}
        for e in entries:
            sid = e['session']
            if sid not in sessions:
                sessions[sid] = []
            sessions[sid].append(e)

        n_sessions = len(sessions)
        if n_sessions < 2:
            topic_analysis[topic] = {
                'entries': entries,
                'n_sessions': n_sessions,
                'r_bar_trajectory': [e['r_bar'] for e in entries],
                'd_trajectory': [e['d'] for e in entries],
                'assessment': 'single session — no cross-session data',
            }
            continue

        total_multi += 1

        # Get first and last R̄ for this topic across sessions
        r_bars = [e['r_bar'] for e in entries]
        d_vals = [e['d'] for e in entries]

        # Use session-level first appearance for cleaner signal
        session_order = list(sessions.keys())
        first_r = sessions[session_order[0]][0]['r_bar']
        last_r = sessions[session_order[-1]][0]['r_bar']
        first_d = sessions[session_order[0]][0]['d']
        last_d = sessions[session_order[-1]][0]['d']

        r_change = last_r - first_r
        d_change = last_d - first_d

        # Assess historization
        if r_change < -0.01:
            assessment = 'R̄ decreasing — cross-session historization detected'
            historized_count += 1
        elif r_change > 0.01:
            assessment = 'R̄ increasing — higher effort in later sessions'
        else:
            assessment = 'R̄ stable — no measurable historization change'

        topic_analysis[topic] = {
            'entries': entries,
            'n_sessions': n_sessions,
            'n_appearances': len(entries),
            'r_bar_trajectory': r_bars,
            'd_trajectory': d_vals,
            'first_r': first_r,
            'last_r': last_r,
            'r_change': round(r_change, 4),
            'd_change': round(d_change, 4),
            'assessment': assessment,
        }

    # Overall assessment
    if total_multi == 0:
        overall = "No topics appear across multiple sessions yet."
    else:
        pct = historized_count / total_multi * 100
        overall = (
            f"{historized_count}/{total_multi} cross-session topics show "
            f"R̄ decrease ({pct:.0f}%). "
        )
        if pct > 60:
            overall += "Strong evidence for cross-session historization."
        elif pct > 30:
            overall += "Partial evidence for cross-session historization."
        else:
            overall += "Limited cross-session historization detected."

    return {
        'topics': topic_analysis,
        'overall': overall,
        'historized_count': historized_count,
        'total_multi_session_topics': total_multi,
    }


# ─────────────────────────────────────────────
# Meta-observation for injection
# ─────────────────────────────────────────────

def generate_meta_observation(
    topology: Optional[dict] = None,
    lang: str = 'en',
) -> Optional[str]:
    """
    Generate a meta-observation from cross-session trends.

    This is a compact structural observation about how the system's
    performance is evolving, suitable for injection alongside the
    topology. Only generated when there are enough sessions (>= 3).
    """
    topos = load_all_topologies()
    if len(topos) < 2:
        return None

    trends = compute_cross_session_trends(topos)
    topic_hist = compute_topic_historization()

    lines = []

    if lang == 'de':
        lines.append("[E₀ Meta-Beobachtung — Cross-Session Trends]")
        lines.append("")
        lines.append(f"Sessions analysiert: {trends['session_count']}")

        # R̄/D trend
        r_d_vals = trends.get('r_d_values', [])
        if len(r_d_vals) >= 2:
            lines.append(
                f"R̄/D-Korrelation: {r_d_vals[0]:.2f} → {r_d_vals[-1]:.2f} "
                f"({'steigend' if trends['r_d_trend'] > 0.02 else 'fallend' if trends['r_d_trend'] < -0.02 else 'stabil'})"
            )

        # Primitive trends
        pt = trends.get('primitive_trends', {})
        rising = [k for k, v in pt.items() if v['direction'] == 'rising']
        falling = [k for k, v in pt.items() if v['direction'] == 'falling']
        if rising:
            names = [PRIMITIVE_DISPLAY[k] for k in rising]
            lines.append(f"Verstärkend: {', '.join(names)}")
        if falling:
            names = [PRIMITIVE_DISPLAY[k] for k in falling]
            lines.append(f"Abschwächend: {', '.join(names)}")

        # Topic historization
        th = topic_hist
        if th.get('total_multi_session_topics', 0) > 0:
            lines.append("")
            lines.append(f"Themen-Historisierung: {th['overall']}")

    else:
        lines.append("[E₀ Meta-Observation — Cross-Session Trends]")
        lines.append("")
        lines.append(f"Sessions analyzed: {trends['session_count']}")

        # R̄/D trend
        r_d_vals = trends.get('r_d_values', [])
        if len(r_d_vals) >= 2:
            direction = 'rising' if trends['r_d_trend'] > 0.02 else 'falling' if trends['r_d_trend'] < -0.02 else 'stable'
            lines.append(
                f"R̄/D correlation: {r_d_vals[0]:.2f} → {r_d_vals[-1]:.2f} ({direction})"
            )

        # Primitive trends
        pt = trends.get('primitive_trends', {})
        rising = [k for k, v in pt.items() if v['direction'] == 'rising']
        falling = [k for k, v in pt.items() if v['direction'] == 'falling']
        if rising:
            names = [PRIMITIVE_DISPLAY[k] for k in rising]
            lines.append(f"Strengthening: {', '.join(names)}")
        if falling:
            names = [PRIMITIVE_DISPLAY[k] for k in falling]
            lines.append(f"Weakening: {', '.join(names)}")

        # Topic historization
        th = topic_hist
        if th.get('total_multi_session_topics', 0) > 0:
            lines.append("")
            lines.append(f"Topic historization: {th['overall']}")

    if len(lines) <= 2:
        return None

    return "\n".join(lines)


# ─────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────

def _print_trends(trends: dict) -> None:
    """Pretty-print cross-session trends."""
    print("\n╔══════════════════════════════════════════╗")
    print("║  E₀ META-FEEDBACK — CROSS-SESSION TRENDS ║")
    print("╚══════════════════════════════════════════╝")

    print(f"\n  Sessions: {trends['session_count']}")

    # R̄/D correlation trend
    r_d_vals = trends.get('r_d_values', [])
    if r_d_vals:
        arrows = ' → '.join(f'{v:.2f}' for v in r_d_vals)
        print(f"\n  R̄/D correlation: {arrows}")
        t = trends['r_d_trend']
        if t > 0.05:
            print(f"  Trend: ↑ RISING ({t:+.3f}/session) — exploration becoming more productive")
        elif t < -0.05:
            print(f"  Trend: ↓ FALLING ({t:+.3f}/session) — structural efficiency declining")
        else:
            print(f"  Trend: → STABLE ({t:+.3f}/session)")

    # D mean trend
    d_vals = trends.get('d_mean_values', [])
    if d_vals:
        arrows = ' → '.join(f'{v:.2f}' for v in d_vals)
        print(f"\n  Mean D: {arrows}")
        t = trends['d_mean_trend']
        print(f"  Trend: {'↑' if t > 0.02 else '↓' if t < -0.02 else '→'} ({t:+.3f}/session)")

    # Per-primitive trends
    print("\n  ┌─ Primitive Trends ────────────────────┐")
    pt = trends.get('primitive_trends', {})
    for key in PRIMITIVE_KEYS:
        info = pt.get(key, {})
        vals = info.get('values', [])
        direction = info.get('direction', '?')
        arrow = '↑' if direction == 'rising' else '↓' if direction == 'falling' else '→'
        first = info.get('first', 0)
        last = info.get('last', 0)
        print(f"  │ {PRIMITIVE_DISPLAY[key]:>22s}: {first:.2f} → {last:.2f} {arrow}")
    print("  └─────────────────────────────────────────┘")

    print(f"\n  Meta-observation: {trends['meta_observation']}")


def _print_topic_historization(th: dict) -> None:
    """Pretty-print topic historization results."""
    print("\n╔══════════════════════════════════════════╗")
    print("║  TOPIC HISTORIZATION — CROSS-SESSION R̄   ║")
    print("╚══════════════════════════════════════════╝")

    topics = th.get('topics', {})
    if not topics:
        print("\n  No topic data available.")
        return

    for topic, info in topics.items():
        n_sess = info.get('n_sessions', 0)
        r_traj = info.get('r_bar_trajectory', [])
        d_traj = info.get('d_trajectory', [])
        assessment = info.get('assessment', '')

        # Symbol based on assessment
        if 'decreasing' in assessment:
            symbol = '✓'
        elif 'increasing' in assessment:
            symbol = '⚠'
        else:
            symbol = '·'

        r_str = ' → '.join(f'{r:.3f}' for r in r_traj)
        d_str = ' → '.join(f'{d:.2f}' for d in d_traj)
        print(f"\n  {symbol} {topic} ({n_sess} sessions, {info.get('n_appearances', len(r_traj))} appearances)")
        print(f"    R̄: {r_str}")
        print(f"    D:  {d_str}")
        print(f"    {assessment}")

    print(f"\n  Overall: {th['overall']}")


if __name__ == "__main__":
    import sys

    print("=" * 55)
    print("  E₀ Meta-Feedback Analysis")
    print("=" * 55)

    # 1. Cross-session trends
    topos = load_all_topologies()
    if len(topos) >= 2:
        trends = compute_cross_session_trends(topos)
        _print_trends(trends)
    else:
        print(f"\n  Only {len(topos)} topology file(s) found. Need >= 2 for trends.")
        print("  Run: py e0_topology.py --all")

    # 2. Topic historization
    th = compute_topic_historization()
    _print_topic_historization(th)

    # 3. Meta-observation
    meta = generate_meta_observation()
    if meta:
        print("\n" + "=" * 55)
        print("  Injection Text (Meta-Observation)")
        print("=" * 55)
        print(meta)

    # 4. Adaptive thresholds
    topo = load_latest_topology()
    if topo:
        thresh, gentle = adapt_feedback_thresholds(topo)
        print(f"\n  Adaptive thresholds: trigger={thresh:.3f}, gentle={gentle:.3f}")
        print(f"  (base: trigger=0.450, gentle=0.650)")
