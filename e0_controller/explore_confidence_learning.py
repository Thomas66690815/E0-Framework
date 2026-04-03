#!/usr/bin/env python3
"""
E₀ C130 — Confidence-Weighted Edge-Role Matching
==================================================
Uses E₀'s existing per-edge data (quality, load, inertia) that the
pipeline has been computing but discarding.

Problem diagnosed in C129:
  The pipeline uses domain_fingerprints → find_equivalences → votes.
  Each Equivalence carries confidence = max(0, 1-distance).
  extract_best_correspondences throws this away: votes += 1.
  A near-perfect match and a barely-qualifying match count the same.

C130 changes two things:

1. Confidence-Weighted Votes
   Instead of  votes[(en, de)] += 1
   we use      votes[(en, de)] += equivalence.confidence
   This uses the 3D edge-role signature (quality, load, inertia) that
   E₀ already computes. High-quality role matches weight more.

2. Edge-Quality Context Score
   C128's context_score asks: "do the NEIGHBORS match?"
   C130 also asks: "do the EDGES TO those neighbors have the same ROLE?"
   If food→water has quality=+0.8 and essen_n→wasser has quality=+0.8,
   that's stronger evidence than if the qualities diverge.

No new parameters. Uses only existing E₀ signals.

Expected:
  - Better separation between correct and wrong pairs
  - Higher confidence for structurally consistent matches
  - Wrong pairs with accidental vote counts get diluted
"""

import random
import sys
import os
from collections import Counter, defaultdict
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
    GROUND_TRUTH, GROUND_TRUTH_REV, config_b, learn_landscape,
)
from e0_controller.explore_level3_learning import (
    ContextEntry, build_neighbor_map,
    make_context_l2_execute,
    VOTE_SCALE, PROMOTION_VOTES, MIN_CONTEXT_SCORE,
    STALE_ROUNDS, MIN_STALE_VOTES,
)


# ══════════════════════════════════════════════
# Confidence-weighted correspondence extraction
# ══════════════════════════════════════════════

def extract_confidence_correspondences(
    equivalences: List[Equivalence],
    known_en: Set[str],
    known_de: Set[str],
    min_confidence: float = 0.5,
) -> List[Tuple[str, str, float, float, int]]:
    """Extract correspondences weighted by equivalence confidence.

    Instead of counting votes (each equivalence = 1),
    weight by confidence = max(0, 1 - distance).

    Returns: List of (en, de, confidence_sum, avg_distance, raw_votes)
    sorted by confidence_sum descending.
    """
    conf_sums: Dict[Tuple[str, str], float] = defaultdict(float)
    dist_sums: Dict[Tuple[str, str], float] = defaultdict(float)
    vote_counts: Dict[Tuple[str, str], int] = defaultdict(int)

    for eq in equivalences:
        en_fp = eq.fp_a if eq.fp_a.domain == "EN" else eq.fp_b
        de_fp = eq.fp_b if eq.fp_a.domain == "EN" else eq.fp_a
        en_edge = en_fp.edge
        de_edge = de_fp.edge

        for en_node, de_node in [(en_edge.source, de_edge.source),
                                  (en_edge.target, de_edge.target)]:
            if en_node in known_en or de_node in known_de:
                continue
            conf_sums[(en_node, de_node)] += eq.confidence
            dist_sums[(en_node, de_node)] += eq.distance
            vote_counts[(en_node, de_node)] += 1

    # Mutual best match (by confidence sum, not raw votes)
    best_for_en: Dict[str, Tuple[str, float]] = {}
    for (en, de), conf in conf_sums.items():
        if conf < min_confidence:
            continue
        if en not in best_for_en or conf > best_for_en[en][1]:
            best_for_en[en] = (de, conf)

    best_for_de: Dict[str, Tuple[str, float]] = {}
    for (en, de), conf in conf_sums.items():
        if conf < min_confidence:
            continue
        if de not in best_for_de or conf > best_for_de[de][1]:
            best_for_de[de] = (en, conf)

    results = []
    for en, (de, conf) in best_for_en.items():
        if de in best_for_de and best_for_de[de][0] == en:
            avg_d = dist_sums[(en, de)] / vote_counts[(en, de)]
            results.append((en, de, conf, avg_d, vote_counts[(en, de)]))

    results.sort(key=lambda x: -x[2])
    return results


# ══════════════════════════════════════════════
# Edge-Role Context Score
# ══════════════════════════════════════════════

def compute_role_context_score(
    en_word: str, de_word: str,
    en2de: Dict[str, str], de2en: Dict[str, str],
    en_nbrs: Dict[str, Set[str]],
    de_nbrs: Dict[str, Set[str]],
    en_landscape: Landscape,
    de_landscape: Landscape,
    mu: float = 5.0,
) -> Tuple[Optional[float], int, int, Optional[float]]:
    """Context score enhanced with edge-role matching.

    Two components:
    1. Topology match (C128): do neighbors map to neighbors?
    2. Role match (C130): do the EDGES to those neighbors have
       similar quality/load/inertia profiles?

    Returns (topo_score, matches, translatable, role_score).
    role_score is the average fingerprint similarity for matched edges.
    None if no translatable neighbors.
    """
    matches = 0
    translatable = 0
    role_similarities = []

    en_hist = en_landscape.historization
    de_hist = de_landscape.historization

    # Forward: EN neighbors → translate → check DE neighbors
    for en_n in en_nbrs.get(en_word, set()):
        if en_n in en2de:
            translatable += 1
            de_mapped = en2de[en_n]
            if de_mapped in de_nbrs.get(de_word, set()):
                matches += 1
                # Edge role comparison: en_word→en_n vs de_word→de_mapped
                en_edge = Edge(en_word, en_n)
                de_edge = Edge(de_word, de_mapped)
                en_fp = EdgeFingerprint(
                    domain="EN", edge=en_edge,
                    quality=en_hist.trace_quality(en_edge),
                    load=en_hist.trace_load(en_edge),
                    inertia=en_hist.inertia_factor(en_edge),
                )
                de_fp = EdgeFingerprint(
                    domain="DE", edge=de_edge,
                    quality=de_hist.trace_quality(de_edge),
                    load=de_hist.trace_load(de_edge),
                    inertia=de_hist.inertia_factor(de_edge),
                )
                d = fingerprint_distance(en_fp, de_fp, mu=mu)
                role_similarities.append(max(0.0, 1.0 - d))

    # Backward: DE neighbors → reverse-translate → check EN neighbors
    for de_n in de_nbrs.get(de_word, set()):
        if de_n in de2en:
            translatable += 1
            en_mapped = de2en[de_n]
            if en_mapped in en_nbrs.get(en_word, set()):
                matches += 1
                de_edge = Edge(de_word, de_n)
                en_edge = Edge(en_word, en_mapped)
                en_fp = EdgeFingerprint(
                    domain="EN", edge=en_edge,
                    quality=en_hist.trace_quality(en_edge),
                    load=en_hist.trace_load(en_edge),
                    inertia=en_hist.inertia_factor(en_edge),
                )
                de_fp = EdgeFingerprint(
                    domain="DE", edge=de_edge,
                    quality=de_hist.trace_quality(de_edge),
                    load=de_hist.trace_load(de_edge),
                    inertia=de_hist.inertia_factor(de_edge),
                )
                d = fingerprint_distance(en_fp, de_fp, mu=mu)
                role_similarities.append(max(0.0, 1.0 - d))

    if translatable == 0:
        return None, 0, 0, None

    topo_score = matches / translatable
    role_score = (sum(role_similarities) / len(role_similarities)
                  if role_similarities else None)

    return topo_score, matches, translatable, role_score


# ══════════════════════════════════════════════
# Confidence Dictionary
# ══════════════════════════════════════════════

@dataclass
class ConfidenceEntry:
    """Translation pair with confidence-weighted votes + role matching."""
    en: str
    de: str
    tier: str                # 'canonical' | 'tentative' | 'confirmed'
    cumulative_conf: float   # C130: confidence sum (not integer votes)
    raw_votes: int           # for comparison with C128
    rounds_seen: int
    first_round: int
    last_round: int
    topo_score: Optional[float] = None
    role_score: Optional[float] = None
    context_matches: int = 0
    context_translatable: int = 0

    @property
    def base_weight(self) -> float:
        if self.tier in ('canonical', 'confirmed'):
            return 1.0
        return min(self.cumulative_conf / VOTE_SCALE, 0.95)

    @property
    def combined_context(self) -> Optional[float]:
        """Combined topology + role score.

        If both available: geometric mean (both must be good).
        If only topology: use topology alone (C128 fallback).
        """
        if self.topo_score is None:
            return None
        if self.role_score is not None:
            return (self.topo_score * self.role_score) ** 0.5
        return self.topo_score

    @property
    def effective_weight(self) -> float:
        if self.tier in ('canonical', 'confirmed'):
            return 1.0
        w = self.base_weight
        ctx = self.combined_context
        if ctx is not None:
            w *= max(ctx, 0.1)
        return w


@dataclass
class ConfidenceDictionary:
    """Dictionary using confidence-weighted votes + edge-role context."""
    entries: Dict[str, ConfidenceEntry] = field(default_factory=dict)
    en_neighbors: Dict[str, Set[str]] = field(default_factory=dict)
    de_neighbors: Dict[str, Set[str]] = field(default_factory=dict)
    en_landscape: Optional[Landscape] = None
    de_landscape: Optional[Landscape] = None

    @property
    def firm_en(self) -> Set[str]:
        return {e.en for e in self.entries.values()
                if e.tier in ('canonical', 'confirmed')}

    @property
    def firm_de(self) -> Set[str]:
        return {e.de for e in self.entries.values()
                if e.tier in ('canonical', 'confirmed')}

    def word_weights(self, lang: str) -> Dict[str, float]:
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

    def build_translation_maps(self) -> Tuple[Dict[str, str], Dict[str, str]]:
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
        """Recompute context scores with edge-role matching."""
        if self.en_landscape is None or self.de_landscape is None:
            return
        en2de, de2en = self.build_translation_maps()
        for entry in self.entries.values():
            if entry.tier == 'canonical':
                entry.topo_score = 1.0
                entry.role_score = 1.0
                continue
            topo, matches, translatable, role = compute_role_context_score(
                entry.en, entry.de, en2de, de2en,
                self.en_neighbors, self.de_neighbors,
                self.en_landscape, self.de_landscape,
            )
            entry.topo_score = topo
            entry.role_score = role
            entry.context_matches = matches
            entry.context_translatable = translatable

    def update(
        self,
        discoveries: List[Tuple[str, str, float, float, int]],
        round_nr: int,
    ) -> None:
        """Accumulate confidence-weighted votes."""
        for en, de, conf, avg_d, raw_v in discoveries:
            key = f"{en}:{de}"
            if key in self.entries:
                entry = self.entries[key]
                if entry.tier == 'canonical':
                    continue
                entry.cumulative_conf += conf
                entry.raw_votes += raw_v
                entry.rounds_seen += 1
                entry.last_round = round_nr
                if (entry.cumulative_conf >= PROMOTION_VOTES
                        and entry.tier == 'tentative'):
                    has_confirmed = any(
                        e.en == en and e.tier == 'confirmed'
                        for e in self.entries.values()
                    )
                    if not has_confirmed:
                        ctx = entry.combined_context
                        if ctx is not None and ctx >= MIN_CONTEXT_SCORE:
                            entry.tier = 'confirmed'
            else:
                self.entries[key] = ConfidenceEntry(
                    en=en, de=de, tier='tentative',
                    cumulative_conf=conf, raw_votes=raw_v,
                    rounds_seen=1,
                    first_round=round_nr, last_round=round_nr,
                )

        # Stale removal
        to_remove = []
        for key, entry in self.entries.items():
            if entry.tier != 'tentative':
                continue
            rounds_since = round_nr - entry.last_round
            if (rounds_since >= STALE_ROUNDS
                    and entry.cumulative_conf < MIN_STALE_VOTES):
                to_remove.append(key)
        for key in to_remove:
            del self.entries[key]

        self.update_context_scores()


# ══════════════════════════════════════════════
# Initialization
# ══════════════════════════════════════════════

def init_confidence_from_config_b() -> ConfidenceDictionary:
    en_nbrs = build_neighbor_map("english_basic")
    de_nbrs = build_neighbor_map("german_basic")
    cd = ConfidenceDictionary(en_neighbors=en_nbrs, de_neighbors=de_nbrs)
    for d in config_b():
        for en, de in d.translations.items():
            key = f"{en}:{de}"
            cd.entries[key] = ConfidenceEntry(
                en=en, de=de, tier='canonical',
                cumulative_conf=0, raw_votes=0,
                rounds_seen=0, first_round=0, last_round=0,
                topo_score=1.0, role_score=1.0,
            )
    return cd


# ══════════════════════════════════════════════
# Single round
# ══════════════════════════════════════════════

def run_confidence_round(
    round_nr: int,
    cd: ConfidenceDictionary,
    verbose: bool = True,
) -> Tuple[List[Tuple[str, str, float, float, int]], Dict[str, float]]:
    """Run one round using confidence-weighted extraction."""
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
            print(f"  Tentative:")
            for e in tent:
                ctx_s = (f"{e.combined_context:.0%}"
                         if e.combined_context is not None else "?")
                topo_s = (f"{e.topo_score:.0%}"
                          if e.topo_score is not None else "?")
                role_s = (f"{e.role_score:.0%}"
                          if e.role_score is not None else "?")
                correct = "✓" if GROUND_TRUTH.get(e.en) == e.de else "✗"
                print(f"    {e.en:>10}↔{e.de:<12} "
                      f"conf={e.cumulative_conf:>5.1f}({e.raw_votes}v) "
                      f"ew={e.effective_weight:.2f} "
                      f"topo={topo_s} role={role_s} ctx={ctx_s} "
                      f"{correct}")
        conf = [(e.en, e.de) for e in cd.entries.values()
                if e.tier == 'confirmed']
        if conf:
            print(f"  Confirmed: {conf}")
        print(f"  Unknown remaining: {len(unknown_pairs)}")
        print(f"{'─'*72}")

    # Learn with context-weighted execute_fn
    en_exec = make_context_l2_execute_conf(cd, "en", seed=42 + round_nr)
    de_exec = make_context_l2_execute_conf(cd, "de", seed=143 + round_nr)
    en_L = learn_landscape("english_basic", en_exec, "EN")
    de_L = learn_landscape("german_basic", de_exec, "DE")

    # Store landscapes for role-context scoring
    cd.en_landscape = en_L
    cd.de_landscape = de_L

    if verbose:
        fps_en = domain_fingerprints(en_L, "EN")
        fps_de = domain_fingerprints(de_L, "DE")
        n_s_en = sum(1 for fp in fps_en if fp.quality > 0)
        n_s_de = sum(1 for fp in fps_de if fp.quality > 0)
        print(f"  EN: {n_s_en}S/{len(fps_en)-n_s_en}F  "
              f"DE: {n_s_de}S/{len(fps_de)-n_s_de}F")

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
            min_c = min(confs)
            max_c = max(confs)
            print(f"  Equivalences: {len(equivalences)}, "
                  f"confidence: avg={avg_c:.3f} "
                  f"min={min_c:.3f} max={max_c:.3f}")

    # Confidence-weighted extraction
    discoveries = extract_confidence_correspondences(
        equivalences, firm_en, firm_de, min_confidence=0.5,
    )

    if verbose and discoveries:
        en2de, de2en = cd.build_translation_maps()
        print(f"\n  Discoveries (confidence-weighted, mutual best):")
        print(f"  {'EN':<12} {'DE':<12} {'Conf':>6} {'Votes':>5} "
              f"{'Avg d':>8}  {'Topo':>5} {'Role':>5}  Status")
        print(f"  {'─'*12} {'─'*12} {'─'*6} {'─'*5} "
              f"{'─'*8}  {'─'*5} {'─'*5}  {'─'*25}")

    correct = 0
    wrong = 0
    for en, de, conf, avg_d, raw_v in discoveries:
        is_correct = GROUND_TRUTH.get(en) == de
        if is_correct:
            correct += 1
        else:
            wrong += 1
        if verbose:
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
                will_promote = (
                    new_conf >= PROMOTION_VOTES
                    and topo is not None
                    and role is not None
                    and (topo * role) ** 0.5 >= MIN_CONTEXT_SCORE
                )
                status = (f"cum {existing.cumulative_conf:.1f}→{new_conf:.1f}"
                          + (" → CONFIRMED" if will_promote else ""))
            elif existing and existing.tier == 'confirmed':
                status = "already confirmed"
            else:
                status = f"NEW conf={conf:.1f}"

            print(f"  {en:<12} {de:<12} {conf:>6.1f} {raw_v:>5} "
                  f"{avg_d:>8.4f}  {topo_s:>5} {role_s:>5}  "
                  f"{marker} {status}")

    if verbose:
        if correct + wrong > 0:
            print(f"\n  Discovery accuracy: {correct}/{correct+wrong} "
                  f"({100*correct/(correct+wrong):.0f}%)")
        else:
            print(f"\n  No discoveries this round.")

    return discoveries, {}


def make_context_l2_execute_conf(
    cd: ConfidenceDictionary, lang: str, seed: int = 42,
):
    """Build Level-2 execute_fn from ConfidenceDictionary weights."""
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
# Bootstrap loop
# ══════════════════════════════════════════════

def confidence_bootstrap(n_rounds: int = 10) -> None:
    """Run C130 confidence-weighted bootstrap."""
    cd = init_confidence_from_config_b()

    print(f"\n{'='*72}")
    print(f"  C130 CONFIDENCE-WEIGHTED EDGE-ROLE BOOTSTRAP "
          f"({cd.tier_summary()})")
    print(f"  Delta 1: votes weighted by equivalence.confidence")
    print(f"  Delta 2: context score includes edge-role matching")
    print(f"  Promotion: conf≥{PROMOTION_VOTES} AND "
          f"combined_ctx≥{MIN_CONTEXT_SCORE:.0%}")
    print(f"  combined_ctx = √(topo_score × role_score)")
    print(f"{'='*72}")

    round_data = []

    for r in range(1, n_rounds + 1):
        discoveries, rankings = run_confidence_round(r, cd)

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
                topo_s = (f"{e.topo_score:.0%}"
                          if e.topo_score is not None else "?")
                role_s = (f"{e.role_score:.0%}"
                          if e.role_score is not None else "?")
                print(f"    {e.tier:>10} {e.en:>10}↔{e.de:<12} "
                      f"conf={e.cumulative_conf:>5.1f}({e.raw_votes}v) "
                      f"ew={e.effective_weight:.2f} "
                      f"topo={topo_s} role={role_s} ctx={ctx_s} "
                      f"R{e.first_round}-R{e.last_round} {correct}")

    # ── Summary ──────────────────────────────
    print(f"\n{'='*72}")
    print(f"  C130 Summary: {len(round_data)} rounds")
    print(f"{'='*72}")

    total_correct = 0
    total_wrong = 0
    for r_nr, disc, (c, t, f) in round_data:
        n_c = sum(1 for en, de, *_ in disc if GROUND_TRUTH.get(en) == de)
        n_w = sum(1 for en, de, *_ in disc if GROUND_TRUTH.get(en) != de)
        total_correct += n_c
        total_wrong += n_w
        disc_str = ", ".join(
            f"{en}↔{de} {conf:.1f}c"
            f"{'✓' if GROUND_TRUTH.get(en)==de else '✗'}"
            for en, de, conf, _, _ in disc)
        print(f"\n  R{r_nr}: {c}C+{t}T+{f}F → {n_c}✓ {n_w}✗")
        print(f"    {disc_str}")

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
    print(f"  Firm total: {can + conf_tot}")

    if total_correct + total_wrong > 0:
        print(f"  Discovery accuracy: "
              f"{total_correct}/{total_correct+total_wrong} "
              f"({100*total_correct/(total_correct+total_wrong):.0f}%)")

    # Role score comparison for key pairs
    print(f"\n  ── Edge-Role Score Analysis ──")
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
        ctx_s = f"{e.combined_context:.0%}" if e.combined_context is not None else "?"
        print(f"  {e.en:>12}↔{e.de:<12} {topo_s:>5} {role_s:>5} "
              f"{ctx_s:>5}  {e.cumulative_conf:>6.1f} "
              f"{e.tier:<10} {correct}")

    # Comparison
    print(f"\n  ── Comparison ──")
    print(f"  C127b cumul L2:    11→15, 50% confirmed — FALSIFIED")
    print(f"  C128  context L3:  11→15, 100% confirmed (topo-only)")
    print(f"  C129  competitive: 11→15, 100% confirmed (identical)")
    print(f"  C130  confidence:  11→{can+conf_tot}, "
          f"{100*conf_ok/conf_tot if conf_tot else 0:.0f}% confirmed "
          f"(edge-role weighted)")


def main() -> None:
    print("=" * 72)
    print("  E₀ C130 — Confidence-Weighted Edge-Role Matching")
    print("  Using quality/load/inertia signals E₀ already computes")
    print("  Starting from Config B (11 canonical pairs)")
    print("=" * 72)

    confidence_bootstrap(n_rounds=10)


if __name__ == "__main__":
    main()
