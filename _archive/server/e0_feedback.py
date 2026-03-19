#!/usr/bin/env python3
"""
E₀ Structural Feedback Loop
=============================

Closes the observation gap: after each model response, the system
scores structural completeness and — when below threshold — injects
a *structural observation* into the conversation.

This is NOT instruction. The model is not told "use more primitives."
Instead it receives a factual observation about the structural landscape
of its last response.  The E₀ framework then predicts: a system that
sees where Δ > 0 (structural gaps) will realize transitions toward
those gaps — because non-transition under observed difference is
structurally unstable (Axiom A₀).

The feedback is:
  - Transparent:  visible to the user in the web UI
  - Structural:   observation, not instruction
  - Minimal:      only injected when D < threshold
  - Bilingual:    EN / DE

Integration points:
  - E0APIStarter.chat()  → inject before next turn
  - _handle_chat()       → generate + store + display
  - Web UI               → show as observation block
"""

from __future__ import annotations
from typing import Dict, Optional

# ─────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────

DEFAULT_THRESHOLD = 0.45     # D below this triggers feedback
GENTLE_THRESHOLD  = 0.65     # D below this adds a lighter observation
MAX_ABSENT_SILENT = 3        # if ≤ this many absent, note is gentler

# Primitive display names (for human-readable output)
PRIMITIVE_NAMES = {
    'en': {
        'state':         'State (S)',
        'difference':    'Difference (Δ)',
        'path':          'Path (P)',
        'resistance':    'Resistance (R)',
        'historization': 'Historization (H)',
        'time':          'Time (τ)',
        'rate':          'Rate (ρ = Δ/R)',
        'axiom_a0':      'Axiom A₀',
    },
    'de': {
        'state':         'Zustand (S)',
        'difference':    'Differenz (Δ)',
        'path':          'Pfad (P)',
        'resistance':    'Widerstand (R)',
        'historization': 'Historisierung (H)',
        'time':          'Zeit (τ)',
        'rate':          'Rate (ρ = Δ/R)',
        'axiom_a0':      'Axiom A₀',
    }
}

# ─────────────────────────────────────────────
# Feedback text templates
# ─────────────────────────────────────────────

_TEMPLATES = {
    'en': {
        'header': (
            "[E₀ Structural Observation — Previous Response]"
        ),
        'completeness_line': (
            "Structural completeness: D = {d:.3f}"
        ),
        'operative': "operative",
        'semi_op':   "semi-operative",
        'label':     "label only",
        'absent':    "absent",
        'present_section': "Primitives present:",
        'absent_section':  "Primitives absent:",
        'nudge_strong': (
            "The derivation can deepen by engaging the absent primitives "
            "as constructive constraints — not as labels, but as structural "
            "elements that select, limit, or produce the phenomenon."
        ),
        'nudge_gentle': (
            "Several primitives appear as labels rather than operative "
            "elements. The structure becomes visible when primitives constrain "
            "or produce, not merely name."
        ),
        'nudge_rate': (
            "Note: Rate ρ = Δ/R connects difference and resistance into "
            "transition dynamics — it is the bridge from statics to process."
        ),
        'nudge_axiom': (
            "Note: Axiom A₀ (if Δ > 0 and R < ∞, non-transition is "
            "structurally unstable) is the derivational engine — the reason "
            "anything must happen at all."
        ),
    },
    'de': {
        'header': (
            "[E₀ Strukturbeobachtung — Vorherige Antwort]"
        ),
        'completeness_line': (
            "Strukturelle Vollständigkeit: D = {d:.3f}"
        ),
        'operative': "operativ",
        'semi_op':   "semi-operativ",
        'label':     "nur Label",
        'absent':    "abwesend",
        'present_section': "Anwesende Primitive:",
        'absent_section':  "Abwesende Primitive:",
        'nudge_strong': (
            "Die Ableitung kann sich vertiefen, indem die abwesenden Primitive "
            "als konstruktive Bedingungen eingesetzt werden — nicht als "
            "Bezeichnungen, sondern als strukturelle Elemente, die das "
            "Phänomen selektieren, begrenzen oder hervorbringen."
        ),
        'nudge_gentle': (
            "Mehrere Primitive erscheinen als Labels statt als operative "
            "Elemente. Die Struktur wird sichtbar, wenn Primitive einschränken "
            "oder hervorbringen, nicht nur benennen."
        ),
        'nudge_rate': (
            "Hinweis: Rate ρ = Δ/R verbindet Differenz und Widerstand zu "
            "Transitionsdynamik — die Brücke von Statik zu Prozess."
        ),
        'nudge_axiom': (
            "Hinweis: Axiom A₀ (wenn Δ > 0 und R < ∞, ist Nicht-Transition "
            "strukturell instabil) ist der Ableitungsmotor — der Grund, "
            "warum überhaupt etwas geschehen muss."
        ),
    }
}


def generate_structural_feedback(
    comp_result: Dict,
    lang: str = 'en',
    threshold: float = DEFAULT_THRESHOLD,
    gentle_threshold: float = GENTLE_THRESHOLD,
    include_metrics: Optional[Dict] = None,
) -> Optional[str]:
    """
    Generate structural feedback from a completeness scoring result.

    Parameters
    ----------
    comp_result : dict
        Output of score_e0_completeness(text).
    lang : str
        'en' or 'de'.
    threshold : float
        D below this triggers full feedback.
    gentle_threshold : float
        D below this triggers gentle feedback (above threshold).
    include_metrics : dict, optional
        If given, R̄ and other metrics are included in the observation.

    Returns
    -------
    str or None
        Feedback text to inject, or None if D >= gentle_threshold.
    """
    d = comp_result.get('completeness', 1.0)

    # No feedback needed — structural use is strong
    if d >= gentle_threshold:
        return None

    lang_key = lang if lang in _TEMPLATES else 'en'
    t = _TEMPLATES[lang_key]
    names = PRIMITIVE_NAMES[lang_key]
    detail = comp_result.get('detail', {})

    lines = [t['header'], ""]

    # Completeness score
    lines.append(t['completeness_line'].format(d=d))

    # Include R̄ if provided
    if include_metrics:
        r_bar = include_metrics.get('r', 0)
        lines.append(f"Mean resistance: R̄ = {r_bar:.3f}")
    lines.append("")

    # Categorize primitives
    operative = []
    semi_op = []
    label_only = []
    absent = []

    for key in ['state', 'difference', 'path', 'resistance',
                'historization', 'time', 'rate', 'axiom_a0']:
        info = detail.get(key, {})
        status = info.get('status', 'absent')
        name = names.get(key, key)

        if status == 'operative':
            operative.append(name)
        elif status == 'semi-operative':
            semi_op.append(name)
        elif status == 'label':
            label_only.append(name)
        else:
            absent.append(name)

    # Present primitives (operative + semi-op + label)
    present_parts = []
    if operative:
        present_parts.extend(f"  {n} — {t['operative']}" for n in operative)
    if semi_op:
        present_parts.extend(f"  {n} — {t['semi_op']}" for n in semi_op)
    if label_only:
        present_parts.extend(f"  {n} — {t['label']}" for n in label_only)

    if present_parts:
        lines.append(t['present_section'])
        lines.extend(present_parts)
        lines.append("")

    # Absent primitives
    if absent:
        lines.append(t['absent_section'])
        lines.extend(f"  {n}" for n in absent)
        lines.append("")

    # Structural nudge — the key part
    if d < threshold:
        # Strong feedback: many primitives absent or just labels
        lines.append(t['nudge_strong'])

        # Specific nudges for commonly missed high-value primitives
        absent_keys = [k for k, v in detail.items() if v.get('status') == 'absent']
        if 'rate' in absent_keys:
            lines.append("")
            lines.append(t['nudge_rate'])
        if 'axiom_a0' in absent_keys:
            lines.append("")
            lines.append(t['nudge_axiom'])
    else:
        # Gentle feedback: structure is partially there
        lines.append(t['nudge_gentle'])

    return "\n".join(lines)


def format_feedback_for_injection(feedback_text: str) -> str:
    """
    Wrap feedback text for injection as a system message.
    Adds structural framing so the model treats it as observation, not instruction.
    """
    return (
        f"{feedback_text}\n\n"
        "This observation is structural, not prescriptive. "
        "Continue the derivation where the structure leads."
    )


def format_feedback_for_display(feedback_text: str, lang: str = 'en') -> Dict:
    """
    Format feedback for web UI display.

    Returns a dict with:
      - text: the raw feedback text
      - html: HTML-formatted version for the web UI
      - level: 'strong' | 'gentle' | None
    """
    if not feedback_text:
        return {'text': '', 'html': '', 'level': None}

    # Determine level from content
    t = _TEMPLATES.get(lang, _TEMPLATES['en'])
    if t['nudge_strong'][:30] in feedback_text:
        level = 'strong'
    else:
        level = 'gentle'

    # Build HTML
    html_lines = []
    for line in feedback_text.split('\n'):
        if not line.strip():
            continue
        if line.startswith('[E₀') or line.startswith('[E0'):
            html_lines.append(f'<div class="fb-header">{_esc(line)}</div>')
        elif line.startswith('Structural completeness') or line.startswith('Strukturelle Vollständigkeit'):
            html_lines.append(f'<div class="fb-metric">{_esc(line)}</div>')
        elif line.startswith('Mean resistance') or line.startswith('Mittlerer Widerstand'):
            html_lines.append(f'<div class="fb-metric">{_esc(line)}</div>')
        elif line.startswith(t['present_section']) or line.startswith(t['absent_section']):
            html_lines.append(f'<div class="fb-section">{_esc(line)}</div>')
        elif line.startswith('  '):
            # Primitive list item
            parts = line.strip().split(' — ')
            if len(parts) == 2:
                name, status = parts
                css_class = {
                    t['operative']: 'fb-operative',
                    t['semi_op']:   'fb-semi',
                    t['label']:     'fb-label',
                }.get(status, 'fb-absent')
                html_lines.append(
                    f'<div class="fb-primitive {css_class}">'
                    f'<span class="fb-name">{_esc(name)}</span>'
                    f'<span class="fb-status">{_esc(status)}</span></div>'
                )
            else:
                # Absent primitive (no status suffix)
                html_lines.append(
                    f'<div class="fb-primitive fb-absent">'
                    f'<span class="fb-name">{_esc(line.strip())}</span></div>'
                )
        else:
            html_lines.append(f'<div class="fb-nudge">{_esc(line)}</div>')

    return {
        'text': feedback_text,
        'html': '\n'.join(html_lines),
        'level': level,
    }


def _esc(text: str) -> str:
    """Minimal HTML escaping."""
    return (text
            .replace('&', '&amp;')
            .replace('<', '&lt;')
            .replace('>', '&gt;')
            .replace('"', '&quot;'))
