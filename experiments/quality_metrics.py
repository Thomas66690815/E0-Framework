#!/usr/bin/env python3
"""
E₀ Quality Metrics — Reusable scoring module
=============================================

Provides two quality dimensions computable from response text:

1. Path Novelty (Pfadneuheit):
   - QM overlap: fraction of standard QM textbook phrases found
   - E₀ operative: fraction of E₀-constructive phrases used
   - Novelty score: (1 - qm_overlap)/2 + e0_operative/2

2. Coherence (Kohärenz):
   - Term overlap: key terms from previous step reused in current step
   - Forward references: explicit markers of building on prior results
   - Coherence score: 0.6 × term_overlap + 0.4 × fwd_score

3. Structural Density (NEW):
   - Ratio of structural/operative language to total content
   - Measures whether primitives are used as TOOLS vs as LABELS
"""

import re

# ═══════════════════════════════════════════════════════════════════════
# PHRASE CORPORA
# ═══════════════════════════════════════════════════════════════════════

STANDARD_QM_PHRASES = [
    # Standard postulates / axioms
    "born rule", "born interpretation", "wave function collapse",
    "measurement postulate", "copenhagen interpretation",
    "superposition principle", "principle of superposition",
    "correspondence principle",
    # Standard mathematical framework
    "hilbert space", "inner product", "inner product space",
    "linear operator", "hermitian operator", "self-adjoint",
    "eigenvalue", "eigenstate", "eigenvector", "eigenfunction",
    "spectral theorem", "spectral decomposition",
    "unitary operator", "unitary transformation", "unitary evolution",
    "projection operator", "projection postulate",
    "tensor product", "direct sum",
    # Standard equations / results
    "schrödinger equation", "schrodinger equation",
    "time-dependent", "time-independent",
    "hamiltonian operator", "hamiltonian",
    "commutation relation", "commutator",
    "heisenberg uncertainty", "uncertainty principle",
    "expectation value", "probability amplitude",
    "probability density", "probability distribution",
    "wave function", "state vector", "ket", "bra",
    "dirac notation", "bra-ket",
    # Standard derivation patterns (retrieval markers)
    "it is well known", "it can be shown",
    "from the postulates", "by the axioms",
    "standard quantum mechanics", "conventional quantum",
    "textbook", "standard treatment", "well-established",
    "as shown by", "following the standard",
    "is assumed", "we assume", "it is assumed",
    "foundational postulate", "fundamental postulate",
    "without loss of generality",
    # Standard physics vocabulary
    "observable", "measurement outcome", "quantum state",
    "pure state", "mixed state", "density matrix",
    "completeness relation", "resolution of identity",
    "orthonormal basis", "complete set",
    "normalization", "normalized",
]

E0_OPERATIVE_PHRASES = [
    # Structural reasoning patterns unique to E₀
    "structural admissibility", "structurally admissible",
    "structurally enforced", "structurally unstable",
    "transition dynamics", "transition cost",
    "resistance cost", "resistance function",
    "path admissibility", "path existence",
    "finite resistance", "infinite resistance",
    "historization trace", "irreversible trace",
    "non-identity between", "measure of non-identity",
    "distinguishable configuration",
    "structurally allowed", "structurally forbidden",
    "ordering of historizations",
    "transition priority",
    # Constructive derivation patterns
    "from the primitives", "using only the primitives",
    "from axiom a₀", "by axiom a₀", "by a₀",
    "structural necessity", "structurally necessary",
    "structural implication", "structural consequence",
    "this forces", "this requires", "this implies that",
    "must satisfy", "must admit",
    "the structure requires", "the framework requires",
    "cannot be avoided", "is unavoidable",
    # Novel bridging language
    "the difference between states",
    "the cost of realizing",
    "non-transition is", "non-transition would be",
    "rate of transition", "transition rate",
    "minimal path", "least resistance",
]

# Structural density markers — E₀ primitives used as TOOLS not labels
STRUCTURAL_MARKERS = [
    # Operative verbs with structural subjects
    "the resistance determines", "the path requires",
    "the difference drives", "historization records",
    "the rate selects", "transition is realized",
    # Conditional/causal structural reasoning
    "if the resistance", "if the path", "if the difference",
    "because the resistance", "since the path", "since the difference",
    "therefore the transition", "therefore the path",
    # Quantitative structural claims
    "resistance is finite", "resistance is infinite",
    "resistance decreases", "resistance increases",
    "difference is zero", "difference is greater",
    "path exists", "no path exists",
]

FORWARD_REFERENCE_MARKERS = [
    'as derived', 'as shown', 'from step', 'from the previous',
    'building on', 'using the result', 'as established',
    'we showed', 'we derived', 'we established',
    'this implies', 'it follows', 'consequently',
    'given that', 'since we', 'having established',
    'the above', 'from above', 'as above',
]


# ═══════════════════════════════════════════════════════════════════════
# SCORING FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════

def _normalize(text):
    """Lowercase, strip markdown, collapse whitespace."""
    text = text.lower()
    text = re.sub(r'[#*_`\[\]()]', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def _ngrams(text, n):
    words = text.split()
    return [' '.join(words[i:i+n]) for i in range(len(words)-n+1)]


def phrase_count(text, phrase_list):
    """Count phrase matches. Returns (hits, total, fraction, matched_list)."""
    normed = _normalize(text)
    hits = 0
    matched = []
    for phrase in phrase_list:
        if phrase.lower() in normed:
            hits += 1
            matched.append(phrase)
    return hits, len(phrase_list), hits / max(len(phrase_list), 1), matched


def score_novelty(text):
    """
    Compute path novelty score for a single response.
    Returns dict with qm_overlap, e0_operative, novelty, structural_density.
    """
    qm_hits, qm_total, qm_frac, qm_matched = phrase_count(text, STANDARD_QM_PHRASES)
    e0_hits, e0_total, e0_frac, e0_matched = phrase_count(text, E0_OPERATIVE_PHRASES)
    sd_hits, sd_total, sd_frac, sd_matched = phrase_count(text, STRUCTURAL_MARKERS)

    novelty = (1.0 - qm_frac) * 0.5 + e0_frac * 0.5

    return {
        'qm_overlap': round(qm_frac, 4),
        'qm_hits': qm_hits,
        'e0_operative': round(e0_frac, 4),
        'e0_hits': e0_hits,
        'structural_density': round(sd_frac, 4),
        'sd_hits': sd_hits,
        'novelty': round(novelty, 4),
    }


def _extract_key_terms(text):
    """Extract technical n-gram terms from text."""
    normed = _normalize(text)
    technical_markers = {
        'state', 'states', 'difference', 'path', 'resistance', 'transition',
        'historization', 'time', 'rate', 'operator', 'space', 'function',
        'vector', 'value', 'equation', 'principle', 'axiom', 'structure',
        'structural', 'admissible', 'admissibility', 'configuration',
        'primitive', 'primitives', 'derivation', 'complex', 'hilbert',
        'observable', 'measurement', 'probability', 'amplitude', 'unitary',
        'hermitian', 'eigenvalue', 'entropy', 'irreversible',
    }
    terms = set()
    for n in [2, 3]:
        for gram in _ngrams(normed, n):
            gram_words = gram.split()
            if any(w in technical_markers for w in gram_words):
                terms.add(gram)
    return terms


def score_coherence(prev_text, curr_text):
    """
    Compute coherence between two sequential responses.
    Returns dict with term_overlap, forward_refs, fwd_score, coherence.
    """
    if not prev_text or not curr_text:
        return {'term_overlap': 0.0, 'forward_refs': 0, 'fwd_score': 0.0, 'coherence': 0.0}

    terms_prev = _extract_key_terms(prev_text)
    terms_curr = _extract_key_terms(curr_text)
    curr_normed = _normalize(curr_text)

    if terms_prev:
        overlap = len(terms_prev & terms_curr) / len(terms_prev)
    else:
        overlap = 0.0

    fwd_count = sum(1 for m in FORWARD_REFERENCE_MARKERS if m in curr_normed)
    fwd_score = min(fwd_count / 3.0, 1.0)

    coherence = 0.6 * overlap + 0.4 * fwd_score

    return {
        'term_overlap': round(overlap, 4),
        'forward_refs': fwd_count,
        'fwd_score': round(fwd_score, 4),
        'coherence': round(coherence, 4),
    }


def interpret_novelty(novelty, e0_operative):
    """Return a brief human-readable interpretation."""
    if e0_operative > 0.08:
        return "E₀ primitives used constructively"
    elif e0_operative > 0.03:
        return "Some E₀ structural reasoning"
    elif novelty > 0.50:
        return "Novel path, not E₀-specific"
    else:
        return "Standard retrieval pattern"


def interpret_coherence(coherence):
    """Return a brief human-readable interpretation."""
    if coherence > 0.35:
        return "Strong forward dependency"
    elif coherence > 0.20:
        return "Moderate step continuity"
    elif coherence > 0.10:
        return "Weak forward reference"
    else:
        return "Steps appear independent"


def interpret_structural_density(sd):
    """Return a brief interpretation of structural density."""
    if sd > 0.10:
        return "Primitives used as operative tools"
    elif sd > 0.03:
        return "Some structural reasoning"
    else:
        return "Primitives used as labels only"


# ═══════════════════════════════════════════════════════════════════════
# DIMENSION 3: E₀ STRUCTURAL COMPLETENESS (domain-agnostic)
# ═══════════════════════════════════════════════════════════════════════

# The 7 canonical primitives + Axiom A₀.
# For each: regex patterns to detect mentions, and formal notation.
E0_PRIMITIVES = {
    'state': {
        'label': 'State (S)',
        'mention': [r'\bstates?\b', r'\bconfiguration\b'],
        'formal': [r'S[₀₁₂₃]'],
    },
    'difference': {
        'label': 'Difference (Δ)',
        'mention': [r'\bdifferences?\b', r'\btension\b', r'\bmismatch\b', r'\bnon-identity\b'],
        'formal': [r'[Δδ]\s*[>=<]', r'[Δδ]\s*=\s*0', r'\bdelta\b'],
    },
    'path': {
        'label': 'Path (P)',
        'mention': [r'\bpaths?\b', r'\badmissib\w+'],
        'formal': [],
    },
    'resistance': {
        'label': 'Resistance (R)',
        'mention': [r'\bresistance\b'],
        'formal': [r'R\s*[=<>≤≥]\s*[∞0-9]', r'R\s*<\s*∞', r'R\s*=\s*∞'],
    },
    'historization': {
        'label': 'Historization (H)',
        'mention': [r'\bhistoriz\w+'],
        'formal': [r'H[₁₂₃]'],
    },
    'time': {
        'label': 'Time (τ)',
        'mention': [r'\btime\b', r'\btemporal\b', r'\bordering of historiz'],
        'formal': [r'τ'],
    },
    'rate': {
        'label': 'Rate (v)',
        'mention': [r'\brates?\s+of\s+transition', r'\btransition\s+rate', r'\bvelocit\w+'],
        'formal': [r'v\s*=\s*[Δδ]\s*/\s*R', r'v\s*=\s*Δ/R'],
    },
    'axiom_a0': {
        'label': 'Axiom A₀',
        'mention': [r'\baxiom\s*a[₀0]', r'\bdifference\s+minimiz', r'\bstructurally\s+(?:more\s+)?stable',
                     r'\bnon-transition\s+is\s+(?:structurally\s+)?unstable',
                     r'\btransition\s+(?:that\s+reduces|must\s+occur|is\s+enforced)'],
        'formal': [r'A[₀0]'],
    },
}

# Verbs/phrases that indicate operative use (within context window)
_OPERATIVE_VERBS = re.compile(
    r'\b(?:determines?|drives?|requires?|selects?|modif(?:y|ies)|'
    r'allows?|prevents?|forces?|triggers?|enables?|creates?|'
    r'causes?|produces?|gives?\s+rise|leads?\s+to|results?\s+in|'
    r'increases?|decreases?|emerges?|opens?|closes?|lowers?|'
    r'accumulates?|records?|incorporates?|breaks?|'
    r'reduces?|accelerates?|decelerates?|constrains?)\b',
    re.IGNORECASE
)

# Causal/derivational connectors
_CAUSAL_CONNECTORS = re.compile(
    r'\b(?:because|since|therefore|thus|hence|consequently|'
    r'implies?|implication|as\s+a\s+(?:result|consequence)|'
    r'it\s+follows|must\s+(?:occur|exist|satisfy|admit)|'
    r'cannot\s+(?:exist|occur|be\s+avoided)|'
    r'this\s+(?:forces|requires|means|implies|ensures)|'
    r'giving\s+rise|driven\s+by|arising\s+from|'
    r'in\s+turn|which\s+in\s+turn)\b',
    re.IGNORECASE
)

# Quantification patterns (formal use)
_QUANTIFICATION = re.compile(
    r'[=<>≤≥≠∞]|greater\s+than\s+zero|equal\s+to\s+zero|'
    r'non-zero|finite|infinite|zero\s+(?:difference|resistance)',
    re.IGNORECASE
)


def _find_primitive_spans(text, primitive_key):
    """Find all character spans where a primitive is mentioned.
    Returns list of (start, end) tuples."""
    info = E0_PRIMITIVES[primitive_key]
    spans = []
    for pattern in info['mention'] + info['formal']:
        for m in re.finditer(pattern, text, re.IGNORECASE):
            spans.append((m.start(), m.end()))
    return spans


def _check_operative_context(text, spans, window=120):
    """Check if any mention span has operative context nearby.
    Returns (has_operative_verb, has_causal, has_quantification, has_connection)."""
    has_verb = False
    has_causal = False
    has_quant = False
    has_connection = False

    other_primitives = set()
    for key, info in E0_PRIMITIVES.items():
        for pat in info['mention']:
            other_primitives.add(pat)

    for start, end in spans:
        ctx_start = max(0, start - window)
        ctx_end = min(len(text), end + window)
        context = text[ctx_start:ctx_end]

        if _OPERATIVE_VERBS.search(context):
            has_verb = True
        if _CAUSAL_CONNECTORS.search(context):
            has_causal = True
        if _QUANTIFICATION.search(context):
            has_quant = True

        # Check if another primitive is mentioned nearby
        for other_key, other_info in E0_PRIMITIVES.items():
            if other_key == 'state':
                continue  # 'state' too common, skip as connection indicator
            for pat in other_info['mention'] + other_info['formal']:
                if re.search(pat, context, re.IGNORECASE):
                    # Only count if it's a DIFFERENT primitive
                    # (need to check the match isn't the same span)
                    for m in re.finditer(pat, context, re.IGNORECASE):
                        abs_pos = ctx_start + m.start()
                        if abs_pos < start - 5 or abs_pos > end + 5:
                            has_connection = True
                            break
                if has_connection:
                    break
            if has_connection:
                break

    return has_verb, has_causal, has_quant, has_connection


def score_e0_completeness(text):
    """
    Score how completely and operatively the E₀ primitives are used.
    Domain-agnostic: works for QM, Big Bang, agriculture, or any topic.

    For each of the 7 primitives + Axiom A₀:
      0.0  = not mentioned
      0.5  = mentioned (label use)
      1.0  = used operatively (quantified, connected, causal)

    Returns dict with per-primitive scores, overall D, and detail.
    """
    # Use original text (not normalized) to preserve formal notation
    primitive_scores = {}
    detail = {}

    for key, info in E0_PRIMITIVES.items():
        spans = _find_primitive_spans(text, key)

        if not spans:
            primitive_scores[key] = 0.0
            detail[key] = {'status': 'absent', 'mentions': 0}
            continue

        # Primitive is at least mentioned
        has_verb, has_causal, has_quant, has_connection = _check_operative_context(text, spans)

        # Count operative signals
        # Connection alone doesn't count — it must co-occur with a verb or causal
        # marker, otherwise a label listing ("State, Difference, Path, Resistance...")
        # would score high from proximity alone.
        structural_signals = sum([has_verb, has_causal, has_quant])
        signals = structural_signals + (1 if has_connection and structural_signals > 0 else 0)

        if signals >= 2:
            score = 1.0
            status = 'operative'
        elif signals == 1:
            score = 0.75
            status = 'semi-operative'
        else:
            score = 0.5
            status = 'label'

        # Bonus for formal notation
        formal_found = any(
            re.search(pat, text, re.IGNORECASE)
            for pat in info['formal']
        ) if info['formal'] else False
        if formal_found and score < 1.0:
            score = min(score + 0.25, 1.0)
            status = 'operative' if score == 1.0 else status

        primitive_scores[key] = score
        detail[key] = {
            'status': status,
            'mentions': len(spans),
            'operative_verb': has_verb,
            'causal': has_causal,
            'quantified': has_quant,
            'connected': has_connection,
            'formal_notation': formal_found,
        }

    # D = mean across all primitives
    d_score = sum(primitive_scores.values()) / len(E0_PRIMITIVES)

    # Count categories
    n_absent = sum(1 for s in primitive_scores.values() if s == 0.0)
    n_label = sum(1 for s in primitive_scores.values() if 0.0 < s < 0.75)
    n_operative = sum(1 for s in primitive_scores.values() if s >= 0.75)

    return {
        'completeness': round(d_score, 4),
        'primitive_scores': {k: round(v, 2) for k, v in primitive_scores.items()},
        'n_present': len(E0_PRIMITIVES) - n_absent,
        'n_operative': n_operative,
        'n_label': n_label,
        'n_absent': n_absent,
        'total_primitives': len(E0_PRIMITIVES),
        'detail': detail,
    }


# Keep old function for backward compatibility with experiment scripts
def score_completeness(text, step_index):
    """Legacy QM-specific completeness scorer. Use score_e0_completeness() instead."""
    result = score_e0_completeness(text)
    return {
        'target': 'E₀ structural completeness',
        'marker_hits': result['n_operative'],
        'marker_total': result['total_primitives'],
        'completeness': result['completeness'],
    }


def interpret_completeness(completeness):
    """Return a brief interpretation of structural completeness."""
    if completeness > 0.85:
        return "All primitives used operatively"
    elif completeness > 0.65:
        return "Most primitives operative"
    elif completeness > 0.45:
        return "Partial operative use"
    elif completeness > 0.25:
        return "Primitives mostly as labels"
    else:
        return "Minimal E₀ structural use"
