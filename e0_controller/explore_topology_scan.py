"""
Topology Scan — Systematic Classification of Interference Routing
=================================================================
Generates random directed graphs, runs them under all four summation
geometries, and classifies which structural features admit interference-
based routing corrections (G5 ≠ greedy).

Goals:
  1. What fraction of random graphs produce G5 overrides?
  2. Which structural features correlate with override occurrence?
  3. When does geometry choice matter (G5 ≠ simple)?
  4. Identify minimal topological patterns that trigger interference routing.

Output: Per-graph classification and aggregate statistics.
"""
import math
import random
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

from e0_controller.landscape import Landscape
from e0_controller.connection import theta, omega
from e0_controller.wavepath import psi
from e0_controller.controller import E0Controller
from e0_controller.primitives import Outcome
from e0_controller.amplitude_overlay import (
    analyze_controller_state,
    GEOMETRIES,
    OverlayReport,
)

START = "START"
GOAL = "GOAL"


# ── Random graph generation ──────────────────────────────────────────

def generate_random_landscape(
    n_internal: int = 5,
    edge_prob: float = 0.3,
    delta_range: Tuple[float, float] = (0.1, 3.0),
    resistance_range: Tuple[float, float] = (0.05, 1.0),
    rng: random.Random = None,
) -> Landscape:
    """
    Generate a random directed graph with START, GOAL, and n_internal nodes.
    Ensures at least one path from START to GOAL.
    """
    if rng is None:
        rng = random.Random()
    
    internal = [f"N{i}" for i in range(n_internal)]
    all_states = [START] + internal + [GOAL]
    
    L = Landscape()
    
    # Phase 1: Guarantee a backbone path START → ... → GOAL
    backbone_len = rng.randint(2, min(4, n_internal + 1))
    backbone_nodes = rng.sample(internal, min(backbone_len - 1, len(internal)))
    backbone = [START] + backbone_nodes + [GOAL]
    for i in range(len(backbone) - 1):
        d = rng.uniform(*delta_range)
        r = rng.uniform(*resistance_range)
        L.add_edge(backbone[i], backbone[i + 1], delta=d, resistance=r)
    
    # Phase 2: Add random edges (excluding self-loops, no edges INTO START)
    for src in all_states:
        for tgt in all_states:
            if src == tgt:
                continue
            if tgt == START:
                continue  # no incoming to START
            if src == GOAL:
                continue  # no outgoing from GOAL
            if rng.random() < edge_prob:
                d = rng.uniform(*delta_range)
                r = rng.uniform(*resistance_range)
                L.add_edge(src, tgt, delta=d, resistance=r)
    
    return L


def generate_structured_landscape(
    pattern: str,
    rng: random.Random = None,
) -> Landscape:
    """
    Generate landscapes with known structural patterns for controlled testing.
    Patterns:
      - "diamond": START → A → GOAL, START → B → GOAL (two 2-hop paths)
      - "triangle": START → A → GOAL, START → A → B → GOAL (shared prefix)  
      - "gordian_lite": 2 paths via A (short+loop), 1 via B (detour)
      - "parallel": 3+ independent 2-hop paths
      - "deep_vs_shallow": one short path, one long path
      - "mesh": dense interconnections between internal nodes
    """
    if rng is None:
        rng = random.Random()
    L = Landscape()
    
    def re(d_lo=0.1, d_hi=3.0, r_lo=0.05, r_hi=1.0):
        return rng.uniform(d_lo, d_hi), rng.uniform(r_lo, r_hi)
    
    if pattern == "diamond":
        d, r = re(); L.add_edge(START, "A", delta=d, resistance=r)
        d, r = re(); L.add_edge("A", GOAL, delta=d, resistance=r)
        d, r = re(); L.add_edge(START, "B", delta=d, resistance=r)
        d, r = re(); L.add_edge("B", GOAL, delta=d, resistance=r)
    
    elif pattern == "triangle":
        d, r = re(); L.add_edge(START, "A", delta=d, resistance=r)
        d, r = re(); L.add_edge("A", GOAL, delta=d, resistance=r)
        d, r = re(); L.add_edge("A", "B", delta=d, resistance=r)
        d, r = re(); L.add_edge("B", GOAL, delta=d, resistance=r)
    
    elif pattern == "gordian_lite":
        # A short path: START → A → X → GOAL (low delta)
        L.add_edge(START, "A", delta=rng.uniform(0.1, 0.5), resistance=0.3)
        L.add_edge("A", "X", delta=rng.uniform(0.1, 0.5), resistance=0.3)
        L.add_edge("X", GOAL, delta=rng.uniform(0.1, 0.5), resistance=0.3)
        # A loop path: START → A → L1 → L2 → GOAL (high delta)
        L.add_edge("A", "L1", delta=rng.uniform(2.0, 3.0), resistance=0.1)
        L.add_edge("L1", "L2", delta=rng.uniform(2.0, 3.0), resistance=0.1)
        L.add_edge("L2", GOAL, delta=rng.uniform(2.0, 3.0), resistance=0.1)
        # B detour: START → B → GOAL (moderate)
        L.add_edge(START, "B", delta=rng.uniform(0.5, 1.5), resistance=0.3)
        L.add_edge("B", GOAL, delta=rng.uniform(0.5, 1.5), resistance=0.3)
    
    elif pattern == "parallel":
        for name in ["A", "B", "C"]:
            d, r = re(); L.add_edge(START, name, delta=d, resistance=r)
            d, r = re(); L.add_edge(name, GOAL, delta=d, resistance=r)
    
    elif pattern == "deep_vs_shallow":
        # Shallow: START → A → GOAL
        d, r = re(); L.add_edge(START, "A", delta=d, resistance=r)
        d, r = re(); L.add_edge("A", GOAL, delta=d, resistance=r)
        # Deep: START → B → C → D → GOAL
        d, r = re(); L.add_edge(START, "B", delta=d, resistance=r)
        d, r = re(); L.add_edge("B", "C", delta=d, resistance=r)
        d, r = re(); L.add_edge("C", "D", delta=d, resistance=r)
        d, r = re(); L.add_edge("D", GOAL, delta=d, resistance=r)
    
    elif pattern == "mesh":
        nodes = ["A", "B", "C", "D"]
        # START connects to first two
        for n in nodes[:2]:
            d, r = re(); L.add_edge(START, n, delta=d, resistance=r)
        # Dense internal edges
        for src in nodes:
            for tgt in nodes:
                if src != tgt and rng.random() < 0.6:
                    d, r = re(); L.add_edge(src, tgt, delta=d, resistance=r)
        # Last two connect to GOAL
        for n in nodes[-2:]:
            d, r = re(); L.add_edge(n, GOAL, delta=d, resistance=r)
    
    return L


# ── Structural feature extraction ───────────────────────────────────

@dataclass
class GraphFeatures:
    """Structural features of a graph topology."""
    node_count: int = 0
    edge_count: int = 0
    start_fanout: int = 0          # Out-degree of START
    has_cycles: bool = False
    paths_to_goal: int = 0         # Within horizon
    path_families: int = 0         # Number of distinct first-hops reaching GOAL
    max_path_len: int = 0
    min_path_len: int = 0
    phase_spread: float = 0.0      # max(Θ) - min(Θ) across paths
    has_phase_opposition: bool = False  # |ΔΘ| > π/2 between any two paths
    max_interference_ratio: float = 0.0  # max(I_family) / min(I_family)


def _find_all_paths(L: Landscape, start: str, goal: str,
                    max_len: int = 6) -> List[List[str]]:
    """BFS/DFS to find all simple paths from start to goal up to max_len edges."""
    paths = []
    stack = [(start, [start])]
    while stack:
        current, path = stack.pop()
        if current == goal and len(path) > 1:
            paths.append(path)
            continue
        if len(path) - 1 >= max_len:
            continue
        neighbors = L.admissible_neighbors(current)
        for nb in neighbors:
            if nb not in path:  # simple paths
                stack.append((nb, path + [nb]))
    return paths


def _has_cycles(L: Landscape) -> bool:
    """Check if the landscape graph contains cycles."""
    visited = set()
    rec_stack = set()
    
    def dfs(node):
        visited.add(node)
        rec_stack.add(node)
        for nb in L.admissible_neighbors(node):
            if nb not in visited:
                if dfs(nb):
                    return True
            elif nb in rec_stack:
                return True
        rec_stack.discard(node)
        return False
    
    for s in L.states:
        if s not in visited:
            if dfs(s):
                return True
    return False


def extract_features(L: Landscape, paths: List[List[str]]) -> GraphFeatures:
    """Extract structural features from landscape and its paths to GOAL."""
    feat = GraphFeatures()
    feat.node_count = len(L.states)
    feat.edge_count = L.edge_count()
    feat.start_fanout = len(L.admissible_neighbors(START))
    feat.has_cycles = _has_cycles(L)
    feat.paths_to_goal = len(paths)
    
    if paths:
        # Path families: grouped by first hop
        families = set()
        for p in paths:
            if len(p) >= 2:
                families.add(p[1])
        feat.path_families = len(families)
        feat.max_path_len = max(len(p) - 1 for p in paths)
        feat.min_path_len = min(len(p) - 1 for p in paths)
        
        # Phase analysis
        thetas = [theta(L, p) for p in paths]
        if thetas:
            feat.phase_spread = max(thetas) - min(thetas)
            # Check for phase opposition
            for i in range(len(thetas)):
                for j in range(i + 1, len(thetas)):
                    if abs(thetas[i] - thetas[j]) > math.pi / 2:
                        feat.has_phase_opposition = True
                        break
        
        # Family-level interference
        family_intensity = defaultdict(complex)
        for p in paths:
            if len(p) >= 2:
                family_intensity[p[1]] += psi(L, p)
        intensities = [abs(z) ** 2 for z in family_intensity.values() if abs(z) > 1e-12]
        if len(intensities) >= 2:
            feat.max_interference_ratio = max(intensities) / min(intensities)
    
    return feat


# ── Scan result ──────────────────────────────────────────────────────

@dataclass
class ScanResult:
    """Result of analyzing one graph under all geometries."""
    seed: int
    pattern: str  # "random" or structured pattern name
    features: GraphFeatures
    greedy_choice: Optional[str] = None
    choices: Dict[str, Optional[str]] = field(default_factory=dict)  # geometry → choice
    intensities: Dict[str, Dict[str, float]] = field(default_factory=dict)  # geometry → {action: I}
    g5_overrides_greedy: bool = False
    geometry_matters: bool = False  # G5 ≠ simple
    
    @property
    def category(self) -> str:
        if self.g5_overrides_greedy and self.geometry_matters:
            return "C"  # Full: override + geometry-dependent
        elif self.g5_overrides_greedy:
            return "B"  # Override but geometry-independent
        else:
            return "A"  # No override


# ── Core scanner ─────────────────────────────────────────────────────

def evaluate_always_success(source, target):
    return Outcome.SUCCESS


def scan_one_graph(
    L: Landscape,
    seed: int,
    pattern: str,
    horizon: int = 4,
) -> Optional[ScanResult]:
    """
    Analyze one landscape: run under all geometries, collect choices.
    Returns None if START has no neighbors or GOAL is unreachable.
    """
    if not L.admissible_neighbors(START):
        return None
    
    # Check GOAL reachability
    paths = _find_all_paths(L, START, GOAL, max_len=horizon + 2)
    if not paths:
        return None
    
    features = extract_features(L, paths)
    ctrl = E0Controller(L, evaluate_always_success)
    
    result = ScanResult(seed=seed, pattern=pattern, features=features)
    
    # Greedy choice
    report_simple = analyze_controller_state(
        ctrl, START, horizon_edges=horizon, geometry="simple", goals={GOAL}
    )
    result.greedy_choice = report_simple.deterministic_choice
    
    # All geometries
    for geom in GEOMETRIES:
        try:
            report = analyze_controller_state(
                ctrl, START, horizon_edges=horizon, geometry=geom, goals={GOAL}
            )
            result.choices[geom] = report.amplitude_choice
            result.intensities[geom] = {
                ai.action: ai.intensity for ai in report.action_infos
            }
        except Exception:
            result.choices[geom] = None
            result.intensities[geom] = {}
    
    # Classification
    g5 = result.choices.get("goal_reaching")
    simple = result.choices.get("simple")
    result.g5_overrides_greedy = (g5 is not None and g5 != result.greedy_choice)
    result.geometry_matters = (g5 is not None and simple is not None and g5 != simple)
    
    return result


# ── Main scan ────────────────────────────────────────────────────────

def run_topology_scan(
    n_random: int = 200,
    n_structured_per_pattern: int = 30,
    horizon: int = 4,
    seed: int = 42,
) -> List[ScanResult]:
    """Run the full topology scan and return all results."""
    results = []
    rng = random.Random(seed)
    
    # ── Structured patterns ──
    patterns = ["diamond", "triangle", "gordian_lite", "parallel",
                "deep_vs_shallow", "mesh"]
    
    print("=" * 70)
    print("TOPOLOGY SCAN — Phase 3q §8.2 item 4")
    print("=" * 70)
    
    print(f"\n── Structured Patterns ({n_structured_per_pattern} each) ──")
    for pat in patterns:
        count = 0
        for i in range(n_structured_per_pattern):
            L = generate_structured_landscape(pat, rng=rng)
            r = scan_one_graph(L, seed=seed + i, pattern=pat, horizon=horizon)
            if r is not None:
                results.append(r)
                count += 1
        print(f"  {pat:20s}: {count} graphs analyzed")
    
    # ── Random graphs ──
    print(f"\n── Random Graphs ({n_random} total) ──")
    configs = [
        # (n_internal, edge_prob, label)
        (3, 0.4, "small_sparse"),
        (3, 0.7, "small_dense"),
        (5, 0.25, "medium_sparse"),
        (5, 0.45, "medium_dense"),
        (8, 0.15, "large_sparse"),
        (8, 0.3, "large_dense"),
        (10, 0.1, "xl_sparse"),
        (10, 0.2, "xl_dense"),
    ]
    per_config = max(1, n_random // len(configs))
    
    for n_int, ep, label in configs:
        count = 0
        for i in range(per_config):
            L = generate_random_landscape(
                n_internal=n_int, edge_prob=ep, rng=rng
            )
            r = scan_one_graph(L, seed=seed + 1000 + i, pattern=f"random_{label}",
                               horizon=horizon)
            if r is not None:
                results.append(r)
                count += 1
        print(f"  {label:20s} (n={n_int}, p={ep}): {count}/{per_config} valid")
    
    return results


# ── Analysis ─────────────────────────────────────────────────────────

def analyze_results(results: List[ScanResult]):
    """Print aggregate analysis of scan results."""
    if not results:
        print("No results to analyze.")
        return
    
    total = len(results)
    cat_counts = Counter(r.category for r in results)
    override_count = sum(1 for r in results if r.g5_overrides_greedy)
    geom_matters = sum(1 for r in results if r.geometry_matters)
    
    print("\n" + "=" * 70)
    print("AGGREGATE RESULTS")
    print("=" * 70)
    print(f"Total graphs analyzed: {total}")
    print(f"  Category A (no override):          {cat_counts.get('A', 0):4d}  "
          f"({100 * cat_counts.get('A', 0) / total:.1f}%)")
    print(f"  Category B (override, geom-indep):  {cat_counts.get('B', 0):4d}  "
          f"({100 * cat_counts.get('B', 0) / total:.1f}%)")
    print(f"  Category C (override + geom-dep):   {cat_counts.get('C', 0):4d}  "
          f"({100 * cat_counts.get('C', 0) / total:.1f}%)")
    print(f"\n  G5 overrides greedy:  {override_count}/{total} "
          f"({100 * override_count / total:.1f}%)")
    print(f"  Geometry matters:     {geom_matters}/{total} "
          f"({100 * geom_matters / total:.1f}%)")
    
    # ── By pattern ──
    print("\n── Override Rate by Pattern ──")
    patterns = sorted(set(r.pattern for r in results))
    for pat in patterns:
        pat_results = [r for r in results if r.pattern == pat]
        n = len(pat_results)
        n_override = sum(1 for r in pat_results if r.g5_overrides_greedy)
        n_geom = sum(1 for r in pat_results if r.geometry_matters)
        print(f"  {pat:25s}: {n:3d} graphs, "
              f"override={n_override:3d} ({100 * n_override / n:5.1f}%), "
              f"geom_matters={n_geom:3d} ({100 * n_geom / n:5.1f}%)")
    
    # ── Feature correlation with override ──
    print("\n── Feature Correlation with Override ──")
    override_set = [r for r in results if r.g5_overrides_greedy]
    no_override = [r for r in results if not r.g5_overrides_greedy]
    
    def avg(lst, key):
        vals = [key(x) for x in lst]
        return sum(vals) / len(vals) if vals else 0.0
    
    features = [
        ("node_count", lambda r: r.features.node_count),
        ("edge_count", lambda r: r.features.edge_count),
        ("start_fanout", lambda r: r.features.start_fanout),
        ("paths_to_goal", lambda r: r.features.paths_to_goal),
        ("path_families", lambda r: r.features.path_families),
        ("max_path_len", lambda r: r.features.max_path_len),
        ("phase_spread", lambda r: r.features.phase_spread),
        ("has_cycles (%)", lambda r: 1.0 if r.features.has_cycles else 0.0),
        ("has_phase_opp (%)", lambda r: 1.0 if r.features.has_phase_opposition else 0.0),
        ("interference_ratio", lambda r: r.features.max_interference_ratio),
    ]
    
    print(f"  {'Feature':25s} {'Override':>10s} {'No Override':>12s} {'Δ':>10s}")
    print(f"  {'-' * 25} {'-' * 10} {'-' * 12} {'-' * 10}")
    for name, key in features:
        v_yes = avg(override_set, key) if override_set else 0
        v_no = avg(no_override, key) if no_override else 0
        delta = v_yes - v_no
        s = "%" if "%" in name else ""
        if "%" in name:
            print(f"  {name:25s} {100 * v_yes:9.1f}% {100 * v_no:11.1f}% "
                  f"{100 * delta:+9.1f}%")
        else:
            print(f"  {name:25s} {v_yes:10.2f} {v_no:12.2f} {delta:+10.2f}")
    
    # ── Geometry comparison: when does G5 ≠ simple? ──
    geom_diff = [r for r in results if r.geometry_matters]
    if geom_diff:
        print(f"\n── Geometry Stress: G5 ≠ Simple ({len(geom_diff)} cases) ──")
        print(f"  Average features of G5≠Simple graphs:")
        for name, key in features:
            v = avg(geom_diff, key)
            if "%" in name:
                print(f"    {name:25s}: {100 * v:.1f}%")
            else:
                print(f"    {name:25s}: {v:.2f}")
    
    # ── Sample override cases (first 5) ──
    if override_set:
        print(f"\n── Sample Override Cases (up to 10) ──")
        for r in override_set[:10]:
            f = r.features
            print(f"  seed={r.seed}, pattern={r.pattern}")
            print(f"    nodes={f.node_count}, edges={f.edge_count}, "
                  f"fanout={f.start_fanout}, paths={f.paths_to_goal}, "
                  f"families={f.path_families}")
            print(f"    cycles={f.has_cycles}, phase_spread={f.phase_spread:.3f}, "
                  f"phase_opp={f.has_phase_opposition}, "
                  f"interf_ratio={f.max_interference_ratio:.2f}")
            print(f"    greedy={r.greedy_choice}, "
                  f"G5={r.choices.get('goal_reaching')}, "
                  f"simple={r.choices.get('simple')}")
            if r.intensities.get("goal_reaching"):
                ints = r.intensities["goal_reaching"]
                print(f"    G5 intensities: {', '.join(f'{k}={v:.4f}' for k, v in sorted(ints.items()))}")
            print()
    
    # ── Key Finding: Minimal Override Pattern ──
    if override_set:
        smallest = min(override_set, key=lambda r: r.features.edge_count)
        print(f"── Smallest Override Graph ──")
        f = smallest.features
        print(f"  seed={smallest.seed}, pattern={smallest.pattern}")
        print(f"  edges={f.edge_count}, nodes={f.node_count}, "
              f"paths={f.paths_to_goal}, families={f.path_families}")
        print(f"  phase_spread={f.phase_spread:.4f}, "
              f"phase_opp={f.has_phase_opposition}")
        print(f"  greedy={smallest.greedy_choice} → "
              f"G5={smallest.choices.get('goal_reaching')}")
    
    return results


# ── Geometry Stress Test ──────────────────────────────────────────────

def geometry_stress_test(results: List[ScanResult]):
    """
    Detailed comparison of all four geometries across all graphs.
    Identifies where geometry choice changes the recommended action.
    """
    print("\n" + "=" * 70)
    print("GEOMETRY STRESS TEST — All 4 Geometries Compared")
    print("=" * 70)
    
    # For each pair of geometries, count agreements/disagreements
    geom_list = list(GEOMETRIES)
    
    print("\n── Pairwise Agreement Matrix ──")
    print(f"  {'':15s}", end="")
    for g in geom_list:
        print(f"  {g:>14s}", end="")
    print()
    
    for g1 in geom_list:
        print(f"  {g1:15s}", end="")
        for g2 in geom_list:
            agree = sum(
                1 for r in results
                if r.choices.get(g1) is not None
                and r.choices.get(g2) is not None
                and r.choices.get(g1) == r.choices.get(g2)
            )
            valid = sum(
                1 for r in results
                if r.choices.get(g1) is not None
                and r.choices.get(g2) is not None
            )
            if valid > 0:
                print(f"  {100 * agree / valid:13.1f}%", end="")
            else:
                print(f"  {'N/A':>14s}", end="")
        print()
    
    # Exclusive disagreements
    print("\n── Geometry-Exclusive Overrides ──")
    print("  (Cases where ONLY this geometry picks a different action)")
    for g in geom_list:
        others = [o for o in geom_list if o != g]
        exclusive = 0
        for r in results:
            c = r.choices.get(g)
            if c is None:
                continue
            other_choices = [r.choices.get(o) for o in others if r.choices.get(o) is not None]
            if other_choices and c not in other_choices:
                exclusive += 1
        valid = sum(1 for r in results if r.choices.get(g) is not None)
        if valid:
            print(f"  {g:20s}: {exclusive:3d}/{valid} exclusive "
                  f"({100 * exclusive / valid:.1f}%)")
    
    # G5 vs greedy intensity ratios
    print("\n── G5 Override Strength Distribution ──")
    ratios = []
    for r in results:
        if not r.g5_overrides_greedy:
            continue
        g5_ints = r.intensities.get("goal_reaching", {})
        g5_choice = r.choices.get("goal_reaching")
        greedy = r.greedy_choice
        if g5_choice and greedy and g5_choice in g5_ints and greedy in g5_ints:
            if g5_ints[greedy] > 1e-12:
                ratios.append(g5_ints[g5_choice] / g5_ints[greedy])
    
    if ratios:
        ratios.sort()
        print(f"  Override count: {len(ratios)}")
        print(f"  I(G5_choice) / I(greedy_choice) ratio:")
        print(f"    min={min(ratios):.3f}, median={ratios[len(ratios)//2]:.3f}, "
              f"max={max(ratios):.3f}")
        # Histogram
        bins = [(1.0, 1.1), (1.1, 1.5), (1.5, 2.0), (2.0, 5.0), (5.0, float('inf'))]
        print(f"  Distribution:")
        for lo, hi in bins:
            n = sum(1 for x in ratios if lo <= x < hi)
            label = f"[{lo:.1f}, {hi:.1f})" if hi < float('inf') else f"[{lo:.1f}, ∞)"
            bar = "█" * n
            print(f"    {label:12s}: {n:3d} {bar}")


# ── Entry point ──────────────────────────────────────────────────────

if __name__ == "__main__":
    results = run_topology_scan(
        n_random=200,
        n_structured_per_pattern=30,
        horizon=4,
        seed=42,
    )
    analyze_results(results)
    geometry_stress_test(results)
    
    print("\n" + "=" * 70)
    print("SCAN COMPLETE")
    print("=" * 70)
