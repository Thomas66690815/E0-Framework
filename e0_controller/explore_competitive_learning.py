#!/usr/bin/env python3
"""
E₀ C129 — Competitive Exclusion
================================
Extends C128 (Level-3 Neighborhood Consistency) with competitive
exclusion: a pair can only promote to 'confirmed' if it holds the
highest effective_weight for both its EN and DE word among all
tentative entries.

Diagnostic from C128 (10 rounds):
  take↔machen  ctx=100% (4/4) WRONG — perfect score, small denominator
  bad↔alt      ctx=67%  (2/3) WRONG — above 50% threshold
  good↔ding    ctx=57%  (4/7) WRONG — but thing↔ding (ew=0.45) beats it

C128 evaluates each pair in isolation. C129 asks:
  "Is this the BEST candidate for both words, or does a rival exist?"

Mechanism:
  C128: promotion requires  votes ≥ 25  AND  ctx ≥ 50%
  C129: additionally        AND  best_for_en  AND  best_for_de

  best_for_X: among all tentative entries sharing this X word,
  the entry must have the highest effective_weight.

This is parameterless — purely structural.

Design principle (E₀):
  Unterscheidung durch Kontrast. Identity emerges from contrast.
  A translation is validated not only by its own evidence but by
  the absence of better alternatives. Ambiguity = uncertainty.

Expected:
  - Identical outcome to C128 when no competition exists
  - Blocks wrong pairs that compete with better-embedded rivals
  - May block correct pairs too (acceptable: system admits
    uncertainty rather than guessing)

Note on output:
  Round output reuses C128's run_context_round (verbose).
  "→ CONFIRMED" predictions are C128's — competitive blocks
  appear separately after each update.
"""

import sys
import os
from collections import defaultdict
from dataclasses import dataclass
from typing import Dict, List, Optional, Set, Tuple

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) + "/..")

from e0_controller.explore_dict_learning import GROUND_TRUTH, config_b
from e0_controller.explore_level3_learning import (
    ContextDictionary, ContextEntry,
    build_neighbor_map, compute_context_score,
    make_context_l2_execute, run_context_round,
    VOTE_SCALE, PROMOTION_VOTES, MIN_CONTEXT_SCORE,
    STALE_ROUNDS, MIN_STALE_VOTES,
)


# ══════════════════════════════════════════════
# Competitive Dictionary
# ══════════════════════════════════════════════

@dataclass
class CompetitiveDictionary(ContextDictionary):
    """ContextDictionary with competitive-exclusion promotion gate.

    A pair en↔de can only promote if it has the highest
    effective_weight among all tentative entries for both
    its EN word and its DE word.
    """

    def is_best_for_word(
        self, entry: ContextEntry, lang: str,
    ) -> Tuple[bool, Optional[ContextEntry]]:
        """Is this the best tentative candidate for its word?

        Returns (is_best, best_rival_or_None).
        Only compares against other tentative entries.
        """
        word = entry.en if lang == 'en' else entry.de
        best_rival = None
        for e in self.entries.values():
            if e is entry or e.tier != 'tentative':
                continue
            if (e.en if lang == 'en' else e.de) != word:
                continue
            if e.effective_weight > entry.effective_weight:
                if (best_rival is None
                        or e.effective_weight > best_rival.effective_weight):
                    best_rival = e
        return (best_rival is None), best_rival

    def update(
        self, discoveries: List[Tuple[str, str, int, float]],
        round_nr: int,
    ) -> None:
        """Accumulate votes with competitive-exclusion promotion gate.

        Same as C128's update, but promotion additionally requires
        being the best candidate for both EN and DE word.
        """
        self._blocked: List[Tuple[str, str, str]] = []

        for en, de, votes, avg_d in discoveries:
            key = f"{en}:{de}"
            if key in self.entries:
                entry = self.entries[key]
                if entry.tier == 'canonical':
                    continue
                entry.cumulative_votes += votes
                entry.rounds_seen += 1
                entry.last_round = round_nr
                if (entry.cumulative_votes >= PROMOTION_VOTES
                        and entry.tier == 'tentative'):
                    has_confirmed = any(
                        e.en == en and e.tier == 'confirmed'
                        for e in self.entries.values()
                    )
                    if not has_confirmed:
                        ctx_ok = (entry.context_score is not None
                                  and entry.context_score >= MIN_CONTEXT_SCORE)
                        if ctx_ok:
                            best_en, rival_en = self.is_best_for_word(
                                entry, 'en')
                            best_de, rival_de = self.is_best_for_word(
                                entry, 'de')
                            if best_en and best_de:
                                entry.tier = 'confirmed'
                            else:
                                reasons = []
                                if not best_en and rival_en:
                                    reasons.append(
                                        f"EN rival: {rival_en.en}↔"
                                        f"{rival_en.de} "
                                        f"ew={rival_en.effective_weight:.3f}")
                                if not best_de and rival_de:
                                    reasons.append(
                                        f"DE rival: {rival_de.en}↔"
                                        f"{rival_de.de} "
                                        f"ew={rival_de.effective_weight:.3f}")
                                self._blocked.append(
                                    (en, de, "; ".join(reasons)))
            else:
                self.entries[key] = ContextEntry(
                    en=en, de=de, tier='tentative',
                    cumulative_votes=votes, rounds_seen=1,
                    first_round=round_nr, last_round=round_nr,
                )

        # Stale removal (same as C128)
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

        self.update_context_scores()


# ══════════════════════════════════════════════
# Initialization
# ══════════════════════════════════════════════

def init_competitive_from_config_b() -> CompetitiveDictionary:
    """Create CompetitiveDictionary seeded from Config B + neighbor maps."""
    en_nbrs = build_neighbor_map("english_basic")
    de_nbrs = build_neighbor_map("german_basic")
    cd = CompetitiveDictionary(en_neighbors=en_nbrs, de_neighbors=de_nbrs)
    for d in config_b():
        for en, de in d.translations.items():
            key = f"{en}:{de}"
            cd.entries[key] = ContextEntry(
                en=en, de=de, tier='canonical',
                cumulative_votes=0, rounds_seen=0,
                first_round=0, last_round=0,
                context_score=1.0,
            )
    return cd


# ══════════════════════════════════════════════
# Bootstrap loop
# ══════════════════════════════════════════════

def competitive_bootstrap(n_rounds: int = 10) -> None:
    """Run C129 competitive-exclusion bootstrap."""
    cd = init_competitive_from_config_b()

    en_total = sum(len(s) for s in cd.en_neighbors.values()) // 2
    de_total = sum(len(s) for s in cd.de_neighbors.values()) // 2
    print(f"\n  Canon: EN {len(cd.en_neighbors)}n/{en_total}e, "
          f"DE {len(cd.de_neighbors)}n/{de_total}e")

    print(f"\n{'='*72}")
    print(f"  C129 COMPETITIVE EXCLUSION BOOTSTRAP ({cd.tier_summary()})")
    print(f"  C128 gates: votes≥{PROMOTION_VOTES} AND ctx≥{MIN_CONTEXT_SCORE:.0%}")
    print(f"  C129 adds:  AND best_for_en AND best_for_de")
    print(f"  No new parameters — purely structural")
    print(f"{'='*72}")

    round_data = []
    all_blocked = []

    for r in range(1, n_rounds + 1):
        discoveries, rankings = run_context_round(r, cd)

        c, t, f = cd.tier_counts()
        round_data.append((r, discoveries, rankings, (c, t, f)))

        if not discoveries:
            print(f"\n  No discoveries in round {r} — stopping.")
            break

        cd.update(discoveries, r)

        # Report competitive blocks
        if cd._blocked:
            print(f"\n  ⚠ COMPETITIVE BLOCK: {len(cd._blocked)} promotion(s) "
                  f"blocked:")
            for en, de, reason in cd._blocked:
                correct = "✓" if GROUND_TRUTH.get(en) == de else "✗"
                print(f"    {en}↔{de} {correct} — {reason}")
                all_blocked.append((r, en, de, reason,
                                    GROUND_TRUTH.get(en) == de))

        # Post-update state with competition annotations
        print(f"\n  After update: {cd.tier_summary()}")
        for e in sorted(cd.entries.values(),
                        key=lambda x: (
                            -{'confirmed': 2, 'canonical': 1,
                              'tentative': 0}[x.tier],
                            -x.cumulative_votes)):
            if e.tier != 'canonical':
                correct = "✓" if GROUND_TRUTH.get(e.en) == e.de else "✗"
                ctx_s = (f"{e.context_score:.0%}"
                         if e.context_score is not None else "?")
                comp = ""
                if e.tier == 'tentative':
                    b_en, r_en = cd.is_best_for_word(e, 'en')
                    b_de, r_de = cd.is_best_for_word(e, 'de')
                    if not b_en and r_en:
                        comp += f" ≺{r_en.de}"
                    if not b_de and r_de:
                        comp += f" ≺{r_de.en}"
                print(f"    {e.tier:>10} {e.en:>10}↔{e.de:<12} "
                      f"cum={e.cumulative_votes:>3} "
                      f"ew={e.effective_weight:.2f} "
                      f"ctx={ctx_s}({e.context_matches}/"
                      f"{e.context_translatable}) "
                      f"R{e.first_round}-R{e.last_round} "
                      f"{correct}{comp}")

    # ── Competition Map ──────────────────────
    print(f"\n{'='*72}")
    print(f"  Competition Map")
    print(f"{'='*72}")

    en_cands = defaultdict(list)
    de_cands = defaultdict(list)
    for e in cd.entries.values():
        if e.tier == 'tentative':
            en_cands[e.en].append(e)
            de_cands[e.de].append(e)

    gt_rev = {v: k for k, v in GROUND_TRUTH.items()}

    contested_en = {w: sorted(es, key=lambda x: -x.effective_weight)
                    for w, es in en_cands.items() if len(es) > 1}
    contested_de = {w: sorted(es, key=lambda x: -x.effective_weight)
                    for w, es in de_cands.items() if len(es) > 1}

    if contested_en:
        print(f"\n  EN words with multiple DE candidates:")
        for en in sorted(contested_en):
            entries = contested_en[en]
            c_de = GROUND_TRUTH.get(en, "?")
            print(f"    {en} (→{c_de}):")
            for i, e in enumerate(entries):
                mark = "✓" if e.de == c_de else "✗"
                ctx_s = (f"{e.context_score:.0%}"
                         if e.context_score is not None else "?")
                tag = " ← BEST" if i == 0 else ""
                print(f"      {e.de:<12} ew={e.effective_weight:.3f} "
                      f"ctx={ctx_s}"
                      f"({e.context_matches}/{e.context_translatable}) "
                      f"cum={e.cumulative_votes} {mark}{tag}")

    if contested_de:
        print(f"\n  DE words with multiple EN candidates:")
        for de in sorted(contested_de):
            entries = contested_de[de]
            c_en = gt_rev.get(de, "?")
            print(f"    {de} (←{c_en}):")
            for i, e in enumerate(entries):
                mark = "✓" if e.en == c_en else "✗"
                ctx_s = (f"{e.context_score:.0%}"
                         if e.context_score is not None else "?")
                tag = " ← BEST" if i == 0 else ""
                print(f"      {e.en:<12} ew={e.effective_weight:.3f} "
                      f"ctx={ctx_s}"
                      f"({e.context_matches}/{e.context_translatable}) "
                      f"cum={e.cumulative_votes} {mark}{tag}")

    if not contested_en and not contested_de:
        print(f"\n  No contested words.")

    # ── Summary ──────────────────────────────
    print(f"\n{'='*72}")
    print(f"  C129 Summary: {len(round_data)} rounds")
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

    # Final stats
    can = sum(1 for e in cd.entries.values() if e.tier == 'canonical')
    conf_ok = sum(1 for e in cd.entries.values()
                  if e.tier == 'confirmed' and GROUND_TRUTH.get(e.en) == e.de)
    conf_tot = sum(1 for e in cd.entries.values() if e.tier == 'confirmed')
    tent_ok = sum(1 for e in cd.entries.values()
                  if e.tier == 'tentative' and GROUND_TRUTH.get(e.en) == e.de)
    tent_tot = sum(1 for e in cd.entries.values() if e.tier == 'tentative')

    print(f"\n  Canonical: {can} (fixed)")
    if conf_tot > 0:
        print(f"  Confirmed: {conf_ok}/{conf_tot} correct "
              f"({100*conf_ok/conf_tot:.0f}%)")
    else:
        print(f"  Confirmed: 0")
    if tent_tot > 0:
        print(f"  Tentative: {tent_ok}/{tent_tot} correct "
              f"({100*tent_ok/tent_tot:.0f}%)")
    else:
        print(f"  Tentative: 0")
    print(f"  Firm total: {can + conf_tot} pairs")

    if total_correct + total_wrong > 0:
        print(f"  Discovery accuracy: "
              f"{total_correct}/{total_correct+total_wrong} "
              f"({100*total_correct/(total_correct+total_wrong):.0f}%)")

    # Competitive stats
    print(f"\n  ── Competitive Exclusion Stats ──")
    print(f"  Total promotions blocked: {len(all_blocked)}")
    if all_blocked:
        b_wrong = sum(1 for _, _, _, _, corr in all_blocked if not corr)
        b_correct = sum(1 for _, _, _, _, corr in all_blocked if corr)
        print(f"    Wrong pairs blocked:   {b_wrong}")
        print(f"    Correct pairs blocked: {b_correct}")
        for r_nr, en, de, reason, corr in all_blocked:
            mark = "✓" if corr else "✗"
            print(f"    R{r_nr}: {en}↔{de} {mark} — {reason}")
    print(f"  Contested EN words: {len(contested_en)}")
    print(f"  Contested DE words: {len(contested_de)}")

    # Comparison
    print(f"\n  ── Comparison ──")
    print(f"  C127b cumul L2:    11→15 firm, 50% confirmed — FALSIFIED")
    print(f"  C128  context L3:  11→15 firm, 100% confirmed (context-gated)")
    print(f"  C129  competitive: 11→{can+conf_tot} firm, "
          f"{100*conf_ok/conf_tot if conf_tot else 0:.0f}% confirmed "
          f"(context + competition)")
    if all_blocked:
        b_wrong = sum(1 for _, _, _, _, c in all_blocked if not c)
        print(f"  Delta: {len(all_blocked)} blocked, "
              f"{b_wrong} correctly prevented")
    else:
        print(f"  Delta: identical outcome (no competition at "
              f"promotion threshold)")


# ══════════════════════════════════════════════
# Main
# ══════════════════════════════════════════════

def main() -> None:
    print("=" * 72)
    print("  E₀ C129 — Competitive Exclusion")
    print("  A translation is only confirmed if no better rival exists")
    print("  Starting from Config B (11 canonical pairs)")
    print("=" * 72)

    competitive_bootstrap(n_rounds=10)


if __name__ == "__main__":
    main()
