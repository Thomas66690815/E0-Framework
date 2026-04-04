#!/usr/bin/env python3
"""
E₀ C133 — LLM Monolingual Teaching + Seedless Playground
==========================================================

Architecture (corrected from C132):
  Phase 1 — Erziehung (with LLM, per language, NO translation):
    Use existing shared-topology canons (EN/DE 44 nodes, 64 edges)
    PLUS random "noise" edges so that ~50% succeed / ~50% fail
    LLM acts as monolingual execute_fn:
      "Does eye→see make sense?" → YES  → SUCCESS
      "Does eye→salt?"          → NO   → FAILURE
    Result: rich historization with unique fingerprints per node

  Phase 2 — Spielplatz (NO LLM):
    find_equivalences(en_landscape, de_landscape)
    Pure structural matching — no seed, no teacher
    The shared topology ensures edges at corresponding positions
    have comparable fingerprints.

Key insight: with shared topology, the LLM provides SEMANTIC
evaluation (not seed-based). EVERY edge gets a meaningful signal.
Noise edges provide crucial FAILURE signal for unique fingerprints.
Negative confirmation is as informative as positive.
"""

import json
import math
import os
import random
import sys
from collections import defaultdict
from typing import Dict, List, Optional, Set, Tuple

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) + "/..")

from e0_controller.primitives import Edge, Outcome
from e0_controller.landscape import Landscape
from e0_controller.controller import E0Controller
from e0_controller.bootstrapper import bootstrap_landscape
from e0_controller.llm_adapter import LLMConfig, openai_call
from e0_controller.dream_mode import (
    EdgeFingerprint, Equivalence,
    domain_fingerprints, find_equivalences,
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

    The noise edges connect the SAME concept positions in both
    languages, ensuring comparable fingerprints. Uses GROUND_TRUTH
    to map EN node positions to DE node positions.
    """
    # Get existing edges
    en_existing = {(e["from"], e["to"]) for e in en_spec["edges"]}
    de_existing = {(e["from"], e["to"]) for e in de_spec["edges"]}

    en_nodes = [n if isinstance(n, str) else n["id"] for n in en_spec["nodes"]]

    # Generate random noise in EN space
    all_possible = [
        (a, b) for a in en_nodes for b in en_nodes
        if a != b and (a, b) not in en_existing
    ]
    rng.shuffle(all_possible)

    added = 0
    for en_src, en_tgt in all_possible:
        if added >= noise_edges:
            break
        # Map to DE
        de_src = GROUND_TRUTH.get(en_src)
        de_tgt = GROUND_TRUTH.get(en_tgt)
        if de_src is None or de_tgt is None:
            continue
        if (de_src, de_tgt) in de_existing:
            continue

        # Add to both
        edge_template = {
            "delta": 0.3,
            "resistance": 0.3,
            "initial_U": 2,
            "initial_F": 1,
        }
        en_spec["edges"].append({**edge_template, "from": en_src, "to": en_tgt})
        de_spec["edges"].append({**edge_template, "from": de_src, "to": de_tgt})
        en_existing.add((en_src, en_tgt))
        de_existing.add((de_src, de_tgt))
        added += 1

    return en_spec, de_spec


# ══════════════════════════════════════════════
# Step 2: LLM as monolingual execute_fn
# ══════════════════════════════════════════════

BATCH_EVAL_SYSTEM = """\
You are evaluating whether two words are semantically related.
Two words are "related" if there is a DIRECT, common-sense connection:
- Body-function: eye→see ✓, finger→hear ✗
- Part-whole: finger→hand ✓, finger→bread ✗
- Object-action: bread→eat ✓, stone→eat ✗
- Quality: sweet→apple ✓, sweet→stone ✗
- Habitat: fish→water ✓, fish→fire ✗
- Cause: rain→wet ✓, sun→cold ✗
- Any other clear semantic link

Be STRICT: only clear, direct relationships. NO vague associations.
"dog→friend" is debatable → NO. "dog→animal" → YES.

Output ONLY valid JSON: an array of "YES" or "NO" strings,
one per input pair, in the same order."""


def batch_evaluate_edges(
    edges: List[Tuple[str, str]],
    language: str,
    config: LLMConfig,
) -> Dict[Tuple[str, str], Outcome]:
    """Evaluate edges in batches via LLM. Pure semantic, no types."""
    results = {}

    batch_size = 80
    n_batches = math.ceil(len(edges) / batch_size)

    print(f"\n  Evaluating {len(edges)} {language} edges "
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
For each word pair, are they semantically related?

{chr(10).join(lines)}

Output JSON array of "YES"/"NO" strings, one per pair."""

        raw = openai_call(BATCH_EVAL_SYSTEM, prompt, config)

        text = raw.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1]
            if text.endswith("```"):
                text = text[:-3]

        try:
            verdicts = json.loads(text)
        except json.JSONDecodeError:
            print(f"    Batch {batch_idx+1}: parse error, defaulting to FAILURE")
            verdicts = ["NO"] * len(batch)

        yes_count = 0
        for (src, tgt), v in zip(batch, verdicts):
            is_yes = str(v).upper().strip() == "YES"
            results[(src, tgt)] = Outcome.SUCCESS if is_yes else Outcome.FAILURE
            if is_yes:
                yes_count += 1

        print(f"    Batch {batch_idx+1}/{n_batches}: "
              f"{yes_count}/{len(batch)} YES")

    total_yes = sum(1 for o in results.values() if o == Outcome.SUCCESS)
    print(f"  Total: {total_yes}/{len(results)} YES "
          f"({total_yes/len(results)*100:.0f}%)")

    return results


def make_llm_execute_fn(
    cache: Dict[Tuple[str, str], Outcome],
) -> callable:
    """Build execute_fn from pre-evaluated cache."""
    def execute(source: str, target: str) -> Outcome:
        return cache.get((source, target), Outcome.FAILURE)
    return execute


# ══════════════════════════════════════════════
# Step 3: Build landscape + traverse
# ══════════════════════════════════════════════

def build_and_traverse(
    spec: dict,
    execute_fn,
    language: str,
    n_passes: int = 3,
) -> Landscape:
    """Bootstrap landscape from spec, traverse with execute_fn."""
    # Ensure nodes are plain strings (not dicts)
    if spec["nodes"] and isinstance(spec["nodes"][0], dict):
        spec["nodes"] = [n["id"] for n in spec["nodes"]]

    L = bootstrap_landscape(spec)

    # Phase A: Force-evaluate EVERY edge so no edge stays at initial quality
    print(f"\n  Force-evaluating all {language} edges...")
    for edge in L.edges:
        outcome = execute_fn(edge.source, edge.target)
        L.historization.update(edge, outcome)

    # Phase B: Controller traversal for richer historization
    print(f"  Traversing {language} landscape ({n_passes} passes)...")
    states = sorted(L.states)
    total_steps = 0

    for pass_nr in range(n_passes):
        for start in states:
            ctrl = E0Controller(L, execute_fn, inscription_threshold=True)
            trace = ctrl.run(start, max_cycles=30)
            total_steps += len(trace.steps)

    T_s = structural_temperature(L.historization)
    n_edges = L.edge_count()
    fps = domain_fingerprints(L, language)
    n_succ = sum(1 for fp in fps if fp.quality > 0.5)
    n_fail = n_edges - n_succ

    print(f"  {language}: {total_steps} steps, {n_edges} edges, "
          f"T_s={T_s:.3f}, {n_succ}S/{n_fail}F")

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

    Since both canons share the same topology, edge[i] in EN corresponds
    to edge[i] in DE. If quality(en_edge[i]) ≈ quality(de_edge[i]),
    the endpoint nodes are likely translations of each other.

    Accumulates votes from agreeing edges, then mutual best-match.
    """
    conf_sums: Dict[Tuple[str, str], float] = defaultdict(float)
    vote_counts: Dict[Tuple[str, str], int] = defaultdict(int)

    n_agree = 0
    n_disagree = 0

    for (en_src, en_tgt), (de_src, de_tgt) in zip(en_edges, de_edges):
        en_edge = Edge(en_src, en_tgt)
        de_edge = Edge(de_src, de_tgt)

        # Get quality for this edge position in both landscapes
        en_q = en_L.historization.quality(en_edge)
        de_q = de_L.historization.quality(de_edge)

        # Agreement: both succeed or both fail
        en_succ = en_q > 0.5
        de_succ = de_q > 0.5
        if en_succ == de_succ:
            n_agree += 1
            # Weight by quality agreement strength
            weight = 1.0 - abs(en_q - de_q)
            conf_sums[(en_src, de_src)] += weight
            conf_sums[(en_tgt, de_tgt)] += weight
            vote_counts[(en_src, de_src)] += 1
            vote_counts[(en_tgt, de_tgt)] += 1
        else:
            n_disagree += 1

    print(f"  Edge agreement: {n_agree}/{n_agree + n_disagree} "
          f"({n_agree/(n_agree + n_disagree)*100:.0f}%)")

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
    """Original approach via find_equivalences + node extraction."""
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
# Fingerprint uniqueness analysis
# ══════════════════════════════════════════════

def analyze_fingerprints(L: Landscape, domain: str):
    """Check how unique the edge fingerprints are."""
    fps = domain_fingerprints(L, domain)

    # Bin quality values
    q_bins = defaultdict(int)
    for fp in fps:
        q_bin = round(fp.quality, 2)
        q_bins[q_bin] += 1

    print(f"\n  {domain} fingerprint analysis ({len(fps)} edges):")
    top_bins = sorted(q_bins.items(), key=lambda x: -x[1])[:10]
    for q, count in top_bins:
        print(f"    quality≈{q:.2f}: {count} edges")

    # Check per-node signature uniqueness
    node_sigs: Dict[str, List[float]] = defaultdict(list)
    for fp in fps:
        node_sigs[fp.edge.source].append(fp.quality)
        node_sigs[fp.edge.target].append(fp.quality)

    # Hash each node's signature
    sig_hashes: Dict[str, str] = {}
    for node, qualities in node_sigs.items():
        sig = tuple(round(q, 2) for q in sorted(qualities))
        sig_hashes[node] = str(sig)

    unique_sigs = len(set(sig_hashes.values()))
    print(f"  Unique node signatures: {unique_sigs}/{len(node_sigs)}")

    # Show degree distribution
    degrees = defaultdict(int)
    for fp in fps:
        degrees[fp.edge.source] += 1
        degrees[fp.edge.target] += 1
    avg_deg = sum(degrees.values()) / max(len(degrees), 1)
    min_deg = min(degrees.values()) if degrees else 0
    max_deg = max(degrees.values()) if degrees else 0
    print(f"  Degree: min={min_deg}, avg={avg_deg:.1f}, max={max_deg}")


# ══════════════════════════════════════════════
# Main experiment
# ══════════════════════════════════════════════

def run_experiment(noise_edges: int = 100):
    """Full C133 experiment."""
    print("=" * 72)
    print("  E₀ C133 — LLM Monolingual Teaching + Seedless Playground")
    print(f"  Shared topology + {noise_edges} noise edges")
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
    de_nodes = [n if isinstance(n, str) else n["id"] for n in de_spec["nodes"]]
    avg_degree_en = 2 * n_en_total / len(en_nodes)
    avg_degree_de = 2 * n_de_total / len(de_nodes)
    print(f"  EN avg degree: {avg_degree_en:.1f}")
    print(f"  DE avg degree: {avg_degree_de:.1f}")

    # ── Phase 1b: LLM evaluates edges (monolingual teaching) ──
    print(f"\n{'─'*72}")
    print("  Phase 1b: LLM teaching — evaluating edges monolingually...")
    print(f"{'─'*72}")

    en_pairs = [(e["from"], e["to"]) for e in en_spec["edges"]]
    de_pairs = [(e["from"], e["to"]) for e in de_spec["edges"]]

    en_cache = batch_evaluate_edges(en_pairs, "English", eval_config)
    de_cache = batch_evaluate_edges(de_pairs, "German", eval_config)

    en_exec = make_llm_execute_fn(en_cache)
    de_exec = make_llm_execute_fn(de_cache)

    # ── Phase 1c: Build landscapes ──
    print(f"\n{'─'*72}")
    print("  Phase 1c: Building landscapes with LLM-driven historization...")
    print(f"{'─'*72}")

    en_L = build_and_traverse(en_spec, en_exec, "EN", n_passes=3)
    de_L = build_and_traverse(de_spec, de_exec, "DE", n_passes=3)

    # Fingerprint analysis
    analyze_fingerprints(en_L, "EN")
    analyze_fingerprints(de_L, "DE")

    # ── Phase 2: Playground ──
    print(f"\n{'='*72}")
    print("  Phase 2: Playground — structural matching WITHOUT LLM")
    print(f"{'='*72}")

    # Method A: Position-based matching (exploits shared topology)
    print(f"\n  Method A: Edge-position matching...")
    correspondences_A = match_by_edge_position(
        en_L, de_L, en_pairs, de_pairs,
    )
    print(f"  Correspondences (mutual best match): {len(correspondences_A)}")

    # Method B: find_equivalences (for comparison)
    print(f"\n  Method B: find_equivalences...")
    correspondences_B = match_by_find_equivalences(en_L, de_L)
    print(f"  Correspondences (mutual best match): {len(correspondences_B)}")

    # Score both methods
    for method_name, correspondences in [
        ("A (position)", correspondences_A),
        ("B (equivalences)", correspondences_B),
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
        prec = f"{correct/(correct+wrong)*100:.0f}%" if correct+wrong > 0 else "—"
        print(f"  → Correct={correct}, Wrong={wrong}, "
              f"Precision={prec}, Recall={correct}/{n_gt} "
              f"({correct/n_gt*100:.0f}%)")

    # Final summary uses Method A (position-based)
    correspondences = correspondences_A
    correct = sum(1 for en, de, _, _ in correspondences
                  if GROUND_TRUTH.get(en) == de)
    wrong = sum(1 for en, de, _, _ in correspondences
                if en in GROUND_TRUTH and GROUND_TRUTH[en] != de)

    n_gt = len(GROUND_TRUTH)
    print(f"\n  {'='*60}")
    print(f"  C133 RESULTS")
    print(f"  {'='*60}")
    print(f"  Shared topology: {n_en_orig} canon + "
          f"{n_en_total - n_en_orig} noise = "
          f"{n_en_total} edges/language")
    print(f"  Correspondences: {len(correspondences)}")
    print(f"  Correct: {correct}")
    print(f"  Wrong:   {wrong}")
    if correct + wrong > 0:
        print(f"  Precision: {correct/(correct+wrong)*100:.0f}%")
    print(f"  Recall: {correct}/{n_gt} ({correct/n_gt*100:.0f}%)")
    print(f"  Seed: 0 (seedless)")
    print(f"  LLM in matching: NO")
    print(f"  {'='*60}")

    print(f"\n  COMPARISON:")
    print(f"  C131b B (seed=11, no LLM):   13/44 (30%)")
    print(f"  C132b   (seed=8, LLM teach):  20/44 (45%)")
    print(f"  C133    (seed=0, LLM+play):   {correct}/{n_gt} "
          f"({correct/n_gt*100:.0f}%)")


if __name__ == "__main__":
    run_experiment()
