#!/usr/bin/env python3
"""
E₀ Dictionary-Mediated Language Learning (C125)
=================================================
Tests the core hypothesis from E0_LANGUAGE_LEARNING_CONCEPT_v1:
Can partial dictionaries create heterogeneous fingerprints that enable
Dream Mode to discover unknown translations?

Two configurations tested:
  Config A (nouns only): 4+4 known word pairs
  Config B (nouns+verbs): 5+6 known word pairs

The partial dictionaries serve as the ``execute_fn`` — the "engine"
that provides SUCCESS/FAILURE signals.  Without them (C124), all
fingerprints converge identically.

Expected result: Config B produces stronger discrimination than Config A.
Both should outperform the uniform-SUCCESS baseline (C124: 614 eq @ q=0.000).
"""

import sys
import os
from collections import Counter
from dataclasses import dataclass, field
from typing import Dict, List, Set, Tuple

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) + "/..")

from e0_controller.canon_loader import load_canon
from e0_controller.curriculum import CurriculumRunner
from e0_controller.controller import E0Controller
from e0_controller.primitives import Edge, Outcome
from e0_controller.structural_entropy import structural_temperature
from e0_controller.dream_mode import (
    DreamObserver, domain_fingerprints, find_equivalences,
)


# ══════════════════════════════════════════════
# Partial Dictionary
# ══════════════════════════════════════════════

@dataclass
class PartialDictionary:
    """A partial translation dictionary covering one semantic domain."""
    name: str
    translations: Dict[str, str]   # EN word → DE word

    @property
    def known_en(self) -> Set[str]:
        return set(self.translations.keys())

    @property
    def known_de(self) -> Set[str]:
        return set(self.translations.values())


def make_dict_execute(dicts: List[PartialDictionary], language: str):
    """Build an execute_fn that validates against partial dictionaries.

    Returns SUCCESS if the target node is a known word in the given
    language according to ANY dictionary.  FAILURE otherwise.
    """
    if language == "en":
        known = set().union(*(d.known_en for d in dicts))
    else:
        known = set().union(*(d.known_de for d in dicts))

    def execute(source: str, target: str) -> Outcome:
        return Outcome.SUCCESS if target in known else Outcome.FAILURE
    return execute


# ══════════════════════════════════════════════
# Ground truth: all correct EN↔DE pairs
# ══════════════════════════════════════════════

GROUND_TRUTH = {
    # L0 primitives
    "thing": "ding", "action": "handlung", "quality": "eigenschaft",
    "relation": "beziehung",
    # L1
    "body": "koerper", "food": "essen_n", "self": "selbst",
    # L2 body parts
    "head": "kopf", "hand": "hand", "arm": "arm", "foot": "fuss",
    "eye": "auge", "mouth": "mund", "ear": "ohr",
    # L2 food items
    "water": "wasser", "bread": "brot", "fruit": "frucht",
    "milk": "milch", "salt": "salz",
    # L3
    "finger": "finger", "apple": "apfel",
    "go": "gehen", "come": "kommen", "see": "sehen", "hear": "hoeren",
    "eat": "essen_v", "drink": "trinken", "give": "geben",
    "take": "nehmen", "make": "machen", "say": "sagen",
    # L4
    "good": "gut", "bad": "schlecht", "big": "gross", "small": "klein",
    "hot": "heiss", "cold": "kalt", "new": "neu", "old": "alt",
    # L5
    "in": "in_de", "with": "mit", "from": "von", "not": "nicht",
    "all": "alle",
}

# Reverse mapping
GROUND_TRUTH_REV = {v: k for k, v in GROUND_TRUTH.items()}


# ══════════════════════════════════════════════
# Dictionary configurations
# ══════════════════════════════════════════════

def config_a() -> List[PartialDictionary]:
    """Config A: nouns only (4+4 = 8 pairs)."""
    return [
        PartialDictionary("body", {
            "hand": "hand", "arm": "arm", "finger": "finger", "ear": "ohr",
        }),
        PartialDictionary("food", {
            "bread": "brot", "water": "wasser", "milk": "milch", "salt": "salz",
        }),
    ]


def config_b() -> List[PartialDictionary]:
    """Config B: nouns + verbs (5+6 = 11 pairs)."""
    return [
        PartialDictionary("body", {
            "hand": "hand", "arm": "arm", "finger": "finger", "ear": "ohr",
            "hear": "hoeren",
        }),
        PartialDictionary("food", {
            "bread": "brot", "water": "wasser", "milk": "milch", "salt": "salz",
            "eat": "essen_v", "drink": "trinken",
        }),
    ]


def config_c() -> List[PartialDictionary]:
    """Config C: Config B + body senses + actions + qualities (11+7 = 18 pairs).

    C131: Expands seed coverage to eliminate context deserts.
    Adds 3 body parts (eye, mouth, foot), 2 actions (see, go),
    2 qualities (good, big) — each in a previously unreachable cluster.
    """
    return [
        PartialDictionary("body", {
            "hand": "hand", "arm": "arm", "finger": "finger", "ear": "ohr",
            "eye": "auge", "mouth": "mund", "foot": "fuss",
            "hear": "hoeren", "see": "sehen", "go": "gehen",
        }),
        PartialDictionary("food", {
            "bread": "brot", "water": "wasser", "milk": "milch", "salt": "salz",
            "eat": "essen_v", "drink": "trinken",
        }),
        PartialDictionary("quality", {
            "good": "gut", "big": "gross",
        }),
    ]


def config_c_r2() -> List[PartialDictionary]:
    """Config C+R2: Config C + 2 relation pairs (18+2 = 20 pairs).

    Targeted fix for relation↔beziehung: seed 2 of its 5 neighbors
    (in↔in_de, with↔mit) so context scoring can validate relation.
    """
    return [
        PartialDictionary("body", {
            "hand": "hand", "arm": "arm", "finger": "finger", "ear": "ohr",
            "eye": "auge", "mouth": "mund", "foot": "fuss",
            "hear": "hoeren", "see": "sehen", "go": "gehen",
        }),
        PartialDictionary("food", {
            "bread": "brot", "water": "wasser", "milk": "milch", "salt": "salz",
            "eat": "essen_v", "drink": "trinken",
        }),
        PartialDictionary("quality", {
            "good": "gut", "big": "gross",
        }),
        PartialDictionary("relation", {
            "in": "in_de", "with": "mit",
        }),
    ]


def config_c_r5() -> List[PartialDictionary]:
    """Config C+R5: Config C + all 5 relation pairs (18+5 = 23 pairs).

    Full relation cluster seeding: in, with, from, not, all.
    Tests whether diminishing returns from overly dense seeding.
    """
    return [
        PartialDictionary("body", {
            "hand": "hand", "arm": "arm", "finger": "finger", "ear": "ohr",
            "eye": "auge", "mouth": "mund", "foot": "fuss",
            "hear": "hoeren", "see": "sehen", "go": "gehen",
        }),
        PartialDictionary("food", {
            "bread": "brot", "water": "wasser", "milk": "milch", "salt": "salz",
            "eat": "essen_v", "drink": "trinken",
        }),
        PartialDictionary("quality", {
            "good": "gut", "big": "gross",
        }),
        PartialDictionary("relation", {
            "in": "in_de", "with": "mit", "from": "von",
            "not": "nicht", "all": "alle",
        }),
    ]


# ══════════════════════════════════════════════
# Learning pipeline
# ══════════════════════════════════════════════

def learn_landscape(canon_name: str, execute_fn, label: str):
    """Run curriculum learning and return the final landscape."""
    runner = CurriculumRunner(
        canon_name,
        execute_fn,
        equilibrium_threshold=2.0,
        equilibrium_patience=3,
        max_episodes_per_turn=15,
        max_cycles_per_episode=40,
    )
    results = runner.run()
    L = runner.final_landscape
    assert L is not None, f"{label} curriculum produced no landscape"

    total_steps = sum(r.total_steps for r in results)
    T_s = structural_temperature(L.historization)
    print(f"  {label} curriculum: {len(results)} turns, {total_steps} steps, "
          f"T_s={T_s:.3f}")

    # Full-coverage exploration: ensure every edge is visited
    # The curriculum only covers ~34% of edges — the rest retain initial
    # fingerprints and the execute_fn never fires for them.
    coverage_steps = explore_full_coverage(L, execute_fn, label)
    T_s2 = structural_temperature(L.historization)
    print(f"  {label} full coverage: {coverage_steps} additional steps, "
          f"T_s={T_s2:.3f}")
    return L


def explore_full_coverage(landscape, execute_fn, label: str) -> int:
    """Run controller from every node to ensure all outgoing edges are visited.

    This is the critical step: without it, most edges retain their initial
    fingerprint (q=0.333 from U=2, F=1) and the execute_fn never fires.
    """
    total_steps = 0
    states = sorted(landscape.states)
    for start in states:
        ctrl = E0Controller(landscape, execute_fn, inscription_threshold=True)
        # Run enough cycles to visit outgoing edges from this node
        trace = ctrl.run(start, max_cycles=20)
        total_steps += len(trace.steps)
    return total_steps


# ══════════════════════════════════════════════
# Fingerprint analysis
# ══════════════════════════════════════════════

def analyze_fingerprints(landscape, label: str) -> None:
    """Show fingerprint diversity statistics."""
    fps = domain_fingerprints(landscape, label)
    qualities = [fp.quality for fp in fps]
    loads = [fp.load for fp in fps]
    inertias = [fp.inertia for fp in fps]

    unique_q = len(set(round(q, 4) for q in qualities))
    q_values = Counter(round(q, 4) for q in qualities)
    n_success = sum(1 for q in qualities if q > 0)
    n_failure = sum(1 for q in qualities if q < 0)
    n_zero = sum(1 for q in qualities if q == 0.0)

    print(f"  {label} fingerprints ({len(fps)} edges):")
    print(f"    quality:  {unique_q} distinct values, "
          f"SUCCESS={n_success}, FAILURE={n_failure}, untouched={n_zero}")
    print(f"    quality range: [{min(qualities):.4f}, {max(qualities):.4f}]")
    print(f"    load range:    [{min(loads):.1f}, {max(loads):.1f}]")
    print(f"    inertia range: [{min(inertias):.4f}, {max(inertias):.4f}]")

    # Show quality distribution
    for val, count in sorted(q_values.items()):
        bar = "█" * count
        print(f"    q={val:+.4f}: {count:2d} {bar}")


# ══════════════════════════════════════════════
# Node correspondence analysis
# ══════════════════════════════════════════════

def node_correspondences(equivalences, label: str) -> Dict[Tuple[str, str], int]:
    """Extract (EN-node, DE-node) vote counts from edge equivalences.

    For each equivalence EN:a→b ↔ DE:x→y, we vote for:
      (a, x) — sources correspond
      (b, y) — targets correspond
    """
    votes: Counter = Counter()
    for eq in equivalences:
        en_edge = eq.fp_a.edge if eq.fp_a.domain == "EN" else eq.fp_b.edge
        de_edge = eq.fp_b.edge if eq.fp_a.domain == "EN" else eq.fp_a.edge
        votes[(en_edge.source, de_edge.source)] += 1
        votes[(en_edge.target, de_edge.target)] += 1
    return dict(votes)


def evaluate_correspondences(votes: Dict[Tuple[str, str], int],
                              unknown_pairs: Dict[str, str],
                              label: str) -> None:
    """Evaluate how well node correspondences match ground truth."""
    print(f"\n  {label} — Node correspondence votes:")
    print(f"  {'EN node':<12} {'DE node':<12} {'Votes':>5}  Correct?  Unknown?")
    print(f"  {'─'*12} {'─'*12} {'─'*5}  {'─'*8}  {'─'*8}")

    # Sort by votes descending
    sorted_votes = sorted(votes.items(), key=lambda x: -x[1])

    correct = 0
    correct_unknown = 0
    shown = 0
    for (en, de), count in sorted_votes:
        is_correct = GROUND_TRUTH.get(en) == de
        is_unknown = en in unknown_pairs
        marker_c = "✓" if is_correct else "✗"
        marker_u = "?" if is_unknown else " "
        if shown < 30 or (is_unknown and is_correct):
            print(f"  {en:<12} {de:<12} {count:>5}  {marker_c:^8}  {marker_u:^8}")
        if is_correct:
            correct += 1
            if is_unknown:
                correct_unknown += 1
        shown += 1

    total = len(sorted_votes)
    print(f"\n  Total pairs voted: {total}")
    print(f"  Correct translations: {correct}/{total}")
    print(f"  Correct UNKNOWN translations: {correct_unknown}/{len(unknown_pairs)}")


# ══════════════════════════════════════════════
# Run one configuration
# ══════════════════════════════════════════════

def run_config(config_name: str, dicts: List[PartialDictionary]) -> None:
    """Run the full learning + dream pipeline for one dictionary config."""
    known_en = set().union(*(d.known_en for d in dicts))
    known_de = set().union(*(d.known_de for d in dicts))

    # Unknown noun pairs we want to discover
    unknown_pairs = {
        en: de for en, de in GROUND_TRUTH.items()
        if en not in known_en and de not in known_de
    }

    print(f"\n{'='*72}")
    print(f"  {config_name}")
    print(f"{'='*72}")
    print(f"  Known EN: {sorted(known_en)}")
    print(f"  Known DE: {sorted(known_de)}")
    print(f"  Unknown pairs to discover: {len(unknown_pairs)}")
    for en, de in sorted(unknown_pairs.items()):
        print(f"    {en} ↔ {de}")
    print()

    # Phase 1: Learn with dictionary-mediated execute_fn
    print("── Phase 1: Curriculum Learning ────────────────────────")
    en_exec = make_dict_execute(dicts, "en")
    de_exec = make_dict_execute(dicts, "de")

    en_L = learn_landscape("english_basic", en_exec, "EN")
    de_L = learn_landscape("german_basic", de_exec, "DE")
    print()

    # Phase 2: Fingerprint analysis
    print("── Phase 2: Fingerprint Analysis ───────────────────────")
    analyze_fingerprints(en_L, "EN")
    print()
    analyze_fingerprints(de_L, "DE")
    print()

    # Phase 3: Dream equivalences
    print("── Phase 3: Dream Equivalences ─────────────────────────")
    equivalences = find_equivalences(
        en_L, de_L,
        domain_a="EN", domain_b="DE",
        quantile=0.15,
    )
    print(f"  Total equivalences (bottom 15%): {len(equivalences)}")

    if equivalences:
        # Distance statistics
        distances = [eq.distance for eq in equivalences]
        print(f"  Distance range: [{min(distances):.4f}, {max(distances):.4f}]")
        unique_d = len(set(round(d, 4) for d in distances))
        print(f"  Distinct distance values: {unique_d}")

        # Show top equivalences
        print(f"\n  Top 25 edge equivalences:")
        print(f"  {'EN edge':<25} {'DE edge':<25} {'dist':>8}  Correct?")
        print(f"  {'─'*25} {'─'*25} {'─'*8}  {'─'*8}")
        for eq in equivalences[:25]:
            en_e = f"{eq.fp_a.edge.source}→{eq.fp_a.edge.target}"
            de_e = f"{eq.fp_b.edge.source}→{eq.fp_b.edge.target}"
            # Check if source↔source and target↔target are correct
            src_ok = GROUND_TRUTH.get(eq.fp_a.edge.source) == eq.fp_b.edge.source
            tgt_ok = GROUND_TRUTH.get(eq.fp_a.edge.target) == eq.fp_b.edge.target
            marker = "✓✓" if (src_ok and tgt_ok) else ("✓·" if (src_ok or tgt_ok) else "✗✗")
            print(f"  {en_e:<25} {de_e:<25} {eq.distance:>8.4f}  {marker}")

    # Phase 4: Node correspondences
    print("\n── Phase 4: Node Correspondences ──────────────────────")
    votes = node_correspondences(equivalences, config_name)
    evaluate_correspondences(votes, unknown_pairs, config_name)

    # Phase 5: Focused analysis — unknown pairs
    print(f"\n── Phase 5: Unknown Pair Rankings ─────────────────────")
    all_eqs = find_equivalences(
        en_L, de_L,
        domain_a="EN", domain_b="DE",
        quantile=1.0,  # all pairs
    )
    print(f"  Total pairwise distances: {len(all_eqs)}")
    for en_word, de_word in sorted(unknown_pairs.items()):
        # Find all equivalences involving edges from/to en_word + de_word
        relevant = []
        for eq in all_eqs:
            en_src = eq.fp_a.edge.source
            en_tgt = eq.fp_a.edge.target
            de_src = eq.fp_b.edge.source
            de_tgt = eq.fp_b.edge.target
            # Correct pairing: EN edge around en_word ↔ DE edge around de_word
            en_involves = (en_src == en_word or en_tgt == en_word)
            de_involves = (de_src == de_word or de_tgt == de_word)
            if en_involves and de_involves:
                relevant.append(eq)
        if relevant:
            best = min(relevant, key=lambda e: e.distance)
            rank = next(i for i, eq in enumerate(all_eqs) if eq is best) + 1
            total = len(all_eqs)
            percentile = rank / total * 100
            print(f"  {en_word:>10} ↔ {de_word:<10}: "
                  f"best d={best.distance:.4f}, "
                  f"rank={rank}/{total} ({percentile:.1f}%ile), "
                  f"{len(relevant)} relevant edges")
        else:
            print(f"  {en_word:>10} ↔ {de_word:<10}: no relevant equivalences found")


# ══════════════════════════════════════════════
# Main
# ══════════════════════════════════════════════

def main() -> None:
    print("=" * 72)
    print("  E₀ Dictionary-Mediated Language Learning (C125)")
    print("  Hypothesis: Partial dictionaries → heterogeneous fingerprints")
    print("  → Dream Mode discovers unknown translations")
    print("=" * 72)

    run_config("Config A: Nouns Only (8 pairs)", config_a())
    run_config("Config B: Nouns + Verbs (11 pairs)", config_b())

    print("\n" + "=" * 72)
    print("  Done — both configurations tested.")
    print("=" * 72)


if __name__ == "__main__":
    main()
