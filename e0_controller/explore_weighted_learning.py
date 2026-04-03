#!/usr/bin/env python3
"""
E₀ Weighted Dictionary Bootstrap (C126c)
==========================================
Tests graduated expansion: tentative entries participate stochastically
in execute_fn (weight < 1.0), can be promoted to confirmed (weight=1.0)
or decay and be removed.

Architecture:
  - canonical entries: original dictionary, weight=1.0, permanent
  - tentative entries: discovered pairs, weight=0.2-0.7, stochastic SUCCESS
  - confirmed entries: promoted tentative, weight=1.0, permanent

Key mechanism: stochastic execute_fn creates intermediate fingerprints
that dream can still use for rediscovery validation.  Correct tentative
pairs create consistent intermediate patterns → rediscovered → promoted.
Wrong tentative pairs create inconsistent patterns → not rediscovered → decay.

Discovery filtering: only FIRM (canonical+confirmed) words are filtered
out.  Tentative words remain eligible for rediscovery — this is the
mechanism that allows weight accumulation across rounds.

Weight mechanics:
  - Initial weight = min(votes/10, 0.7)  → 2 votes=0.2, 8 votes=0.7
  - Rediscovery boost: +0.15 per round
  - Decay: -0.1 per round not seen
  - Promotion threshold: weight ≥ 0.8 → confirmed (weight=1.0)
  - Removal: weight ≤ 0 → deleted

Success criteria (from user spec):
  1. Growth > gated C126b (>16 pairs)
  2. Accuracy > ungated C126 (>40%)
  3. Rankings stable (no degradation)
  4. Saturation later/softer
  5. Weak-but-correct pairs (e.g. foot↔fuss) can work their way up
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


# ══════════════════════════════════════════════
# Weighted Dictionary
# ══════════════════════════════════════════════

@dataclass
class WeightedEntry:
    """A single translation pair with graduated confidence."""
    en: str
    de: str
    tier: str           # 'canonical' | 'tentative' | 'confirmed'
    weight: float       # 1.0 for canonical/confirmed, <1.0 for tentative
    rounds_seen: int = 1
    total_votes: int = 0
    last_round: int = 0


PROMOTION_THRESHOLD = 0.8
DECAY_RATE = 0.1
BOOST_PER_REDISCOVERY = 0.15
MAX_INITIAL_WEIGHT = 0.7


@dataclass
class WeightedDictionary:
    """Dictionary with graduated entry confidence."""
    entries: Dict[str, WeightedEntry] = field(default_factory=dict)

    @property
    def firm_en(self) -> Set[str]:
        """Canonical + confirmed = firmly established EN words."""
        return {e.en for e in self.entries.values()
                if e.tier in ('canonical', 'confirmed')}

    @property
    def firm_de(self) -> Set[str]:
        return {e.de for e in self.entries.values()
                if e.tier in ('canonical', 'confirmed')}

    def word_weights(self, lang: str) -> Dict[str, float]:
        """Get {word: weight} map for building execute_fn."""
        result = {}
        for e in self.entries.values():
            word = e.en if lang == 'en' else e.de
            result[word] = e.weight
        return result

    def tier_counts(self) -> Tuple[int, int, int]:
        c = sum(1 for e in self.entries.values() if e.tier == 'canonical')
        t = sum(1 for e in self.entries.values() if e.tier == 'tentative')
        f = sum(1 for e in self.entries.values() if e.tier == 'confirmed')
        return c, t, f

    def tier_summary(self) -> str:
        c, t, f = self.tier_counts()
        return f"{c}C + {t}T + {f}F = {c+t+f} total"

    def update(self, discoveries: List[Tuple[str, str, int, float]],
               round_nr: int) -> None:
        """Update weights based on this round's discoveries."""
        seen_en = set()

        for en, de, votes, avg_d in discoveries:
            seen_en.add(en)

            if en in self.entries:
                entry = self.entries[en]
                if entry.tier == 'canonical':
                    continue
                if entry.de == de:
                    # Same pair rediscovered → strengthen
                    entry.weight = min(entry.weight + BOOST_PER_REDISCOVERY,
                                       1.0)
                    entry.rounds_seen += 1
                    entry.total_votes += votes
                    entry.last_round = round_nr
                    # Promote?
                    if (entry.weight >= PROMOTION_THRESHOLD
                            and entry.tier == 'tentative'):
                        entry.tier = 'confirmed'
                        entry.weight = 1.0
                else:
                    # Conflict: different DE for same EN
                    if entry.tier == 'confirmed':
                        continue  # don't override confirmed
                    if votes > entry.total_votes or entry.weight < 0.01:
                        self.entries[en] = WeightedEntry(
                            en, de, 'tentative',
                            weight=min(votes / 10, MAX_INITIAL_WEIGHT),
                            rounds_seen=1, total_votes=votes,
                            last_round=round_nr,
                        )
            else:
                # New discovery → tentative
                self.entries[en] = WeightedEntry(
                    en, de, 'tentative',
                    weight=min(votes / 10, MAX_INITIAL_WEIGHT),
                    rounds_seen=1, total_votes=votes,
                    last_round=round_nr,
                )

        # Decay tentative entries not rediscovered this round
        to_remove = []
        for en, entry in self.entries.items():
            if entry.tier != 'tentative':
                continue
            if en not in seen_en:
                entry.weight -= DECAY_RATE
                if entry.weight < 0.01:
                    to_remove.append(en)
        for en in to_remove:
            del self.entries[en]

        # Final cleanup: remove any zero-weight zombies
        zombies = [en for en, e in self.entries.items()
                   if e.tier == 'tentative' and e.weight < 0.01]
        for en in zombies:
            del self.entries[en]


def make_weighted_execute(wd: WeightedDictionary, lang: str,
                          seed: int = 42):
    """Build execute_fn with stochastic SUCCESS for tentative entries.

    Canonical/confirmed words → always SUCCESS.
    Tentative words → SUCCESS with probability = weight.
    Unknown words → always FAILURE.
    """
    weights = wd.word_weights(lang)
    rng = random.Random(seed)

    def execute(source: str, target: str) -> Outcome:
        w = weights.get(target)
        if w is None:
            return Outcome.FAILURE
        if w >= 1.0:
            return Outcome.SUCCESS
        return Outcome.SUCCESS if rng.random() < w else Outcome.FAILURE

    return execute


def init_from_config_b() -> WeightedDictionary:
    """Create WeightedDictionary seeded from Config B (11 canonical pairs)."""
    wd = WeightedDictionary()
    for d in config_b():
        for en, de in d.translations.items():
            wd.entries[en] = WeightedEntry(
                en, de, 'canonical', weight=1.0,
                rounds_seen=0, total_votes=0, last_round=0,
            )
    return wd


# ══════════════════════════════════════════════
# Single weighted round
# ══════════════════════════════════════════════

def run_weighted_round(
    round_nr: int,
    wd: WeightedDictionary,
    verbose: bool = True,
) -> Tuple[List[Tuple[str, str, int, float]], Dict[str, float]]:
    """Run one weighted bootstrap round.

    Returns (discoveries, rankings).
    discoveries = [(en, de, votes, avg_dist), ...]
    rankings = {en_word: percentile_rank}
    """
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

    # Learn with weighted execute_fn (different seeds per round+language)
    en_exec = make_weighted_execute(wd, "en", seed=42 + round_nr)
    de_exec = make_weighted_execute(wd, "de", seed=143 + round_nr)
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

    # Extract discoveries — filter by FIRM only (tentative stays discoverable)
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

    # Rankings for unknown pairs (using full equivalence set)
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
# Weighted bootstrap loop
# ══════════════════════════════════════════════

def weighted_bootstrap(n_rounds: int = 8) -> None:
    """Run the weighted bootstrap loop."""
    wd = init_from_config_b()

    print(f"\n{'='*72}")
    print(f"  WEIGHTED BOOTSTRAP: Config B start ({wd.tier_summary()})")
    print(f"  promotion={PROMOTION_THRESHOLD}, decay={DECAY_RATE}, "
          f"boost={BOOST_PER_REDISCOVERY}")
    print(f"  initial weight = min(votes/10, {MAX_INITIAL_WEIGHT})")
    print(f"{'='*72}")

    round_data = []  # (round_nr, discoveries, rankings, tier_snapshot)

    for r in range(1, n_rounds + 1):
        discoveries, rankings = run_weighted_round(r, wd)

        c, t, f = wd.tier_counts()
        round_data.append((r, discoveries, rankings, (c, t, f)))

        if not discoveries:
            print(f"\n  No discoveries in round {r} — stopping.")
            break

        # Update weights (this modifies wd in place)
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
    print(f"  Weighted Bootstrap Summary: {len(round_data)} rounds")
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

    # Comparison reference
    print(f"\n  ── Comparison ──")
    print(f"  C126  ungated: 11→25 known, 40% accuracy, rankings DEGRADE")
    print(f"  C126b gated:   11→16 known, 100% added, rankings STABLE")
    print(f"  C126c weighted: 11→{can+conf_tot} firm, "
          f"{100*conf_ok/conf_tot if conf_tot else 0:.0f}% confirmed accuracy")


# ══════════════════════════════════════════════
# Main
# ══════════════════════════════════════════════

def main() -> None:
    print("=" * 72)
    print("  E₀ Weighted Dictionary Bootstrap (C126c)")
    print("  Graduated expansion: canonical → tentative → confirmed")
    print("  Stochastic execute_fn for tentative entries")
    print("  Starting from Config B (11 canonical pairs)")
    print("=" * 72)

    weighted_bootstrap(n_rounds=8)


if __name__ == "__main__":
    main()
