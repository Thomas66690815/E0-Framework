"""
C184: Real-World Validation — Wikispeedia Navigation

First real-world domain for E₀: human navigation on Wikipedia hyperlinks.
Uses the Wikispeedia dataset (West & Leskovec, WWW 2012; SNAP Stanford).

Key question: Can E₀'s interference-based routing outperform human
navigation and identify the same structural traps — without ever seeing
a human path?

Data: 4,604 articles, 119,882 directed links, 51,318 finished paths,
24,875 unfinished paths.

Δ mapping:  d(target_of_edge, goal) / d_max  — structural distance to goal
R₀ mapping: 1 / sqrt(out_degree)             — navigability of target article
"""

from __future__ import annotations

import os
import csv
import math
import random
from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple, FrozenSet
from urllib.parse import unquote
from collections import defaultdict

from e0_controller.landscape import Landscape
from e0_controller.controller import E0Controller, HybridMode
from e0_controller.primitives import Outcome, Edge


# ─────────────────────── Data loading ───────────────────────

DATA_DIR = Path(__file__).parent.parent / "data" / "wikispeedia" / "wikispeedia_paths-and-graph"


def _skip_comments(filepath: Path) -> list[str]:
    """Read TSV file, skip comment lines starting with #."""
    lines = []
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            if line.startswith("#") or line.strip() == "":
                continue
            lines.append(line.rstrip("\n"))
    return lines


def load_articles() -> list[str]:
    """Load article names (URL-decoded)."""
    raw = _skip_comments(DATA_DIR / "articles.tsv")
    return [unquote(a) for a in raw]


def load_links() -> list[tuple[str, str]]:
    """Load directed links as (source, target) pairs."""
    raw = _skip_comments(DATA_DIR / "links.tsv")
    links = []
    for line in raw:
        parts = line.split("\t")
        if len(parts) == 2:
            links.append((unquote(parts[0]), unquote(parts[1])))
    return links


def load_distance_matrix(articles: list[str]) -> Dict[str, Dict[str, int]]:
    """Load shortest-path distance matrix.
    Returns dict[source][target] = distance (int), or -1 if unreachable.
    """
    raw = _skip_comments(DATA_DIR / "shortest-path-distance-matrix.txt")
    dist: Dict[str, Dict[str, int]] = {}
    for i, row in enumerate(raw):
        if i >= len(articles):
            break
        src = articles[i]
        d = {}
        for j, ch in enumerate(row):
            if j >= len(articles):
                break
            tgt = articles[j]
            if ch == "_":
                d[tgt] = -1
            else:
                d[tgt] = int(ch)
        dist[src] = d
    return dist


@dataclass
class NavigationPath:
    """A human navigation attempt."""
    path: list[str]         # sequence of articles visited
    target: str             # goal article
    duration_sec: int       # time taken
    finished: bool          # reached goal?
    rating: Optional[int]   # difficulty rating 1-5 (finished only)
    back_clicks: int        # number of '<' back-clicks


def load_finished_paths() -> list[NavigationPath]:
    """Load successful human navigation paths."""
    raw = _skip_comments(DATA_DIR / "paths_finished.tsv")
    paths = []
    for line in raw:
        parts = line.split("\t")
        if len(parts) < 4:
            continue
        duration = int(parts[2])
        raw_path = parts[3].split(";")
        # Decode and count back clicks
        decoded = []
        back_clicks = 0
        for step in raw_path:
            if step == "<":
                back_clicks += 1
                if decoded:
                    decoded.pop()  # back click removes last
            else:
                decoded.append(unquote(step))
        target = decoded[-1] if decoded else ""
        rating = None
        if len(parts) >= 5 and parts[4] != "NULL":
            rating = int(parts[4])
        paths.append(NavigationPath(
            path=decoded, target=target, duration_sec=duration,
            finished=True, rating=rating, back_clicks=back_clicks,
        ))
    return paths


def load_unfinished_paths() -> list[NavigationPath]:
    """Load failed human navigation paths."""
    raw = _skip_comments(DATA_DIR / "paths_unfinished.tsv")
    paths = []
    for line in raw:
        parts = line.split("\t")
        if len(parts) < 5:
            continue
        duration = int(parts[2])
        raw_path = parts[3].split(";")
        target = unquote(parts[4])
        decoded = []
        back_clicks = 0
        for step in raw_path:
            if step == "<":
                back_clicks += 1
                if decoded:
                    decoded.pop()
            else:
                decoded.append(unquote(step))
        paths.append(NavigationPath(
            path=decoded, target=target, duration_sec=duration,
            finished=False, rating=None, back_clicks=back_clicks,
        ))
    return paths


def load_categories() -> Dict[str, list[str]]:
    """Load article → category mappings."""
    raw = _skip_comments(DATA_DIR / "categories.tsv")
    cats: Dict[str, list[str]] = defaultdict(list)
    for line in raw:
        parts = line.split("\t")
        if len(parts) == 2:
            cats[unquote(parts[0])].append(parts[1])
    return dict(cats)


# ─────────────────────── Graph analysis ───────────────────────

@dataclass
class WikiGraph:
    """In-memory representation of the Wikipedia hyperlink graph."""
    articles: list[str]
    article_set: FrozenSet[str]
    out_links: Dict[str, list[str]]     # article → [targets]
    in_links: Dict[str, list[str]]      # article → [sources]
    dist: Dict[str, Dict[str, int]]     # shortest path distances
    categories: Dict[str, list[str]]

    @property
    def num_articles(self) -> int:
        return len(self.articles)

    @property
    def num_links(self) -> int:
        return sum(len(v) for v in self.out_links.values())

    def out_degree(self, article: str) -> int:
        return len(self.out_links.get(article, []))

    def in_degree(self, article: str) -> int:
        return len(self.in_links.get(article, []))

    def shortest_dist(self, source: str, target: str) -> int:
        """Return shortest path distance, or -1 if unreachable."""
        return self.dist.get(source, {}).get(target, -1)

    def neighbors_toward_goal(self, article: str, goal: str) -> list[str]:
        """Neighbors that are closer to goal than current article."""
        d_curr = self.shortest_dist(article, goal)
        if d_curr <= 0:
            return []
        return [
            n for n in self.out_links.get(article, [])
            if 0 <= self.shortest_dist(n, goal) < d_curr
        ]

    def is_trap_article(self, article: str, goal: str) -> bool:
        """Article is a 'trap' if no outgoing link gets closer to goal."""
        return len(self.neighbors_toward_goal(article, goal)) == 0


def load_wikigraph() -> WikiGraph:
    """Load the complete Wikispeedia graph into memory."""
    articles = load_articles()
    links = load_links()
    dist = load_distance_matrix(articles)
    categories = load_categories()

    article_set = frozenset(articles)
    out_links: Dict[str, list[str]] = defaultdict(list)
    in_links: Dict[str, list[str]] = defaultdict(list)
    for src, tgt in links:
        if src in article_set and tgt in article_set:
            out_links[src].append(tgt)
            in_links[tgt].append(src)

    return WikiGraph(
        articles=articles,
        article_set=article_set,
        out_links=dict(out_links),
        in_links=dict(in_links),
        dist=dist,
        categories=categories,
    )


# ─────────── Subgraph extraction for E₀ ───────────

def extract_subgraph(
    graph: WikiGraph,
    source: str,
    goal: str,
    max_depth: int = 4,
    max_nodes: int = 80,
) -> Tuple[Set[str], Set[Tuple[str, str]]]:
    """Extract a path-anchored subgraph for a navigation task.

    Strategy (path-first, then expand):
    1. Find shortest path(s) from source to goal via BFS on full graph.
    2. Include all nodes on shortest paths as the 'spine'.
    3. BFS-expand from spine nodes to add neighborhood for alternatives.
    4. Only keep edges between subgraph members.

    This ensures goal reachability while providing enough neighborhood
    for E₀ interference to operate.
    """
    nodes: Set[str] = set()
    edges: Set[Tuple[str, str]] = set()

    # Step 1: BFS to find ALL shortest paths from source to goal
    from collections import deque
    parent: Dict[str, list[str]] = {source: []}
    dist_from_src: Dict[str, int] = {source: 0}
    queue = deque([source])
    goal_dist = -1

    while queue:
        node = queue.popleft()
        d = dist_from_src[node]
        if goal_dist >= 0 and d > goal_dist:
            break
        if node == goal:
            goal_dist = d
            continue
        for nb in graph.out_links.get(node, []):
            if nb not in dist_from_src:
                dist_from_src[nb] = d + 1
                parent[nb] = [node]
                queue.append(nb)
            elif dist_from_src[nb] == d + 1:
                parent[nb].append(node)

    # Step 2: Backtrack to collect all nodes on shortest paths
    spine: Set[str] = set()
    if goal in parent or goal == source:
        backtrack = [goal]
        while backtrack:
            node = backtrack.pop()
            spine.add(node)
            for p in parent.get(node, []):
                if p not in spine:
                    backtrack.append(p)
    else:
        # Goal unreachable — just use source neighborhood
        spine = {source}

    nodes.update(spine)

    # Step 3: Add edges along the spine
    for node in spine:
        for nb in graph.out_links.get(node, []):
            if nb in spine:
                edges.add((node, nb))

    # Step 4: BFS-expand from spine, up to max_nodes
    frontier = list(spine)
    visited = set(spine)
    for _depth in range(max_depth):
        if len(nodes) >= max_nodes:
            break
        next_frontier = []
        for node in frontier:
            for nb in graph.out_links.get(node, []):
                if nb not in visited and len(nodes) < max_nodes:
                    visited.add(nb)
                    nodes.add(nb)
                    next_frontier.append(nb)
                if node in nodes and nb in nodes:
                    edges.add((node, nb))
        frontier = next_frontier
        if not frontier:
            break

    # Step 5: Add ALL edges between subgraph members
    for node in nodes:
        for nb in graph.out_links.get(node, []):
            if nb in nodes:
                edges.add((node, nb))

    return nodes, edges


# ─────────── Δ and R₀ mapping ───────────

def compute_delta(
    graph: WikiGraph,
    source: str,
    target: str,
    goal: str,
    d_max: int = 9,
) -> float:
    """Compute Δ for edge source→target given navigation goal.

    Δ = d(target, goal) / d_max

    Structural interpretation: Δ measures how far the target article
    is from the goal in the link graph. Edges pointing toward the goal
    have low Δ (< 0.5), edges pointing away have high Δ.

    If target is unreachable from goal's perspective, Δ = 1.0 (maximum tension).
    """
    d = graph.shortest_dist(target, goal)
    if d < 0:  # unreachable
        return 1.0
    if d == 0:  # target IS the goal
        return 0.05  # small positive (E₀ requires Δ > 0)
    return max(0.05, d / d_max)


def compute_resistance(
    graph: WikiGraph,
    target: str,
) -> float:
    """Compute R₀ for edge pointing to target article.

    R₀ = 1 / sqrt(out_degree(target))

    Structural interpretation: Articles with many outgoing links
    are 'easier' to navigate from — lower resistance.
    Articles with few links (potential dead-ends) have high resistance.
    """
    deg = graph.out_degree(target)
    if deg == 0:
        return 5.0  # dead-end: maximum resistance
    return 1.0 / math.sqrt(deg)


# ─────────── Landscape construction ───────────

def build_landscape(
    graph: WikiGraph,
    source: str,
    goal: str,
    max_depth: int = 4,
    max_nodes: int = 80,
) -> Tuple[Landscape, Set[str]]:
    """Build an E₀ Landscape from a Wikispeedia navigation task.

    Returns (landscape, node_set) for the subgraph.
    """
    nodes, edges = extract_subgraph(graph, source, goal, max_depth, max_nodes)

    L = Landscape()
    for node in nodes:
        L.add_state(node)

    d_max = 9  # maximum possible shortest path in Wikispeedia
    for src, tgt in edges:
        delta = compute_delta(graph, src, tgt, goal, d_max)
        resistance = compute_resistance(graph, tgt)
        L.add_edge(src, tgt, delta=delta, resistance=resistance)

    return L, nodes


# ─────────── Execute function (deterministic for benchmark) ───────────

def make_execute_fn(graph: WikiGraph):
    """Create an execute_fn that always succeeds if edge exists."""
    def execute(source: str, target: str) -> Outcome:
        if target in graph.out_links.get(source, []):
            return Outcome.SUCCESS
        return Outcome.FAILURE
    return execute


# ─────────── Navigation task selection ───────────

@dataclass
class NavigationTask:
    """A specific source→target navigation problem with human data."""
    source: str
    target: str
    shortest_path_len: int
    human_paths: list[NavigationPath]          # successful attempts
    human_failures: list[NavigationPath]        # failed attempts
    avg_human_steps: float
    avg_human_duration: float
    difficulty: float  # fraction of attempts that failed


def select_benchmark_tasks(
    graph: WikiGraph,
    finished: list[NavigationPath],
    unfinished: list[NavigationPath],
    min_attempts: int = 10,
    min_shortest: int = 3,
    max_shortest: int = 7,
) -> list[NavigationTask]:
    """Select navigation tasks with enough human data for comparison.

    Criteria:
    - At least min_attempts total (finished + unfinished)
    - Shortest path between 3 and 7 (tractable for E₀, non-trivial for humans)
    - Both source and target exist in graph
    """
    # Group paths by (source, target) pair
    finished_by_pair: Dict[Tuple[str, str], list[NavigationPath]] = defaultdict(list)
    for p in finished:
        if len(p.path) >= 2:
            src = p.path[0]
            finished_by_pair[(src, p.target)].append(p)

    unfinished_by_pair: Dict[Tuple[str, str], list[NavigationPath]] = defaultdict(list)
    for p in unfinished:
        if p.path:
            src = p.path[0]
            unfinished_by_pair[(src, p.target)].append(p)

    # Collect all (source, target) pairs
    all_pairs = set(finished_by_pair.keys()) | set(unfinished_by_pair.keys())

    tasks = []
    for src, tgt in all_pairs:
        if src not in graph.article_set or tgt not in graph.article_set:
            continue
        d = graph.shortest_dist(src, tgt)
        if d < min_shortest or d > max_shortest:
            continue

        fin = finished_by_pair.get((src, tgt), [])
        unfin = unfinished_by_pair.get((src, tgt), [])
        total = len(fin) + len(unfin)
        if total < min_attempts:
            continue

        avg_steps = sum(len(p.path) - 1 for p in fin) / len(fin) if fin else 0
        avg_dur = sum(p.duration_sec for p in fin) / len(fin) if fin else 0
        difficulty = len(unfin) / total

        tasks.append(NavigationTask(
            source=src, target=tgt,
            shortest_path_len=d,
            human_paths=fin,
            human_failures=unfin,
            avg_human_steps=avg_steps,
            avg_human_duration=avg_dur,
            difficulty=difficulty,
        ))

    # Sort by difficulty descending (hardest first)
    tasks.sort(key=lambda t: t.difficulty, reverse=True)
    return tasks


# ─────────── E₀ benchmark runner ───────────

@dataclass
class BenchmarkResult:
    """Result of running E₀ on a single navigation task."""
    task: NavigationTask
    e0_path: list[str]
    e0_steps: int
    e0_reached_goal: bool
    greedy_path: list[str]      # shortest-path-greedy baseline
    greedy_steps: int
    greedy_reached_goal: bool
    human_avg_steps: float
    shortest_path_len: int
    e0_overrides: int           # amplitude overrides of greedy
    trap_articles_detected: list[str]  # articles where interference flagged traps


def run_greedy_baseline(
    graph: WikiGraph,
    source: str,
    goal: str,
    max_steps: int = 30,
) -> Tuple[list[str], bool]:
    """Greedy baseline: always pick neighbor closest to goal."""
    path = [source]
    current = source
    visited_count: Dict[str, int] = defaultdict(int)
    visited_count[source] = 1

    for _ in range(max_steps):
        if current == goal:
            return path, True
        neighbors = graph.out_links.get(current, [])
        if not neighbors:
            return path, False

        # Pick neighbor with smallest shortest-path distance to goal
        # Break ties by fewest visits (avoid loops)
        best = None
        best_d = float("inf")
        for n in neighbors:
            d = graph.shortest_dist(n, goal)
            if d < 0:
                continue
            if d < best_d or (d == best_d and visited_count.get(n, 0) < visited_count.get(best, 0)):
                best = n
                best_d = d
        if best is None:
            return path, False
        current = best
        path.append(current)
        visited_count[current] = visited_count.get(current, 0) + 1

    return path, current == goal


def run_e0_on_task(
    graph: WikiGraph,
    task: NavigationTask,
    max_cycles: int = 30,
    hybrid_horizon: int = 3,
) -> BenchmarkResult:
    """Run E₀ controller on a navigation task and compare with baselines."""

    landscape, nodes = build_landscape(
        graph, task.source, task.target,
        max_depth=2, max_nodes=80,
    )

    execute_fn = make_execute_fn(graph)

    controller = E0Controller(
        landscape=landscape,
        execute_fn=execute_fn,
        alpha=2.0,
        recent_k=3,
        hybrid_mode=HybridMode.AMPLITUDE_ON_DISAGREE,
        hybrid_horizon=hybrid_horizon,
        hybrid_goals={task.target},
        hybrid_geometry="goal_reaching",
        confidence_threshold=0.5,
    )

    trace = controller.run(
        start=task.source,
        max_cycles=max_cycles,
        goal=task.target,
        overlay_horizon=hybrid_horizon,
    )

    e0_path = trace.path
    e0_reached = e0_path[-1] == task.target if e0_path else False
    e0_steps = len(trace.steps)

    # Count overrides and trap detections
    overrides = 0
    traps = []
    for step in trace.steps:
        if step.overlay:
            ov = step.overlay
            if (ov.deterministic_choice and ov.amplitude_choice
                    and ov.deterministic_choice != ov.amplitude_choice):
                overrides += 1
            # Detect trap: article where interference intensity is very low
            for ai in ov.action_infos:
                if ai.intensity < 0.05 and ai.path_count >= 2:
                    if ai.action not in traps:
                        traps.append(ai.action)

    # Greedy baseline
    greedy_path, greedy_reached = run_greedy_baseline(
        graph, task.source, task.target, max_steps=max_cycles,
    )

    return BenchmarkResult(
        task=task,
        e0_path=e0_path,
        e0_steps=e0_steps,
        e0_reached_goal=e0_reached,
        greedy_path=greedy_path,
        greedy_steps=len(greedy_path) - 1,
        greedy_reached_goal=greedy_reached,
        human_avg_steps=task.avg_human_steps,
        shortest_path_len=task.shortest_path_len,
        e0_overrides=overrides,
        trap_articles_detected=traps,
    )


# ─────────── Main exploration ───────────

def run_exploration():
    """Run the full Wikispeedia exploration."""

    print("=" * 70)
    print("C184: Real-World Validation — Wikispeedia Navigation")
    print("=" * 70)

    # Phase 1: Load data
    print("\n--- Phase 1: Loading Wikispeedia data ---")
    graph = load_wikigraph()
    print(f"  Articles: {graph.num_articles}")
    print(f"  Links:    {graph.num_links}")

    finished = load_finished_paths()
    unfinished = load_unfinished_paths()
    print(f"  Finished paths:   {len(finished)}")
    print(f"  Unfinished paths: {len(unfinished)}")

    # Phase 2: Graph statistics
    print("\n--- Phase 2: Graph structure analysis ---")
    degrees = [graph.out_degree(a) for a in graph.articles]
    avg_deg = sum(degrees) / len(degrees)
    max_deg = max(degrees)
    min_deg = min(degrees)
    dead_ends = sum(1 for d in degrees if d == 0)
    print(f"  Avg out-degree:   {avg_deg:.1f}")
    print(f"  Max out-degree:   {max_deg}")
    print(f"  Min out-degree:   {min_deg}")
    print(f"  Dead-end articles: {dead_ends}")

    # Phase 3: Select benchmark tasks
    print("\n--- Phase 3: Selecting benchmark tasks ---")
    tasks = select_benchmark_tasks(
        graph, finished, unfinished,
        min_attempts=10, min_shortest=3, max_shortest=7,
    )
    print(f"  Tasks meeting criteria: {len(tasks)}")
    if not tasks:
        print("  WARNING: No tasks found with sufficient human data!")
        return {}

    # Show hardest tasks
    print(f"\n  Top 10 hardest tasks (by human failure rate):")
    for t in tasks[:10]:
        total = len(t.human_paths) + len(t.human_failures)
        print(f"    {t.source[:30]:30s} → {t.target[:30]:30s}  "
              f"d={t.shortest_path_len}  "
              f"attempts={total}  "
              f"fail={t.difficulty:.0%}  "
              f"avg_steps={t.avg_human_steps:.1f}")

    # Phase 4: Run E₀ on selected tasks
    # Take top 20 hardest tasks for intensive evaluation
    eval_tasks = tasks[:20]
    print(f"\n--- Phase 4: Running E₀ on {len(eval_tasks)} tasks ---")

    results: list[BenchmarkResult] = []
    for i, task in enumerate(eval_tasks):
        try:
            result = run_e0_on_task(graph, task, max_cycles=30, hybrid_horizon=3)
            results.append(result)
            status = "✓" if result.e0_reached_goal else "✗"
            print(f"  [{i+1:2d}/{len(eval_tasks)}] {status} "
                  f"{task.source[:25]:25s} → {task.target[:25]:25s}  "
                  f"E₀={result.e0_steps:2d}  "
                  f"greedy={result.greedy_steps:2d}  "
                  f"human={result.human_avg_steps:4.1f}  "
                  f"shortest={result.shortest_path_len}  "
                  f"overrides={result.e0_overrides}")
        except Exception as e:
            print(f"  [{i+1:2d}/{len(eval_tasks)}] ERROR: {task.source} → {task.target}: {e}")

    # Phase 5: Aggregate analysis
    print("\n--- Phase 5: Aggregate results ---")
    if results:
        e0_success = sum(1 for r in results if r.e0_reached_goal)
        greedy_success = sum(1 for r in results if r.greedy_reached_goal)
        total = len(results)

        print(f"  E₀ success rate:     {e0_success}/{total} ({e0_success/total:.0%})")
        print(f"  Greedy success rate:  {greedy_success}/{total} ({greedy_success/total:.0%})")

        # Among successful runs: compare path lengths
        both_success = [r for r in results if r.e0_reached_goal and r.greedy_reached_goal]
        if both_success:
            avg_e0 = sum(r.e0_steps for r in both_success) / len(both_success)
            avg_greedy = sum(r.greedy_steps for r in both_success) / len(both_success)
            avg_human = sum(r.human_avg_steps for r in both_success) / len(both_success)
            avg_shortest = sum(r.shortest_path_len for r in both_success) / len(both_success)
            avg_overrides = sum(r.e0_overrides for r in both_success) / len(both_success)

            print(f"\n  Path length comparison ({len(both_success)} tasks where both succeed):")
            print(f"    Shortest path (optimal): {avg_shortest:.1f}")
            print(f"    E₀ controller:           {avg_e0:.1f}")
            print(f"    Greedy baseline:         {avg_greedy:.1f}")
            print(f"    Human average:           {avg_human:.1f}")
            print(f"    E₀ amplitude overrides:  {avg_overrides:.1f} per task")

            # Efficiency ratios
            print(f"\n  Efficiency (steps / shortest):")
            print(f"    E₀:      {avg_e0/avg_shortest:.2f}x optimal")
            print(f"    Greedy:  {avg_greedy/avg_shortest:.2f}x optimal")
            print(f"    Human:   {avg_human/avg_shortest:.2f}x optimal")

        # Trap detection quality
        all_traps = set()
        for r in results:
            all_traps.update(r.trap_articles_detected)
        print(f"\n  Trap articles detected by interference: {len(all_traps)}")
        if all_traps:
            # Check if trapped articles correlate with human failures
            trap_in_failures = 0
            for r in results:
                for trap in r.trap_articles_detected:
                    for fp in r.task.human_failures:
                        if trap in fp.path:
                            trap_in_failures += 1
                            break
            print(f"  Trap articles that appear in human failure paths: {trap_in_failures}/{len(all_traps)}")

    # Phase 6: Per-task detailed report
    print("\n--- Phase 6: Detailed per-task results ---")
    print(f"{'Source':<28s} {'Target':<28s} {'d':>2s} {'E₀':>3s} {'Gr':>3s} "
          f"{'Hum':>5s} {'Diff':>5s} {'Ovr':>3s} {'E₀ok':>4s} {'Grok':>4s}")
    print("-" * 110)
    for r in results:
        print(f"{r.task.source[:27]:<28s} {r.task.target[:27]:<28s} "
              f"{r.shortest_path_len:2d} {r.e0_steps:3d} {r.greedy_steps:3d} "
              f"{r.human_avg_steps:5.1f} {r.task.difficulty:5.2f} {r.e0_overrides:3d} "
              f"{'  ✓' if r.e0_reached_goal else '  ✗':>4s} "
              f"{'  ✓' if r.greedy_reached_goal else '  ✗':>4s}")

    print("\n" + "=" * 70)
    print("C184 exploration complete.")

    return {
        "graph": graph,
        "tasks": tasks,
        "results": results,
    }


if __name__ == "__main__":
    run_exploration()
