#!/usr/bin/env python3
"""
E₀ Iterative Dictionary Expansion (C126)
==========================================
Tests the bootstrap hypothesis: Can Dream Mode discoveries from round N
become dictionary entries for round N+1, creating a self-improving loop?

Architecture:
  Round 1: Config B dictionaries (11 pairs) → learn → dream → discover
  Round 2: Config B + best discoveries from round 1 → learn → dream → discover
  Round 3: Expanded + best from round 2 → ...

The key question: Does each round discover NEW correct translations that
previous rounds couldn't find?  Does the known-word set grow correctly?

This is the E₀ bootstrap in its purest form:
  partial knowledge → differential historization → pattern discovery
  → expanded knowledge → better historization → deeper discovery
"""

import sys
import os
from collections import Counter
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) + "/..")

from e0_controller.canon_loader import load_canon
from e0_controller.curriculum import CurriculumRunner
from e0_controller.controller import E0Controller
from e0_controller.primitives import Edge, Outcome
from e0_controller.structural_entropy import structural_temperature
from e0_controller.dream_mode import (
    DreamObserver, domain_fingerprints, find_equivalences,
)

# Reuse data structures from C125
from e0_controller.explore_dict_learning import (
    PartialDictionary, make_dict_execute, GROUND_TRUTH, GROUND_TRUTH_REV,
    config_b, learn_landscape, analyze_fingerprints,
)


# ══════════════════════════════════════════════
# Node correspondence extraction with filtering
# ══════════════════════════════════════════════

def extract_best_correspondences(
    equivalences,
    known_en: Set[str],
    known_de: Set[str],
    min_votes: int = 2,
) -> List[Tuple[str, str, int, float]]:
    """Extract the best (EN, DE) node correspondences from edge equivalences.

    For each EN node, find the DE node with the most votes.  Only return
    pairs where:
    - The EN node is not already known
    - The DE node is not already known
    - The EN node is the best match for the DE node AND vice versa
      (mutual best match = bijective constraint)
    - Vote count >= min_votes

    Returns: List of (en_word, de_word, votes, avg_distance) sorted by votes desc.
    """
    # Count votes: for each equivalence a→b ↔ x→y, vote for (a,x) and (b,y)
    votes: Counter = Counter()
    dist_sums: Counter = Counter()
    dist_counts: Counter = Counter()

    for eq in equivalences:
        en_edge = eq.fp_a.edge if eq.fp_a.domain == "EN" else eq.fp_b.edge
        de_edge = eq.fp_b.edge if eq.fp_a.domain == "EN" else eq.fp_a.edge
        for en_node, de_node in [(en_edge.source, de_edge.source),
                                  (en_edge.target, de_edge.target)]:
            votes[(en_node, de_node)] += 1
            dist_sums[(en_node, de_node)] += eq.distance
            dist_counts[(en_node, de_node)] += 1

    # Find best DE match for each EN node
    best_for_en: Dict[str, Tuple[str, int]] = {}
    for (en, de), count in votes.items():
        if en in known_en or de in known_de:
            continue
        if count < min_votes:
            continue
        if en not in best_for_en or count > best_for_en[en][1]:
            best_for_en[en] = (de, count)

    # Find best EN match for each DE node
    best_for_de: Dict[str, Tuple[str, int]] = {}
    for (en, de), count in votes.items():
        if en in known_en or de in known_de:
            continue
        if count < min_votes:
            continue
        if de not in best_for_de or count > best_for_de[de][1]:
            best_for_de[de] = (en, count)

    # Keep only mutual best matches (bijective)
    results = []
    for en, (de, count) in best_for_en.items():
        if de in best_for_de and best_for_de[de][0] == en:
            avg_d = dist_sums[(en, de)] / dist_counts[(en, de)]
            results.append((en, de, count, avg_d))

    results.sort(key=lambda x: -x[2])
    return results


# ══════════════════════════════════════════════
# Single bootstrap round
# ══════════════════════════════════════════════

@dataclass
class RoundResult:
    """Result of one bootstrap round."""
    round_nr: int
    known_en: Set[str]
    known_de: Set[str]
    n_known_pairs: int
    discoveries: List[Tuple[str, str, int, float]]  # (en, de, votes, avg_dist)
    correct_discoveries: int
    wrong_discoveries: int
    # Per-unknown-pair rankings
    rankings: Dict[str, float]  # en_word → percentile rank


def run_round(
    round_nr: int,
    dicts: List[PartialDictionary],
    verbose: bool = True,
) -> RoundResult:
    """Run one learning + dream round and extract discoveries."""
    known_en = set().union(*(d.known_en for d in dicts))
    known_de = set().union(*(d.known_de for d in dicts))
    n_pairs = sum(len(d.translations) for d in dicts)

    unknown_pairs = {
        en: de for en, de in GROUND_TRUTH.items()
        if en not in known_en and de not in known_de
    }

    if verbose:
        print(f"\n{'─'*72}")
        print(f"  Round {round_nr}: {n_pairs} known pairs, "
              f"{len(unknown_pairs)} unknown")
        print(f"{'─'*72}")
        print(f"  Known EN: {sorted(known_en)}")
        print(f"  Known DE: {sorted(known_de)}")

    # Learn
    en_exec = make_dict_execute(dicts, "en")
    de_exec = make_dict_execute(dicts, "de")
    en_L = learn_landscape("english_basic", en_exec, "EN")
    de_L = learn_landscape("german_basic", de_exec, "DE")

    # Fingerprint summary
    if verbose:
        fps_en = domain_fingerprints(en_L, "EN")
        fps_de = domain_fingerprints(de_L, "DE")
        n_success_en = sum(1 for fp in fps_en if fp.quality > 0)
        n_success_de = sum(1 for fp in fps_de if fp.quality > 0)
        print(f"  EN: {n_success_en}S/{len(fps_en)-n_success_en}F  "
              f"DE: {n_success_de}S/{len(fps_de)-n_success_de}F")

    # Dream
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

    # Extract discoveries
    discoveries = extract_best_correspondences(
        equivalences, known_en, known_de, min_votes=2,
    )

    correct = 0
    wrong = 0
    if verbose and discoveries:
        print(f"\n  Discoveries (mutual best matches, ≥2 votes):")
        print(f"  {'EN':<12} {'DE':<12} {'Votes':>5} {'Avg d':>8}  Correct?")
        print(f"  {'─'*12} {'─'*12} {'─'*5} {'─'*8}  {'─'*8}")
    for en, de, votes, avg_d in discoveries:
        is_correct = GROUND_TRUTH.get(en) == de
        if is_correct:
            correct += 1
        else:
            wrong += 1
        if verbose:
            marker = "✓" if is_correct else "✗"
            print(f"  {en:<12} {de:<12} {votes:>5} {avg_d:>8.4f}  {marker}")

    if verbose:
        print(f"\n  Discovery accuracy: {correct}/{correct+wrong} "
              f"({100*correct/(correct+wrong) if (correct+wrong) else 0:.0f}%)")

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
            en_involves = (eq.fp_a.edge.source == en_word or
                          eq.fp_a.edge.target == en_word)
            de_involves = (eq.fp_b.edge.source == de_word or
                          eq.fp_b.edge.target == de_word)
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
            bar = "█" * max(1, int(pct / 2))
            quality = "★" if pct < 10 else ("●" if pct < 25 else "○")
            print(f"    {quality} {en_word:>10} ↔ {de_word:<12} {pct:>5.1f}%ile")

    return RoundResult(
        round_nr=round_nr,
        known_en=known_en,
        known_de=known_de,
        n_known_pairs=n_pairs,
        discoveries=discoveries,
        correct_discoveries=correct,
        wrong_discoveries=wrong,
        rankings=rankings,
    )


# ══════════════════════════════════════════════
# Expand dictionaries from discoveries
# ══════════════════════════════════════════════

def expand_dicts(
    base_dicts: List[PartialDictionary],
    discoveries: List[Tuple[str, str, int, float]],
    max_add: int = 5,
    min_confidence: int = 2,
) -> List[PartialDictionary]:
    """Create new dictionaries by adding top discoveries.

    Only adds discoveries that are correct according to ground truth.
    Wait — that would be cheating.  We DON'T check ground truth here.
    The system must use its own confidence (vote count) to decide.

    Strategy: Add top-N discoveries by vote count that pass the
    confidence gate.  If the system adds wrong pairs, that will degrade
    future rounds — a natural self-correcting signal.

    Args:
        min_confidence: Minimum vote count to accept a discovery.
            Default=2 (permissive). Higher values = more conservative.
    """
    # Copy existing
    new_dicts = [
        PartialDictionary(d.name, dict(d.translations))
        for d in base_dicts
    ]

    # Add a "discovered" dictionary for new pairs
    new_translations = {}
    added = 0
    for en, de, votes, avg_d in discoveries:
        if added >= max_add:
            break
        if votes < min_confidence:
            continue
        new_translations[en] = de
        added += 1

    if new_translations:
        new_dicts.append(PartialDictionary("discovered", new_translations))

    return new_dicts


# ══════════════════════════════════════════════
# Bootstrap loop
# ══════════════════════════════════════════════

def bootstrap(
    n_rounds: int = 4,
    max_add_per_round: int = 5,
    min_confidence: int = 2,
    label: str = "",
) -> None:
    """Run the iterative bootstrap loop."""
    dicts = config_b()
    all_results: List[RoundResult] = []

    for r in range(1, n_rounds + 1):
        result = run_round(r, dicts)
        all_results.append(result)

        if not result.discoveries:
            print(f"\n  No discoveries in round {r} — stopping.")
            break

        # Expand dictionaries for next round
        dicts = expand_dicts(
            dicts, result.discoveries,
            max_add=max_add_per_round,
            min_confidence=min_confidence,
        )

    # ── Summary ──────────────────────────────────────────────
    print(f"\n{'='*72}")
    print(f"  Bootstrap Summary: {len(all_results)} rounds")
    print(f"{'='*72}")

    total_correct = 0
    total_wrong = 0
    all_discovered_en: Set[str] = set()

    for r in all_results:
        correct_list = [(en, de) for en, de, v, d in r.discoveries
                        if GROUND_TRUTH.get(en) == de]
        wrong_list = [(en, de) for en, de, v, d in r.discoveries
                      if GROUND_TRUTH.get(en) != de]
        total_correct += len(correct_list)
        total_wrong += len(wrong_list)

        print(f"\n  Round {r.round_nr}: {r.n_known_pairs} known → "
              f"{r.correct_discoveries}✓ {r.wrong_discoveries}✗ discoveries")
        for en, de, v, d in r.discoveries:
            is_correct = GROUND_TRUTH.get(en) == de
            marker = "✓" if is_correct else "✗"
            new = "NEW" if en not in all_discovered_en else "dup"
            print(f"    {marker} {en}↔{de} (votes={v}, d={d:.4f}) [{new}]")
            all_discovered_en.add(en)

    # Show progression of specific pairs across rounds
    print(f"\n  Ranking progression (selected pairs):")
    tracked = ["mouth", "eye", "head", "foot", "fruit", "apple",
               "body", "good", "self", "thing"]
    print(f"  {'Pair':<20}", end="")
    for r in all_results:
        print(f"  R{r.round_nr:>1}", end="")
    print()
    for en in tracked:
        de = GROUND_TRUTH.get(en, "?")
        print(f"  {en}↔{de:<12}", end="")
        for r in all_results:
            if en in r.rankings:
                pct = r.rankings[en]
                print(f"  {pct:>4.0f}", end="")
            else:
                # Already known by this round
                print(f"    ✓", end="")
        print()

    # Final stats
    final = all_results[-1]
    final_known = final.n_known_pairs + len(final.discoveries)
    print(f"\n  Initial known pairs: {all_results[0].n_known_pairs}")
    print(f"  Final known pairs:   ~{final_known}")
    print(f"  Total discoveries:   {total_correct}✓ + {total_wrong}✗")
    print(f"  Discovery accuracy:  {100*total_correct/(total_correct+total_wrong) if (total_correct+total_wrong) else 0:.0f}%")


# ══════════════════════════════════════════════
# Main
# ══════════════════════════════════════════════

def main() -> None:
    print("=" * 72)
    print("  E₀ Iterative Dictionary Expansion (C126b)")
    print("  Comparing: ungated vs. confidence-gated bootstrap")
    print("  Starting from Config B (11 pairs)")
    print("=" * 72)

    print("\n\n" + "▓" * 72)
    print("  STRATEGY 1: Ungated (min_confidence=2, as C126)")
    print("▓" * 72)
    bootstrap(n_rounds=5, max_add_per_round=5, min_confidence=2)

    print("\n\n" + "▓" * 72)
    print("  STRATEGY 2: Confidence-Gated (min_confidence=6)")
    print("▓" * 72)
    bootstrap(n_rounds=5, max_add_per_round=5, min_confidence=6)

    print("\n" + "=" * 72)
    print("  Done — both strategies compared.")
    print("=" * 72)


if __name__ == "__main__":
    main()
