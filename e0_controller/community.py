"""
E₀ Controller — Community Detection
=====================================
Emergent structure from Historization — no imposed labels.

C255: Communities are discovered from R_eff edge weights using
weighted Label Propagation (LPA).  Low resistance = strong
connection → nodes that are frequently co-traversed cluster together.

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
from typing import Dict, List, Set, TYPE_CHECKING

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
