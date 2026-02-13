#!/usr/bin/env python3
"""
Quality Scorer — Path Novelty + Coherence Analysis
====================================================

Measures two quality dimensions that R̄ alone cannot capture:

1. PATH NOVELTY (Pfadneuheit): Does the response create derivation paths
   that deviate from standard textbook QM presentation?
   - Measured by: n-gram overlap with a reference corpus of standard QM phrases
   - Lower overlap → higher novelty

2. COHERENCE (Kohärenz): Does Step N+1 operatively use results from Step N?
   - Measured by: concept/term tracking across sequential steps
   - Forward references and dependency chains

Usage:
    py experiments/quality_scorer.py
    py experiments/quality_scorer.py --condition e0
    py experiments/quality_scorer.py --run 0 --verbose
"""

import json
import glob
import re
import argparse
import os
from collections import Counter

# ─────────────────────────────────────────────────────────────────────────
# REFERENCE CORPUS: Standard QM textbook phrases
# These are phrases you'd find in any standard QM derivation (Griffiths,
# Sakurai, etc.). High overlap with these = retrieval, low overlap = novel.
# ─────────────────────────────────────────────────────────────────────────

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
    # Standard derivation patterns
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

# E₀ OPERATIVE phrases — terms used constructively (not just mentioned)
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

# ─────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────

def normalize(text):
    """Lowercase, strip markdown, collapse whitespace."""
    text = text.lower()
    text = re.sub(r'[#*_`\[\]()]', ' ', text)  # strip markdown
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def ngrams(text, n):
    """Generate word n-grams from text."""
    words = text.split()
    return [' '.join(words[i:i+n]) for i in range(len(words)-n+1)]

def phrase_overlap(text, phrase_list):
    """
    Count how many standard phrases appear in text.
    Returns (count, total_phrases, fraction).
    """
    normed = normalize(text)
    hits = 0
    matched = []
    for phrase in phrase_list:
        if phrase.lower() in normed:
            hits += 1
            matched.append(phrase)
    return hits, len(phrase_list), hits / len(phrase_list), matched

def bigram_novelty(text, reference_texts):
    """
    Measure bigram novelty: fraction of bigrams in text NOT found in any reference.
    Higher = more novel.
    """
    normed = normalize(text)
    text_bigrams = set(ngrams(normed, 2))
    if not text_bigrams:
        return 0.0

    ref_bigrams = set()
    for ref in reference_texts:
        ref_bigrams.update(ngrams(normalize(ref), 2))

    novel = text_bigrams - ref_bigrams
    return len(novel) / len(text_bigrams)

def extract_key_terms(text):
    """
    Extract key technical terms from a response.
    Returns set of multi-word terms (2-3 word phrases that appear technical).
    """
    normed = normalize(text)
    words = normed.split()
    terms = set()

    # Extract 2-3 word phrases containing technical-looking words
    technical_markers = {
        'state', 'states', 'difference', 'path', 'resistance', 'transition',
        'historization', 'time', 'rate', 'operator', 'space', 'function',
        'vector', 'value', 'equation', 'principle', 'axiom', 'structure',
        'structural', 'admissible', 'admissibility', 'configuration',
        'primitive', 'primitives', 'derivation', 'complex', 'hilbert',
        'observable', 'measurement', 'probability', 'amplitude', 'unitary',
        'hermitian', 'eigenvalue', 'entropy', 'irreversible',
    }

    for n in [2, 3]:
        for gram in ngrams(normed, n):
            gram_words = gram.split()
            if any(w in technical_markers for w in gram_words):
                terms.add(gram)

    return terms

def step_coherence(responses):
    """
    Measure coherence across sequential steps.
    For each step pair (i, i+1), compute:
    - term_overlap: fraction of key terms from step i that appear in step i+1
    - forward_reference: does step i+1 explicitly reference earlier results?

    Returns per-pair scores and overall coherence score.
    """
    if len(responses) < 2:
        return {'overall': 0.0, 'pairs': []}

    pairs = []
    for i in range(len(responses) - 1):
        terms_i = extract_key_terms(responses[i])
        terms_i1 = extract_key_terms(responses[i+1])
        text_i1 = normalize(responses[i+1])

        # How many terms from step i appear in step i+1?
        if terms_i:
            overlap = len(terms_i & terms_i1) / len(terms_i)
        else:
            overlap = 0.0

        # Forward reference detection
        forward_markers = [
            'as derived', 'as shown', 'from step', 'from the previous',
            'building on', 'using the result', 'as established',
            'we showed', 'we derived', 'we established',
            'this implies', 'it follows', 'consequently',
            'given that', 'since we', 'having established',
            'the above', 'from above', 'as above',
        ]
        fwd_count = sum(1 for m in forward_markers if m in text_i1)
        fwd_score = min(fwd_count / 3.0, 1.0)  # cap at 1.0

        pair_score = 0.6 * overlap + 0.4 * fwd_score
        pairs.append({
            'step_pair': f'{i}→{i+1}',
            'term_overlap': overlap,
            'forward_refs': fwd_count,
            'fwd_score': fwd_score,
            'coherence': pair_score,
        })

    overall = sum(p['coherence'] for p in pairs) / len(pairs)
    return {'overall': overall, 'pairs': pairs}


# ─────────────────────────────────────────────────────────────────────────
# MAIN ANALYSIS
# ─────────────────────────────────────────────────────────────────────────

def load_experiment(condition_dir):
    """Load the experiment JSON with the most runs from a condition directory."""
    jsons = glob.glob(os.path.join(condition_dir, 'experiment_*.json'))
    if not jsons:
        return None
    # Pick the one with most runs
    best = None
    best_n = 0
    for j in jsons:
        with open(j) as f:
            d = json.load(f)
        n = len(d.get('runs', []))
        if n > best_n:
            best_n = n
            best = d
    return best

def analyze_condition(name, data, verbose=False, run_filter=None):
    """Analyze all runs in a condition."""
    runs = data['runs']
    if run_filter is not None:
        runs = [r for r in runs if r['turns'][0].get('run_id', runs.index(r)) == run_filter]
        if not runs:
            runs = [data['runs'][run_filter]] if run_filter < len(data['runs']) else []

    all_novelty = []
    all_qm_overlap = []
    all_e0_operative = []
    all_coherence = []

    for ri, run in enumerate(runs):
        responses = [t['response_text'] for t in run['turns']]

        # Per-step scores
        run_qm = []
        run_e0 = []
        for si, resp in enumerate(responses):
            qm_hits, qm_total, qm_frac, qm_matched = phrase_overlap(resp, STANDARD_QM_PHRASES)
            e0_hits, e0_total, e0_frac, e0_matched = phrase_overlap(resp, E0_OPERATIVE_PHRASES)
            run_qm.append(qm_frac)
            run_e0.append(e0_frac)

            if verbose:
                print(f"    Step {si}: QM overlap={qm_frac:.3f} ({qm_hits}/{qm_total})  "
                      f"E₀ operative={e0_frac:.3f} ({e0_hits}/{e0_total})")
                if qm_matched:
                    print(f"      QM phrases: {', '.join(qm_matched[:8])}")
                if e0_matched:
                    print(f"      E₀ phrases: {', '.join(e0_matched[:8])}")

        # Coherence
        coh = step_coherence(responses)

        # Path novelty = low QM overlap + high E₀ operative use
        # Score: novelty = (1 - qm_overlap) * 0.5 + e0_operative * 0.5
        mean_qm = sum(run_qm) / len(run_qm)
        mean_e0 = sum(run_e0) / len(run_e0)
        novelty = (1.0 - mean_qm) * 0.5 + mean_e0 * 0.5

        all_novelty.append(novelty)
        all_qm_overlap.append(mean_qm)
        all_e0_operative.append(mean_e0)
        all_coherence.append(coh['overall'])

        if verbose:
            print(f"  Run {ri}: novelty={novelty:.3f}  QM={mean_qm:.3f}  "
                  f"E₀op={mean_e0:.3f}  coherence={coh['overall']:.3f}")
            for p in coh['pairs']:
                print(f"    {p['step_pair']}: term_overlap={p['term_overlap']:.3f}  "
                      f"fwd_refs={p['forward_refs']}  coh={p['coherence']:.3f}")

    return {
        'name': name,
        'n_runs': len(runs),
        'novelty_mean': sum(all_novelty) / len(all_novelty) if all_novelty else 0,
        'novelty_vals': all_novelty,
        'qm_overlap_mean': sum(all_qm_overlap) / len(all_qm_overlap) if all_qm_overlap else 0,
        'e0_operative_mean': sum(all_e0_operative) / len(all_e0_operative) if all_e0_operative else 0,
        'coherence_mean': sum(all_coherence) / len(all_coherence) if all_coherence else 0,
        'coherence_vals': all_coherence,
    }


def cohens_d(a, b):
    """Compute Cohen's d between two lists."""
    import numpy as np
    a, b = np.array(a), np.array(b)
    na, nb = len(a), len(b)
    if na < 2 or nb < 2:
        return 0.0
    pooled = np.sqrt(((na-1)*np.std(a,ddof=1)**2 + (nb-1)*np.std(b,ddof=1)**2) / (na+nb-2))
    return (np.mean(a) - np.mean(b)) / pooled if pooled > 0 else 0


def main():
    parser = argparse.ArgumentParser(description='Quality Scorer: Path Novelty + Coherence')
    parser.add_argument('--condition', type=str, default=None,
                        help='Single condition to analyze (e0, null, placebo, inverted)')
    parser.add_argument('--run', type=int, default=None,
                        help='Single run index to analyze')
    parser.add_argument('--verbose', '-v', action='store_true',
                        help='Print per-step detail')
    args = parser.parse_args()

    base = 'experiments/results'
    conditions = {
        'E₀ (QM)': os.path.join(base, 'qm_derivation_e0'),
        'Placebo (ZFC)': os.path.join(base, 'qm_derivation_placebo'),
        'Inverted (Thermo)': os.path.join(base, 'qm_derivation_inverted'),
        'Null': os.path.join(base, 'qm_derivation_null'),
    }

    # Filter if requested
    if args.condition:
        key_map = {'e0': 'E₀ (QM)', 'placebo': 'Placebo (ZFC)',
                    'inverted': 'Inverted (Thermo)', 'null': 'Null'}
        if args.condition.lower() in key_map:
            k = key_map[args.condition.lower()]
            conditions = {k: conditions[k]}
        else:
            print(f"Unknown condition: {args.condition}")
            return

    results = []
    for name, path in conditions.items():
        data = load_experiment(path)
        if not data:
            print(f"  [SKIP] {name}: no experiment JSON found in {path}")
            continue
        print(f"\n{'='*70}")
        print(f"  Analyzing: {name}  (N={len(data['runs'])})")
        print(f"{'='*70}")
        r = analyze_condition(name, data, verbose=args.verbose, run_filter=args.run)
        results.append(r)

    if len(results) < 2:
        return

    # ── Summary Table ──
    print("\n" + "=" * 80)
    print("QUALITY SUMMARY — ALL CONDITIONS")
    print("=" * 80)
    print(f"\n  {'Condition':<22} {'Novelty':>8} {'QM Overlap':>11} {'E₀ Operative':>13} {'Coherence':>10}")
    print(f"  {'─'*22} {'─'*8} {'─'*11} {'─'*13} {'─'*10}")

    for r in results:
        print(f"  {r['name']:<22} {r['novelty_mean']:>8.3f} {r['qm_overlap_mean']:>11.3f} "
              f"{r['e0_operative_mean']:>13.3f} {r['coherence_mean']:>10.3f}")

    # ── Pairwise effect sizes ──
    print(f"\n  {'Comparison':<30} {'Novelty d':>10} {'Coherence d':>12}")
    print(f"  {'─'*30} {'─'*10} {'─'*12}")

    for i in range(len(results)):
        for j in range(i+1, len(results)):
            a, b = results[i], results[j]
            d_nov = cohens_d(a['novelty_vals'], b['novelty_vals'])
            d_coh = cohens_d(a['coherence_vals'], b['coherence_vals'])
            label = f"{a['name']} vs {b['name']}"
            print(f"  {label:<30} {d_nov:>+10.3f} {d_coh:>+12.3f}")

    # ── Interpretation ──
    print("\n" + "=" * 80)
    print("INTERPRETATION")
    print("=" * 80)

    # Find E₀ and Null results
    e0_r = next((r for r in results if 'E₀' in r['name']), None)
    null_r = next((r for r in results if 'Null' in r['name']), None)

    if e0_r and null_r:
        print(f"""
  Path Novelty:
    E₀ = {e0_r['novelty_mean']:.3f}   Null = {null_r['novelty_mean']:.3f}
    {'→ E₀ produces MORE novel derivation paths' if e0_r['novelty_mean'] > null_r['novelty_mean'] else '→ Null is surprisingly more novel (or scoring needs calibration)'}

  Coherence:
    E₀ = {e0_r['coherence_mean']:.3f}   Null = {null_r['coherence_mean']:.3f}
    {'→ E₀ steps BUILD ON each other more' if e0_r['coherence_mean'] > null_r['coherence_mean'] else '→ No clear coherence advantage for E₀'}

  Combined Quality Score (novelty × 0.5 + coherence × 0.5):
    E₀ = {(e0_r['novelty_mean'] + e0_r['coherence_mean'])/2:.3f}
    Null = {(null_r['novelty_mean'] + null_r['coherence_mean'])/2:.3f}
""")

    print("  Scoring key:")
    print("    Novelty: (1 - QM_overlap)/2 + E₀_operative/2")
    print("      Higher = less textbook retrieval + more E₀-constructive reasoning")
    print("    Coherence: 0.6 × term_overlap + 0.4 × forward_references")
    print("      Higher = steps build on each other more")
    print()
    print("  NOTE: These are heuristic proxies. They capture the *direction* of the")
    print("  categorical quality difference observed in manual inspection.")
    print("  They are not a substitute for human expert evaluation.")


if __name__ == '__main__':
    main()
