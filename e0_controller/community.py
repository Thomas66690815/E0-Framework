"""
E₀ Controller — Community Detection
=====================================
Emergent structure from Historization — no imposed labels.

C255: Communities are discovered from R_eff edge weights using
weighted Label Propagation (LPA).  Low resistance = strong
connection → nodes that are frequently co-traversed cluster together.

C256: Dual-mode validation — extract_community_landscapes() parallel
to legacy _extract_domain_landscapes(), plus normalized_mutual_information()
for quantitative comparison between emergent and prefix-based partitions.

Key properties:
    - Built from E₀ primitives only (R_eff = R₀ + δ_H)
    - No external dependencies, no semantic labels
    - Cold start (δ_H = 0): communities = connected components
    - After navigation: clusters emerge from traversal patterns
    - Deterministic (sorted node order, smallest-label tiebreaker)
    - Self-similar: same algorithm works at any scale

This replaces the prefix-based domain partitioning (_DOMAIN_PREFIXES)
which imposed E₂-level semantic categories as E₀-level structure.
See GT-7 in bootstrap.json for the full analysis.
"""

from __future__ import annotations

import math
from collections import defaultdict
from typing import Any, Dict, List, Set, TYPE_CHECKING

if TYPE_CHECKING:
    from .landscape import Landscape


def detect_communities(
    landscape: "Landscape",
    max_iterations: int = 100,
) -> List[Set[str]]:
    """Discover communities from R_eff edge weights.

    Uses weighted Label Propagation Algorithm (LPA):
    1. Each node starts with a unique label.
    2. Iteratively, each node adopts the label with the highest
       summed weight among its neighbors.
    3. Weight = 1/R_eff — low resistance means strong connection.
    4. Directed edges are treated as undirected (both directions
       contribute weight between the two nodes).
    5. Ties broken by smallest label (deterministic).
    6. Converges when no label changes, or after *max_iterations*.

    Parameters
    ----------
    landscape : Landscape
        The landscape to partition. Uses effective_resistance()
        which includes Historization (R_eff = R₀ + δ_H).
    max_iterations : int
        Safety cap on LPA iterations (default 100).

    Returns
    -------
    list of sets
        Each set contains the state names in one community.
        Empty landscape → empty list.
        Isolated nodes form singleton communities.
        Order of communities is deterministic (sorted by smallest member).
    """
    nodes = sorted(landscape.states)
    if not nodes:
        return []

    # --- Build undirected weighted adjacency ---
    # For each directed edge, add 1/R_eff to both directions.
    # If A→B and B→A both exist, both contribute.
    adj: Dict[str, Dict[str, float]] = defaultdict(lambda: defaultdict(float))
    for edge in landscape.edges:
        r_eff = landscape.effective_resistance(edge.source, edge.target)
        if math.isinf(r_eff) or r_eff <= 0:
            continue
        w = 1.0 / r_eff
        adj[edge.source][edge.target] += w
        adj[edge.target][edge.source] += w

    # --- Label Propagation ---
    # Initial label = node index (integer for efficiency)
    node_to_idx = {node: i for i, node in enumerate(nodes)}
    labels = list(range(len(nodes)))  # labels[i] = label of nodes[i]

    for _ in range(max_iterations):
        changed = False
        for i, node in enumerate(nodes):
            neighbors = adj[node]
            if not neighbors:
                continue  # isolated node keeps its label

            # Sum weights per neighbor label
            label_weights: Dict[int, float] = defaultdict(float)
            for neighbor, weight in neighbors.items():
                j = node_to_idx[neighbor]
                label_weights[labels[j]] += weight

            # Best label: max weight, then smallest label for ties
            best_label = min(
                label_weights,
                key=lambda lbl: (-label_weights[lbl], lbl),
            )
            if best_label != labels[i]:
                labels[i] = best_label
                changed = True

        if not changed:
            break

    # --- Group by label → communities ---
    groups: Dict[int, Set[str]] = defaultdict(set)
    for i, node in enumerate(nodes):
        groups[labels[i]].add(node)

    # Deterministic order: sort by smallest member in each community
    return sorted(groups.values(), key=lambda s: min(s))


# ── C256: Dual-Mode Validation ──────────────────────────────────


def normalized_mutual_information(
    partition_a: List[Set[str]],
    partition_b: List[Set[str]],
) -> float:
    """Normalized Mutual Information (NMI) between two partitions.

    Measures how much knowing one partition reduces uncertainty about
    the other.  NMI ∈ [0, 1]:
        0.0 → independent (no correlation)
        1.0 → identical partitioning

    Uses the arithmetic-mean normalization:
        NMI = 2 · MI(A, B) / (H(A) + H(B))

    Both partitions must cover the same set of nodes.  Nodes not
    in either partition are ignored (intersection is used).

    Parameters
    ----------
    partition_a, partition_b : list of sets
        Two partitions of node names.

    Returns
    -------
    float
        NMI score in [0, 1].  Returns 1.0 if both partitions are
        trivial (single cluster each) or empty.
    """
    # Collect all nodes present in both partitions
    nodes_a = set().union(*partition_a) if partition_a else set()
    nodes_b = set().union(*partition_b) if partition_b else set()
    universe = nodes_a & nodes_b
    n = len(universe)
    if n == 0:
        return 1.0

    # Build node → cluster-index maps (only for shared nodes)
    label_a: Dict[str, int] = {}
    for idx, cluster in enumerate(partition_a):
        for node in cluster:
            if node in universe:
                label_a[node] = idx
    label_b: Dict[str, int] = {}
    for idx, cluster in enumerate(partition_b):
        for node in cluster:
            if node in universe:
                label_b[node] = idx

    # Contingency table
    contingency: Dict[tuple, int] = defaultdict(int)
    for node in universe:
        contingency[(label_a[node], label_b[node])] += 1

    # Marginals
    row_sums: Dict[int, int] = defaultdict(int)
    col_sums: Dict[int, int] = defaultdict(int)
    for (i, j), count in contingency.items():
        row_sums[i] += count
        col_sums[j] += count

    # Entropy H(A), H(B), MI(A,B)
    h_a = -sum(
        (c / n) * math.log(c / n)
        for c in row_sums.values() if c > 0
    )
    h_b = -sum(
        (c / n) * math.log(c / n)
        for c in col_sums.values() if c > 0
    )

    mi = 0.0
    for (i, j), nij in contingency.items():
        if nij > 0:
            mi += (nij / n) * math.log(nij * n / (row_sums[i] * col_sums[j]))

    denom = h_a + h_b
    if denom < 1e-12:
        return 1.0  # both trivial → identical

    return min(1.0, max(0.0, 2.0 * mi / denom))


def extract_community_landscapes(
    landscape: "Landscape",
    communities: List[Set[str]] | None = None,
) -> Dict[str, Any]:
    """Extract per-community sub-landscapes from a landscape.

    Parallel to legacy _extract_domain_landscapes(), but uses emergent
    communities from detect_communities() instead of prefix labels.

    Each community gets its own Landscape with intra-community edges
    and historization copied from the source landscape.

    Parameters
    ----------
    landscape : Landscape
        The source landscape.
    communities : list of sets, optional
        Pre-computed communities.  If None, detect_communities() is called.

    Returns
    -------
    dict
        Mapping from community name (``"community_0"``, ``"community_1"``, ...)
        to sub-Landscape.  Names are assigned by sorted order (smallest member
        first), matching detect_communities() output order.
    """
    from .landscape import Landscape as LS
    from .primitives import Edge

    if communities is None:
        communities = detect_communities(landscape)

    # Build node → community index for fast lookup
    node_community: Dict[str, int] = {}
    for idx, cluster in enumerate(communities):
        for node in cluster:
            node_community[node] = idx

    # Collect intra-community edges
    community_edges: Dict[int, list] = defaultdict(list)
    for edge in landscape.edges:
        src_c = node_community.get(edge.source)
        tgt_c = node_community.get(edge.target)
        if src_c is not None and src_c == tgt_c:
            community_edges[src_c].append(edge)

    # Build sub-landscapes
    hist = landscape.historization
    result: Dict[str, Any] = {}
    for idx, cluster in enumerate(communities):
        name = f"community_{idx}"
        ls = LS()
        ls.inertia_modulation = True
        for node in cluster:
            ls.add_state(node)
        for edge in community_edges.get(idx, []):
            delta = landscape.difference(edge.source, edge.target)
            r0 = landscape.base_resistance(edge.source, edge.target)
            ls.add_edge(
                edge.source, edge.target,
                delta=delta if delta is not None else 0.3,
                resistance=r0 if not math.isinf(r0) else 0.2,
            )
            # Copy historization traces
            sub_edge = Edge(edge.source, edge.target)
            U = hist._U.get(edge, 0.0)
            F = hist._F.get(edge, 0.0)
            if U > 0 or F > 0:
                ls.historization._U[sub_edge] = U
                ls.historization._F[sub_edge] = F
                ls.historization._tau_last[sub_edge] = ls.historization._tau
        result[name] = ls

    return result


def prefix_partition(landscape: "Landscape") -> List[Set[str]]:
    """Build a partition from the legacy prefix convention.

    Groups nodes by their ``^[A-Z]+:`` prefix.  Nodes without a
    recognized prefix form a single 'other' group (if any).
    Returns same format as detect_communities() for NMI comparison.
    """
    import re
    prefix_re = re.compile(r"^([A-Z]+:)")
    groups: Dict[str, Set[str]] = defaultdict(set)
    other: Set[str] = set()
    for node in landscape.states:
        m = prefix_re.match(node)
        if m:
            groups[m.group(1)].add(node)
        else:
            other.add(node)
    result = sorted(groups.values(), key=lambda s: min(s))
    if other:
        result.append(other)
    return result


def compare_partitions(landscape: "Landscape") -> Dict[str, Any]:
    """Compare emergent communities with prefix-based domains.

    Returns a diagnostic dict with:
        communities: list of community sets
        prefixes: list of prefix-group sets
        nmi: NMI score between the two
        community_count: number of emergent communities
        prefix_count: number of prefix groups
        verdict: 'aligned' (NMI ≥ 0.7), 'divergent' (NMI < 0.3),
                 or 'partial' (in between)
    """
    communities = detect_communities(landscape)
    prefixes = prefix_partition(landscape)
    nmi = normalized_mutual_information(communities, prefixes)

    if nmi >= 0.7:
        verdict = "aligned"
    elif nmi < 0.3:
        verdict = "divergent"
    else:
        verdict = "partial"

    return {
        "communities": communities,
        "prefixes": prefixes,
        "nmi": round(nmi, 4),
        "community_count": len(communities),
        "prefix_count": len(prefixes),
        "verdict": verdict,
    }
