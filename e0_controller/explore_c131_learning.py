#!/usr/bin/env python3
"""
E₀ C131 — Canon Restructuring: Bridge Edges + Seed Expansion
==============================================================
Two independent changes to break the 13-15 firm pair plateau:

  Direction 1: Cross-cluster bridge edges (EN 64→77, DE 64→76)
    13 shared edges connecting isolated clusters (qualities, relations,
    actions) to concrete seeded nouns. Eliminates context deserts.

  Direction 2: Seed expansion Config B→C (11→18 pairs)
    +7 seed pairs: eye↔auge, mouth↔mund, foot↔fuss, see↔sehen,
    go↔gehen, good↔gut, big↔gross.

Experiment structure (isolate each direction):
  Phase 1: Config B (old seed, 11 pairs) + v1.2 canons (new edges)
           → shows pure effect of topology change
  Phase 2: Config C (new seed, 18 pairs) + v1.2 canons (new edges)
           → shows combined effect

Baseline (C130): Config B + v1.1 canons → 11→13 firm, 100% confirmed.
"""

import random
import sys
import os
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) + "/..")

from e0_controller.primitives import Edge, Outcome
from e0_controller.landscape import Landscape
from e0_controller.canon_loader import load_canon_spec
from e0_controller.dream_mode import (
    EdgeFingerprint, Equivalence,
    domain_fingerprints, find_equivalences, fingerprint_distance,
)
from e0_controller.explore_dict_learning import (
    GROUND_TRUTH, GROUND_TRUTH_REV, config_b, config_c, learn_landscape,
)
from e0_controller.explore_level3_learning import (
    ContextEntry, build_neighbor_map,
    VOTE_SCALE, PROMOTION_VOTES, MIN_CONTEXT_SCORE,
    STALE_ROUNDS, MIN_STALE_VOTES,
)
from e0_controller.explore_confidence_learning import (
    ConfidenceEntry, ConfidenceDictionary,
    extract_confidence_correspondences,
    compute_role_context_score,
    make_context_l2_execute_conf,
)


# ══════════════════════════════════════════════
# Initialization from any config
# ══════════════════════════════════════════════

def init_confidence(config_fn, label: str) -> ConfidenceDictionary:
    """Create ConfidenceDictionary from arbitrary config."""
    en_nbrs = build_neighbor_map("english_basic")
    de_nbrs = build_neighbor_map("german_basic")
    cd = ConfidenceDictionary(en_neighbors=en_nbrs, de_neighbors=de_nbrs)
    pairs = config_fn()
    n_pairs = 0
    for d in pairs:
        for en, de in d.translations.items():
            key = f"{en}:{de}"
            cd.entries[key] = ConfidenceEntry(
                en=en, de=de, tier='canonical',
                cumulative_conf=0, raw_votes=0,
                rounds_seen=0, first_round=0, last_round=0,
                topo_score=1.0, role_score=1.0,
            )
            n_pairs += 1
    print(f"  {label}: {n_pairs} canonical pairs from {len(pairs)} groups")
    return cd


# ══════════════════════════════════════════════
# Single round (reuses C130 mechanics)
# ══════════════════════════════════════════════

def run_round(
    round_nr: int,
    cd: ConfidenceDictionary,
    verbose: bool = True,
) -> List[Tuple[str, str, float, float, int]]:
    """Run one learning round using C130 confidence-weighted extraction."""
    firm_en = cd.firm_en
    firm_de = cd.firm_de
    unknown_pairs = {
        en: de for en, de in GROUND_TRUTH.items()
        if en not in firm_en and de not in firm_de
    }

    cd.update_context_scores()

    if verbose:
        print(f"\n{'─'*72}")
        print(f"  Round {round_nr}: {cd.tier_summary()}")
        print(f"  Firm: {sorted(firm_en)}")
        tent = sorted(
            [e for e in cd.entries.values() if e.tier == 'tentative'],
            key=lambda e: -e.cumulative_conf,
        )
        if tent:
            print(f"  Tentative ({len(tent)}):")
            for e in tent[:10]:  # cap display
                ctx_s = (f"{e.combined_context:.0%}"
                         if e.combined_context is not None else "?")
                correct = "✓" if GROUND_TRUTH.get(e.en) == e.de else "✗"
                print(f"    {e.en:>10}↔{e.de:<12} "
                      f"conf={e.cumulative_conf:>5.1f}({e.raw_votes}v) "
                      f"ew={e.effective_weight:.2f} ctx={ctx_s} {correct}")
            if len(tent) > 10:
                print(f"    ... and {len(tent)-10} more")
        conf = [(e.en, e.de) for e in cd.entries.values()
                if e.tier == 'confirmed']
        if conf:
            print(f"  Confirmed: {conf}")
        print(f"  Unknown remaining: {len(unknown_pairs)}")
        print(f"{'─'*72}")

    # Learn
    en_exec = make_context_l2_execute_conf(cd, "en", seed=42 + round_nr)
    de_exec = make_context_l2_execute_conf(cd, "de", seed=143 + round_nr)
    en_L = learn_landscape("english_basic", en_exec, "EN")
    de_L = learn_landscape("german_basic", de_exec, "DE")

    cd.en_landscape = en_L
    cd.de_landscape = de_L

    if verbose:
        fps_en = domain_fingerprints(en_L, "EN")
        fps_de = domain_fingerprints(de_L, "DE")
        n_s_en = sum(1 for fp in fps_en if fp.quality > 0)
        n_s_de = sum(1 for fp in fps_de if fp.quality > 0)
        print(f"  EN: {n_s_en}S/{len(fps_en)-n_s_en}F edges  "
              f"DE: {n_s_de}S/{len(fps_de)-n_s_de}F edges")

    # Find equivalences
    equivalences = find_equivalences(
        en_L, de_L,
        domain_a="EN", domain_b="DE",
        quantile=0.15,
    )

    if verbose:
        confs = [eq.confidence for eq in equivalences]
        if confs:
            avg_c = sum(confs) / len(confs)
            print(f"  Equivalences: {len(equivalences)}, "
                  f"avg confidence={avg_c:.3f}")

    # Extract confidence-weighted correspondences
    discoveries = extract_confidence_correspondences(
        equivalences, firm_en, firm_de, min_confidence=0.5,
    )

    if verbose and discoveries:
        en2de, de2en = cd.build_translation_maps()
        print(f"\n  Discoveries:")
        print(f"  {'EN':<12} {'DE':<12} {'Conf':>6} {'Votes':>5} "
              f"{'Topo':>5} {'Role':>5}  Status")
        print(f"  {'─'*65}")

        for en, de, conf, avg_d, raw_v in discoveries:
            is_correct = GROUND_TRUTH.get(en) == de
            marker = "✓" if is_correct else "✗"
            topo, _, _, role = compute_role_context_score(
                en, de, en2de, de2en,
                cd.en_neighbors, cd.de_neighbors,
                en_L, de_L,
            )
            topo_s = f"{topo:.0%}" if topo is not None else "?"
            role_s = f"{role:.0%}" if role is not None else "?"
            key = f"{en}:{de}"
            existing = cd.entries.get(key)
            if existing and existing.tier == 'tentative':
                new_conf = existing.cumulative_conf + conf
                status = f"cum {existing.cumulative_conf:.1f}→{new_conf:.1f}"
            else:
                status = f"NEW conf={conf:.1f}"
            print(f"  {en:<12} {de:<12} {conf:>6.1f} {raw_v:>5} "
                  f"{topo_s:>5} {role_s:>5}  {marker} {status}")

    if verbose:
        correct = sum(1 for en, de, *_ in discoveries
                      if GROUND_TRUTH.get(en) == de)
        wrong = len(discoveries) - correct
        if correct + wrong > 0:
            print(f"\n  Accuracy: {correct}/{correct+wrong} "
                  f"({100*correct/(correct+wrong):.0f}%)")

    return discoveries


# ══════════════════════════════════════════════
# Bootstrap loop
# ══════════════════════════════════════════════

def run_bootstrap(
    config_fn,
    config_label: str,
    n_rounds: int = 10,
) -> ConfidenceDictionary:
    """Run confidence-weighted bootstrap from given config."""
    cd = init_confidence(config_fn, config_label)
    can_count = sum(1 for e in cd.entries.values() if e.tier == 'canonical')

    print(f"\n{'='*72}")
    print(f"  C131 {config_label}: {cd.tier_summary()}")
    print(f"  Canons: english_basic v1.2 (77 edges), "
          f"german_basic v1.2 (76 edges)")
    print(f"  Promotion: conf≥{PROMOTION_VOTES} AND "
          f"combined_ctx≥{MIN_CONTEXT_SCORE:.0%}")
    print(f"{'='*72}")

    round_data = []

    for r in range(1, n_rounds + 1):
        discoveries = run_round(r, cd)

        c, t, f = cd.tier_counts()
        round_data.append((r, discoveries, (c, t, f)))

        if not discoveries:
            print(f"\n  No discoveries in round {r} — stopping.")
            break

        cd.update(discoveries, r)

        print(f"\n  After update: {cd.tier_summary()}")
        for e in sorted(cd.entries.values(),
                        key=lambda x: (
                            -{'confirmed': 2, 'canonical': 1,
                              'tentative': 0}[x.tier],
                            -x.cumulative_conf)):
            if e.tier != 'canonical':
                correct = "✓" if GROUND_TRUTH.get(e.en) == e.de else "✗"
                ctx_s = (f"{e.combined_context:.0%}"
                         if e.combined_context is not None else "?")
                print(f"    {e.tier:>10} {e.en:>10}↔{e.de:<12} "
                      f"conf={e.cumulative_conf:>5.1f}({e.raw_votes}v) "
                      f"ctx={ctx_s} R{e.first_round}-R{e.last_round} "
                      f"{correct}")

    # ── Summary ──────────────────────────────
    print(f"\n{'='*72}")
    print(f"  {config_label} Summary: {len(round_data)} rounds")
    print(f"{'='*72}")

    total_correct = 0
    total_wrong = 0
    for r_nr, disc, (c, t, f) in round_data:
        n_c = sum(1 for en, de, *_ in disc if GROUND_TRUTH.get(en) == de)
        n_w = sum(1 for en, de, *_ in disc if GROUND_TRUTH.get(en) != de)
        total_correct += n_c
        total_wrong += n_w
        disc_str = ", ".join(
            f"{en}↔{de}{'✓' if GROUND_TRUTH.get(en)==de else '✗'}"
            for en, de, *_ in disc)
        print(f"  R{r_nr}: {c}C+{t}T+{f}F → {n_c}✓ {n_w}✗  {disc_str}")

    can = sum(1 for e in cd.entries.values() if e.tier == 'canonical')
    conf_ok = sum(1 for e in cd.entries.values()
                  if e.tier == 'confirmed' and GROUND_TRUTH.get(e.en) == e.de)
    conf_tot = sum(1 for e in cd.entries.values() if e.tier == 'confirmed')
    tent_ok = sum(1 for e in cd.entries.values()
                  if e.tier == 'tentative' and GROUND_TRUTH.get(e.en) == e.de)
    tent_tot = sum(1 for e in cd.entries.values() if e.tier == 'tentative')

    print(f"\n  Canonical: {can}")
    if conf_tot > 0:
        print(f"  Confirmed: {conf_ok}/{conf_tot} = "
              f"{100*conf_ok/conf_tot:.0f}% correct")
    else:
        print(f"  Confirmed: 0")
    if tent_tot > 0:
        print(f"  Tentative: {tent_ok}/{tent_tot} = "
              f"{100*tent_ok/tent_tot:.0f}% correct")
    else:
        print(f"  Tentative: 0")
    firm = can + conf_tot
    print(f"  Firm total: {firm} (was {can} canonical)")

    if total_correct + total_wrong > 0:
        print(f"  Discovery accuracy: "
              f"{total_correct}/{total_correct+total_wrong} "
              f"({100*total_correct/(total_correct+total_wrong):.0f}%)")

    # Context analysis for non-canonical entries
    print(f"\n  ── Context Analysis ──")
    print(f"  {'Pair':<26} {'Topo':>5} {'Role':>5} {'Comb':>5}  "
          f"{'Conf':>6} {'Status':<10}")
    print(f"  {'─'*26} {'─'*5} {'─'*5} {'─'*5}  {'─'*6} {'─'*10}")
    for e in sorted(cd.entries.values(),
                    key=lambda x: -(x.combined_context or -1)):
        if e.tier == 'canonical':
            continue
        correct = "✓" if GROUND_TRUTH.get(e.en) == e.de else "✗"
        topo_s = f"{e.topo_score:.0%}" if e.topo_score is not None else "?"
        role_s = f"{e.role_score:.0%}" if e.role_score is not None else "?"
        ctx_s = (f"{e.combined_context:.0%}"
                 if e.combined_context is not None else "?")
        print(f"  {e.en:>12}↔{e.de:<12} {topo_s:>5} {role_s:>5} "
              f"{ctx_s:>5}  {e.cumulative_conf:>6.1f} "
              f"{e.tier:<10} {correct}")

    return cd


# ══════════════════════════════════════════════
# Coverage analysis
# ══════════════════════════════════════════════

def analyze_coverage(config_fn, config_label: str) -> None:
    """Analyze how many nodes have translatable neighbors."""
    en_nbrs = build_neighbor_map("english_basic")
    de_nbrs = build_neighbor_map("german_basic")

    seed_en = set()
    seed_de = set()
    for d in config_fn():
        for en, de in d.translations.items():
            seed_en.add(en)
            seed_de.add(de)

    print(f"\n  ── Coverage Analysis: {config_label} ──")
    print(f"  Seed EN: {sorted(seed_en)}")
    print(f"  Seed DE: {sorted(seed_de)}")

    # For each non-seed word, count translatable neighbors
    en2de = {}
    de2en = {}
    for d in config_fn():
        for en, de in d.translations.items():
            en2de[en] = de
            de2en[de] = en

    buckets = {0: [], 1: [], 2: [], 3: []}
    for en_word in sorted(GROUND_TRUTH.keys()):
        if en_word in seed_en:
            continue
        count = 0
        for nbr in en_nbrs.get(en_word, set()):
            if nbr in en2de:
                count += 1
        de_word = GROUND_TRUTH[en_word]
        for nbr in de_nbrs.get(de_word, set()):
            if nbr in de2en:
                count += 1
        bucket = min(count, 3)
        buckets[bucket].append(en_word)

    for k in sorted(buckets.keys()):
        label = f"{k}+" if k == 3 else str(k)
        print(f"  {label} translatable neighbors: "
              f"{len(buckets[k])} words — {buckets[k]}")

    total_non_seed = sum(len(v) for v in buckets.values())
    reachable = total_non_seed - len(buckets[0])
    print(f"\n  Reachable by context: {reachable}/{total_non_seed} "
          f"({100*reachable/total_non_seed:.0f}%)")
    print(f"  Context deserts: {len(buckets[0])} words")


def main() -> None:
    print("=" * 72)
    print("  E₀ C131 — Canon Restructuring: Bridge Edges + Seed Expansion")
    print("  Two directions of change, measured independently")
    print("=" * 72)

    # ── Coverage analysis ──
    analyze_coverage(config_b, "Config B (old seed)")
    analyze_coverage(config_c, "Config C (expanded seed)")

    # ── Phase 1: Config B + v1.2 canons (topology only) ──
    print(f"\n\n{'#'*72}")
    print(f"  PHASE 1: Config B (11 pairs) + v1.2 canons (new edges)")
    print(f"  Isolates effect of cross-cluster bridges")
    print(f"  Baseline C130: 11→13 firm, 100% confirmed")
    print(f"{'#'*72}")
    cd_b = run_bootstrap(config_b, "Phase 1 (B+v1.2)", n_rounds=10)

    # ── Phase 2: Config C + v1.2 canons (both changes) ──
    print(f"\n\n{'#'*72}")
    print(f"  PHASE 2: Config C (18 pairs) + v1.2 canons (new edges)")
    print(f"  Combined effect: expanded seed + cross-cluster bridges")
    print(f"{'#'*72}")
    cd_c = run_bootstrap(config_c, "Phase 2 (C+v1.2)", n_rounds=10)

    # ── Comparison ──
    print(f"\n\n{'='*72}")
    print("  C131 COMPARISON")
    print(f"{'='*72}")

    def summarize(cd: ConfidenceDictionary, label: str):
        can = sum(1 for e in cd.entries.values() if e.tier == 'canonical')
        conf_tot = sum(1 for e in cd.entries.values()
                       if e.tier == 'confirmed')
        conf_ok = sum(1 for e in cd.entries.values()
                      if e.tier == 'confirmed'
                      and GROUND_TRUTH.get(e.en) == e.de)
        tent_tot = sum(1 for e in cd.entries.values()
                       if e.tier == 'tentative')
        tent_ok = sum(1 for e in cd.entries.values()
                      if e.tier == 'tentative'
                      and GROUND_TRUTH.get(e.en) == e.de)
        firm = can + conf_tot
        acc = (f"{100*conf_ok/conf_tot:.0f}%" if conf_tot > 0 else "n/a")
        print(f"  {label:<28} {can:>3}C {conf_ok}/{conf_tot}F={acc:>4} "
              f"{tent_ok}/{tent_tot}T  firm={firm}")

    print(f"  {'Config':<28} {'Can':>4} {'Confirmed':>10} "
          f"{'Tentative':>10}  {'Firm':>5}")
    print(f"  {'─'*28} {'─'*4} {'─'*10} {'─'*10}  {'─'*5}")
    print(f"  {'C130 baseline (B+v1.1)':<28} {'11':>4} "
          f"{'2/2=100%':>10} {'–':>10}  {'13':>5}")
    summarize(cd_b, "Phase 1 (B+v1.2 edges)")
    summarize(cd_c, "Phase 2 (C+v1.2 both)")


if __name__ == "__main__":
    main()
