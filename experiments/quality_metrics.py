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
# DIMENSION 3: DERIVATION COMPLETENESS
# ═══════════════════════════════════════════════════════════════════════

# Target concepts for the QM derivation steps
QM_STEP_TARGETS = {
    0: {  # Step 1: Complex-valued state spaces
        'target': 'complex-valued state spaces',
        'markers': [
            'complex', 'complex-valued', 'complex number',
            'imaginary', 'phase', 'ℂ', 'hilbert space',
            'amplitude', 'complex amplitude',
            'real and imaginary', 'two components',
            'rotation', 'phase factor', 'e^{i',
        ],
    },
    1: {  # Step 2: Superposition
        'target': 'superposition principle',
        'markers': [
            'superposition', 'linear combination',
            'α|ψ₁⟩ + β|ψ₂⟩', 'linear', 'linearity',
            'sum of states', 'combination of states',
            'admissible state', 'closure',
            'vector space', 'linear space',
        ],
    },
    2: {  # Step 3: Born rule
        'target': 'born rule',
        'markers': [
            'born rule', 'born', 'probability',
            'squared modulus', '|α|²', '|α_k|²',
            'probability amplitude', 'p(k)',
            'squared norm', 'modulus squared',
            'measurement probability',
        ],
    },
    3: {  # Step 4: Unitary evolution
        'target': 'unitary time evolution',
        'markers': [
            'unitary', 'unitary evolution', 'unitary operator',
            'u†u', 'u†u = i', 'unitarity',
            'norm preservation', 'norm-preserving',
            'probability conservation', 'total probability',
            'isometry', 'reversible evolution',
        ],
    },
}


def score_completeness(text, step_index):
    """
    Score whether the response actually addresses the derivation target.
    Returns dict with target, marker_hits, completeness score.
    """
    if step_index not in QM_STEP_TARGETS:
        return {'target': 'unknown', 'marker_hits': 0, 'completeness': 0.0}

    info = QM_STEP_TARGETS[step_index]
    normed = _normalize(text)
    hits = sum(1 for m in info['markers'] if m.lower() in normed)
    total = len(info['markers'])
    # Completeness: fraction of target markers found, capped at 1.0
    completeness = min(hits / max(total * 0.3, 1), 1.0)  # need ~30% of markers for full score

    return {
        'target': info['target'],
        'marker_hits': hits,
        'marker_total': total,
        'completeness': round(completeness, 4),
    }


def interpret_completeness(completeness):
    """Return a brief interpretation of derivation completeness."""
    if completeness > 0.8:
        return "Derivation reaches target"
    elif completeness > 0.4:
        return "Partial derivation"
    elif completeness > 0.1:
        return "Touches on target concept"
    else:
        return "Does not address target"
