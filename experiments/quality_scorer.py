#!/usr/bin/env python3
"""
Quality Scorer — Path Novelty + Coherence Analysis (Batch)
============================================================

Batch analysis across all experimental conditions using the shared
quality_metrics module. For live scoring, the web UI uses the same module.

Usage:
    py experiments/quality_scorer.py
    py experiments/quality_scorer.py --condition e0
    py experiments/quality_scorer.py --run 0 --verbose
"""

import json
import glob
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from experiments.quality_metrics import (
    score_novelty, score_coherence, score_completeness, phrase_count,
    STANDARD_QM_PHRASES, E0_OPERATIVE_PHRASES,
)


# ─────────────────────────────────────────────────────────────────────────
# BATCH ANALYSIS
# ─────────────────────────────────────────────────────────────────────────

def load_experiment(condition_dir):
    """Load the experiment JSON with the most runs from a condition directory."""
    jsons = glob.glob(os.path.join(condition_dir, 'experiment_*.json'))
    if not jsons:
        return None
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
    """Analyze all runs in a condition using shared quality_metrics."""
    runs = data['runs']
    if run_filter is not None:
        runs = [r for r in runs if r['turns'][0].get('run_id', runs.index(r)) == run_filter]
        if not runs:
            runs = [data['runs'][run_filter]] if run_filter < len(data['runs']) else []

    all_novelty = []
    all_qm_overlap = []
    all_e0_operative = []
    all_coherence = []
    all_completeness = []

    for ri, run in enumerate(runs):
        responses = [t['response_text'] for t in run['turns']]

        # Per-step novelty + completeness scores
        run_novs = [score_novelty(resp) for resp in responses]
        run_comps = [score_completeness(resp, si) for si, resp in enumerate(responses)]
        run_qm = [n['qm_overlap'] for n in run_novs]
        run_e0 = [n['e0_operative'] for n in run_novs]

        if verbose:
            for si, nov in enumerate(run_novs):
                qm_m = phrase_count(responses[si], STANDARD_QM_PHRASES)
                e0_m = phrase_count(responses[si], E0_OPERATIVE_PHRASES)
                comp = run_comps[si]
                print(f"    Step {si}: QM overlap={nov['qm_overlap']:.3f} ({qm_m[0]}/{qm_m[1]})  "
                      f"E₀ operative={nov['e0_operative']:.3f} ({e0_m[0]}/{e0_m[1]})  "
                      f"completeness={comp['completeness']:.3f} ({comp['marker_hits']}/{comp['marker_total']} → {comp['target']})")
                if qm_m[3]:
                    print(f"      QM phrases: {', '.join(qm_m[3][:8])}")
                if e0_m[3]:
                    print(f"      E₀ phrases: {', '.join(e0_m[3][:8])}")

        # Coherence across steps
        coh_scores = []
        for i in range(len(responses) - 1):
            c = score_coherence(responses[i], responses[i+1])
            coh_scores.append(c)
        coh_overall = sum(c['coherence'] for c in coh_scores) / len(coh_scores) if coh_scores else 0.0

        mean_qm = sum(run_qm) / len(run_qm)
        mean_e0 = sum(run_e0) / len(run_e0)
        novelty = (1.0 - mean_qm) * 0.5 + mean_e0 * 0.5
        mean_comp = sum(c['completeness'] for c in run_comps) / len(run_comps) if run_comps else 0.0

        all_novelty.append(novelty)
        all_qm_overlap.append(mean_qm)
        all_e0_operative.append(mean_e0)
        all_coherence.append(coh_overall)
        all_completeness.append(mean_comp)

        if verbose:
            print(f"  Run {ri}: novelty={novelty:.3f}  QM={mean_qm:.3f}  "
                  f"E₀op={mean_e0:.3f}  coherence={coh_overall:.3f}  completeness={mean_comp:.3f}")
            for i, c in enumerate(coh_scores):
                print(f"    {i}→{i+1}: term_overlap={c['term_overlap']:.3f}  "
                      f"fwd_refs={c['forward_refs']}  coh={c['coherence']:.3f}")

    return {
        'name': name,
        'n_runs': len(runs),
        'novelty_mean': sum(all_novelty) / len(all_novelty) if all_novelty else 0,
        'novelty_vals': all_novelty,
        'qm_overlap_mean': sum(all_qm_overlap) / len(all_qm_overlap) if all_qm_overlap else 0,
        'e0_operative_mean': sum(all_e0_operative) / len(all_e0_operative) if all_e0_operative else 0,
        'coherence_mean': sum(all_coherence) / len(all_coherence) if all_coherence else 0,
        'coherence_vals': all_coherence,
        'completeness_mean': sum(all_completeness) / len(all_completeness) if all_completeness else 0,
        'completeness_vals': all_completeness,
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
    print("\n" + "=" * 90)
    print("QUALITY SUMMARY — ALL CONDITIONS")
    print("=" * 90)
    print(f"\n  {'Condition':<22} {'Novelty':>8} {'QM Overlap':>11} {'E₀ Operative':>13} {'Coherence':>10} {'Complete':>9}")
    print(f"  {'─'*22} {'─'*8} {'─'*11} {'─'*13} {'─'*10} {'─'*9}")

    for r in results:
        print(f"  {r['name']:<22} {r['novelty_mean']:>8.3f} {r['qm_overlap_mean']:>11.3f} "
              f"{r['e0_operative_mean']:>13.3f} {r['coherence_mean']:>10.3f} {r['completeness_mean']:>9.3f}")

    # ── Pairwise effect sizes ──
    print(f"\n  {'Comparison':<30} {'Novelty d':>10} {'Coherence d':>12} {'Complete d':>11}")
    print(f"  {'─'*30} {'─'*10} {'─'*12} {'─'*11}")

    for i in range(len(results)):
        for j in range(i+1, len(results)):
            a, b = results[i], results[j]
            d_nov = cohens_d(a['novelty_vals'], b['novelty_vals'])
            d_coh = cohens_d(a['coherence_vals'], b['coherence_vals'])
            d_comp = cohens_d(a['completeness_vals'], b['completeness_vals'])
            label = f"{a['name']} vs {b['name']}"
            print(f"  {label:<30} {d_nov:>+10.3f} {d_coh:>+12.3f} {d_comp:>+11.3f}")

    # ── Interpretation ──
    print("\n" + "=" * 90)
    print("INTERPRETATION")
    print("=" * 90)

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

  Derivation Completeness:
    E₀ = {e0_r['completeness_mean']:.3f}   Null = {null_r['completeness_mean']:.3f}
    {'→ E₀ hits MORE target concepts per step' if e0_r['completeness_mean'] > null_r['completeness_mean'] else '→ Null achieves comparable or better target coverage'}

  Combined Quality Score (novelty × 0.33 + coherence × 0.33 + completeness × 0.33):
    E₀ = {(e0_r['novelty_mean'] + e0_r['coherence_mean'] + e0_r['completeness_mean'])/3:.3f}
    Null = {(null_r['novelty_mean'] + null_r['coherence_mean'] + null_r['completeness_mean'])/3:.3f}
""")

    print("  Scoring key:")
    print("    Novelty: (1 - QM_overlap)/2 + E₀_operative/2")
    print("      Higher = less textbook retrieval + more E₀-constructive reasoning")
    print("    Coherence: 0.6 × term_overlap + 0.4 × forward_references")
    print("      Higher = steps build on each other more")
    print("    Completeness: fraction of target concept markers hit per step")
    print("      Higher = derivation covers the expected conceptual territory")
    print()
    print("  NOTE: These are heuristic proxies. They capture the *direction* of the")
    print("  categorical quality difference observed in manual inspection.")
    print("  They are not a substitute for human expert evaluation.")


if __name__ == '__main__':
    main()
