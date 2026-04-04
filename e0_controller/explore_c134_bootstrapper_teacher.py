#!/usr/bin/env python3
"""
E₀ C134b — Bootstrapper as Monolingual Teacher + Node Equivalences
=================================================

Evolution: C133 used binary YES/NO from LLM → quality ±1.0 → homogeneous
fingerprints → find_equivalences fails (position-matching needed as crutch).

C134a replaces the binary signal with the BOOTSTRAPPER's native mechanism:
  - LLM scores each edge 0–10 (semantic relatedness)
  - Score maps to initial_U / initial_F in the bootstrap spec
  - bootstrap_landscape() injects continuous traces
  - Result: 11 distinct quality levels → truly diverse fingerprints

Key constraint (from ChatGPT review):
  - Bootstrapper ONLY models monolingual teaching phase
  - NO cross-language leakage in the LLM prompt
  - Same shared topology as C133 (44 nodes, 64+100 edges)
  - Same matching methods — only the teaching signal changes

Hypothesis: Continuous quality from bootstrapper makes find_equivalences
viable without position-based matching. If so, the bootstrapper IS the
natural teacher component of the framework.
"""

import json
import math
import os
import random
import sys
from collections import defaultdict
from typing import Dict, List, Tuple

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) + "/..")

from e0_controller.primitives import Edge, Outcome
from e0_controller.landscape import Landscape
from e0_controller.bootstrapper import bootstrap_landscape
from e0_controller.llm_adapter import LLMConfig, openai_call
from e0_controller.dream_mode import (
    EdgeFingerprint, Equivalence,
    NodeEquivalence, NodeFingerprint,
    domain_fingerprints, find_equivalences,
    find_node_equivalences, node_fingerprints,
)
from e0_controller.structural_entropy import structural_temperature
from e0_controller.canon_loader import load_canon_spec
from e0_controller.explore_dict_learning import GROUND_TRUTH, GROUND_TRUTH_REV


# ══════════════════════════════════════════════
# Step 1: Load shared topology + add noise edges
# ══════════════════════════════════════════════

def build_noise_mapping(
    en_spec: dict,
    de_spec: dict,
    rng: random.Random,
    noise_edges: int = 100,
) -> Tuple[dict, dict]:
    """Add the SAME noise edge pattern to both canons.

    Identical to C133 — shared topology is the 'common world'.
    """
    en_existing = {(e["from"], e["to"]) for e in en_spec["edges"]}
    de_existing = {(e["from"], e["to"]) for e in de_spec["edges"]}

    en_nodes = [n if isinstance(n, str) else n["id"] for n in en_spec["nodes"]]

    all_possible = [
        (a, b) for a in en_nodes for b in en_nodes
        if a != b and (a, b) not in en_existing
    ]
    rng.shuffle(all_possible)

    added = 0
    for en_src, en_tgt in all_possible:
        if added >= noise_edges:
            break
        de_src = GROUND_TRUTH.get(en_src)
        de_tgt = GROUND_TRUTH.get(en_tgt)
        if de_src is None or de_tgt is None:
            continue
        if (de_src, de_tgt) in de_existing:
            continue

        # Placeholder — scores will be filled by LLM in Phase 1b
        edge_template = {
            "delta": 0.3,
            "resistance": 0.3,
            "initial_U": 0,
            "initial_F": 0,
        }
        en_spec["edges"].append({**edge_template, "from": en_src, "to": en_tgt})
        de_spec["edges"].append({**edge_template, "from": de_src, "to": de_tgt})
        en_existing.add((en_src, en_tgt))
        de_existing.add((de_src, de_tgt))
        added += 1

    return en_spec, de_spec


# ══════════════════════════════════════════════
# Step 2: LLM as monolingual scorer (0–10)
# ══════════════════════════════════════════════

BATCH_SCORE_SYSTEM = """\
You are evaluating how strongly two words are semantically related.
Rate each pair on a scale from 0 to 10:

  10 = directly, strongly related (eye→see, bread→eat, hand→finger)
   7 = clearly related (water→cold, fruit→apple)
   5 = moderately related (food→good, body→action)
   3 = loosely related (head→big, salt→water)
   1 = very weakly related (ear→bread, arm→milk)
   0 = completely unrelated (finger→from, salt→hear)

Be consistent. Judge ONLY within the given language.
Do NOT consider translations or other languages.

Output ONLY valid JSON: an array of integers (0–10),
one per input pair, in the same order."""


def batch_score_edges(
    edges: List[Tuple[str, str]],
    language: str,
    config: LLMConfig,
) -> Dict[Tuple[str, str], int]:
    """Score edges in batches via LLM. Returns score 0-10 per edge."""
    results = {}

    batch_size = 80
    n_batches = math.ceil(len(edges) / batch_size)

    print(f"\n  Scoring {len(edges)} {language} edges "
          f"via LLM ({n_batches} batches)...")

    for batch_idx in range(n_batches):
        start_idx = batch_idx * batch_size
        end_idx = min(start_idx + batch_size, len(edges))
        batch = edges[start_idx:end_idx]

        lines = []
        for i, (src, tgt) in enumerate(batch):
            lines.append(f"{i+1}. {src} → {tgt}")

        prompt = f"""\
Language: {language}
Rate the semantic relatedness of each word pair (0–10):

{chr(10).join(lines)}

Output JSON array of integers (0–10), one per pair."""

        raw = openai_call(BATCH_SCORE_SYSTEM, prompt, config)

        text = raw.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1]
            if text.endswith("```"):
                text = text[:-3]

        try:
            scores = json.loads(text)
        except json.JSONDecodeError:
            print(f"    Batch {batch_idx+1}: parse error, defaulting to 0")
            scores = [0] * len(batch)

        # Distribution for this batch
        dist = defaultdict(int)
        for (src, tgt), s in zip(batch, scores):
            score = max(0, min(10, int(s)))
            results[(src, tgt)] = score
            dist[score] += 1

        dist_str = " ".join(f"{k}:{v}" for k, v in sorted(dist.items()))
        print(f"    Batch {batch_idx+1}/{n_batches}: {dist_str}")

    # Overall distribution
    overall = defaultdict(int)
    for s in results.values():
        overall[s] += 1
    dist_str = " ".join(f"{k}:{v}" for k, v in sorted(overall.items()))
    avg = sum(results.values()) / max(len(results), 1)
    print(f"  Distribution: {dist_str}")
    print(f"  Mean score: {avg:.1f}")

    return results


# ══════════════════════════════════════════════
# Step 3: Inject scores into spec + bootstrap
# ══════════════════════════════════════════════

def inject_scores_into_spec(
    spec: dict,
    scores: Dict[Tuple[str, str], int],
) -> dict:
    """Set initial_U / initial_F from LLM scores.

    Score 0  → U=0,  F=10 → quality ≈ -1.0
    Score 5  → U=5,  F=5  → quality ≈  0.0
    Score 10 → U=10, F=0  → quality ≈ +1.0

    Confidence is always 1.0 — the score IS the teacher's judgment.
    """
    for edge in spec["edges"]:
        key = (edge["from"], edge["to"])
        score = scores.get(key, 0)
        edge["initial_U"] = float(score)
        edge["initial_F"] = float(10 - score)
        edge["confidence"] = 1.0
    return spec


def build_landscape(
    spec: dict,
    language: str,
) -> Landscape:
    """Bootstrap landscape from spec with LLM-scored traces."""
    # Ensure nodes are plain strings
    if spec["nodes"] and isinstance(spec["nodes"][0], dict):
        spec["nodes"] = [n["id"] for n in spec["nodes"]]

    L = bootstrap_landscape(spec)

    n_edges = L.edge_count()
    fps = domain_fingerprints(L, language)

    # Quality distribution
    q_bins = defaultdict(int)
    for fp in fps:
        q_bin = round(fp.quality, 1)
        q_bins[q_bin] += 1

    dist_str = " ".join(f"{k:+.1f}:{v}" for k, v in sorted(q_bins.items()))
    print(f"  {language}: {n_edges} edges, quality dist: {dist_str}")

    return L


# ══════════════════════════════════════════════
# Step 4: Playground — seedless matching
# ══════════════════════════════════════════════

def match_by_edge_position(
    en_L: Landscape,
    de_L: Landscape,
    en_edges: List[Tuple[str, str]],
    de_edges: List[Tuple[str, str]],
) -> List[Tuple[str, str, float, int]]:
    """Match nodes by comparing quality at corresponding edge positions.

    C134 difference from C133: quality is now continuous, so agreement
    can be graded rather than binary (both>0.5 or both<0.5).
    """
    conf_sums: Dict[Tuple[str, str], float] = defaultdict(float)
    vote_counts: Dict[Tuple[str, str], int] = defaultdict(int)

    n_agree = 0
    n_total = 0

    for (en_src, en_tgt), (de_src, de_tgt) in zip(en_edges, de_edges):
        en_edge = Edge(en_src, en_tgt)
        de_edge = Edge(de_src, de_tgt)

        en_q = en_L.historization.quality(en_edge)
        de_q = de_L.historization.quality(de_edge)

        n_total += 1
        distance = abs(en_q - de_q)

        # Continuous agreement: weight = 1 - distance
        # (identical quality → weight 1.0, opposite → weight 0.0)
        weight = max(0.0, 1.0 - distance)

        if weight > 0.3:  # Threshold for counting as agreement
            n_agree += 1
            conf_sums[(en_src, de_src)] += weight
            conf_sums[(en_tgt, de_tgt)] += weight
            vote_counts[(en_src, de_src)] += 1
            vote_counts[(en_tgt, de_tgt)] += 1

    print(f"  Edge agreement (>0.3): {n_agree}/{n_total} "
          f"({n_agree/n_total*100:.0f}%)")

    # Mutual best match
    best_for_en: Dict[str, Tuple[str, float]] = {}
    for (en, de), conf in conf_sums.items():
        if en not in best_for_en or conf > best_for_en[en][1]:
            best_for_en[en] = (de, conf)

    best_for_de: Dict[str, Tuple[str, float]] = {}
    for (en, de), conf in conf_sums.items():
        if de not in best_for_de or conf > best_for_de[de][1]:
            best_for_de[de] = (en, conf)

    results = []
    for en, (de, conf) in best_for_en.items():
        if de in best_for_de and best_for_de[de][0] == en:
            results.append((en, de, conf, vote_counts[(en, de)]))

    results.sort(key=lambda x: -x[2])
    return results


def match_by_find_equivalences(
    en_L: Landscape,
    de_L: Landscape,
) -> List[Tuple[str, str, float, int]]:
    """Match via find_equivalences (edge-level)."""
    equivalences = find_equivalences(
        en_L, de_L,
        domain_a="EN", domain_b="DE",
        quantile=0.05,
    )

    print(f"  Equivalences found: {len(equivalences)}")
    if equivalences:
        dists = [eq.distance for eq in equivalences]
        print(f"  Distance range: {min(dists):.4f} — {max(dists):.4f}")

    return extract_node_correspondences(equivalences, "EN")


def match_by_node_equivalences(
    en_L: Landscape,
    de_L: Landscape,
) -> List[Tuple[str, str, float, int]]:
    """Match via find_node_equivalences (node-level profiles).

    C134b: The key test. Node profiles (sorted quality vectors) should
    capture the structural role of each node without needing position info.
    """
    node_eqs = find_node_equivalences(
        en_L, de_L,
        domain_a="EN", domain_b="DE",
        quantile=0.15,
    )

    print(f"  Node equivalences found: {len(node_eqs)}")
    if node_eqs:
        dists = [eq.distance for eq in node_eqs]
        print(f"  Distance range: {min(dists):.4f} — {max(dists):.4f}")

    # Direct mutual best-match from node equivalences
    best_for_en: Dict[str, Tuple[str, float]] = {}
    vote_counts: Dict[Tuple[str, str], int] = defaultdict(int)

    for eq in node_eqs:
        en_node = eq.fp_a.node
        de_node = eq.fp_b.node
        conf = eq.confidence
        vote_counts[(en_node, de_node)] += 1
        if en_node not in best_for_en or conf > best_for_en[en_node][1]:
            best_for_en[en_node] = (de_node, conf)

    best_for_de: Dict[str, Tuple[str, float]] = {}
    for eq in node_eqs:
        en_node = eq.fp_a.node
        de_node = eq.fp_b.node
        conf = eq.confidence
        if de_node not in best_for_de or conf > best_for_de[de_node][1]:
            best_for_de[de_node] = (en_node, conf)

    results = []
    for en, (de, conf) in best_for_en.items():
        if de in best_for_de and best_for_de[de][0] == en:
            results.append((en, de, conf, vote_counts[(en, de)]))

    results.sort(key=lambda x: -x[2])
    return results


def extract_node_correspondences(
    equivalences: List[Equivalence],
    en_domain: str = "EN",
) -> List[Tuple[str, str, float, int]]:
    """Extract node correspondences from edge equivalences."""
    conf_sums: Dict[Tuple[str, str], float] = defaultdict(float)
    vote_counts: Dict[Tuple[str, str], int] = defaultdict(int)

    for eq in equivalences:
        en_fp = eq.fp_a if eq.fp_a.domain == en_domain else eq.fp_b
        de_fp = eq.fp_b if eq.fp_a.domain == en_domain else eq.fp_a

        for en_node, de_node in [
            (en_fp.edge.source, de_fp.edge.source),
            (en_fp.edge.target, de_fp.edge.target),
        ]:
            conf_sums[(en_node, de_node)] += eq.confidence
            vote_counts[(en_node, de_node)] += 1

    best_for_en: Dict[str, Tuple[str, float]] = {}
    for (en, de), conf in conf_sums.items():
        if en not in best_for_en or conf > best_for_en[en][1]:
            best_for_en[en] = (de, conf)

    best_for_de: Dict[str, Tuple[str, float]] = {}
    for (en, de), conf in conf_sums.items():
        if de not in best_for_de or conf > best_for_de[de][1]:
            best_for_de[de] = (en, conf)

    results = []
    for en, (de, conf) in best_for_en.items():
        if de in best_for_de and best_for_de[de][0] == en:
            results.append((en, de, conf, vote_counts[(en, de)]))

    results.sort(key=lambda x: -x[2])
    return results


# ══════════════════════════════════════════════
# Fingerprint analysis
# ══════════════════════════════════════════════

def analyze_fingerprints(L: Landscape, domain: str):
    """Check fingerprint diversity — C134 key metric."""
    fps = domain_fingerprints(L, domain)

    # Quality distribution (rounded to 1 decimal)
    q_bins = defaultdict(int)
    for fp in fps:
        q_bin = round(fp.quality, 1)
        q_bins[q_bin] += 1

    print(f"\n  {domain} fingerprint analysis ({len(fps)} edges):")
    print(f"    Quality distribution (11 levels):")
    for q in sorted(q_bins.keys()):
        bar = "█" * q_bins[q]
        print(f"      q={q:+.1f}: {q_bins[q]:>3} {bar}")

    # Per-node signature uniqueness
    node_sigs: Dict[str, List[float]] = defaultdict(list)
    for fp in fps:
        node_sigs[fp.edge.source].append(round(fp.quality, 1))
        node_sigs[fp.edge.target].append(round(fp.quality, 1))

    sig_hashes: Dict[str, str] = {}
    for node, qualities in node_sigs.items():
        sig = tuple(sorted(qualities))
        sig_hashes[node] = str(sig)

    unique_sigs = len(set(sig_hashes.values()))
    print(f"    Unique node signatures: {unique_sigs}/{len(node_sigs)}")

    # Degree distribution
    degrees = defaultdict(int)
    for fp in fps:
        degrees[fp.edge.source] += 1
        degrees[fp.edge.target] += 1
    avg_deg = sum(degrees.values()) / max(len(degrees), 1)
    min_deg = min(degrees.values()) if degrees else 0
    max_deg = max(degrees.values()) if degrees else 0
    print(f"    Degree: min={min_deg}, avg={avg_deg:.1f}, max={max_deg}")


# ══════════════════════════════════════════════
# Main experiment
# ══════════════════════════════════════════════

def run_experiment(noise_edges: int = 100):
    """C134b: Bootstrapper as monolingual teacher + node equivalences."""
    print("=" * 72)
    print("  E₀ C134b — Bootstrapper as Monolingual Teacher + Node Equivalences")
    print(f"  Shared topology + {noise_edges} noise edges")
    print(f"  Score 0–10 → initial_U/F → bootstrap_landscape()")
    print("=" * 72)

    eval_config = LLMConfig(temperature=0.0, max_tokens=4096)
    rng = random.Random(42)

    # ── Phase 1a: Load and augment canons ──
    print(f"\n{'─'*72}")
    print("  Phase 1a: Loading shared-topology canons + adding noise edges...")
    print(f"{'─'*72}")

    en_spec = load_canon_spec("english_basic")
    de_spec = load_canon_spec("german_basic")

    n_en_orig = len(en_spec["edges"])
    n_de_orig = len(de_spec["edges"])

    en_spec, de_spec = build_noise_mapping(
        en_spec, de_spec, rng, noise_edges=noise_edges,
    )

    n_en_total = len(en_spec["edges"])
    n_de_total = len(de_spec["edges"])

    print(f"  EN: {n_en_orig} → {n_en_total} edges "
          f"(+{n_en_total - n_en_orig} noise)")
    print(f"  DE: {n_de_orig} → {n_de_total} edges "
          f"(+{n_de_total - n_de_orig} noise)")

    en_nodes = [n if isinstance(n, str) else n["id"] for n in en_spec["nodes"]]
    avg_degree = 2 * n_en_total / len(en_nodes)
    print(f"  Avg degree: {avg_degree:.1f}")

    # ── Phase 1b: LLM scores edges (monolingual, 0-10) ──
    print(f"\n{'─'*72}")
    print("  Phase 1b: LLM scoring — monolingual relatedness 0-10...")
    print(f"{'─'*72}")

    en_pairs = [(e["from"], e["to"]) for e in en_spec["edges"]]
    de_pairs = [(e["from"], e["to"]) for e in de_spec["edges"]]

    en_scores = batch_score_edges(en_pairs, "English", eval_config)
    de_scores = batch_score_edges(de_pairs, "German", eval_config)

    # ── Phase 1c: Inject scores + bootstrap ──
    print(f"\n{'─'*72}")
    print("  Phase 1c: Bootstrapping landscapes with scored traces...")
    print(f"{'─'*72}")

    en_spec = inject_scores_into_spec(en_spec, en_scores)
    de_spec = inject_scores_into_spec(de_spec, de_scores)

    en_L = build_landscape(en_spec, "EN")
    de_L = build_landscape(de_spec, "DE")

    # Fingerprint analysis
    analyze_fingerprints(en_L, "EN")
    analyze_fingerprints(de_L, "DE")

    # ── Phase 2: Playground ──
    print(f"\n{'='*72}")
    print("  Phase 2: Playground — structural matching WITHOUT LLM")
    print(f"{'='*72}")

    # Method A: Position-based matching
    print(f"\n  Method A: Edge-position matching...")
    correspondences_A = match_by_edge_position(
        en_L, de_L, en_pairs, de_pairs,
    )
    print(f"  Correspondences (mutual best match): {len(correspondences_A)}")

    # Method B: find_equivalences (edge-level, for comparison)
    print(f"\n  Method B: find_equivalences (edge-level)...")
    correspondences_B = match_by_find_equivalences(en_L, de_L)
    print(f"  Correspondences (mutual best match): {len(correspondences_B)}")

    # Method C: find_node_equivalences — THE C134b TEST
    print(f"\n  Method C: find_node_equivalences (node profiles)...")
    correspondences_C = match_by_node_equivalences(en_L, de_L)
    print(f"  Correspondences (mutual best match): {len(correspondences_C)}")

    # Score all methods
    for method_name, correspondences in [
        ("A (position)", correspondences_A),
        ("B (edge-eq)", correspondences_B),
        ("C (node-eq)", correspondences_C),
    ]:
        correct = 0
        wrong = 0
        print(f"\n  {'─'*60}")
        print(f"  Method {method_name}: {len(correspondences)} pairs")
        print(f"  {'EN':<14} {'DE matched':<14} {'Expected':<14} "
              f"{'Conf':>7} {'Votes':>5}  Verdict")
        print(f"  {'─'*70}")

        for en, de, conf, votes in correspondences:
            expected = GROUND_TRUTH.get(en, "—")
            if expected == de:
                verdict = "✓"
                correct += 1
            elif expected == "—":
                verdict = "?"
            else:
                verdict = f"✗ (→{expected})"
                wrong += 1

            print(f"  {en:<14} {de:<14} {expected:<14} "
                  f"{conf:>7.1f} {votes:>5}  {verdict}")

        n_gt = len(GROUND_TRUTH)
        prec = (f"{correct/(correct+wrong)*100:.0f}%"
                if correct + wrong > 0 else "—")
        print(f"  → Correct={correct}, Wrong={wrong}, "
              f"Precision={prec}, Recall={correct}/{n_gt} "
              f"({correct/n_gt*100:.0f}%)")

    # Final summary
    print(f"\n  {'='*60}")
    print(f"  C134b RESULTS")
    print(f"  {'='*60}")

    all_methods = [
        ("A (position)", correspondences_A),
        ("B (edge-eq)", correspondences_B),
        ("C (node-eq)", correspondences_C),
    ]
    for method_name, correspondences in all_methods:
        correct = sum(1 for en, de, _, _ in correspondences
                      if GROUND_TRUTH.get(en) == de)
        wrong = sum(1 for en, de, _, _ in correspondences
                    if en in GROUND_TRUTH and GROUND_TRUTH[en] != de)
        n_gt = len(GROUND_TRUTH)
        print(f"  Method {method_name}: "
              f"{correct}/{n_gt} correct, {wrong} wrong")

    print(f"\n  Signal: Score 0–10 → initial_U/F (continuous)")
    print(f"  Traversal: NONE (pure bootstrap)")
    print(f"  Seed: 0 (seedless)")
    print(f"  LLM in matching: NO")
    print(f"  {'='*60}")

    print(f"\n  COMPARISON:")
    print(f"  C131b (seed=11, binary):       13/44 (30%)")
    print(f"  C132b (seed=8, LLM teach):     20/44 (45%)")
    print(f"  C133  (seed=0, binary+pos):    44/44 (100%) [position]")
    print(f"  C133  (seed=0, binary+eq):      1/44 (2%)  [find_eq]")

    c_A = sum(1 for en, de, _, _ in correspondences_A
              if GROUND_TRUTH.get(en) == de)
    c_B = sum(1 for en, de, _, _ in correspondences_B
              if GROUND_TRUTH.get(en) == de)
    c_C = sum(1 for en, de, _, _ in correspondences_C
              if GROUND_TRUTH.get(en) == de)
    n_gt = len(GROUND_TRUTH)
    print(f"  C134b (seed=0, scored+pos):   {c_A}/{n_gt} "
          f"({c_A/n_gt*100:.0f}%) [position]")
    print(f"  C134b (seed=0, edge-eq):      {c_B}/{n_gt} "
          f"({c_B/n_gt*100:.0f}%) [edge-eq]")
    print(f"  C134b (seed=0, node-eq):      {c_C}/{n_gt} "
          f"({c_C/n_gt*100:.0f}%) [node-eq]  ← KEY TEST")


if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 100
    run_experiment(noise_edges=n)
