#!/usr/bin/env python3
"""
E₀ Level-3 Neighborhood Consistency Bootstrap (C128)
=====================================================
Adds structural validation to cumulative voting: a candidate pair
en↔de is validated by checking whether the neighborhoods of en and de
map consistently through the current dictionary.

Core insight: "Sprache sind nicht Wörter sondern Bedeutungen, also
eigentlich selbst in einer Relation." — Meaning is relational.
A word's identity is defined by its connections, not its isolated
fingerprint. If relation maps to essen_n, then relation's neighbors
(in, with, from) should map to essen_n's neighbors (wasser, brot, ...).
They don't → wrong pair.

Mechanism:
  context_score(en, de) = bidirectional neighborhood consistency.

  Forward:  for each EN neighbor of en with known translation,
            is that translation a DE neighbor of de?
  Backward: for each DE neighbor of de with known reverse translation,
            is that reverse translation an EN neighbor of en?

  score = matches / translatable_neighbors (None if 0 translatable)

Weight model:      w = base_w × max(context_score, 0.1)
  base_w = min(cumulative_votes / VOTE_SCALE, 0.95)
  If context_score is None (no evidence), w = base_w (unchanged).

Promotion requires: cumulative_votes >= 25 AND context_score >= 50%.

Example (from C127b falsification):
  relation↔essen_n (WRONG, 36 votes in C127b):
    Backward: essen_n neighbors {wasser, brot, salz, milch}
      → reverse-translate via Config B → {water, bread, salt, milk}
      → are these EN neighbors of relation? NO → score ≈ 0%
    → weight suppressed → not promoted

  food↔essen_n (CORRECT):
    Forward: food neighbors include water, bread, salt, milk
      → translate via Config B → {wasser, brot, salz, milch}
      → are these DE neighbors of essen_n? YES → score ≈ 100%
    → weight confirmed → promoted

Combined with Level-2 pair validation: p(SUCCESS) = w(src) × w(tgt).

Comparison targets:
  C127b cumul L2:  11→15 firm, 50% confirmed — FALSIFIED
  C128  context L3: ? → should reject structural false matches
"""

import random
import sys
import os
from collections import Counter
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) + "/..")

from e0_controller.primitives import Outcome
from e0_controller.canon_loader import load_canon_spec
from e0_controller.dream_mode import domain_fingerprints, find_equivalences
from e0_controller.explore_dict_learning import (
    GROUND_TRUTH, GROUND_TRUTH_REV, config_b, learn_landscape,
)
from e0_controller.explore_bootstrap_learning import (
    extract_best_correspondences,
)


# ══════════════════════════════════════════════
# Constants
# ══════════════════════════════════════════════

VOTE_SCALE = 30         # cumulative votes for base_weight=1.0
PROMOTION_VOTES = 25    # cumulative votes needed for promotion
MIN_CONTEXT_SCORE = 0.5 # minimum context score for promotion
STALE_ROUNDS = 3        # rounds without rediscovery before stale check
MIN_STALE_VOTES = 5     # minimum cumulative votes to survive stale check


# ══════════════════════════════════════════════
# Neighborhood graph from canon topology
# ══════════════════════════════════════════════

def build_neighbor_map(canon_name: str) -> Dict[str, Set[str]]:
    """Build undirected neighbor map from static canon topology.

    The canon JSON defines directed edges (from→to). We treat them
    as undirected: if A→B exists, both A∈neighbors(B) and B∈neighbors(A).
    """
    spec = load_canon_spec(canon_name)
    neighbors: Dict[str, Set[str]] = {}
    for edge in spec.get("edges", []):
        src = edge["from"]
        tgt = edge["to"]
        neighbors.setdefault(src, set()).add(tgt)
        neighbors.setdefault(tgt, set()).add(src)
    return neighbors


# ══════════════════════════════════════════════
# Context scoring
# ══════════════════════════════════════════════

def compute_context_score(
    en_word: str, de_word: str,
    en2de: Dict[str, str], de2en: Dict[str, str],
    en_nbrs: Dict[str, Set[str]],
    de_nbrs: Dict[str, Set[str]],
) -> Tuple[Optional[float], int, int]:
    """Bidirectional neighborhood consistency score.

    Forward:  EN neighbors of en_word → translate → in DE neighbors of de_word?
    Backward: DE neighbors of de_word → reverse → in EN neighbors of en_word?

    Returns (score_or_None, matches, translatable).
    None if no translatable neighbors at all (= no structural evidence).
    """
    matches = 0
    translatable = 0

    # Forward: EN neighbors → translate → check DE neighbors
    for en_n in en_nbrs.get(en_word, set()):
        if en_n in en2de:
            translatable += 1
            if en2de[en_n] in de_nbrs.get(de_word, set()):
                matches += 1

    # Backward: DE neighbors → reverse-translate → check EN neighbors
    for de_n in de_nbrs.get(de_word, set()):
        if de_n in de2en:
            translatable += 1
            if de2en[de_n] in en_nbrs.get(en_word, set()):
                matches += 1

    if translatable == 0:
        return None, 0, 0
    return matches / translatable, matches, translatable


# ══════════════════════════════════════════════
# Context Dictionary
# ══════════════════════════════════════════════

@dataclass
class ContextEntry:
    """Translation pair with cumulative votes + context validation."""
    en: str
    de: str
    tier: str               # 'canonical' | 'tentative' | 'confirmed'
    cumulative_votes: int
    rounds_seen: int
    first_round: int
    last_round: int
    context_score: Optional[float] = None
    context_matches: int = 0
    context_translatable: int = 0

    @property
    def base_weight(self) -> float:
        """Cumulative-vote-based weight (same as C127b)."""
        if self.tier in ('canonical', 'confirmed'):
            return 1.0
        return min(self.cumulative_votes / VOTE_SCALE, 0.95)

    @property
    def effective_weight(self) -> float:
        """Weight modulated by neighborhood consistency.

        No context evidence → pure base_weight (neutral).
        Low context → weight suppressed (× 0.1 floor).
        High context → weight boosted (up to × 1.0).
        """
        if self.tier in ('canonical', 'confirmed'):
            return 1.0
        w = self.base_weight
        if self.context_score is not None:
            w *= max(self.context_score, 0.1)
        return w


@dataclass
class ContextDictionary:
    """Dictionary with cumulative votes + Level-3 neighborhood validation."""
    entries: Dict[str, ContextEntry] = field(default_factory=dict)
    en_neighbors: Dict[str, Set[str]] = field(default_factory=dict)
    de_neighbors: Dict[str, Set[str]] = field(default_factory=dict)

    @property
    def firm_en(self) -> Set[str]:
        return {e.en for e in self.entries.values()
                if e.tier in ('canonical', 'confirmed')}

    @property
    def firm_de(self) -> Set[str]:
        return {e.de for e in self.entries.values()
                if e.tier in ('canonical', 'confirmed')}

    def word_weights(self, lang: str) -> Dict[str, float]:
        """Get {word: max_effective_weight} for building execute_fn."""
        result: Dict[str, float] = {}
        for e in self.entries.values():
            word = e.en if lang == 'en' else e.de
            w = e.effective_weight
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

    def build_translation_maps(
        self,
    ) -> Tuple[Dict[str, str], Dict[str, str]]:
        """Build en→de and de→en from best entries per word.

        For each EN word, pick the entry with highest effective_weight.
        This creates the system's current best-guess bidirectional mapping.
        """
        en2de: Dict[str, str] = {}
        best_w_en: Dict[str, float] = {}
        for entry in self.entries.values():
            w = entry.effective_weight
            if entry.en not in best_w_en or w > best_w_en[entry.en]:
                en2de[entry.en] = entry.de
                best_w_en[entry.en] = w

        de2en: Dict[str, str] = {}
        best_w_de: Dict[str, float] = {}
        for entry in self.entries.values():
            w = entry.effective_weight
            if entry.de not in best_w_de or w > best_w_de[entry.de]:
                de2en[entry.de] = entry.en
                best_w_de[entry.de] = w

        return en2de, de2en

    def update_context_scores(self) -> None:
        """Recompute context scores for all non-canonical entries."""
        en2de, de2en = self.build_translation_maps()
        for entry in self.entries.values():
            if entry.tier == 'canonical':
                entry.context_score = 1.0
                continue
            score, matches, translatable = compute_context_score(
                entry.en, entry.de, en2de, de2en,
                self.en_neighbors, self.de_neighbors,
            )
            entry.context_score = score
            entry.context_matches = matches
            entry.context_translatable = translatable

    def update(self, discoveries: List[Tuple[str, str, int, float]],
               round_nr: int) -> None:
        """Accumulate votes, check promotion with context gate."""
        for en, de, votes, avg_d in discoveries:
            key = f"{en}:{de}"
            if key in self.entries:
                entry = self.entries[key]
                if entry.tier == 'canonical':
                    continue
                entry.cumulative_votes += votes
                entry.rounds_seen += 1
                entry.last_round = round_nr
                # Promotion: votes + context gate
                if (entry.cumulative_votes >= PROMOTION_VOTES
                        and entry.tier == 'tentative'):
                    has_confirmed = any(
                        e.en == en and e.tier == 'confirmed'
                        for e in self.entries.values()
                    )
                    if not has_confirmed:
                        if (entry.context_score is not None
                                and entry.context_score >= MIN_CONTEXT_SCORE):
                            entry.tier = 'confirmed'
            else:
                self.entries[key] = ContextEntry(
                    en=en, de=de, tier='tentative',
                    cumulative_votes=votes, rounds_seen=1,
                    first_round=round_nr, last_round=round_nr,
                )

        # Stale removal
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

        # Recompute context scores after update
        self.update_context_scores()


# ══════════════════════════════════════════════
# Level-2 execute_fn with context-modulated weights
# ══════════════════════════════════════════════

def make_context_l2_execute(cd: ContextDictionary, lang: str,
                            seed: int = 42):
    """Build Level-2 execute_fn using context-modulated weights.

    p(SUCCESS) = w(source) × w(target), where w = effective_weight
    includes context_score modulation.
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


# ══════════════════════════════════════════════
# Initialization
# ══════════════════════════════════════════════

def init_context_from_config_b() -> ContextDictionary:
    """Create ContextDictionary seeded from Config B + neighbor maps."""
    en_nbrs = build_neighbor_map("english_basic")
    de_nbrs = build_neighbor_map("german_basic")

    cd = ContextDictionary(en_neighbors=en_nbrs, de_neighbors=de_nbrs)
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
# Single round
# ══════════════════════════════════════════════

def run_context_round(
    round_nr: int,
    cd: ContextDictionary,
    verbose: bool = True,
) -> Tuple[List[Tuple[str, str, int, float]], Dict[str, float]]:
    """Run one Level-3 context-validated bootstrap round."""
    firm_en = cd.firm_en
    firm_de = cd.firm_de

    unknown_pairs = {
        en: de for en, de in GROUND_TRUTH.items()
        if en not in firm_en and de not in firm_de
    }

    # Update context scores BEFORE building execute_fn
    cd.update_context_scores()

    if verbose:
        print(f"\n{'─'*72}")
        print(f"  Round {round_nr}: {cd.tier_summary()}")
        print(f"  Firm: {sorted(firm_en)}")
        tent = sorted(
            [e for e in cd.entries.values() if e.tier == 'tentative'],
            key=lambda e: -e.cumulative_votes,
        )
        if tent:
            print(f"  Tentative:")
            for e in tent:
                ctx_s = (f"{e.context_score:.0%}" if e.context_score is not None
                         else "?")
                correct = "✓" if GROUND_TRUTH.get(e.en) == e.de else "✗"
                print(f"    {e.en:>10}↔{e.de:<12} cum={e.cumulative_votes:>3} "
                      f"bw={e.base_weight:.2f} ew={e.effective_weight:.2f} "
                      f"ctx={ctx_s}({e.context_matches}/{e.context_translatable}) "
                      f"{correct}")
        conf = [(e.en, e.de) for e in cd.entries.values()
                if e.tier == 'confirmed']
        if conf:
            print(f"  Confirmed: {conf}")
        print(f"  Unknown remaining: {len(unknown_pairs)}")
        print(f"{'─'*72}")

    # Learn with context-weighted Level-2 execute_fn
    en_exec = make_context_l2_execute(cd, "en", seed=42 + round_nr)
    de_exec = make_context_l2_execute(cd, "de", seed=143 + round_nr)
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
        n_distinct = (len(set(round(d, 4) for d in distances))
                      if distances else 0)
        print(f"  Equivalences: {len(equivalences)}, "
              f"distinct distances: {n_distinct}")

    # Extract discoveries — filter by FIRM only
    discoveries = extract_best_correspondences(
        equivalences, firm_en, firm_de, min_votes=2,
    )

    correct = 0
    wrong = 0
    if verbose and discoveries:
        # Compute preview context scores for display
        en2de, de2en = cd.build_translation_maps()

        print(f"\n  Discoveries (mutual best matches, ≥2 votes):")
        print(f"  {'EN':<12} {'DE':<12} {'Votes':>5} {'Avg d':>8}  "
              f"{'Ctx':>5}  Status")
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

            ctx, ctx_m, ctx_t = compute_context_score(
                en, de, en2de, de2en,
                cd.en_neighbors, cd.de_neighbors,
            )
            ctx_str = f"{ctx:.0%}" if ctx is not None else "?"

            if existing and existing.tier == 'tentative':
                new_cum = existing.cumulative_votes + votes
                new_bw = min(new_cum / VOTE_SCALE, 0.95)
                will_promote = (
                    new_cum >= PROMOTION_VOTES
                    and ctx is not None
                    and ctx >= MIN_CONTEXT_SCORE
                )
                status = (f"cum {existing.cumulative_votes}→{new_cum} "
                          f"bw={new_bw:.2f}"
                          + (" → CONFIRMED" if will_promote else ""))
            elif existing and existing.tier == 'confirmed':
                status = "already confirmed"
            else:
                w0 = min(votes / VOTE_SCALE, 0.95)
                status = f"NEW cum={votes} bw={w0:.2f}"

            print(f"  {en:<12} {de:<12} {votes:>5} {avg_d:>8.4f}  "
                  f"{ctx_str:>5}  {marker} {status}")

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
            rank = next(
                i for i, eq in enumerate(all_eqs) if eq is best) + 1
            rankings[en_word] = rank / len(all_eqs) * 100
        else:
            rankings[en_word] = 100.0

    if verbose:
        print(f"\n  Unknown pair rankings (lower = better):")
        for en_word in sorted(rankings, key=lambda w: rankings[w]):
            de_word = unknown_pairs.get(en_word, "?")
            pct = rankings[en_word]
            quality = ("★" if pct < 10
                       else ("●" if pct < 25 else "○"))
            print(f"    {quality} {en_word:>10} ↔ {de_word:<12} "
                  f"{pct:>5.1f}%ile")

    return discoveries, rankings


# ══════════════════════════════════════════════
# Bootstrap loop
# ══════════════════════════════════════════════

def context_bootstrap(n_rounds: int = 10) -> None:
    """Run the Level-3 context-validated bootstrap loop."""
    cd = init_context_from_config_b()

    # Print neighbor stats
    print(f"\n  Canon topology:")
    en_total_edges = sum(len(s) for s in cd.en_neighbors.values()) // 2
    de_total_edges = sum(len(s) for s in cd.de_neighbors.values()) // 2
    print(f"    EN: {len(cd.en_neighbors)} nodes, {en_total_edges} edges")
    print(f"    DE: {len(cd.de_neighbors)} nodes, {de_total_edges} edges")

    # Show initial Config B neighborhood coverage
    en2de, de2en = cd.build_translation_maps()
    print(f"\n  Config B neighborhood coverage:")
    for en in sorted(en2de):
        de = en2de[en]
        en_n = cd.en_neighbors.get(en, set())
        de_n = cd.de_neighbors.get(de, set())
        en_n_known = [n for n in en_n if n in en2de]
        de_n_known = [n for n in de_n if n in de2en]
        ctx, m, t = compute_context_score(
            en, de, en2de, de2en,
            cd.en_neighbors, cd.de_neighbors,
        )
        ctx_s = f"{ctx:.0%}" if ctx is not None else "?"
        correct = "✓" if GROUND_TRUTH.get(en) == de else "✗"
        print(f"    {en:>10}↔{de:<12} ctx={ctx_s:>4} "
              f"({m}/{t} matches) "
              f"EN-nbrs={len(en_n)}({len(en_n_known)}known) "
              f"DE-nbrs={len(de_n)}({len(de_n_known)}known) {correct}")

    print(f"\n{'='*72}")
    print(f"  LEVEL-3 CONTEXT BOOTSTRAP: Config B start ({cd.tier_summary()})")
    print(f"  Level-2: p(SUCCESS) = w(src) × w(tgt)")
    print(f"  Level-3: w = base_w × context_score (neighborhood consistency)")
    print(f"  Promotion: votes>={PROMOTION_VOTES} AND "
          f"context>={MIN_CONTEXT_SCORE:.0%}")
    print(f"{'='*72}")

    round_data = []

    for r in range(1, n_rounds + 1):
        discoveries, rankings = run_context_round(r, cd)

        c, t, f = cd.tier_counts()
        round_data.append((r, discoveries, rankings, (c, t, f)))

        if not discoveries:
            print(f"\n  No discoveries in round {r} — stopping.")
            break

        # Update votes + context
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
                ctx_s = (f"{e.context_score:.0%}"
                         if e.context_score is not None else "?")
                print(f"    {e.tier:>10} {e.en:>10}↔{e.de:<12} "
                      f"cum={e.cumulative_votes:>3} bw={e.base_weight:.2f} "
                      f"ew={e.effective_weight:.2f} "
                      f"ctx={ctx_s}({e.context_matches}/{e.context_translatable})"
                      f" seen={e.rounds_seen}x "
                      f"R{e.first_round}-R{e.last_round} {correct}")

    # ── Summary ──────────────────────────────
    print(f"\n{'='*72}")
    print(f"  Level-3 Context Bootstrap Summary: {len(round_data)} rounds")
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
    print(f"  C127b cumul:  64 → 38 → 55 → 83 → 111 → 66 → 55 → 66 → 59 → 73")

    # Context score analysis
    print(f"\n  Context score distribution:")
    for e in sorted(cd.entries.values(),
                    key=lambda x: (
                        -{'confirmed': 2, 'canonical': 1,
                          'tentative': 0}[x.tier],
                        -(x.context_score or 0))):
        if e.tier == 'canonical':
            continue
        correct = "✓" if GROUND_TRUTH.get(e.en) == e.de else "✗"
        ctx_s = (f"{e.context_score:.0%}" if e.context_score is not None
                 else "?")
        print(f"    {e.tier:>10} {e.en:>12}↔{e.de:<14} "
              f"cum={e.cumulative_votes:>3} ctx={ctx_s}"
              f"({e.context_matches}/{e.context_translatable}) "
              f"{correct}")

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
        print(f"  Confirmed: 0 (none promoted)")
    if tent_tot > 0:
        print(f"  Tentative: {tent_ok}/{tent_tot} correct "
              f"({100*tent_ok/tent_tot:.0f}%)")
    else:
        print(f"  Tentative: 0")
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
    print(f"  C127b cumul L2:    11→15 firm, 50% confirmed — FALSIFIED")
    print(f"  C128  context L3:  11→{can+conf_tot} firm, "
          f"{100*conf_ok/conf_tot if conf_tot else 0:.0f}% confirmed "
          f"(context-gated)")


# ══════════════════════════════════════════════
# Main
# ══════════════════════════════════════════════

def main() -> None:
    print("=" * 72)
    print("  E₀ Level-3 Neighborhood Consistency Bootstrap (C128)")
    print("  Meaning is relational — validate via structure, not just votes")
    print("  Starting from Config B (11 canonical pairs)")
    print("=" * 72)

    context_bootstrap(n_rounds=10)


if __name__ == "__main__":
    main()
