#!/usr/bin/env python3
"""
E₀ Level-2 Cumulative Vote Bootstrap (C127b)
==============================================
Replaces per-round boost/decay weight mechanics with cumulative vote
historization: weight = f(total accumulated votes across all rounds).

Key insight: cumulative votes ARE historization.
  - Correct pairs get voted for consistently → votes grow → weight grows
  - Wrong pairs get sporadic votes → votes stagnate → weight stays low
  - No artificial boost/decay constants needed
  - Weight is a direct function of accumulated evidence

Weight model:
  weight = min(cumulative_votes / VOTE_SCALE, 1.0)
  - 5 cumulative votes →  w=0.17
  - 15 cumulative votes → w=0.50
  - 30 cumulative votes → w=1.00 → promotion

Conflict handling: same EN node may map to multiple DE candidates.
Each (en, de) pair tracks its own cumulative votes independently.
The one with highest cumulative determines the entry weight.

Stale removal: entries not seen for STALE_ROUNDS consecutive rounds
AND with cumulative_votes < MIN_STALE_VOTES are removed.

Combined with Level-2 pair validation: p(SUCCESS) = w(source) × w(target).

Comparison targets:
  C127 L2 per-round: diversity preserved but oscillation, 1 confirmed
  C127b cumulative:  should stabilize oscillation, more promotions
"""

import random
import sys
import os
from collections import Counter
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
# Constants
# ══════════════════════════════════════════════

VOTE_SCALE = 30        # cumulative votes for weight=1.0
PROMOTION_VOTES = 25   # cumulative votes for confirmed
STALE_ROUNDS = 3       # rounds without rediscovery before stale check
MIN_STALE_VOTES = 5    # minimum cumulative votes to survive stale check


# ══════════════════════════════════════════════
# Cumulative Dictionary
# ══════════════════════════════════════════════

@dataclass
class CumulativeEntry:
    """A translation pair with cumulative vote historization."""
    en: str
    de: str
    tier: str               # 'canonical' | 'tentative' | 'confirmed'
    cumulative_votes: int   # total votes across all rounds
    rounds_seen: int        # how many rounds this pair was discovered
    first_round: int        # round of first discovery
    last_round: int         # round of most recent discovery

    @property
    def weight(self) -> float:
        if self.tier in ('canonical', 'confirmed'):
            return 1.0
        return min(self.cumulative_votes / VOTE_SCALE, 0.95)


@dataclass
class CumulativeDictionary:
    """Dictionary where weight = f(cumulative votes)."""
    entries: Dict[str, CumulativeEntry] = field(default_factory=dict)

    @property
    def firm_en(self) -> Set[str]:
        return {e.en for e in self.entries.values()
                if e.tier in ('canonical', 'confirmed')}

    @property
    def firm_de(self) -> Set[str]:
        return {e.de for e in self.entries.values()
                if e.tier in ('canonical', 'confirmed')}

    def word_weights(self, lang: str) -> Dict[str, float]:
        """Get {word: max_weight} map for building execute_fn.

        If multiple entries exist for the same word (conflicts),
        use the highest weight.
        """
        result: Dict[str, float] = {}
        for e in self.entries.values():
            word = e.en if lang == 'en' else e.de
            w = e.weight
            if word not in result or w > result[word]:
                result[word] = w
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
        """Accumulate votes from this round's discoveries."""

        for en, de, votes, avg_d in discoveries:
            key = f"{en}:{de}"

            if key in self.entries:
                entry = self.entries[key]
                if entry.tier == 'canonical':
                    continue
                # Accumulate votes
                entry.cumulative_votes += votes
                entry.rounds_seen += 1
                entry.last_round = round_nr
                # Check promotion
                if (entry.cumulative_votes >= PROMOTION_VOTES
                        and entry.tier == 'tentative'):
                    # Only promote if no confirmed entry exists for this EN
                    has_confirmed = any(
                        e.en == en and e.tier == 'confirmed'
                        for e in self.entries.values()
                    )
                    if not has_confirmed:
                        entry.tier = 'confirmed'
            else:
                # New discovery
                self.entries[key] = CumulativeEntry(
                    en=en, de=de, tier='tentative',
                    cumulative_votes=votes, rounds_seen=1,
                    first_round=round_nr, last_round=round_nr,
                )

        # Stale removal: entries not seen for STALE_ROUNDS
        # with cumulative_votes < MIN_STALE_VOTES
        to_remove = []
        for key, entry in self.entries.items():
            if entry.tier != 'tentative':
                continue
            rounds_since = round_nr - entry.last_round
            if (rounds_since >= STALE_ROUNDS
                    and entry.cumulative_votes < MIN_STALE_VOTES):
                to_remove.append(key)
        for key in to_remove:
            del self.entries[key]

    def best_entry_for(self, en: str) -> CumulativeEntry | None:
        """Get the entry with highest cumulative votes for a given EN word."""
        best = None
        for e in self.entries.values():
            if e.en == en and e.tier != 'canonical':
                if best is None or e.cumulative_votes > best.cumulative_votes:
                    best = e
        return best


def make_cumulative_l2_execute(cd: CumulativeDictionary, lang: str,
                               seed: int = 42):
    """Build Level-2 pair-based execute_fn with cumulative weights.

    p(SUCCESS) = w(source) × w(target), where weights come from
    cumulative vote counts.
    """
    weights = cd.word_weights(lang)
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


def init_cumulative_from_config_b() -> CumulativeDictionary:
    """Create CumulativeDictionary seeded from Config B (11 canonical)."""
    cd = CumulativeDictionary()
    for d in config_b():
        for en, de in d.translations.items():
            key = f"{en}:{de}"
            cd.entries[key] = CumulativeEntry(
                en=en, de=de, tier='canonical',
                cumulative_votes=0, rounds_seen=0,
                first_round=0, last_round=0,
            )
    return cd


# ══════════════════════════════════════════════
# Single round
# ══════════════════════════════════════════════

def run_cumulative_round(
    round_nr: int,
    cd: CumulativeDictionary,
    verbose: bool = True,
) -> Tuple[List[Tuple[str, str, int, float]], Dict[str, float]]:
    """Run one cumulative Level-2 bootstrap round."""
    firm_en = cd.firm_en
    firm_de = cd.firm_de

    unknown_pairs = {
        en: de for en, de in GROUND_TRUTH.items()
        if en not in firm_en and de not in firm_de
    }

    if verbose:
        print(f"\n{'─'*72}")
        print(f"  Round {round_nr}: {cd.tier_summary()}")
        print(f"  Firm: {sorted(firm_en)}")
        tent = sorted(
            [(e.en, e.de, f"v={e.cumulative_votes} w={e.weight:.2f}")
             for e in cd.entries.values() if e.tier == 'tentative'],
            key=lambda x: x[0],
        )
        if tent:
            print(f"  Tentative: {tent}")
        conf = [(e.en, e.de) for e in cd.entries.values()
                if e.tier == 'confirmed']
        if conf:
            print(f"  Confirmed: {conf}")
        print(f"  Unknown remaining: {len(unknown_pairs)}")
        print(f"{'─'*72}")

    # Learn with Level-2 cumulative execute_fn
    en_exec = make_cumulative_l2_execute(cd, "en", seed=42 + round_nr)
    de_exec = make_cumulative_l2_execute(cd, "de", seed=143 + round_nr)
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
        print(f"  {'EN':<12} {'DE':<12} {'Votes':>5} {'Avg d':>8}  "
              f"{'Cum':>5}  Status")
        print(f"  {'─'*12} {'─'*12} {'─'*5} {'─'*8}  {'─'*5}  {'─'*25}")
    for en, de, votes, avg_d in discoveries:
        is_correct = GROUND_TRUTH.get(en) == de
        if is_correct:
            correct += 1
        else:
            wrong += 1
        if verbose:
            marker = "✓" if is_correct else "✗"
            key = f"{en}:{de}"
            existing = cd.entries.get(key)
            if existing and existing.tier == 'tentative':
                new_cum = existing.cumulative_votes + votes
                new_w = min(new_cum / VOTE_SCALE, 0.95)
                promoted = (" → CONFIRMED"
                            if new_cum >= PROMOTION_VOTES else "")
                status = (f"cum {existing.cumulative_votes}→{new_cum} "
                          f"w={new_w:.2f}{promoted}")
            elif existing and existing.tier == 'confirmed':
                status = "already confirmed"
            else:
                w0 = min(votes / VOTE_SCALE, 0.95)
                status = f"NEW cum={votes} w={w0:.2f}"
            print(f"  {en:<12} {de:<12} {votes:>5} {avg_d:>8.4f}  "
                  f"{(existing.cumulative_votes if existing and existing.tier=='tentative' else 0)+votes:>5}  "
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
# Bootstrap loop
# ══════════════════════════════════════════════

def cumulative_bootstrap(n_rounds: int = 10) -> None:
    """Run the cumulative Level-2 bootstrap loop."""
    cd = init_cumulative_from_config_b()

    print(f"\n{'='*72}")
    print(f"  CUMULATIVE L2 BOOTSTRAP: Config B start ({cd.tier_summary()})")
    print(f"  weight = min(cumulative_votes/{VOTE_SCALE}, 0.95)")
    print(f"  promotion at {PROMOTION_VOTES} cumulative votes")
    print(f"  stale removal: {STALE_ROUNDS} rounds unseen + <{MIN_STALE_VOTES} votes")
    print(f"{'='*72}")

    round_data = []

    for r in range(1, n_rounds + 1):
        discoveries, rankings = run_cumulative_round(r, cd)

        c, t, f = cd.tier_counts()
        round_data.append((r, discoveries, rankings, (c, t, f)))

        if not discoveries:
            print(f"\n  No discoveries in round {r} — stopping.")
            break

        # Update cumulative votes
        cd.update(discoveries, r)

        # Show post-update state
        print(f"\n  After update: {cd.tier_summary()}")
        for e in sorted(cd.entries.values(),
                        key=lambda x: (
                            -{'confirmed': 2, 'canonical': 1,
                              'tentative': 0}[x.tier],
                            -x.cumulative_votes)):
            if e.tier != 'canonical':
                correct = "✓" if GROUND_TRUTH.get(e.en) == e.de else "✗"
                print(f"    {e.tier:>10} {e.en:>10}↔{e.de:<12} "
                      f"cum={e.cumulative_votes:>3} w={e.weight:.2f} "
                      f"seen={e.rounds_seen}x R{e.first_round}-R{e.last_round} "
                      f"{correct}")

    # ── Summary ──────────────────────────────
    print(f"\n{'='*72}")
    print(f"  Cumulative Bootstrap Summary: {len(round_data)} rounds")
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
        print(f"  R{r_nr:>2}", end="")
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
    print(f"  C126c L1:     53 → 1 → 1 → 1 → 1 → 1 → 1 → 1")
    print(f"  C127  L2:     64 → 52 → 99 → 154 → 116 → 135 → 77 → 68")

    # Cumulative vote leaders
    print(f"\n  Cumulative vote leaders:")
    all_tent = sorted(
        [e for e in cd.entries.values() if e.tier != 'canonical'],
        key=lambda x: -x.cumulative_votes,
    )
    for e in all_tent[:15]:
        correct = "✓" if GROUND_TRUTH.get(e.en) == e.de else "✗"
        print(f"    {e.tier:>10} {e.en:>12}↔{e.de:<14} "
              f"cum={e.cumulative_votes:>3} w={e.weight:.2f} "
              f"seen={e.rounds_seen}x R{e.first_round}-R{e.last_round} "
              f"{correct}")

    # Final dictionary state
    print(f"\n  Final dictionary: {cd.tier_summary()}")
    can = sum(1 for e in cd.entries.values() if e.tier == 'canonical')
    conf_ok = sum(1 for e in cd.entries.values()
                  if e.tier == 'confirmed' and GROUND_TRUTH.get(e.en) == e.de)
    conf_tot = sum(1 for e in cd.entries.values() if e.tier == 'confirmed')
    tent_ok = sum(1 for e in cd.entries.values()
                  if e.tier == 'tentative' and GROUND_TRUTH.get(e.en) == e.de)
    tent_tot = sum(1 for e in cd.entries.values() if e.tier == 'tentative')

    print(f"  Canonical: {can} (fixed)")
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
    print(f"  C127  weighted L2: 11→12 firm, 100% conf, diversity PRESERVED")
    print(f"  C127b cumul L2:    11→{can+conf_tot} firm, "
          f"{100*conf_ok/conf_tot if conf_tot else 0:.0f}% confirmed")


# ══════════════════════════════════════════════
# Main
# ══════════════════════════════════════════════

def main() -> None:
    print("=" * 72)
    print("  E₀ Level-2 Cumulative Vote Bootstrap (C127b)")
    print("  weight = f(cumulative votes across rounds)")
    print("  Votes ARE historization — no artificial boost/decay")
    print("  Starting from Config B (11 canonical pairs)")
    print("=" * 72)

    cumulative_bootstrap(n_rounds=10)


if __name__ == "__main__":
    main()
