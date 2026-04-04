#!/usr/bin/env python3
"""
E₀ C131b — Seed Expansion Variants on v1.1 Canons
====================================================
Systematic comparison: seed expansion ONLY, no topology changes.

Canons: english_basic v1.1 (64 edges), german_basic v1.1 (64 edges).
No bridge edges — clean measurement of seed effect.

Variants:
  Config B    (11 pairs) — baseline (body + food clusters)
  Config C    (18 pairs) — +eye, mouth, foot, see, go, good, big
  Config C+R2 (20 pairs) — Config C + in↔in_de, with↔mit
  Config C+R5 (23 pairs) — Config C + all 5 relation pairs

Question 1: Does seed expansion alone break the 13-pair plateau?
Question 2: Does targeted relation seeding unlock relation↔beziehung?
Question 3: Is R5 (full cluster) better than R2 (2 pairs)?
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) + "/..")

from e0_controller.explore_dict_learning import (
    GROUND_TRUTH, config_b, config_c, config_c_r2, config_c_r5,
)
from e0_controller.explore_level3_learning import (
    build_neighbor_map, PROMOTION_VOTES, MIN_CONTEXT_SCORE,
)
from e0_controller.explore_confidence_learning import (
    ConfidenceEntry, ConfidenceDictionary,
    make_context_l2_execute_conf,
)
from e0_controller.explore_c131_learning import (
    init_confidence, run_round, analyze_coverage,
)


# ══════════════════════════════════════════════
# Bootstrap loop (compact version)
# ══════════════════════════════════════════════

def run_variant(config_fn, label: str, n_rounds: int = 10) -> dict:
    """Run bootstrap and return summary dict."""
    cd = init_confidence(config_fn, label)
    can_start = sum(1 for e in cd.entries.values() if e.tier == 'canonical')

    print(f"\n{'='*72}")
    print(f"  {label}: {cd.tier_summary()}")
    print(f"  Canons: v1.1 (64/64 edges, NO bridge edges)")
    print(f"{'='*72}")

    round_summaries = []

    for r in range(1, n_rounds + 1):
        discoveries = run_round(r, cd, verbose=(r <= 3 or r == n_rounds))

        c, t, f = cd.tier_counts()

        if not discoveries:
            print(f"\n  No discoveries in round {r} — stopping.")
            break

        cd.update(discoveries, r)

        n_ok = sum(1 for en, de, *_ in discoveries
                   if GROUND_TRUTH.get(en) == de)
        n_bad = len(discoveries) - n_ok
        round_summaries.append((r, n_ok, n_bad, c, t, f))

        if r <= 3 or r == n_rounds:
            print(f"\n  After R{r}: {cd.tier_summary()}")
            for e in sorted(cd.entries.values(),
                            key=lambda x: (
                                -{'confirmed': 2, 'canonical': 1,
                                  'tentative': 0}[x.tier],
                                -x.cumulative_conf)):
                if e.tier != 'canonical':
                    correct = "✓" if GROUND_TRUTH.get(e.en) == e.de else "✗"
                    ctx_s = (f"{e.combined_context:.0%}"
                             if e.combined_context is not None else "?")
                    print(f"    {e.tier:>10} {e.en:>12}↔{e.de:<12} "
                          f"conf={e.cumulative_conf:>5.1f} "
                          f"ctx={ctx_s} {correct}")

    # Collect results
    can = sum(1 for e in cd.entries.values() if e.tier == 'canonical')
    conf_ok = sum(1 for e in cd.entries.values()
                  if e.tier == 'confirmed' and GROUND_TRUTH.get(e.en) == e.de)
    conf_tot = sum(1 for e in cd.entries.values() if e.tier == 'confirmed')
    tent_ok = sum(1 for e in cd.entries.values()
                  if e.tier == 'tentative' and GROUND_TRUTH.get(e.en) == e.de)
    tent_tot = sum(1 for e in cd.entries.values() if e.tier == 'tentative')
    firm = can + conf_tot

    # Check relation specifically
    rel_entry = None
    for e in cd.entries.values():
        if e.en == 'relation' and e.de == 'beziehung':
            rel_entry = e
            break

    rel_status = "not seen"
    if rel_entry:
        rel_status = (f"{rel_entry.tier} conf={rel_entry.cumulative_conf:.0f} "
                      f"ctx={'?' if rel_entry.combined_context is None else f'{rel_entry.combined_context:.0%}'}")

    total_ok = sum(n for _, n, _, _, _, _ in round_summaries)
    total_bad = sum(n for _, _, n, _, _, _ in round_summaries)

    result = {
        'label': label,
        'can': can,
        'conf_ok': conf_ok,
        'conf_tot': conf_tot,
        'tent_ok': tent_ok,
        'tent_tot': tent_tot,
        'firm': firm,
        'disc_ok': total_ok,
        'disc_bad': total_bad,
        'relation': rel_status,
        'rounds': len(round_summaries),
        'cd': cd,
    }

    print(f"\n  {'─'*60}")
    print(f"  {label} RESULT: {can}C + {conf_ok}/{conf_tot}F + "
          f"{tent_ok}/{tent_tot}T = {firm} firm")
    print(f"  Discovery accuracy: {total_ok}/{total_ok+total_bad}")
    print(f"  relation↔beziehung: {rel_status}")
    print(f"  {'─'*60}")

    return result


def main() -> None:
    print("=" * 72)
    print("  E₀ C131b — Seed Expansion Variants (v1.1 Canons)")
    print("  Systematic comparison: seed effect only, no topology changes")
    print("=" * 72)

    # ── Coverage analysis for each config ──
    configs = [
        (config_b, "Config B (11)"),
        (config_c, "Config C (18)"),
        (config_c_r2, "Config C+R2 (20)"),
        (config_c_r5, "Config C+R5 (23)"),
    ]

    for fn, label in configs:
        analyze_coverage(fn, label)

    # ── Run all variants ──
    results = []
    for fn, label in configs:
        result = run_variant(fn, label, n_rounds=10)
        results.append(result)

    # ── Final comparison ──
    print(f"\n\n{'='*72}")
    print("  C131b COMPARISON — Seed Expansion on v1.1 Canons")
    print(f"{'='*72}")

    print(f"\n  {'Config':<22} {'Seed':>4} {'Firm':>4} {'Conf':>8} "
          f"{'Tent':>8} {'Disc':>8}  relation↔beziehung")
    print(f"  {'─'*22} {'─'*4} {'─'*4} {'─'*8} "
          f"{'─'*8} {'─'*8}  {'─'*25}")

    for r in results:
        conf_s = (f"{r['conf_ok']}/{r['conf_tot']}"
                  if r['conf_tot'] > 0 else "0/0")
        tent_s = (f"{r['tent_ok']}/{r['tent_tot']}"
                  if r['tent_tot'] > 0 else "0/0")
        disc_s = f"{r['disc_ok']}/{r['disc_ok']+r['disc_bad']}"
        print(f"  {r['label']:<22} {r['can']:>4} {r['firm']:>4} "
              f"{conf_s:>8} {tent_s:>8} {disc_s:>8}  {r['relation']}")

    # ── Delta analysis ──
    print(f"\n  ── Delta Analysis ──")
    if len(results) >= 2:
        b, c = results[0], results[1]
        new_disc = c['firm'] - b['firm']
        seed_delta = c['can'] - b['can']
        print(f"  B→C: +{seed_delta} seed → +{new_disc} firm "
              f"(net discovery: {new_disc - seed_delta:+d})")
    if len(results) >= 3:
        c, cr2 = results[1], results[2]
        new_disc = cr2['firm'] - c['firm']
        seed_delta = cr2['can'] - c['can']
        print(f"  C→C+R2: +{seed_delta} seed → +{new_disc} firm "
              f"(net discovery: {new_disc - seed_delta:+d})")
    if len(results) >= 4:
        cr2, cr5 = results[2], results[3]
        new_disc = cr5['firm'] - cr2['firm']
        seed_delta = cr5['can'] - cr2['can']
        print(f"  C+R2→C+R5: +{seed_delta} seed → +{new_disc} firm "
              f"(net discovery: {new_disc - seed_delta:+d})")

    print(f"\n  Key question: does relation↔beziehung get promoted")
    print(f"  with R2 or R5 seeding?")


if __name__ == "__main__":
    main()
