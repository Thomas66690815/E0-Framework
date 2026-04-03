#!/usr/bin/env python3
"""
E₀ Level-2 Pair-Based Validation Bootstrap (C127)
===================================================
Replaces Level-1 validation (target ∈ known → SUCCESS) with Level-2
pair-based validation (both source AND target known → SUCCESS).

Key mechanism: multiplicative weighting.
  p(SUCCESS) = w(source) × w(target)
  - canonical × canonical = 1.0  → always SUCCESS
  - canonical × tentative = 0.3  → 30% SUCCESS
  - tentative × tentative = 0.09 → 9% SUCCESS
  - any × unknown = 0            → always FAILURE

Why this matters:
  C126c showed distance collapse by R2 (distinct distances → 1).
  Root cause: Level-1 validation floods SUCCESS as tentative entries grow.
  Level-2 keeps SUCCESS tight — BOTH endpoints must be known for the edge
  to succeed.  The multiplicative nature prevents tentative entries from
  expanding the SUCCESS pool uncontrollably.

Config B canon analysis:
  Level-1: 15/64 edges SUCCESS (23%)
  Level-2:  5/64 edges SUCCESS (8%)
  → 3× more restrictive at baseline, gap widens as entries accumulate

Comparison targets:
  C126c Level-1 weighted: 11→15 firm, 100% confirmed, MIXED rankings
  C127  Level-2 weighted: ? → maintain diversity across rounds

Success criteria:
  1. Distance diversity preserved (distinct distances >> 1 beyond R1)
  2. Rankings stable across rounds
  3. Confirmed accuracy remains high
  4. Growth maintains or exceeds C126c
"""

import random
import sys
import os
from dataclasses import dataclass, field
from typing import Dict, List, Set, Tuple

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) + "/..")

from e0_controller.primitives import Outcome
from e0_controller.dream_mode import domain_fingerprints, find_equivalences
from e0_controller.explore_dict_learning import (
    GROUND_TRUTH, config_b, learn_landscape,
)
from e0_controller.explore_bootstrap_learning import (
    extract_best_correspondences,
)
from e0_controller.explore_weighted_learning import (
    WeightedEntry, WeightedDictionary,
    PROMOTION_THRESHOLD, DECAY_RATE, BOOST_PER_REDISCOVERY,
    MAX_INITIAL_WEIGHT, init_from_config_b,
)


# ══════════════════════════════════════════════
# Level-2 pair-based execute_fn
# ══════════════════════════════════════════════

def make_level2_execute(wd: WeightedDictionary, lang: str,
                        seed: int = 42):
    """Build Level-2 pair-based execute_fn.

    p(SUCCESS) = w(source) × w(target).
    Only edges where BOTH endpoints are at least partially known
    can produce SUCCESS.  The multiplicative nature keeps the SUCCESS
    pool extremely tight.
    """
    weights = wd.word_weights(lang)
    rng = random.Random(seed)

    def execute(source: str, target: str) -> Outcome:
        w_s = weights.get(source, 0.0)
        w_t = weights.get(target, 0.0)
        w = w_s * w_t
        if w < 0.01:
            return Outcome.FAILURE
        if w >= 1.0:
            return Outcome.SUCCESS
        return Outcome.SUCCESS if rng.random() < w else Outcome.FAILURE

    return execute


# ══════════════════════════════════════════════
# Single Level-2 round
# ══════════════════════════════════════════════

def run_level2_round(
    round_nr: int,
    wd: WeightedDictionary,
    verbose: bool = True,
) -> Tuple[List[Tuple[str, str, int, float]], Dict[str, float]]:
    """Run one Level-2 weighted bootstrap round."""
    firm_en = wd.firm_en
    firm_de = wd.firm_de

    unknown_pairs = {
        en: de for en, de in GROUND_TRUTH.items()
        if en not in firm_en and de not in firm_de
    }

    if verbose:
        print(f"\n{'─'*72}")
        print(f"  Round {round_nr}: {wd.tier_summary()}")
        print(f"  Firm: {sorted(firm_en)}")
        tent = [(e.en, e.de, f"w={e.weight:.2f}")
                for e in wd.entries.values() if e.tier == 'tentative']
        if tent:
            print(f"  Tentative: {tent}")
        conf = [(e.en, e.de) for e in wd.entries.values()
                if e.tier == 'confirmed']
        if conf:
            print(f"  Confirmed: {conf}")
        print(f"  Unknown remaining: {len(unknown_pairs)}")
        print(f"{'─'*72}")

    # Learn with Level-2 execute_fn (different seeds per round+language)
    en_exec = make_level2_execute(wd, "en", seed=42 + round_nr)
    de_exec = make_level2_execute(wd, "de", seed=143 + round_nr)
    en_L = learn_landscape("english_basic", en_exec, "EN")
    de_L = learn_landscape("german_basic", de_exec, "DE")

    # Fingerprint stats
    if verbose:
        fps_en = domain_fingerprints(en_L, "EN")
        fps_de = domain_fingerprints(de_L, "DE")
        n_s_en = sum(1 for fp in fps_en if fp.quality > 0)
        n_s_de = sum(1 for fp in fps_de if fp.quality > 0)
        print(f"  EN: {n_s_en}S/{len(fps_en)-n_s_en}F  "
              f"DE: {n_s_de}S/{len(fps_de)-n_s_de}F")

    # Dream — find equivalences
    equivalences = find_equivalences(
        en_L, de_L,
        domain_a="EN", domain_b="DE",
        quantile=0.15,
    )
    if verbose:
        distances = [eq.distance for eq in equivalences]
        n_distinct = len(set(round(d, 4) for d in distances)) if distances else 0
        print(f"  Equivalences: {len(equivalences)}, "
              f"distinct distances: {n_distinct}")

    # Extract discoveries — filter by FIRM only
    discoveries = extract_best_correspondences(
        equivalences, firm_en, firm_de, min_votes=2,
    )

    correct = 0
    wrong = 0
    if verbose and discoveries:
        print(f"\n  Discoveries (mutual best matches, ≥2 votes):")
        print(f"  {'EN':<12} {'DE':<12} {'Votes':>5} {'Avg d':>8}  Status")
        print(f"  {'─'*12} {'─'*12} {'─'*5} {'─'*8}  {'─'*25}")
    for en, de, votes, avg_d in discoveries:
        is_correct = GROUND_TRUTH.get(en) == de
        if is_correct:
            correct += 1
        else:
            wrong += 1
        if verbose:
            marker = "✓" if is_correct else "✗"
            existing = wd.entries.get(en)
            if existing and existing.tier == 'tentative' and existing.de == de:
                new_w = min(existing.weight + BOOST_PER_REDISCOVERY, 1.0)
                promoted = " → CONFIRMED" if new_w >= PROMOTION_THRESHOLD else ""
                status = (f"rediscovery w={existing.weight:.2f}→"
                          f"{new_w:.2f}{promoted}")
            elif existing and existing.tier == 'tentative':
                status = f"conflict (was {existing.de})"
            elif existing and existing.tier == 'confirmed':
                status = f"already confirmed"
            else:
                w0 = min(votes / 10, MAX_INITIAL_WEIGHT)
                status = f"NEW tentative w={w0:.2f}"
            print(f"  {en:<12} {de:<12} {votes:>5} {avg_d:>8.4f}  "
                  f"{marker} {status}")

    if verbose:
        if correct + wrong > 0:
            print(f"\n  Discovery accuracy: {correct}/{correct+wrong} "
                  f"({100*correct/(correct+wrong):.0f}%)")
        else:
            print(f"\n  No discoveries this round.")

    # Rankings for unknown pairs
    all_eqs = find_equivalences(
        en_L, de_L,
        domain_a="EN", domain_b="DE",
        quantile=1.0,
    )
    rankings = {}
    for en_word, de_word in sorted(unknown_pairs.items()):
        relevant = []
        for eq in all_eqs:
            en_involves = (eq.fp_a.edge.source == en_word
                           or eq.fp_a.edge.target == en_word)
            de_involves = (eq.fp_b.edge.source == de_word
                           or eq.fp_b.edge.target == de_word)
            if en_involves and de_involves:
                relevant.append(eq)
        if relevant:
            best = min(relevant, key=lambda e: e.distance)
            rank = next(i for i, eq in enumerate(all_eqs) if eq is best) + 1
            rankings[en_word] = rank / len(all_eqs) * 100
        else:
            rankings[en_word] = 100.0

    if verbose:
        print(f"\n  Unknown pair rankings (lower = better):")
        for en_word in sorted(rankings, key=lambda w: rankings[w]):
            de_word = unknown_pairs.get(en_word, "?")
            pct = rankings[en_word]
            quality = "★" if pct < 10 else ("●" if pct < 25 else "○")
            print(f"    {quality} {en_word:>10} ↔ {de_word:<12} {pct:>5.1f}%ile")

    return discoveries, rankings


# ══════════════════════════════════════════════
# Level-2 bootstrap loop
# ══════════════════════════════════════════════

def level2_bootstrap(n_rounds: int = 8) -> None:
    """Run the Level-2 weighted bootstrap loop."""
    wd = init_from_config_b()

    print(f"\n{'='*72}")
    print(f"  LEVEL-2 WEIGHTED BOOTSTRAP: Config B start ({wd.tier_summary()})")
    print(f"  p(SUCCESS) = w(source) × w(target)")
    print(f"  promotion={PROMOTION_THRESHOLD}, decay={DECAY_RATE}, "
          f"boost={BOOST_PER_REDISCOVERY}")
    print(f"{'='*72}")

    round_data = []

    for r in range(1, n_rounds + 1):
        discoveries, rankings = run_level2_round(r, wd)

        c, t, f = wd.tier_counts()
        round_data.append((r, discoveries, rankings, (c, t, f)))

        if not discoveries:
            print(f"\n  No discoveries in round {r} — stopping.")
            break

        # Update weights
        wd.update(discoveries, r)

        # Show post-update state
        print(f"\n  After update: {wd.tier_summary()}")
        for e in sorted(wd.entries.values(),
                        key=lambda x: (
                            -{'confirmed': 2, 'canonical': 1,
                              'tentative': 0}[x.tier],
                            -x.weight)):
            if e.tier != 'canonical':
                correct = "✓" if GROUND_TRUTH.get(e.en) == e.de else "✗"
                print(f"    {e.tier:>10} {e.en:>10}↔{e.de:<12} "
                      f"w={e.weight:.2f} seen={e.rounds_seen}x "
                      f"votes={e.total_votes} {correct}")

    # ── Summary ──────────────────────────────
    print(f"\n{'='*72}")
    print(f"  Level-2 Bootstrap Summary: {len(round_data)} rounds")
    print(f"{'='*72}")

    total_correct = 0
    total_wrong = 0

    for r_nr, disc, rank, (c, t, f) in round_data:
        n_c = sum(1 for en, de, v, d in disc if GROUND_TRUTH.get(en) == de)
        n_w = sum(1 for en, de, v, d in disc if GROUND_TRUTH.get(en) != de)
        total_correct += n_c
        total_wrong += n_w
        disc_str = ", ".join(
            f"{en}↔{de} {v}v{'✓' if GROUND_TRUTH.get(en)==de else '✗'}"
            for en, de, v, d in disc)
        print(f"\n  R{r_nr}: {c}C+{t}T+{f}F → {n_c}✓ {n_w}✗")
        print(f"    {disc_str}")

    # Ranking progression
    print(f"\n  Ranking progression (selected pairs):")
    tracked = ["mouth", "eye", "head", "foot", "fruit", "apple",
               "body", "good", "self", "thing"]
    print(f"  {'Pair':<20}", end="")
    for r_nr, _, _, _ in round_data:
        print(f"  R{r_nr:>1}", end="")
    print()
    for en in tracked:
        de = GROUND_TRUTH.get(en, "?")
        print(f"  {en}↔{de:<12}", end="")
        for _, _, rank, _ in round_data:
            if en in rank:
                pct = rank[en]
                print(f"  {pct:>4.0f}", end="")
            else:
                print(f"    ✓", end="")
        print()

    # Distance diversity across rounds
    print(f"\n  Distance diversity (distinct distances per round):")
    print(f"  C126c L1: 53 → 1 → 1 → 1 → 1 → 1 → 1 → 1  (collapses R2)")

    # Final dictionary state
    print(f"\n  Final dictionary: {wd.tier_summary()}")
    for e in sorted(wd.entries.values(),
                    key=lambda x: (
                        -{'confirmed': 2, 'canonical': 1,
                          'tentative': 0}[x.tier],
                        -x.weight)):
        correct = "✓" if GROUND_TRUTH.get(e.en) == e.de else "✗"
        if e.tier != 'canonical':
            print(f"    {e.tier:>10} {e.en:>10}↔{e.de:<12} "
                  f"w={e.weight:.2f} seen={e.rounds_seen}x "
                  f"votes={e.total_votes} {correct}")

    # Final stats
    can = sum(1 for e in wd.entries.values() if e.tier == 'canonical')
    conf_ok = sum(1 for e in wd.entries.values()
                  if e.tier == 'confirmed' and GROUND_TRUTH.get(e.en) == e.de)
    conf_tot = sum(1 for e in wd.entries.values() if e.tier == 'confirmed')
    tent_ok = sum(1 for e in wd.entries.values()
                  if e.tier == 'tentative' and GROUND_TRUTH.get(e.en) == e.de)
    tent_tot = sum(1 for e in wd.entries.values() if e.tier == 'tentative')

    print(f"\n  Canonical: {can} (fixed)")
    print(f"  Confirmed: {conf_ok}/{conf_tot} correct "
          f"({100*conf_ok/conf_tot if conf_tot else 0:.0f}%)")
    print(f"  Tentative: {tent_ok}/{tent_tot} correct "
          f"({100*tent_ok/tent_tot if tent_tot else 0:.0f}%)")
    print(f"  Firm total: {can + conf_tot} pairs")
    if total_correct + total_wrong > 0:
        print(f"  Discovery accuracy (all rounds): "
              f"{total_correct}/{total_correct+total_wrong} "
              f"({100*total_correct/(total_correct+total_wrong):.0f}%)")

    # Comparison
    print(f"\n  ── Comparison ──")
    print(f"  C126  ungated L1:  11→25 firm, 40% accuracy, rankings DEGRADE")
    print(f"  C126b gated L1:    11→16 firm, 100% added, rankings STABLE")
    print(f"  C126c weighted L1: 11→15 firm, 100% confirmed, MIXED rankings")
    print(f"  C127  weighted L2: 11→{can+conf_tot} firm, "
          f"{100*conf_ok/conf_tot if conf_tot else 0:.0f}% confirmed accuracy")


# ══════════════════════════════════════════════
# Main
# ══════════════════════════════════════════════

def main() -> None:
    print("=" * 72)
    print("  E₀ Level-2 Pair-Based Validation Bootstrap (C127)")
    print("  p(SUCCESS) = w(source) × w(target)")
    print("  Multiplicative pair validation preserves fingerprint diversity")
    print("  Starting from Config B (11 canonical pairs)")
    print("=" * 72)

    level2_bootstrap(n_rounds=8)


if __name__ == "__main__":
    main()
