"""
C181 — Dream Transitivity Exploration

Research question: Do dream equivalences form transitive chains?
  If A↔B and B↔C have equivalences, does A↔C follow?

Setup: N=5 mesh (EN + DE + ONTO + COOK + PROJ) from C180.
  Known clusters: {EN,DE} and {COOK,PROJ}.
  ONTO acts as bridge node (compat shifts post-navigation).

Transitivity test:
  1. Run mesh until ONTO bridges clusters (ONTO↔COOK, ONTO↔PROJ compat < 0.6)
  2. Walk Dream Landscape edges to find transitive chains:
     A:x → ONTO:y → C:z means A↔C via ONTO
  3. Compare transitive equivalences against direct WL distance
  4. Measure: are transitive chains structurally meaningful or noise?

Three possible outcomes:
  A. Transitivity holds: transitive chains have low distance → emergent
  B. Transitivity fails: transitive chains are noise → locality, not global
  C. Partial: some chains work (similar topology) → conditional transitivity

Reference: docs/E0_STRATEGIC_ROADMAP_v1.md Priority 3, open question 3
"""

from __future__ import annotations

import math
import time
from collections import defaultdict
from dataclasses import dataclass, field
from itertools import combinations
from typing import Dict, List, Optional, Set, Tuple

from e0_controller.bootstrapper import bootstrap_landscape
from e0_controller.canon_loader import load_canon
from e0_controller.controller import E0Controller, HybridMode
from e0_controller.coupling_router import (
    CouplingRouter,
    Universe,
    update_weights_from_dream,
)
from e0_controller.curriculum import CurriculumRunner
from e0_controller.dream_mode import (
    DreamObserver,
    dream_compatibility,
    wl_node_fingerprints,
    wl_node_distance,
    find_wl_node_equivalences_hungarian,
)
from e0_controller.primitives import Outcome
from e0_controller.structural_entropy import (
    dream_pressure,
    structural_temperature,
)
from e0_controller.explore_n_domain_mesh_n5 import (
    build_cooking_landscape,
    build_project_landscape,
    CANON_DOMAINS,
    BOOTSTRAP_DOMAINS,
    ALL_LABELS,
    EXEC_FN,
    COMPATIBILITY_THRESHOLD,
)


# ── Configuration ────────────────────────────────────────────────────

N_EPISODES = 10          # more episodes to let ONTO bridge stabilize
MAX_CYCLES_PER_RUN = 40


# ── Transitivity Data Structures ─────────────────────────────────────

@dataclass
class TransitiveChain:
    """A transitive equivalence chain A:x → B:y → C:z."""
    source_domain: str
    source_state: str           # Dream Landscape state (e.g., "EN:thing→self")
    bridge_domain: str
    bridge_state: str           # "ONTO:difference→identity"
    target_domain: str
    target_state: str           # "COOK:PLANNING→SERVING"
    distance_ab: float          # edge quality source→bridge
    distance_bc: float          # edge quality bridge→target
    total_distance: float       # sum (lower = better)


@dataclass
class TransitivityReport:
    """Results of the transitivity analysis."""
    bridge_domain: str
    chains_found: int
    unique_source_targets: int          # unique (source_domain, target_domain) pairs
    chains_by_pair: Dict[str, List[TransitiveChain]]
    direct_compatibility: Dict[str, float]  # direct WL compat for same pairs
    verdict: str


# ── Core Analysis ────────────────────────────────────────────────────

def find_transitive_chains(
    observer: DreamObserver,
    bridge_domain: str,
    *,
    exclude_known_compatible: bool = False,
    landscapes: Optional[Dict[str, dict]] = None,
) -> List[TransitiveChain]:
    """Find all transitive equivalence chains through a bridge domain.

    Walks the Dream Landscape: for each edge A:x↔BRIDGE:y and each
    edge BRIDGE:y↔C:z, creates a TransitiveChain if A≠C and neither
    is the bridge domain.

    Uses Dream Landscape historization quality as distance proxy.
    """
    dl = observer._dream_landscape
    if dl is None:
        return []

    # ── Step 1: Build adjacency from Dream Landscape edges
    # Collect all bridge states and their neighbors
    bridge_prefix = f"{bridge_domain}:"
    bridge_neighbors: Dict[str, List[Tuple[str, float]]] = defaultdict(list)

    for edge in dl.edges:
        src, tgt = edge.source, edge.target
        # Use effective tension as distance proxy (lower = closer match)
        dist = dl.effective_tension(src, tgt)
        if math.isinf(dist):
            dist = 1e6  # large but finite sentinel

        if src.startswith(bridge_prefix) and not tgt.startswith(bridge_prefix):
            bridge_neighbors[src].append((tgt, dist))
        elif tgt.startswith(bridge_prefix) and not src.startswith(bridge_prefix):
            bridge_neighbors[tgt].append((src, dist))

    # ── Step 2: Find chains through bridge states
    chains = []
    for bridge_state, neighbors in bridge_neighbors.items():
        # Group neighbors by domain
        by_domain: Dict[str, List[Tuple[str, float]]] = defaultdict(list)
        for state, dist in neighbors:
            domain = state.split(":")[0]
            if domain != bridge_domain:
                by_domain[domain].append((state, dist))

        # Generate chains: every cross-domain pair through this bridge state
        domains = list(by_domain.keys())
        for i, dom_a in enumerate(domains):
            for dom_b in domains[i + 1:]:
                for state_a, dist_a in by_domain[dom_a]:
                    for state_b, dist_b in by_domain[dom_b]:
                        chains.append(TransitiveChain(
                            source_domain=dom_a,
                            source_state=state_a,
                            bridge_domain=bridge_domain,
                            bridge_state=bridge_state,
                            target_domain=dom_b,
                            target_state=state_b,
                            distance_ab=dist_a,
                            distance_bc=dist_b,
                            total_distance=dist_a + dist_b,
                        ))

    chains.sort(key=lambda c: c.total_distance)
    return chains


def analyze_transitivity(
    observer: DreamObserver,
    landscapes: Dict[str, dict],
    bridge_domain: str = "ONTO",
) -> TransitivityReport:
    """Full transitivity analysis for a given bridge domain."""
    chains = find_transitive_chains(observer, bridge_domain)

    # Group by pair
    chains_by_pair: Dict[str, List[TransitiveChain]] = defaultdict(list)
    for c in chains:
        pair = f"{c.source_domain}↔{c.target_domain}"
        chains_by_pair[pair].append(c)

    # Compute direct compatibility for each transitive pair
    direct_compat: Dict[str, float] = {}
    for pair in chains_by_pair:
        a, b = pair.split("↔")
        if a in landscapes and b in landscapes:
            score = dream_compatibility(
                landscapes[a]["landscape"],
                landscapes[b]["landscape"],
            )
            direct_compat[pair] = score

    # Verdict
    if not chains:
        verdict = "NO_CHAINS — bridge domain has no cross-domain neighbors"
    elif not chains_by_pair:
        verdict = "NO_PAIRS — all chains are within same domain pair"
    else:
        # Check: do any transitive pairs lack direct equivalences?
        new_connections = []
        for pair in chains_by_pair:
            a, b = pair.split("↔")
            # Check direct equivalences
            eqs_a = observer.equivalences_for(a)
            direct_count = sum(1 for eq in eqs_a
                              if eq["partner_state"].startswith(f"{b}:"))
            if direct_count == 0:
                new_connections.append(pair)

        if new_connections:
            verdict = (f"TRANSITIVE_NEW — {len(new_connections)} domain pairs "
                      f"connected only via bridge: {new_connections}")
        else:
            verdict = ("TRANSITIVE_REDUNDANT — all transitive pairs already "
                      "have direct equivalences")

    unique_pairs = len(chains_by_pair)
    return TransitivityReport(
        bridge_domain=bridge_domain,
        chains_found=len(chains),
        unique_source_targets=unique_pairs,
        chains_by_pair=dict(chains_by_pair),
        direct_compatibility=direct_compat,
        verdict=verdict,
    )


# ── Phases ───────────────────────────────────────────────────────────

def phase_domain_prep() -> Dict[str, dict]:
    """Phase 1: Prepare all 5 domains (curriculum + bootstrap)."""
    print("── Phase 1: Domain Preparation ─────────────────────────")
    trained = {}

    for label, canon_name, start, goal in CANON_DOMAINS:
        t0 = time.time()
        runner = CurriculumRunner(
            canon_name, EXEC_FN,
            equilibrium_threshold=2.0,
            equilibrium_patience=3,
            max_episodes_per_turn=15,
            max_cycles_per_episode=40,
        )
        runner.run()
        L = runner.final_landscape
        dt = time.time() - t0
        T_s = structural_temperature(L.historization)
        n_n, n_e = len(L.states), len(L.edges)
        print(f"  {label:6s}: curriculum, {n_n}n/{n_e}e, "
              f"T_s={T_s:.3f}  ({dt:.1f}s)")
        trained[label] = {"landscape": L, "start": start, "goal": goal}

    builders = [
        ("COOK", build_cooking_landscape, "PLANNING", "SERVING"),
        ("PROJ", build_project_landscape, "PLANNING", "DEPLOYMENT"),
    ]
    for label, builder_fn, start, goal in builders:
        L = builder_fn()
        n_n, n_e = len(L.states), len(L.edges)
        print(f"  {label:6s}: bootstrap, {n_n}n/{n_e}e")
        trained[label] = {"landscape": L, "start": start, "goal": goal}

    print()
    return trained


def phase_mesh_run(trained: Dict) -> Tuple[DreamObserver, CouplingRouter, Dict]:
    """Phase 2: Assemble mesh and run episodes."""
    print(f"── Phase 2: Mesh Assembly + {N_EPISODES} Episodes ──────────────")

    observer = DreamObserver(
        readiness_threshold=0.0,
        node_equivalence_method="hungarian",
        compatibility_threshold=COMPATIBILITY_THRESHOLD,
    )
    universes = []
    controllers = {}
    for label in ALL_LABELS:
        info = trained[label]
        L = info["landscape"]
        observer.register(label, L)
        ctrl = E0Controller(L, EXEC_FN, hybrid_mode=HybridMode.GREEDY)
        controllers[label] = ctrl
        universes.append(Universe(
            name=label, landscape=L,
            execute_fn=EXEC_FN, start=info["start"], goal=info["goal"],
        ))
    router = CouplingRouter(universes)

    for ep in range(1, N_EPISODES + 1):
        for label in ALL_LABELS:
            info = trained[label]
            controllers[label].run(info["start"], max_cycles=MAX_CYCLES_PER_RUN,
                                   goal=info["goal"])
        result = observer.dream_cycle()
        update_weights_from_dream(router, observer)

        # Per-episode summary
        eq_counts = {}
        for a, b in combinations(ALL_LABELS, 2):
            eqs = observer.equivalences_for(a)
            count = sum(1 for e in eqs if e["partner_state"].startswith(f"{b}:"))
            if count > 0:
                eq_counts[f"{a}↔{b}"] = count
        skipped = len(result.compatibility_skipped)
        eq_str = "  ".join(f"{k}={v}" for k, v in sorted(eq_counts.items()))
        print(f"  Ep {ep:2d}: eq=[{eq_str}]  skip={skipped}")

    print()
    return observer, router, controllers


def phase_compatibility_matrix(trained: Dict, label: str = "3"):
    """Phase 3: Post-navigation compatibility matrix."""
    print(f"── Phase {label}: Post-Navigation Compatibility ────────────")
    labels = list(trained.keys())
    for a, b in combinations(labels, 2):
        score = dream_compatibility(
            trained[a]["landscape"], trained[b]["landscape"])
        verdict = "PASS" if score < COMPATIBILITY_THRESHOLD else "SKIP"
        print(f"  {a:4s}↔{b:4s}: {score:.4f}  [{verdict}]")
    print()


def phase_transitivity_analysis(
    observer: DreamObserver,
    trained: Dict,
) -> TransitivityReport:
    """Phase 4: Find and analyze transitive chains."""
    print("── Phase 4: Transitivity Analysis (bridge=ONTO) ────────")

    report = analyze_transitivity(observer, trained, bridge_domain="ONTO")

    print(f"\n  Chains found: {report.chains_found}")
    print(f"  Unique domain pairs: {report.unique_source_targets}")
    print(f"  Verdict: {report.verdict}")

    if report.chains_by_pair:
        print(f"\n  Per-pair breakdown:")
        for pair, chains in sorted(report.chains_by_pair.items()):
            direct = report.direct_compatibility.get(pair, float("nan"))
            direct_status = "COMPAT" if direct < COMPATIBILITY_THRESHOLD else "INCOMPAT"
            best_chain = chains[0]  # already sorted by total_distance
            worst_chain = chains[-1]
            print(f"\n    {pair} ({len(chains)} chains, "
                  f"direct compat={direct:.4f} [{direct_status}]):")
            print(f"      Best:  {best_chain.source_state} → "
                  f"{best_chain.bridge_state} → {best_chain.target_state}")
            print(f"              dist_AB={best_chain.distance_ab:.4f}  "
                  f"dist_BC={best_chain.distance_bc:.4f}  "
                  f"total={best_chain.total_distance:.4f}")
            if len(chains) > 1:
                print(f"      Worst: total={worst_chain.total_distance:.4f}")

            # Show direct equivalences for same pair
            a, b = pair.split("↔")
            direct_eqs = observer.equivalences_for(a)
            direct_count = sum(1 for e in direct_eqs
                              if e["partner_state"].startswith(f"{b}:"))
            print(f"      Direct equivalences: {direct_count}"
                  f"  {'← only via bridge!' if direct_count == 0 else ''}")

    # ── Check for second-order transitivity: any other bridge domain?
    print("\n  Second-order check: testing all domains as potential bridges...")
    for bridge in ALL_LABELS:
        if bridge == "ONTO":
            continue
        r = analyze_transitivity(observer, trained, bridge_domain=bridge)
        if r.chains_found > 0:
            print(f"    {bridge}: {r.chains_found} chains, "
                  f"{r.unique_source_targets} pairs")
        else:
            print(f"    {bridge}: no transitive chains")

    print()
    return report


def phase_node_level_transitivity(
    observer: DreamObserver,
    trained: Dict,
):
    """Phase 5: Node-level transitivity via WL fingerprints.

    Even if the Dream Landscape doesn't show transitive chains
    (because equivalences were compatibility-gated), we can check:
    do WL fingerprints show that A↔C via B should work?

    Method: Compare WL fingerprints of A and C directly.
    If A↔B works and B↔C works, and A's fingerprints are similar
    to C's (transitivity of WL similarity), then the structure
    supports transitivity even if the DreamObserver doesn't exploit it.
    """
    print("── Phase 5: Node-Level WL Transitivity ─────────────────")

    # For each pair that has no direct equivalences,
    # compute direct WL compatibility
    labels = list(trained.keys())
    bridge = "ONTO"

    # Find all indirect connections via ONTO
    onto_compatible = []
    for label in labels:
        if label == bridge:
            continue
        score = dream_compatibility(
            trained[label]["landscape"],
            trained[bridge]["landscape"])
        if score < COMPATIBILITY_THRESHOLD:
            onto_compatible.append(label)

    print(f"  Domains compatible with {bridge}: {onto_compatible}")

    if len(onto_compatible) >= 2:
        print(f"\n  Transitive WL distance (via {bridge}):")
        for a, c in combinations(onto_compatible, 2):
            # Direct A↔C WL compat
            direct = dream_compatibility(
                trained[a]["landscape"],
                trained[c]["landscape"])
            # A↔ONTO
            ab = dream_compatibility(
                trained[a]["landscape"],
                trained[bridge]["landscape"])
            # ONTO↔C
            bc = dream_compatibility(
                trained[bridge]["landscape"],
                trained[c]["landscape"])
            # Triangle inequality check
            triangle_sum = ab + bc
            holds = direct <= triangle_sum * 1.5  # generous slack

            print(f"    {a}↔{c}: direct={direct:.4f}  "
                  f"{a}↔{bridge}={ab:.4f} + {bridge}↔{c}={bc:.4f} = {triangle_sum:.4f}")
            print(f"           triangle {'HOLDS' if holds else 'VIOLATED'}  "
                  f"(direct {'≤' if holds else '>'} 1.5×sum)")

        # Specific test: EN↔COOK via ONTO
        # This is the key chain: EN↔ONTO (post-nav compat) + ONTO↔COOK (post-nav compat)
        # → does EN↔COOK have low enough WL distance to be compatible?
        for a, c in combinations(onto_compatible, 2):
            direct = dream_compatibility(
                trained[a]["landscape"],
                trained[c]["landscape"])
            compatible = direct < COMPATIBILITY_THRESHOLD
            print(f"\n    {a}↔{c}: WL compat = {direct:.4f} → "
                  f"{'COMPATIBLE (transitivity holds!)' if compatible else 'INCOMPATIBLE (transitivity fails)'}")
    else:
        print(f"  Only {len(onto_compatible)} domain(s) compatible with "
              f"{bridge} — cannot test transitivity")

    print()


def phase_verdict(report: TransitivityReport, trained: Dict, observer: DreamObserver):
    """Final verdict."""
    print("=" * 70)
    print("  VERDICT: Dream Transitivity")
    print("=" * 70)

    if report.chains_found == 0:
        print("\n  No transitive chains found through ONTO.")
        print("  This means either:")
        print("    a) ONTO has no cross-domain equivalences yet, or")
        print("    b) ONTO's equivalences are all within one cluster")
        print("\n  Result: TRANSITIVITY NOT APPLICABLE")
    else:
        # Check for genuinely new connections
        new_pairs = []
        redundant_pairs = []
        for pair, chains in report.chains_by_pair.items():
            a, b = pair.split("↔")
            eqs = observer.equivalences_for(a)
            direct = sum(1 for e in eqs if e["partner_state"].startswith(f"{b}:"))
            if direct == 0:
                new_pairs.append((pair, len(chains)))
            else:
                redundant_pairs.append((pair, len(chains), direct))

        if new_pairs:
            print(f"\n  NEW connections via bridge (not reachable directly):")
            for pair, n_chains in new_pairs:
                compat = report.direct_compatibility.get(pair, float("nan"))
                print(f"    {pair}: {n_chains} chains  "
                      f"(direct WL compat={compat:.4f})")
            print(f"\n  Result: TRANSITIVITY EXTENDS REACH")
            print("  → Bridge domain creates connections that")
            print("    direct compatibility gating would miss.")
        else:
            print(f"\n  All {len(redundant_pairs)} transitive pairs already "
                  "have direct equivalences:")
            for pair, n_chains, n_direct in redundant_pairs:
                print(f"    {pair}: {n_chains} chains, {n_direct} direct eqs")
            print(f"\n  Result: TRANSITIVITY REDUNDANT")
            print("  → All transitive pairs already discoverable directly.")

    print("=" * 70)


# ── Main ─────────────────────────────────────────────────────────────

def main():
    print("=" * 70)
    print("C181 — Dream Transitivity Exploration")
    print("      (Do cross-domain analogies form transitive chains?)")
    print("=" * 70)
    print()

    trained = phase_domain_prep()
    observer, router, controllers = phase_mesh_run(trained)
    phase_compatibility_matrix(trained, label="3")
    report = phase_transitivity_analysis(observer, trained)
    phase_node_level_transitivity(observer, trained)
    phase_verdict(report, trained, observer)


if __name__ == "__main__":
    main()
