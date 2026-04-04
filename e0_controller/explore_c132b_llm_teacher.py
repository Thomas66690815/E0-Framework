#!/usr/bin/env python3
"""
E₀ C132b — LLM as Teacher (Elternteil)
=========================================

Insight from C132: enriching canon topology makes things WORSE (more
noise, homogeneous fingerprints). The LLM should not be architect —
it should be teacher.

Analogy: A 5-year-old doesn't learn by studying a dictionary. They
learn by pointing at things and asking "Mama, what's that called?"
The parent confirms or corrects. The child's WORLD (canon topology)
stays the same — what grows is VOCABULARY (seed pairs).

Design:
  1. Start with Config A (8 pairs) — minimal seed
  2. Run 3 bootstrap rounds → candidates emerge structurally
  3. Show top candidates to LLM: "Is 'food' = 'essen_n'?"
  4. LLM confirms correct ones → new canonical pairs
  5. Continue bootstrap with expanded seed
  6. Repeat teaching cycles (max 5)

The LLM is a bounded oracle: it can only say yes/no on OUR candidates.
It cannot introduce pairs we haven't discovered structurally.
This ensures E₀ drives discovery, LLM only validates.

Canons: v1.1 (64/64 edges, untouched).
"""

import json
import os
import sys
from typing import Dict, List, Optional, Set, Tuple

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) + "/..")

from e0_controller.llm_adapter import LLMConfig, openai_call
from e0_controller.explore_dict_learning import (
    GROUND_TRUTH, GROUND_TRUTH_REV, config_a, config_b, learn_landscape,
    PartialDictionary,
)
from e0_controller.explore_level3_learning import (
    build_neighbor_map, PROMOTION_VOTES, MIN_CONTEXT_SCORE,
)
from e0_controller.explore_confidence_learning import (
    ConfidenceEntry, ConfidenceDictionary,
    extract_confidence_correspondences,
    compute_role_context_score,
    make_context_l2_execute_conf,
)
from e0_controller.dream_mode import (
    domain_fingerprints, find_equivalences,
)


# ══════════════════════════════════════════════
# LLM Teacher
# ══════════════════════════════════════════════

TEACHER_SYSTEM = """\
You are a bilingual teacher helping students learn vocabulary.
You will be given candidate English↔German word pairs.
For each pair, respond ONLY with:
  CORRECT — if the translation is right
  WRONG — if the translation is wrong

Important:
- "food" in English = "Essen" (noun, das Essen) in German
- "eat" in English = "essen" (verb) in German
- Use ONLY these exact German IDs when answering:
  ding, handlung, eigenschaft, beziehung, koerper, essen_n, selbst,
  kopf, hand, arm, fuss, auge, mund, ohr, finger,
  wasser, brot, frucht, apfel, milch, salz,
  gehen, kommen, sehen, hoeren, essen_v, trinken, geben, nehmen, machen, sagen,
  gut, schlecht, gross, klein, heiss, kalt, neu, alt,
  in_de, mit, von, nicht, alle

Output ONLY valid JSON: [{"en": "...", "de": "...", "verdict": "CORRECT"}, ...]
No commentary."""


def ask_teacher(
    candidates: List[Tuple[str, str, float]],
    config: LLMConfig = None,
) -> List[Tuple[str, str, bool]]:
    """Ask LLM teacher to validate candidate pairs.

    Returns list of (en, de, is_correct) from LLM judgment.
    """
    if config is None:
        config = LLMConfig(temperature=0.0, max_tokens=2048)

    pairs_text = "\n".join(
        f"  {i+1}. {en} ↔ {de} (confidence={conf:.1f})"
        for i, (en, de, conf) in enumerate(candidates)
    )

    user_prompt = f"""\
Please check these English↔German translation candidates:
{pairs_text}

For each pair, is the translation CORRECT or WRONG?
Output as JSON array: [{{"en": "...", "de": "...", "verdict": "CORRECT"|"WRONG"}}]"""

    print(f"\n  📚 Asking teacher about {len(candidates)} candidates...")
    raw = openai_call(TEACHER_SYSTEM, user_prompt, config)

    # Parse JSON
    text = raw.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1]
        if text.endswith("```"):
            text = text[:-3]

    try:
        verdicts = json.loads(text)
    except json.JSONDecodeError as e:
        print(f"  ERROR: Failed to parse teacher response: {e}")
        print(f"  Raw: {raw[:500]}")
        return []

    results = []
    for v in verdicts:
        en = v.get("en", "")
        de = v.get("de", "")
        verdict = v.get("verdict", "").upper()
        is_correct = verdict == "CORRECT"
        results.append((en, de, is_correct))

    return results


# ══════════════════════════════════════════════
# Bootstrap round (reuses C131 mechanics)
# ══════════════════════════════════════════════

def run_round(
    round_nr: int,
    cd: ConfidenceDictionary,
    verbose: bool = True,
) -> List[Tuple[str, str, float, float, int]]:
    """Run one learning round on v1.1 canons."""
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
        print(f"  Firm ({len(cd.firm_en)}): {sorted(firm_en)}")
        tent = sorted(
            [e for e in cd.entries.values() if e.tier == 'tentative'],
            key=lambda e: -e.cumulative_conf,
        )
        if tent:
            print(f"  Tentative ({len(tent)}):")
            for e in tent[:8]:
                ctx_s = (f"{e.combined_context:.0%}"
                         if e.combined_context is not None else "?")
                correct = "✓" if GROUND_TRUTH.get(e.en) == e.de else "✗"
                print(f"    {e.en:>12}↔{e.de:<14} "
                      f"conf={e.cumulative_conf:>5.1f}({e.raw_votes}v) "
                      f"ctx={ctx_s} {correct}")
            if len(tent) > 8:
                print(f"    ... and {len(tent)-8} more")
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

    discoveries = extract_confidence_correspondences(
        equivalences, firm_en, firm_de, min_confidence=0.5,
    )

    if verbose and discoveries:
        en2de, de2en = cd.build_translation_maps()
        print(f"\n  Discoveries:")
        print(f"  {'EN':<12} {'DE':<14} {'Conf':>6} {'Votes':>5} "
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
            print(f"  {en:<12} {de:<14} {conf:>6.1f} {raw_v:>5} "
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
# Teaching cycle
# ══════════════════════════════════════════════

def select_candidates_for_teacher(
    cd: ConfidenceDictionary,
    max_candidates: int = 10,
    min_conf: float = 2.0,
) -> List[Tuple[str, str, float]]:
    """Select best tentative pairs to show the teacher.

    Strategy: pick tentative entries with highest confidence,
    excluding those already submitted.
    """
    candidates = []
    for entry in cd.entries.values():
        if entry.tier != 'tentative':
            continue
        if entry.cumulative_conf < min_conf:
            continue
        candidates.append((entry.en, entry.de, entry.cumulative_conf))

    # Sort by confidence descending
    candidates.sort(key=lambda x: -x[2])
    return candidates[:max_candidates]


def teach(
    cd: ConfidenceDictionary,
    cycle_nr: int,
    llm_config: LLMConfig,
) -> Tuple[int, int]:
    """One teaching cycle: select candidates, ask LLM, integrate.

    Returns (n_confirmed, n_rejected).
    """
    candidates = select_candidates_for_teacher(cd)
    if not candidates:
        print(f"\n  Teaching cycle {cycle_nr}: no candidates to ask about")
        return 0, 0

    # Ask teacher
    verdicts = ask_teacher(candidates, llm_config)

    n_confirmed = 0
    n_rejected = 0
    promoted = []
    rejected_list = []

    for en, de, is_correct in verdicts:
        key = f"{en}:{de}"
        entry = cd.entries.get(key)
        if entry is None:
            continue

        if is_correct:
            # Teacher confirms → promote to canonical (as if seeded)
            entry.tier = 'canonical'
            entry.cumulative_conf = 0  # reset — it's now ground truth
            n_confirmed += 1
            promoted.append(f"{en}↔{de}")
            actual = GROUND_TRUTH.get(en)
            marker = "✓" if actual == de else "✗ (LLM wrong!)"
            print(f"    ✓ {en}↔{de} → canonical {marker}")
        else:
            # Teacher rejects → remove from dictionary
            if key in cd.entries:
                del cd.entries[key]
            n_rejected += 1
            rejected_list.append(f"{en}↔{de}")
            print(f"    ✗ {en}↔{de} → removed")

    print(f"\n  Teaching cycle {cycle_nr}: "
          f"{n_confirmed} confirmed, {n_rejected} rejected")
    return n_confirmed, n_rejected


# ══════════════════════════════════════════════
# Main experiment
# ══════════════════════════════════════════════

def run_experiment(
    start_config=config_a,
    start_label: str = "Config A",
    n_bootstrap_rounds: int = 3,
    n_teaching_cycles: int = 5,
    n_final_rounds: int = 5,
):
    """Full C132b experiment: bootstrap → teach → bootstrap → teach → ..."""
    print("=" * 72)
    print("  E₀ C132b — LLM as Teacher (Elternteil)")
    print("=" * 72)

    llm_config = LLMConfig(temperature=0.0, max_tokens=2048)

    # Initialize from start config
    en_nbrs = build_neighbor_map("english_basic")
    de_nbrs = build_neighbor_map("german_basic")
    cd = ConfidenceDictionary(en_neighbors=en_nbrs, de_neighbors=de_nbrs)
    pairs = start_config()
    for d in pairs:
        for en, de in d.translations.items():
            key = f"{en}:{de}"
            cd.entries[key] = ConfidenceEntry(
                en=en, de=de, tier='canonical',
                cumulative_conf=0, raw_votes=0,
                rounds_seen=0, first_round=0, last_round=0,
                topo_score=1.0, role_score=1.0,
            )

    initial_seed = sum(1 for e in cd.entries.values() if e.tier == 'canonical')
    print(f"\n  Start: {start_label} ({initial_seed} seed pairs)")
    print(f"  Canons: v1.1 (64/64 edges)")
    print(f"  Plan: {n_bootstrap_rounds}R bootstrap → teach → repeat × {n_teaching_cycles}")

    total_round = 0
    total_llm_calls = 0
    total_taught = 0
    history = []  # (round, event, firm_count, detail)

    for cycle in range(1, n_teaching_cycles + 1):
        print(f"\n{'='*72}")
        print(f"  ── Teaching Cycle {cycle}/{n_teaching_cycles} ──")
        print(f"{'='*72}")

        # Bootstrap rounds
        for r in range(1, n_bootstrap_rounds + 1):
            total_round += 1
            discoveries = run_round(total_round, cd, verbose=True)

            # Integrate discoveries
            cd.update(discoveries, total_round)

            c, t, f = cd.tier_counts()
            firm_count = c + f + sum(
                1 for e in cd.entries.values()
                if e.tier == 'tentative' and GROUND_TRUTH.get(e.en) == e.de
            )
            history.append((total_round, "bootstrap", c + f, f"R{total_round}"))

        # Teaching: ask LLM about candidates
        n_conf, n_rej = teach(cd, cycle, llm_config)
        total_llm_calls += 1
        total_taught += n_conf

        c, t, f = cd.tier_counts()
        history.append((total_round, "teach", c + f, f"T{cycle}: +{n_conf}/-{n_rej}"))

        # Early stop if no candidates left
        if n_conf == 0 and n_rej == 0:
            print(f"\n  No more candidates — stopping teaching cycles")
            break

    # Final bootstrap rounds (no more teaching)
    if n_final_rounds > 0:
        print(f"\n{'='*72}")
        print(f"  ── Final Bootstrap ({n_final_rounds} rounds, no teacher) ──")
        print(f"{'='*72}")

        for r in range(1, n_final_rounds + 1):
            total_round += 1
            discoveries = run_round(total_round, cd, verbose=(r <= 2 or r == n_final_rounds))
            cd.update(discoveries, total_round)

            c, t, f = cd.tier_counts()
            history.append((total_round, "final", c + f, f"R{total_round}"))

    # ── Results ──
    print_results(cd, total_round, total_llm_calls, total_taught,
                  initial_seed, start_label, history)


def print_results(
    cd: ConfidenceDictionary,
    total_rounds: int,
    llm_calls: int,
    taught: int,
    initial_seed: int,
    start_label: str,
    history: list,
):
    """Print comprehensive results."""
    c_count, t_count, f_count = cd.tier_counts()

    confirmed_correct = sum(
        1 for e in cd.entries.values()
        if e.tier == 'confirmed' and GROUND_TRUTH.get(e.en) == e.de
    )
    confirmed_total = sum(1 for e in cd.entries.values() if e.tier == 'confirmed')

    tent_correct = sum(
        1 for e in cd.entries.values()
        if e.tier == 'tentative' and GROUND_TRUTH.get(e.en) == e.de
    )
    tent_total = sum(1 for e in cd.entries.values() if e.tier == 'tentative')

    # Canonical now includes teacher-confirmed
    canonical_correct = sum(
        1 for e in cd.entries.values()
        if e.tier == 'canonical' and GROUND_TRUTH.get(e.en) == e.de
    )

    firm = c_count + confirmed_total + tent_correct

    # Show all non-canonical entries
    print(f"\n  After R{total_rounds}: {cd.tier_summary()}")
    for e in sorted(cd.entries.values(),
                    key=lambda x: (
                        0 if x.tier == 'canonical' else
                        1 if x.tier == 'confirmed' else 2,
                        -x.cumulative_conf,
                    )):
        if e.tier == 'canonical':
            continue
        ctx_s = (f"{e.combined_context:.0%}"
                 if e.combined_context is not None else "?")
        correct = "✓" if GROUND_TRUTH.get(e.en) == e.de else "✗"
        print(f"     {e.tier:12s} {e.en:>12}↔{e.de:<14} "
              f"conf={e.cumulative_conf:>5.1f} ctx={ctx_s} {correct}")

    # Canonical entries (including teacher-confirmed)
    print(f"\n  Canonical ({c_count} — {initial_seed} seed + "
          f"{c_count - initial_seed} teacher-confirmed):")
    for e in sorted(cd.entries.values(), key=lambda x: x.en):
        if e.tier != 'canonical':
            continue
        correct = "✓" if GROUND_TRUTH.get(e.en) == e.de else "✗"
        print(f"    {e.en:>12}↔{e.de:<14} {correct}")

    # relation↔beziehung status
    rel_key = "relation:beziehung"
    rel_entry = cd.entries.get(rel_key)
    if rel_entry:
        rel_status = f"{rel_entry.tier} conf={rel_entry.cumulative_conf:.0f}"
        if rel_entry.combined_context is not None:
            rel_status += f" ctx={rel_entry.combined_context:.0%}"
        else:
            rel_status += " ctx=?"
    else:
        rel_status = "not discovered"

    # LLM accuracy (did the LLM confirm wrongly?)
    teacher_wrong = sum(
        1 for e in cd.entries.values()
        if e.tier == 'canonical' and GROUND_TRUTH.get(e.en) != e.de
    ) - initial_seed  # subtract initial seed (those were correct by definition)
    # Actually, initial seed is always correct, so:
    teacher_wrong = max(0, teacher_wrong)

    print(f"\n  {'─'*60}")
    print(f"  {start_label} + LLM Teacher RESULT:")
    print(f"  {'─'*60}")
    print(f"  Initial seed:     {initial_seed} pairs")
    print(f"  LLM calls:        {llm_calls}")
    print(f"  Teacher-confirmed: {taught} pairs (wrong: {teacher_wrong})")
    print(f"  Final canonical:  {c_count} ({canonical_correct}/{c_count} correct)")
    print(f"  Confirmed (auto): {confirmed_correct}/{confirmed_total}")
    print(f"  Tentative (corr): {tent_correct}/{tent_total}")
    print(f"  FIRM TOTAL:       {firm}/44 ({firm/44*100:.0f}%)")
    print(f"  relation↔beziehung: {rel_status}")
    print(f"  {'─'*60}")

    # History timeline
    print(f"\n  Timeline:")
    print(f"  {'Round':>5}  {'Event':>10}  {'Firm':>4}  Detail")
    print(f"  {'─'*45}")
    for rnd, event, firm_n, detail in history:
        print(f"  {rnd:>5}  {event:>10}  {firm_n:>4}  {detail}")

    # Comparison
    print(f"\n  {'='*60}")
    print(f"  COMPARISON")
    print(f"  {'='*60}")
    print(f"  C131b Config B only (v1.1): 11 seed → 13 firm (30%)")
    print(f"  C131b Config C+R5  (v1.1): 23 seed → 26 firm (59%)")
    print(f"  C132b {start_label} + Teacher: "
          f"{initial_seed} seed + {taught} taught → {firm} firm ({firm/44*100:.0f}%)")
    print(f"  {'='*60}")


if __name__ == "__main__":
    run_experiment()
