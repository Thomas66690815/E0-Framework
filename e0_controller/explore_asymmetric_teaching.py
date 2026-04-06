#!/usr/bin/env python3
"""
E₀ C171 — Asymmetric Teaching Exploration
===========================================

Open Question Q4: Does transfer direction matter when LLMs evaluate
differently per language?

Research note: docs/research/E0_ASYMMETRIC_TEACHING_RESEARCH_v1.md

Phases:
  1. Landscape construction + curriculum training (EN, DE, ONTO)
  2. Quality differentiation analysis per domain
  3. WL fingerprint information content comparison
  4. Asymmetric transfer simulation (EN→DE vs DE→EN)
  5. LLM-scored landscape comparison (if API available)
  6. Summary + design verdict
"""

import sys
import os
import time
import math
import statistics
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) + "/..")

from e0_controller.canon_loader import load_canon
from e0_controller.curriculum import CurriculumRunner
from e0_controller.bootstrapper import bootstrap_landscape
from e0_controller.landscape import Landscape
from e0_controller.primitives import Edge, Outcome
from e0_controller.dream_mode import (
    dream_compatibility,
    wl_node_fingerprints,
    wl_node_distance,
    WLNodeFingerprint,
    find_wl_node_equivalences_hungarian,
    find_equivalences,
    DreamObserver,
    propose_bridges,
    propose_node_bridges,
)
from e0_controller.historization import Historization

EXEC_FN = lambda s, t: Outcome.SUCCESS  # noqa: E731


# ──────────────────────────────────────────────
# Analysis helpers
# ──────────────────────────────────────────────

def quality_stats(landscape: Landscape) -> dict:
    """Per-landscape quality differentiation statistics."""
    h = landscape.historization
    qualities = [h.trace_quality(e) for e in landscape.edges]
    loads = [h.trace_load(e) for e in landscape.edges]

    if not qualities:
        return {"q_mean": 0, "q_std": 0, "q_range": 0,
                "load_mean": 0, "load_std": 0, "n_edges": 0}

    q_mean = statistics.mean(qualities)
    q_std = statistics.stdev(qualities) if len(qualities) > 1 else 0.0
    load_mean = statistics.mean(loads)
    load_std = statistics.stdev(loads) if len(loads) > 1 else 0.0

    return {
        "q_mean": q_mean,
        "q_std": q_std,
        "q_range": max(qualities) - min(qualities),
        "q_min": min(qualities),
        "q_max": max(qualities),
        "load_mean": load_mean,
        "load_std": load_std,
        "n_edges": len(qualities),
    }


def fingerprint_info_content(fps: list) -> dict:
    """Measure information content of WL fingerprints.

    Higher variance across features = more discriminative fingerprints.
    Higher inter-node distance spread = better node differentiation.
    """
    if not fps:
        return {}

    n_dims = len(fps[0].features)
    n_nodes = len(fps)

    # Per-dimension variance across nodes
    dim_variances = []
    for d in range(n_dims):
        vals = [fp.features[d] for fp in fps]
        if len(vals) > 1:
            dim_variances.append(statistics.variance(vals))
        else:
            dim_variances.append(0.0)

    # Mean fingerprint norm
    norms = [math.sqrt(sum(x**2 for x in fp.features) / n_dims) for fp in fps]

    # Inter-node distance distribution
    if n_nodes >= 2:
        dists = []
        for i in range(min(n_nodes, 50)):  # cap for performance
            for j in range(i + 1, min(n_nodes, 50)):
                dists.append(wl_node_distance(fps[i], fps[j]))
        dist_mean = statistics.mean(dists)
        dist_std = statistics.stdev(dists) if len(dists) > 1 else 0.0
    else:
        dist_mean = 0.0
        dist_std = 0.0

    # Active dimensions (variance > threshold)
    active_dims = sum(1 for v in dim_variances if v > 1e-6)

    return {
        "n_nodes": n_nodes,
        "n_dims": n_dims,
        "mean_dim_variance": statistics.mean(dim_variances),
        "max_dim_variance": max(dim_variances),
        "active_dims": active_dims,
        "active_fraction": active_dims / n_dims if n_dims > 0 else 0,
        "mean_norm": statistics.mean(norms),
        "norm_std": statistics.stdev(norms) if len(norms) > 1 else 0.0,
        "inter_node_dist_mean": dist_mean,
        "inter_node_dist_std": dist_std,
    }


def transfer_quality(
    observer: DreamObserver,
    donor_name: str,
    target_name: str,
    target_landscape: Landscape,
) -> dict:
    """Measure transfer quality from donor to target.

    Uses propose_bridges + propose_node_bridges to see what the dream
    pipeline would suggest, then measures proposal quality.
    """
    # Pick a random start/goal from target for bridge proposals
    states = sorted(target_landscape.states)
    if len(states) < 2:
        return {"n_bridges": 0, "n_node_bridges": 0}

    current = states[0]
    goal = states[-1]

    # Edge-level bridges
    try:
        br = propose_bridges(
            observer, target_name, current, goal,
            max_bridges=10, min_quality=-1.0,
        )
        n_bridges = len(br.proposals)
        bridge_discounts = [p.coupling_discount for p in br.proposals]
    except Exception:
        n_bridges = 0
        bridge_discounts = []

    # Node-level bridges
    try:
        nbr = propose_node_bridges(
            observer, target_name, current, goal,
            min_quality=-1.0, max_proposals=10,
        )
        n_node_bridges = len(nbr.proposals)
        node_discounts = [p.coupling_discount for p in nbr.proposals]
    except Exception:
        n_node_bridges = 0
        node_discounts = []

    return {
        "n_bridges": n_bridges,
        "mean_bridge_discount": (statistics.mean(bridge_discounts)
                                 if bridge_discounts else 0.0),
        "n_node_bridges": n_node_bridges,
        "mean_node_discount": (statistics.mean(node_discounts)
                               if node_discounts else 0.0),
    }


# ═══════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════

def main():
    t0 = time.time()

    # ── Phase 1: Construct + train landscapes ─────────────────
    print("=" * 70)
    print("PHASE 1: Landscape Construction + Curriculum Training")
    print("=" * 70)

    landscapes = {}
    canon_map = {
        "EN": "english_basic_enriched",
        "DE": "german_basic_enriched",
        "ONTO": "ontodynamics",
    }

    for label, name in canon_map.items():
        runner = CurriculumRunner(
            name, EXEC_FN,
            equilibrium_threshold=2.0,
            equilibrium_patience=3,
            max_episodes_per_turn=15,
            max_cycles_per_episode=40,
        )
        results = runner.run()
        landscapes[label] = runner.final_landscape
        total_steps = sum(r.total_steps for r in results)
        print(f"  {label}: {len(results)} turns, {total_steps} steps, "
              f"{len(landscapes[label].states)} nodes, "
              f"{len(landscapes[label].edges)} edges")

    # ── Phase 2: Quality differentiation analysis ─────────────
    print("\n" + "=" * 70)
    print("PHASE 2: Quality Differentiation per Domain")
    print("=" * 70)

    print(f"\n  {'Domain':>8} {'edges':>6} {'q_mean':>7} {'q_std':>7} "
          f"{'q_range':>8} {'q_min':>7} {'q_max':>7} {'load_μ':>7} {'load_σ':>7}")
    print("  " + "-" * 75)

    for name in ("EN", "DE", "ONTO"):
        qs = quality_stats(landscapes[name])
        print(f"  {name:>8} {qs['n_edges']:>6} {qs['q_mean']:>7.4f} {qs['q_std']:>7.4f} "
              f"{qs['q_range']:>8.4f} {qs['q_min']:>7.4f} {qs['q_max']:>7.4f} "
              f"{qs['load_mean']:>7.2f} {qs['load_std']:>7.2f}")

    # Per-node quality stats (degree-weighted)
    print("\n  Per-node edge quality std (top-10 most differentiated):")
    for name in ("EN", "DE"):
        ls = landscapes[name]
        h = ls.historization
        node_qstds = {}
        for node in sorted(ls.states):
            qs = []
            for e in ls.edges:
                if e.source == node or e.target == node:
                    qs.append(h.trace_quality(e))
            if len(qs) > 1:
                node_qstds[node] = statistics.stdev(qs)
            else:
                node_qstds[node] = 0.0
        top10 = sorted(node_qstds.items(), key=lambda x: -x[1])[:10]
        print(f"\n    {name}:")
        for node, qstd in top10:
            deg = sum(1 for e in ls.edges if e.source == node or e.target == node)
            print(f"      {node:>20}: q_std={qstd:.4f}  deg={deg}")

    # ── Phase 3: WL fingerprint information content ───────────
    print("\n" + "=" * 70)
    print("PHASE 3: WL Fingerprint Information Content")
    print("=" * 70)

    fps_data = {}
    for name in ("EN", "DE", "ONTO"):
        fps = wl_node_fingerprints(landscapes[name], name, depth=2)
        fps_data[name] = fps
        info = fingerprint_info_content(fps)
        print(f"\n  {name}:")
        print(f"    Nodes: {info['n_nodes']}, Dims: {info['n_dims']}")
        print(f"    Mean dim variance: {info['mean_dim_variance']:.6f}")
        print(f"    Max dim variance:  {info['max_dim_variance']:.6f}")
        print(f"    Active dims (var>1e-6): {info['active_dims']}/{info['n_dims']} "
              f"({info['active_fraction']:.1%})")
        print(f"    Mean norm: {info['mean_norm']:.4f} ± {info['norm_std']:.4f}")
        print(f"    Inter-node distance: {info['inter_node_dist_mean']:.4f} "
              f"± {info['inter_node_dist_std']:.4f}")

    # Compare EN vs DE feature-by-feature
    print("\n  EN vs DE fingerprint comparison (first 27 dims = round 0+1):")
    fps_en = fps_data["EN"]
    fps_de = fps_data["DE"]

    print(f"  {'Dim':>4} {'EN_var':>10} {'DE_var':>10} {'ratio':>8} {'dominant':>10}")
    print("  " + "-" * 50)
    for d in range(min(27, len(fps_en[0].features))):
        vals_en = [fp.features[d] for fp in fps_en]
        vals_de = [fp.features[d] for fp in fps_de]
        var_en = statistics.variance(vals_en) if len(vals_en) > 1 else 0.0
        var_de = statistics.variance(vals_de) if len(vals_de) > 1 else 0.0
        ratio = var_en / var_de if var_de > 1e-10 else float("inf")
        dom = "EN" if ratio > 1.1 else ("DE" if ratio < 0.9 else "≈")
        print(f"  {d:>4} {var_en:>10.6f} {var_de:>10.6f} {ratio:>8.3f} {dom:>10}")

    # ── Phase 4: Hungarian match asymmetry ────────────────────
    print("\n" + "=" * 70)
    print("PHASE 4: Hungarian Match Asymmetry (EN↔DE)")
    print("=" * 70)

    eqs = find_wl_node_equivalences_hungarian(
        landscapes["EN"], landscapes["DE"],
        domain_a="EN", domain_b="DE", depth=2,
    )

    print(f"\n  {len(eqs)} node pairs matched")
    print(f"\n  {'Rank':>4} {'dist':>7} {'EN_node':>20} {'DE_node':>20} "
          f"{'EN_deg':>6} {'DE_deg':>6} {'EN_qstd':>8} {'DE_qstd':>8}")
    print("  " + "-" * 85)

    en_info = {}
    de_info = {}
    h_en = landscapes["EN"].historization
    h_de = landscapes["DE"].historization

    for node in landscapes["EN"].states:
        qs = [h_en.trace_quality(e) for e in landscapes["EN"].edges
              if e.source == node or e.target == node]
        deg = len(qs)
        qstd = statistics.stdev(qs) if len(qs) > 1 else 0.0
        en_info[node] = {"deg": deg, "qstd": qstd}

    for node in landscapes["DE"].states:
        qs = [h_de.trace_quality(e) for e in landscapes["DE"].edges
              if e.source == node or e.target == node]
        deg = len(qs)
        qstd = statistics.stdev(qs) if len(qs) > 1 else 0.0
        de_info[node] = {"deg": deg, "qstd": qstd}

    # Show top-10 and bottom-5 matches
    for i, eq in enumerate(eqs[:10], 1):
        en_n = eq.fp_a.node
        de_n = eq.fp_b.node
        ei = en_info.get(en_n, {"deg": 0, "qstd": 0})
        di = de_info.get(de_n, {"deg": 0, "qstd": 0})
        print(f"  {i:>4} {eq.distance:>7.4f} {en_n:>20} {de_n:>20} "
              f"{ei['deg']:>6} {di['deg']:>6} {ei['qstd']:>8.4f} {di['qstd']:>8.4f}")
    if len(eqs) > 15:
        print("  ...")
        for eq in eqs[-5:]:
            en_n = eq.fp_a.node
            de_n = eq.fp_b.node
            ei = en_info.get(en_n, {"deg": 0, "qstd": 0})
            di = de_info.get(de_n, {"deg": 0, "qstd": 0})
            print(f"       {eq.distance:>7.4f} {en_n:>20} {de_n:>20} "
                  f"{ei['deg']:>6} {di['deg']:>6} {ei['qstd']:>8.4f} {di['qstd']:>8.4f}")

    # Correlation: does match quality correlate with q_std difference?
    qstd_diffs = []
    match_dists = []
    for eq in eqs:
        en_n = eq.fp_a.node
        de_n = eq.fp_b.node
        ei = en_info.get(en_n, {"qstd": 0})
        di = de_info.get(de_n, {"qstd": 0})
        qstd_diffs.append(abs(ei["qstd"] - di["qstd"]))
        match_dists.append(eq.distance)

    # Simple correlation (Pearson)
    if len(qstd_diffs) > 2:
        mean_d = statistics.mean(qstd_diffs)
        mean_m = statistics.mean(match_dists)
        cov = sum((d - mean_d) * (m - mean_m) for d, m in zip(qstd_diffs, match_dists)) / len(qstd_diffs)
        std_d = statistics.stdev(qstd_diffs)
        std_m = statistics.stdev(match_dists)
        corr = cov / (std_d * std_m) if std_d > 0 and std_m > 0 else 0.0
        print(f"\n  Correlation(|q_std_diff|, match_distance) = {corr:.4f}")
        if abs(corr) > 0.3:
            print("  → Quality differentiation gap DOES predict match quality")
        else:
            print("  → Quality differentiation gap does NOT predict match quality")

    # ── Phase 5: Transfer direction simulation ────────────────
    print("\n" + "=" * 70)
    print("PHASE 5: Transfer Direction Simulation")
    print("=" * 70)

    # Set up DreamObserver with EN+DE
    observer = DreamObserver(
        readiness_threshold=0.0,  # accept all
        node_equivalence_method="hungarian",
        wl_depth=2,
        compatibility_threshold=None,  # don't gate
    )
    observer.register("EN", landscapes["EN"])
    observer.register("DE", landscapes["DE"])

    # Run dream cycles to build up equivalences
    print("\n  Running 3 dream cycles...")
    for i in range(3):
        result = observer.dream_cycle()
        print(f"    Cycle {i+1}: {result.equivalences_new} new eq edges, "
              f"{result.equivalences_found} total eq, "
              f"{result.node_equivalences_found} node eq")

    # Feed back SUCCESS on all equivalences to build up trace_quality
    print("\n  Providing feedback (SUCCESS on all equivalences)...")
    dl = observer._dream_landscape
    if dl is not None:
        feedback_count = 0
        for edge in dl.edges:
            for _ in range(3):  # 3 rounds of positive feedback
                observer.feedback(edge.source, edge.target, Outcome.SUCCESS)
                feedback_count += 1
        print(f"    {feedback_count} feedback events recorded")

    # Test transfer EN→DE
    print("\n  Transfer EN→DE (EN donates to DE):")
    en_to_de = transfer_quality(observer, "EN", "DE", landscapes["DE"])
    print(f"    Edge bridges: {en_to_de['n_bridges']}, "
          f"mean discount: {en_to_de['mean_bridge_discount']:.4f}")
    print(f"    Node bridges: {en_to_de['n_node_bridges']}, "
          f"mean discount: {en_to_de['mean_node_discount']:.4f}")

    # Test transfer DE→EN
    print("\n  Transfer DE→EN (DE donates to EN):")
    de_to_en = transfer_quality(observer, "DE", "EN", landscapes["EN"])
    print(f"    Edge bridges: {de_to_en['n_bridges']}, "
          f"mean discount: {de_to_en['mean_bridge_discount']:.4f}")
    print(f"    Node bridges: {de_to_en['n_node_bridges']}, "
          f"mean discount: {de_to_en['mean_node_discount']:.4f}")

    # Compare directions
    print("\n  Direction comparison:")
    if en_to_de['n_bridges'] > 0 and de_to_en['n_bridges'] > 0:
        ratio_b = en_to_de['mean_bridge_discount'] / de_to_en['mean_bridge_discount']
        print(f"    Bridge discount ratio (EN→DE / DE→EN): {ratio_b:.4f}")
        if abs(ratio_b - 1.0) < 0.05:
            print("    → SYMMETRIC: transfer direction does not matter for bridges")
        else:
            better = "EN→DE" if ratio_b > 1.0 else "DE→EN"
            print(f"    → ASYMMETRIC: {better} has higher discounts")

    if en_to_de['n_node_bridges'] > 0 and de_to_en['n_node_bridges'] > 0:
        ratio_n = en_to_de['mean_node_discount'] / de_to_en['mean_node_discount']
        print(f"    Node discount ratio (EN→DE / DE→EN): {ratio_n:.4f}")
        if abs(ratio_n - 1.0) < 0.05:
            print("    → SYMMETRIC: transfer direction does not matter for nodes")
        else:
            better = "EN→DE" if ratio_n > 1.0 else "DE→EN"
            print(f"    → ASYMMETRIC: {better} has higher discounts")

    # ── Phase 6: Equivalence quality per direction ────────────
    print("\n" + "=" * 70)
    print("PHASE 6: Dream Landscape Equivalence Quality")
    print("=" * 70)

    # Query equivalences from each domain's perspective
    for domain in ("EN", "DE"):
        eqs_for = observer.equivalences_for(domain, min_quality=-1.0)
        if eqs_for:
            qualities = [e["trace_quality"] for e in eqs_for]
            loads = [e["trace_load"] for e in eqs_for]
            print(f"\n  {domain} perspective ({len(eqs_for)} equivalences):")
            print(f"    trace_quality: mean={statistics.mean(qualities):.4f} "
                  f"std={statistics.stdev(qualities) if len(qualities) > 1 else 0:.4f}")
            print(f"    trace_load:    mean={statistics.mean(loads):.2f} "
                  f"std={statistics.stdev(loads) if len(loads) > 1 else 0:.2f}")

            # Quality distribution
            q_bins = {"q<0": 0, "0≤q<0.3": 0, "0.3≤q<0.6": 0, "q≥0.6": 0}
            for q in qualities:
                if q < 0:
                    q_bins["q<0"] += 1
                elif q < 0.3:
                    q_bins["0≤q<0.3"] += 1
                elif q < 0.6:
                    q_bins["0.3≤q<0.6"] += 1
                else:
                    q_bins["q≥0.6"] += 1
            print(f"    Distribution: {q_bins}")
        else:
            print(f"\n  {domain}: no equivalences found")

    # ── Phase 7: Hypothesis test with different training ──────
    print("\n" + "=" * 70)
    print("PHASE 7: Asymmetric Training Effect")
    print("=" * 70)
    print("\n  Test: What if one domain has MORE training than the other?")

    # Same canon (EN), different training intensity
    # This isolates training effect from topology differences
    runner_en_heavy = CurriculumRunner(
        "english_basic_enriched", EXEC_FN,
        equilibrium_threshold=2.0,
        equilibrium_patience=5,
        max_episodes_per_turn=30,
        max_cycles_per_episode=60,
    )
    results_heavy = runner_en_heavy.run()
    en_heavy = runner_en_heavy.final_landscape
    heavy_steps = sum(r.total_steps for r in results_heavy)

    runner_en_light = CurriculumRunner(
        "english_basic_enriched", EXEC_FN,
        equilibrium_threshold=2.0,
        equilibrium_patience=2,
        max_episodes_per_turn=5,
        max_cycles_per_episode=20,
    )
    results_light = runner_en_light.run()
    en_light = runner_en_light.final_landscape
    light_steps = sum(r.total_steps for r in results_light)

    qs_heavy = quality_stats(en_heavy)
    qs_light = quality_stats(en_light)
    compat = dream_compatibility(en_heavy, en_light)

    print(f"\n  Same canon (EN), different training:")
    print(f"  EN_heavy ({heavy_steps} steps): q_std={qs_heavy['q_std']:.4f}, "
          f"load_mean={qs_heavy['load_mean']:.2f}")
    print(f"  EN_light ({light_steps} steps): q_std={qs_light['q_std']:.4f}, "
          f"load_mean={qs_light['load_mean']:.2f}")
    print(f"  Compatibility (same canon, diff training): {compat:.4f}")

    # Fingerprint info content comparison
    fps_heavy = wl_node_fingerprints(en_heavy, "EN_H", depth=2)
    fps_light = wl_node_fingerprints(en_light, "EN_L", depth=2)
    info_heavy = fingerprint_info_content(fps_heavy)
    info_light = fingerprint_info_content(fps_light)

    print(f"\n  Fingerprint info (heavy vs light training, same topology):")
    print(f"    EN_heavy: mean_var={info_heavy['mean_dim_variance']:.6f}, "
          f"inter_dist={info_heavy['inter_node_dist_mean']:.4f}")
    print(f"    EN_light: mean_var={info_light['mean_dim_variance']:.6f}, "
          f"inter_dist={info_light['inter_node_dist_mean']:.4f}")

    var_ratio = (info_heavy['mean_dim_variance'] / info_light['mean_dim_variance']
                 if info_light['mean_dim_variance'] > 1e-10 else float("inf"))
    print(f"    Variance ratio (heavy/light): {var_ratio:.3f}")

    # Also compare EN vs DE (topology effect)
    info_en = fingerprint_info_content(fps_data["EN"])
    info_de = fingerprint_info_content(fps_data["DE"])
    topo_ratio = (info_en['mean_dim_variance'] / info_de['mean_dim_variance']
                  if info_de['mean_dim_variance'] > 1e-10 else float("inf"))
    print(f"\n  For comparison — EN vs DE (same training, diff topology):")
    print(f"    Variance ratio (EN/DE): {topo_ratio:.3f}")

    if abs(var_ratio - 1.0) < 0.1:
        print("\n    → Training intensity does NOT change fingerprint information content")
        print("    → Asymmetry from training is negligible")
    else:
        print("\n    → Training intensity DOES change fingerprint information content")
        print("    → Asymmetric teaching from training differences may matter")

    if abs(topo_ratio - 1.0) > abs(var_ratio - 1.0):
        print("    → Topology effect DOMINATES over training effect")
    else:
        print("    → Training effect is LARGER than topology effect")

    # ── Phase 8: Summary ──────────────────────────────────────
    print("\n" + "=" * 70)
    print("PHASE 8: Summary + Design Verdict")
    print("=" * 70)

    print(f"""
  Q4 Findings:
  
  1. Quality differentiation (same training, diff topology):
     EN q_std = {quality_stats(landscapes['EN'])['q_std']:.4f}
     DE q_std = {quality_stats(landscapes['DE'])['q_std']:.4f}
     Topology variance ratio EN/DE = {topo_ratio:.3f}
  
  2. WL fingerprint information:
     EN inter-node dist = {fingerprint_info_content(fps_data['EN'])['inter_node_dist_mean']:.4f}
     DE inter-node dist = {fingerprint_info_content(fps_data['DE'])['inter_node_dist_mean']:.4f}
  
  3. Transfer direction (EN↔DE):
     EN→DE bridges: {en_to_de['n_bridges']} (discount={en_to_de['mean_bridge_discount']:.4f})
     DE→EN bridges: {de_to_en['n_bridges']} (discount={de_to_en['mean_bridge_discount']:.4f})
  
  4. Training asymmetry (same topology, diff training):
     Heavy/light variance ratio: {var_ratio:.3f}
     Topology effect vs training effect: {'topology dominates' if abs(topo_ratio - 1.0) > abs(var_ratio - 1.0) else 'training dominates'}
  
  VERDICT:
""")

    # Determine verdict based on data
    q_diff = abs(quality_stats(landscapes['EN'])['q_std'] - quality_stats(landscapes['DE'])['q_std'])
    training_effect = abs(var_ratio - 1.0)
    topology_effect = abs(topo_ratio - 1.0)

    if training_effect < 0.01:
        print("  For curriculum-trained (always-SUCCESS) canons:")
        print(f"  → Training has ZERO effect on fingerprints (ratio={var_ratio:.3f})")
        print(f"  → All differences are topology-driven (EN/DE ratio={topo_ratio:.3f})")
        print(f"  → Quality differentiation is minor (EN={quality_stats(landscapes['EN'])['q_std']:.4f}, "
              f"DE={quality_stats(landscapes['DE'])['q_std']:.4f})")
        print("")
        print("  CONCLUSION: Asymmetric teaching is NOT needed for curriculum-trained canons.")
        print("  WL fingerprints are fully determined by topology (edge count, connectivity).")
        print("  Training intensity, training steps, and direction are irrelevant.")
        print("")
        print("  Asymmetric teaching becomes relevant ONLY when:")
        print("  - LLM scoring produces genuinely different quality distributions per language")
        print("  - Bootstrapped domains have different score resolutions")
        print("  This constrains the feature scope to LLM-bootstrapped domains only.")
    else:
        print("  Training intensity changes fingerprint information content!")
        print(f"  → Training effect: {training_effect:.3f}")
        print(f"  → Topology effect: {topology_effect:.3f}")
        print("  → Asymmetric teaching may be warranted.")

    t_total = time.time() - t0
    print(f"\n  Total runtime: {t_total:.1f}s")
    print("=" * 70)


if __name__ == "__main__":
    main()
