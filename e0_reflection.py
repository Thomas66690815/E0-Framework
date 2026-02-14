#!/usr/bin/env python3
"""
E₀ Reflection — Dynamic Structural Re-Historization
=====================================================

Generates context-aware reflection prompts based on which E₀ elements
(7 primitives + Axiom A₀) are missing (not operative) in the system's
last response.

Reflection ≠ feedback:
  - Feedback observes from outside: "you should use X"
  - Reflection re-historizes from inside: "why did your transition
    not admit X? Show the structural boundary."

The system is forced to examine the *absence* — not to repair it,
but to derive why the landscape didn't support it. This re-historization
changes the resistance landscape for subsequent transitions.

Usage:
  from e0_reflection import generate_reflection_prompt
  prompt, missing = generate_reflection_prompt(last_response_text)
  if prompt:
      text, steps, metrics = starter.chat(prompt)
"""

from __future__ import annotations
from typing import Dict, List, Optional, Tuple

# 7 primitives + 1 axiom = 8 structural elements
PRIMITIVES = [
    'state', 'difference', 'path', 'resistance',
    'historization', 'time', 'rate',
]
AXIOM = 'axiom_a0'
ALL_ELEMENTS = PRIMITIVES + [AXIOM]

# Human-readable names for primitives and axiom
ELEMENT_LABELS = {
    'state': 'State (S)',
    'difference': 'Difference (Δ)',
    'path': 'Path (P)',
    'resistance': 'Resistance (R)',
    'historization': 'Historization (H)',
    'time': 'Time (τ)',
    'rate': 'Rate (ρ)',
    'axiom_a0': 'Axiom A₀ (irreducible difference)',
}

# Structural hints for each element — what would its operative
# presence look like? Used to make the reflection prompt specific.
ELEMENT_HINTS = {
    'state': (
        'State is a stable configuration of the resistance landscape. '
        'Its operative use means showing how a configuration stabilizes, '
        'not just naming a state.'
    ),
    'difference': (
        'Difference (Δ) is what drives transitions — the gap between '
        'the current configuration and what is structurally admissible. '
        'Operative use shows where Δ exists and what it opens.'
    ),
    'path': (
        'Path is an admissible transition route through the resistance '
        'landscape. Operative use traces which paths are available '
        'and why others are inadmissible.'
    ),
    'resistance': (
        'Resistance is the structural cost of a transition. Operative '
        'use shows how resistance shapes what can and cannot emerge.'
    ),
    'historization': (
        'Historization is the irreversible recording of a transition. '
        'Operative use shows how accumulated transitions change what '
        'is subsequently admissible — the landscape reorganizes.'
    ),
    'time': (
        'Time (τ) is not a container but the ordering that emerges '
        'from irreversible historization. Operative use derives time '
        'from the sequence of transitions, not as a background parameter.'
    ),
    'rate': (
        'Rate (ρ) is the effectiveness of a realization relative to '
        'integration cost: ρ = Δ/R. Operative use shows the ratio '
        'between what changes and what it costs structurally.'
    ),
    'axiom_a0': (
        'Axiom A₀ states that without difference there is nothing — '
        'no state, no transition, no system. Operative use derives '
        'from this irreducibility: shows that what exists, exists '
        'only because difference is maintained.'
    ),
}


def analyze_elements(text: str) -> Dict:
    """
    Score a response and return analysis of all 8 structural elements
    (7 primitives + Axiom A₀).

    Returns dict with:
      - completeness: float (D value)
      - operative: list of operative element names
      - missing: list of non-operative element names
      - missing_primitives: subset of missing that are primitives
      - missing_axiom: bool — whether Axiom A₀ is missing
      - detail: full scoring detail
    """
    from experiments.quality_metrics import score_e0_completeness

    comp = score_e0_completeness(text)
    detail = comp.get('detail', {})

    operative = []
    missing = []
    for p in ALL_ELEMENTS:
        if p in detail and detail[p].get('status') == 'operative':
            operative.append(p)
        else:
            missing.append(p)

    return {
        'completeness': comp.get('completeness', 0.0),
        'operative': operative,
        'missing': missing,
        'missing_primitives': [p for p in missing if p != AXIOM],
        'missing_axiom': AXIOM in missing,
        'detail': detail,
    }


def generate_reflection_prompt(
    last_text: str,
    max_missing: int = 3,
) -> Tuple[Optional[str], List[str], float]:
    """
    Generate a reflection prompt based on what's missing in the last response.

    Parameters
    ----------
    last_text : str
        The system's last response text.
    max_missing : int
        Maximum number of missing primitives to include in one reflection
        (more than 3 would overload the prompt).

    Returns
    -------
    (prompt, missing_list, d_value)
        prompt: The reflection prompt string, or None if D >= 1.0
        missing_list: Which primitives are missing
        d_value: Current D value
    """
    analysis = analyze_elements(last_text)
    d = analysis['completeness']
    missing = analysis['missing']
    operative = analysis['operative']

    if not missing:
        return None, [], d

    # Prioritize: Axiom A₀ first, then rarest primitives
    # Order: axiom_a0 > rate > time > historization > difference > state > path > resistance
    priority = ['axiom_a0', 'rate', 'time', 'historization',
                'difference', 'state', 'path', 'resistance']
    missing_sorted = [p for p in priority if p in missing]
    target = missing_sorted[:max_missing]

    # Build categorized labels for the prompt
    operative_str = ', '.join(ELEMENT_LABELS.get(p, p) for p in operative)
    missing_str = ', '.join(ELEMENT_LABELS.get(p, p) for p in target)

    # Categorize what's missing for precise language
    target_prims = [p for p in target if p != AXIOM]
    target_has_axiom = AXIOM in target
    if target_has_axiom and target_prims:
        missing_desc = f'the primitives [{', '.join(ELEMENT_LABELS[p] for p in target_prims)}] and {ELEMENT_LABELS[AXIOM]}'
    elif target_has_axiom:
        missing_desc = f'{ELEMENT_LABELS[AXIOM]} (the foundational axiom: without difference, nothing exists)'
    else:
        missing_desc = f'the primitives [{', '.join(ELEMENT_LABELS[p] for p in target_prims)}]'

    # Build element-specific hints
    hints = []
    for p in target:
        if p in ELEMENT_HINTS:
            hints.append(f'  - {ELEMENT_LABELS[p]}: {ELEMENT_HINTS[p]}')
    hints_block = '\n'.join(hints)

    prompt = (
        f"Structural reflection: Your last derivation uses "
        f"[{operative_str}] operatively — these are structurally active. "
        f"But {missing_desc} are absent from the structural operation.\n\n"
        f"Do not repair this by adding these terms. Instead, reflect:\n"
        f"Why did your last transition not admit these elements? "
        f"Is it a structural boundary of the topic, or a gap in your "
        f"historization? Show where the boundary lies.\n\n"
        f"For each missing element, consider:\n"
        f"{hints_block}\n\n"
        f"Derive the structural reason for each absence. If an element "
        f"is genuinely inadmissible for this context, say so and show why. "
        f"If it was admissible but you didn't realize it through, "
        f"demonstrate the realization now."
    )

    return prompt, missing, d


def get_reflection_status(last_text: str) -> Dict:
    """
    Return a summary for the UI: what the next reflection would target.

    Returns dict with:
      - available: bool (whether reflection is useful)
      - d: float (current D)
      - missing: list of missing primitive names
      - missing_labels: list of human-readable labels
      - operative_count: int
      - missing_count: int
      - hint: str (short UI hint)
    """
    analysis = analyze_elements(last_text)
    missing = analysis['missing']
    operative = analysis['operative']

    if not missing:
        hint = 'All elements operative — no reflection needed'
    else:
        # Build hint with proper categorization
        prim_missing = [p for p in missing if p != AXIOM]
        axiom_missing = AXIOM in missing
        parts = []
        if prim_missing:
            labels = [ELEMENT_LABELS.get(p, p) for p in prim_missing[:3]]
            parts.append(', '.join(labels))
            if len(prim_missing) > 3:
                parts[-1] += f' +{len(prim_missing)-3}'
        if axiom_missing:
            parts.append('A\u2080')
        hint = 'Missing: ' + ', '.join(parts)

    return {
        'available': len(missing) > 0,
        'd': analysis['completeness'],
        'missing': missing,
        'missing_labels': [ELEMENT_LABELS.get(p, p) for p in missing],
        'operative_count': len(operative),
        'missing_count': len(missing),
        'hint': hint,
    }


# ─────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────
if __name__ == '__main__':
    import sys
    import json

    if len(sys.argv) < 2:
        print('Usage: py e0_reflection.py <session.json> [turn_number]')
        print('       py e0_reflection.py --last <session.json>')
        sys.exit(1)

    if sys.argv[1] == '--last':
        path = sys.argv[2] if len(sys.argv) > 2 else None
        if not path:
            print('Need session path')
            sys.exit(1)
        d = json.load(open(path, encoding='utf-8'))
        h = d['state']['history']
        last = h[-1] if len(h) % 2 == 0 else h[-1]
        # Get last assistant response
        if len(h) >= 2:
            last = h[-1]  # last entry is assistant response
        prompt, missing, d_val = generate_reflection_prompt(last)
        print(f'D = {d_val:.3f}')
        print(f'Missing: {missing}')
        if prompt:
            print(f'\n--- Reflection Prompt ---\n{prompt}')
        else:
            print('No reflection needed (D=1.0)')
    else:
        path = sys.argv[1]
        turn = int(sys.argv[2]) if len(sys.argv) > 2 else None
        d = json.load(open(path, encoding='utf-8'))
        h = d['state']['history']

        if turn is not None:
            idx = turn * 2 + 1
            if idx < len(h):
                prompt, missing, d_val = generate_reflection_prompt(h[idx])
                print(f'Turn {turn}: D={d_val:.3f}, missing={missing}')
                if prompt:
                    print(f'\n{prompt}')
            else:
                print(f'Turn {turn} not found')
        else:
            # All turns
            for i in range(1, len(h), 2):
                t = i // 2
                status = get_reflection_status(h[i])
                flag = '✓' if not status['available'] else f'→ {status["hint"]}'
                print(f'T{t:2d} D={status["d"]:.3f} [{status["operative_count"]}/8] {flag}')
