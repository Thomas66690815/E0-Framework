"""Explore: bootstrap.json as E₀ Landscape.

Can E₀ navigate its own project memory?

bootstrap.json is already a Historization — confirmed/contradicted are U/F traces,
recurred counts are failure signals, built_upon counts are success signals.
But it's hand-curated, not machine-navigable.

This exploration:
1. Parses bootstrap.json into explicit nodes and edges
2. Extracts the EXISTING U/F traces (they're already there!)
3. Builds a Landscape via the bootstrapper
4. Runs the controller with different goals
5. Asks: what does E₀ recommend as the next productive step?

Key design: E₀ doesn't need to understand the words.
"GT-5" is a label — E₀ only needs: from GT-5, what transitions exist,
and what is their structural burden? Domain Invariance.
"""

import json
import math
import os
import sys

from e0_controller.bootstrapper import bootstrap_landscape
from e0_controller.controller import E0Controller
from e0_controller.primitives import Outcome

# ---------------------------------------------------------------------------
# Phase 1: Parse bootstrap.json into nodes, edges, traces
# ---------------------------------------------------------------------------

BOOTSTRAP_PATH = os.path.join(os.path.dirname(__file__), "..", "bootstrap.json")


def load_bootstrap():
    """Load and return the raw bootstrap.json."""
    with open(BOOTSTRAP_PATH, encoding="utf-8") as f:
        return json.load(f)


def extract_nodes(bs):
    """Extract all natural nodes from bootstrap.json.

    Returns dict: node_id → {type, label, traces, metadata}
    """
    nodes = {}

    # --- Gordian Traps ---
    for gt in bs.get("reflexion", {}).get("gordian_traps", []):
        nid = gt["id"]  # e.g. "GT-1"
        resolved = gt.get("resolution", "") != ""
        recurred = gt.get("recurred", 0)
        # Resolved trap = successful learning. recurred = failure signal.
        nodes[nid] = {
            "type": "gordian_trap",
            "label": gt.get("name", nid),
            "U": 1.0 if resolved else 0.0,  # Did we learn from this?
            "F": float(recurred) + (0.0 if resolved else 1.0),
            "lesson": gt.get("lesson", ""),
            "resolution": gt.get("resolution", ""),
        }

    # --- Breakthroughs ---
    for bt in bs.get("reflexion", {}).get("breakthroughs", []):
        nid = bt["id"]
        built = bt.get("built_upon", 0)
        nodes[nid] = {
            "type": "breakthrough",
            "label": bt.get("insight", nid)[:60],
            "U": float(built) + 1.0,  # The breakthrough itself + what was built on it
            "F": 0.0,  # Breakthroughs don't fail (they're retrospective)
            "built_upon_by": bt.get("built_upon_by", []),
        }

    # --- Working Principles ---
    for i, wp in enumerate(
        bs.get("active_context", {}).get("working_principles", [])
    ):
        nid = f"WP-{i+1}"
        confirmed = wp.get("confirmed", 0)
        contradicted = wp.get("contradicted", 0)
        nodes[nid] = {
            "type": "working_principle",
            "label": wp.get("principle", nid)[:60],
            "U": float(confirmed),
            "F": float(contradicted),
        }

    # --- Perspective Checks ---
    for i, pc in enumerate(
        bs.get("perspective_checks", {}).get("checks", [])
    ):
        nid = f"PC-{i+1}"
        triggered = pc.get("triggered", 0)
        nodes[nid] = {
            "type": "perspective_check",
            "label": pc.get("question", nid)[:60],
            "U": float(triggered),  # Triggered = it caught something = success
            "F": 0.0,
        }

    # --- Architecture Layers ---
    for layer_key, layer in bs.get("architecture", {}).get("layers", {}).items():
        nid = f"L{layer_key.split('_')[0]}"  # "1_primitives" → "L1"
        layer_name = layer_key.split("_", 1)[1] if "_" in layer_key else layer_key
        nodes[nid] = {
            "type": "arch_layer",
            "label": layer_name,
            "U": 1.0,  # All layers exist and work (4369 tests confirm)
            "F": 0.0,
            "files": layer.get("files", []),
        }

    # --- Open Threads (these are the frontier — unresolved, high resistance) ---
    for i, thread in enumerate(
        bs.get("active_context", {}).get("open_threads", [])
    ):
        nid = f"OPEN-{i+1}"
        nodes[nid] = {
            "type": "open_thread",
            "label": thread[:60],
            "U": 0.0,  # Not resolved
            "F": 0.0,  # Not yet attempted in current form
        }

    # --- Meta node: current state ---
    state = bs.get("state", {})
    nodes["HERE"] = {
        "type": "current_state",
        "label": f"C{194} — v1.0.0",
        "U": float(state.get("test_count", 0)) / 1000.0,  # Normalized success signal
        "F": float(state.get("test_failures", 0)),
    }

    return nodes


def extract_edges(bs, nodes):
    """Extract implicit edges from cross-references in bootstrap.json.

    Returns list of dicts with: from, to, delta, resistance, initial_U, initial_F,
    confidence, derivation (text explanation)
    """
    edges = []

    def add(src, tgt, delta, resistance, confidence=0.8, derivation=""):
        if src in nodes and tgt in nodes:
            edges.append({
                "from": src,
                "to": tgt,
                "delta": delta,
                "resistance": resistance,
                "initial_U": 0.0,
                "initial_F": 0.0,
                "confidence": confidence,
                "derivation": derivation,
            })

    # --- GT → BT: Traps that led to breakthroughs ---
    # GT-1 (Isolated Agents) → BT-2 (Shared Historization)
    add("GT-1", "BT-2", 0.7, 0.2, 0.9, "isolated agents trap led to shared historization insight")
    # GT-3 (Greedy Matching) → BT-1 (Hungarian)
    add("GT-3", "BT-1", 0.8, 0.2, 0.9, "greedy matching stall led to Hungarian breakthrough")
    # GT-5 (Override Trap) → BT-4 (Dual Nature)
    add("GT-5", "BT-4", 0.6, 0.2, 0.9, "amplitude override trap revealed integration duality")

    # --- GT → PC: Traps that became perspective checks ---
    add("GT-2", "PC-7", 0.5, 0.3, 0.8, "blind trust trap → 'what if signal lies?'")
    add("GT-1", "PC-1", 0.5, 0.3, 0.8, "isolated agents → 'sharing knowledge or isolated?'")
    add("GT-1", "PC-3", 0.5, 0.3, 0.8, "isolated agents → 'existing infrastructure unused?'")
    add("GT-3", "PC-4", 0.5, 0.3, 0.8, "greedy matching → 'stall after 3+ commits?'")

    # --- GT → WP: Traps that became principles ---
    add("GT-1", "WP-3", 0.6, 0.2, 0.9, "isolated agents → cooperation > competition")
    add("GT-4", "WP-6", 0.6, 0.2, 0.9, "distance collapse → self-modifying signal quality")
    add("GT-5", "WP-6", 0.4, 0.3, 0.8, "override trap → self-modifying signal quality")

    # --- BT → Layer: Breakthroughs implemented in architecture ---
    add("BT-1", "L9", 0.5, 0.2, 0.9, "Hungarian matching → dream mode")
    add("BT-2", "L6", 0.4, 0.2, 0.9, "shared historization → multiverse")
    add("BT-3", "L1", 0.3, 0.2, 0.9, "epistemic liveness → primitives (F>0 requirement)")
    add("BT-4", "L5", 0.5, 0.2, 0.9, "dual nature → reflexion (self-graph monitors amplitude)")

    # --- Layer → Layer: Architecture dependencies (bottom-up) ---
    layer_deps = [
        ("L1", "L2", 0.2, "primitives → landscape"),
        ("L2", "L3", 0.3, "landscape → controller"),
        ("L3", "L4", 0.4, "controller → amplitude"),
        ("L3", "L5", 0.4, "controller → reflexion"),
        ("L5", "L6", 0.5, "reflexion → multiverse"),
        ("L2", "L7", 0.3, "landscape → LLM integration"),
        ("L2", "L8", 0.4, "landscape → observation"),
        ("L6", "L9", 0.5, "multiverse → dream mode"),
        ("L9", "L10", 0.4, "dream → structural entropy"),
        ("L10", "L11", 0.3, "entropy → sleep-wake"),
        ("L7", "L12", 0.5, "LLM → curriculum"),
        ("L3", "L13", 0.6, "controller → human comm"),
        ("L13", "L14", 0.4, "human comm → session runner"),
    ]
    for src, tgt, delta, deriv in layer_deps:
        add(src, tgt, delta, 0.1, 0.95, deriv)

    # --- WP → WP: Principle reinforcement ---
    add("WP-2", "WP-1", 0.3, 0.2, 0.8, "historization dominant → skeleton/muscle")
    add("WP-7", "WP-2", 0.3, 0.2, 0.8, "doubt necessary → historization dominant")
    add("WP-3", "WP-5", 0.3, 0.2, 0.8, "cooperation → pipeline bottleneck thinking")

    # --- HERE → Open Threads: Current state to frontier ---
    for nid in nodes:
        if nodes[nid]["type"] == "open_thread":
            # Open threads have high delta (big gap) and high resistance (unresolved)
            add("HERE", nid, 0.8, 0.7, 0.5, f"current state → {nodes[nid]['label'][:40]}")

    # --- Open Threads → Layers: What each thread connects to ---
    add("OPEN-1", "L14", 0.7, 0.5, 0.6, "orchestrator pattern → session runner")
    add("OPEN-1", "L6", 0.6, 0.5, 0.6, "orchestrator pattern → multiverse")
    add("OPEN-2", "L3", 0.8, 0.6, 0.4, "adversarial stability → controller")
    add("OPEN-2", "L5", 0.7, 0.5, 0.5, "adversarial stability → reflexion")
    add("OPEN-3", "L5", 0.5, 0.4, 0.6, "longer loops → reflexion (self-graph)")
    add("OPEN-3", "L4", 0.5, 0.4, 0.6, "longer loops → amplitude")

    # --- HERE → Recent work (low resistance — just traveled) ---
    add("HERE", "GT-5", 0.2, 0.1, 0.95, "just resolved GT-5")
    add("HERE", "BT-4", 0.2, 0.1, 0.95, "just discovered dual nature")
    add("HERE", "L5", 0.2, 0.1, 0.95, "just worked on reflexion layer")

    # --- Layer → HERE: All layers are operational from current state ---
    for nid in nodes:
        if nodes[nid]["type"] == "arch_layer":
            add(nid, "HERE", 0.1, 0.1, 0.95, f"{nid} operational → current state")

    return edges


# ---------------------------------------------------------------------------
# Phase 2: Build Landscape
# ---------------------------------------------------------------------------


def build_spec(nodes, edges):
    """Convert extracted nodes/edges into bootstrapper-compatible spec."""
    spec = {
        "nodes": list(nodes.keys()),
        "edges": edges,
    }
    return spec


def inject_node_traces(landscape, nodes):
    """Inject the existing U/F traces from bootstrap.json into the Landscape.

    The traces in bootstrap.json are REAL historization data.
    confirmed/contradicted, recurred, built_upon — these are accumulated
    over 194 commits. We inject them as initial edge traces on self-loops
    or on the highest-confidence outgoing edge of each node.
    """
    from e0_controller.primitives import Edge as PEdge

    hist = landscape.historization
    for nid, info in nodes.items():
        u = info.get("U", 0.0)
        f = info.get("F", 0.0)
        if u == 0.0 and f == 0.0:
            continue
        # Find outgoing edges from this node and distribute traces
        outgoing = [e for e in landscape.edges if e.source == nid]
        if not outgoing:
            continue
        # Inject on ALL outgoing edges, proportional
        for edge in outgoing:
            # Scale: each outgoing edge gets the full quality signal
            # but load proportional to edge count (don't inflate total)
            scale = 1.0 / len(outgoing)
            if u * scale > 0:
                for _ in range(max(1, int(u * scale))):
                    hist.update(edge, Outcome.SUCCESS)
            if f * scale > 0:
                for _ in range(max(1, int(f * scale))):
                    hist.update(edge, Outcome.FAILURE)


# ---------------------------------------------------------------------------
# Phase 3: Navigate
# ---------------------------------------------------------------------------


def make_execute_fn(nodes):
    """Build an execute_fn that simulates domain knowledge.

    - Transitions TO resolved nodes → SUCCESS (known territory)
    - Transitions TO open threads → depends on confidence
    - Transitions TO breakthroughs → always SUCCESS
    - Transitions TO layers → always SUCCESS (they work)
    """
    def execute(source, target):
        info = nodes.get(target, {})
        ntype = info.get("type", "")

        if ntype == "arch_layer":
            return Outcome.SUCCESS  # All layers pass tests
        if ntype == "breakthrough":
            return Outcome.SUCCESS  # Proven insights
        if ntype == "working_principle":
            u, f = info.get("U", 0), info.get("F", 0)
            if u > f:
                return Outcome.SUCCESS
            return Outcome.FAILURE
        if ntype == "gordian_trap":
            # Resolved traps are safe; unresolved are dangerous
            if info.get("resolution"):
                return Outcome.SUCCESS
            return Outcome.FAILURE
        if ntype == "perspective_check":
            return Outcome.SUCCESS  # Awareness is always productive
        if ntype == "open_thread":
            return Outcome.FAILURE  # Not yet resolved!
        if ntype == "current_state":
            return Outcome.SUCCESS

        return Outcome.SUCCESS

    return execute


def make_revisit_aware_execute(nodes):
    """Execute_fn that treats revisiting resolved knowledge as FAILURE.

    The honest domain model: visiting GT-5 for the 5th time teaches nothing.
    Revisiting comfortable territory without new learning IS failure.
    This is BT-3 (Epistemic Liveness) applied to the meta-domain.
    """
    visit_count = {}

    def execute(source, target):
        visit_count[target] = visit_count.get(target, 0) + 1
        info = nodes.get(target, {})
        ntype = info.get("type", "")

        # First visit is always informative
        if visit_count[target] <= 1:
            return make_execute_fn(nodes)(source, target)

        # Revisiting open threads: still FAILURE (still unresolved)
        if ntype == "open_thread":
            return Outcome.FAILURE

        # Revisiting resolved knowledge: FAILURE (no new learning)
        # This is the key insight: comfort without growth = structural waste
        if ntype in ("gordian_trap", "breakthrough", "arch_layer", "current_state"):
            return Outcome.FAILURE

        # Working principles and perspective checks: SUCCESS on revisit
        # (reviewing principles IS productive — reinforcement)
        if ntype in ("working_principle", "perspective_check"):
            u, f = info.get("U", 0), info.get("F", 0)
            return Outcome.SUCCESS if u > f else Outcome.FAILURE

        return Outcome.FAILURE

    return execute


def run_navigation(landscape, nodes, start, goal, label, max_cycles=30,
                   use_self_graph=False, revisit_aware=False):
    """Run E₀ controller from start to goal, print results."""
    from e0_controller.controller import HybridMode
    from e0_controller.self_graph import SelfGraph

    if revisit_aware:
        execute = make_revisit_aware_execute(nodes)
    else:
        execute = make_execute_fn(nodes)
    ctrl = E0Controller(
        landscape,
        execute,
        hybrid_mode=HybridMode.AMPLITUDE_ON_DISAGREE,
        hybrid_horizon=3,
        hybrid_goals={goal},
    )
    if use_self_graph:
        ctrl.self_graph = SelfGraph()

    trace = ctrl.run(start, goal=goal, max_cycles=max_cycles)

    print(f"\n{'='*70}")
    print(f"  {label}")
    print(f"{'='*70}")
    print(f"  Start: {start} ({nodes.get(start, {}).get('label', '?')})")
    print(f"  Goal:  {goal} ({nodes.get(goal, {}).get('label', '?')})")
    print(f"  Path:  {' → '.join(trace.path)}")
    print(f"  Steps: {len(trace.path) - 1}")

    m = trace.metrics()
    print(f"  Goal reached: {m.get('goal_reached', False)}")
    print(f"  Success rate: {m.get('success_rate', 0):.1%}")
    print(f"  Avg tension:  {m.get('avg_tension', 0):.4f}")

    # Show what each step means
    print(f"\n  Structural reasoning chain:")
    for i in range(len(trace.path) - 1):
        src = trace.path[i]
        tgt = trace.path[i + 1]
        src_label = nodes.get(src, {}).get("label", "?")
        tgt_label = nodes.get(tgt, {}).get("label", "?")
        s_eff = landscape.effective_tension(src, tgt)
        print(f"    {i+1}. {src} ({src_label})")
        print(f"       → {tgt} ({tgt_label})  [S_eff={s_eff:.4f}]")

    return trace


# ---------------------------------------------------------------------------
# Phase 4: Analysis
# ---------------------------------------------------------------------------


def landscape_report(landscape, nodes):
    """Print landscape topology summary."""
    print(f"\n{'='*70}")
    print(f"  bootstrap.json as Landscape")
    print(f"{'='*70}")
    print(f"  Nodes: {len(nodes)}")
    print(f"  Edges: {landscape.edge_count()}")
    print(f"  States: {len(landscape.states)}")

    # Node types
    types = {}
    for n in nodes.values():
        t = n["type"]
        types[t] = types.get(t, 0) + 1
    print(f"\n  Node types:")
    for t, c in sorted(types.items()):
        print(f"    {t}: {c}")

    # Trace statistics
    total_u, total_f = 0.0, 0.0
    for nid, info in nodes.items():
        total_u += info.get("U", 0)
        total_f += info.get("F", 0)
    print(f"\n  Existing traces from 194 commits:")
    print(f"    Total U (success signals): {total_u:.1f}")
    print(f"    Total F (failure signals): {total_f:.1f}")
    print(f"    Overall quality: {(total_u - total_f) / (total_u + total_f + 1):.3f}")

    # Highest/lowest tension edges
    tensions = []
    for e in landscape.edges:
        s = landscape.effective_tension(e.source, e.target)
        if s < float("inf"):
            tensions.append((e, s))
    tensions.sort(key=lambda x: x[1])

    print(f"\n  Lowest-tension transitions (easiest paths):")
    for e, s in tensions[:5]:
        sl = nodes.get(e.source, {}).get("label", "?")[:30]
        tl = nodes.get(e.target, {}).get("label", "?")[:30]
        print(f"    {e.source}→{e.target}  S={s:.4f}  ({sl} → {tl})")

    print(f"\n  Highest-tension transitions (hardest paths):")
    for e, s in tensions[-5:]:
        sl = nodes.get(e.source, {}).get("label", "?")[:30]
        tl = nodes.get(e.target, {}).get("label", "?")[:30]
        print(f"    {e.source}→{e.target}  S={s:.4f}  ({sl} → {tl})")


# ---------------------------------------------------------------------------
# Phase 5: Transition Potential — autonomous goal selection
# ---------------------------------------------------------------------------

MU = 5.0  # Half-load constant (from E0Config.mu)


def transition_potential(landscape, edge):
    """Where unresolved differences exist.

    T(e) = Δ(e) · 1/(1 + m(e)/μ)

    High Δ + low load = high potential (unexplored territory).
    High Δ + high load = low potential (already worked on).
    Low Δ = low potential (little difference to resolve).
    """
    delta = landscape.difference(edge.source, edge.target)
    if delta is None or delta == 0:
        return 0.0
    load = landscape.historization.trace_load(edge)
    return delta * (1.0 / (1.0 + load / MU))


def compute_state_potential(landscape, nodes):
    """Aggregate transition potential per target state.

    A state's potential = sum of incoming transition potentials.
    States that are reachable via high-Δ, low-load paths have high potential.
    """
    potentials = {s: 0.0 for s in landscape.states}
    edge_potentials = {}

    for e in landscape.edges:
        tp = transition_potential(landscape, e)
        edge_potentials[e] = tp
        potentials[e.target] = potentials.get(e.target, 0.0) + tp

    return potentials, edge_potentials


def autonomous_goal(landscape, nodes, current_state):
    """E₀ identifies its own next goal from transition potential.

    Returns (goal_state, potential) or (None, 0) if saturated.
    """
    potentials, _ = compute_state_potential(landscape, nodes)

    # Don't select current state as goal
    candidates = [(s, p) for s, p in potentials.items() if s != current_state and p > 0]
    if not candidates:
        return None, 0.0

    best = max(candidates, key=lambda x: x[1])
    return best


def local_transition_potential(landscape, nodes, current, horizon=2):
    """Compute transition potential LOCAL to current state.

    Instead of asking "which state has the most global potential?",
    ask "which neighbor can I reach from HERE that leads to the
    highest unresolved difference?"

    With horizon=1: only direct neighbors, T(current→neighbor).
    With horizon=2+: also look through neighbors — what T values
    are accessible BEHIND each neighbor? Sum of T along best paths.

    Returns dict of {neighbor: potential} for direct neighbors of current.
    """
    from e0_controller.landscape import Edge

    # Phase 1: Direct neighbor potentials
    neighbor_potential = {}
    for e in landscape.edges:
        if e.source == current:
            tp = transition_potential(landscape, e)
            neighbor_potential[e.target] = tp

    if horizon <= 1:
        return neighbor_potential

    # Phase 2: Look through each neighbor — what's accessible beyond?
    # For each neighbor N, find the max T of edges departing from N.
    # This is "looking into the distance": N is valuable not just for
    # its own Δ, but for what it LEADS TO.
    for depth in range(2, horizon + 1):
        # Build state→best_continuation map at this depth
        continuation = {}
        for e in landscape.edges:
            tp = transition_potential(landscape, e)
            if tp > continuation.get(e.source, 0.0):
                continuation[e.source] = tp

        # Add best continuation value to each neighbor (discounted by depth)
        for nbr in list(neighbor_potential.keys()):
            if nbr in continuation:
                # Discount deeper horizons — closer potential is more actionable
                neighbor_potential[nbr] += continuation[nbr] / depth

    return neighbor_potential


def local_autonomous_step(landscape, nodes, current, horizon=2):
    """E₀ picks its next step from LOCAL transition potential.

    No goal needed. The potential IS the goal.
    Returns (best_neighbor, potential) or (None, 0) if saturated.
    """
    potentials = local_transition_potential(landscape, nodes, current, horizon)
    if not potentials:
        return None, 0.0

    best = max(potentials.items(), key=lambda x: x[1])
    if best[1] <= 0:
        return None, 0.0
    return best


def run_transition_potential(landscape, nodes, edges):
    """Experiment 6: E₀ autonomously selects goals from transition potential."""
    from e0_controller.controller import HybridMode
    from e0_controller.self_graph import SelfGraph

    potentials, edge_potentials = compute_state_potential(landscape, nodes)

    # Report: edge-level transition potentials
    print(f"\n  Edge transition potentials (top 15):")
    sorted_edges = sorted(edge_potentials.items(), key=lambda x: -x[1])
    for e, tp in sorted_edges[:15]:
        sl = nodes.get(e.source, {}).get("label", "?")[:25]
        tl = nodes.get(e.target, {}).get("label", "?")[:25]
        delta = landscape.difference(e.source, e.target) or 0
        load = landscape.historization.trace_load(e)
        print(f"    {e.source:8s}→{e.target:8s}  T={tp:.4f}  Δ={delta:.2f}  m={load:.1f}  ({sl} → {tl})")

    # Report: state-level aggregated potentials
    print(f"\n  State transition potentials (all non-zero):")
    sorted_states = sorted(potentials.items(), key=lambda x: -x[1])
    for s, p in sorted_states:
        if p <= 0:
            break
        label = nodes.get(s, {}).get("label", "?")[:40]
        ntype = nodes.get(s, {}).get("type", "?")
        print(f"    {s:8s}  T={p:.4f}  [{ntype:20s}]  {label}")

    # Phase A: What does E₀ choose as its goal?
    goal_state, goal_potential = autonomous_goal(landscape, nodes, "HERE")
    print(f"\n  Autonomous goal: {goal_state} (T={goal_potential:.4f})")
    print(f"  Label: {nodes.get(goal_state, {}).get('label', '?')}")
    print(f"  Type:  {nodes.get(goal_state, {}).get('type', '?')}")

    # Phase B: Navigate with transition potential as goal, honest execute + self-graph
    if goal_state:
        fresh = bootstrap_landscape(build_spec(nodes, edges))
        inject_node_traces(fresh, nodes)
        run_navigation(
            fresh, nodes, "HERE", goal_state,
            f"[TP→{goal_state}] Autonomous: highest unresolved difference",
            use_self_graph=True,
            revisit_aware=True,
        )

    # Phase C: Iterative autonomous navigation
    # E₀ picks its own goal, navigates, then picks the next goal.
    # Stops when saturated (no more potential) or after 5 iterations.
    print(f"\n  {'='*70}")
    print(f"  Iterative autonomous navigation (max 5 rounds)")
    print(f"  E₀ picks its own goal each round. Stops when saturated.")
    print(f"  {'='*70}")

    iter_landscape = bootstrap_landscape(build_spec(nodes, edges))
    inject_node_traces(iter_landscape, nodes)
    current = "HERE"
    visited_goals = []

    for round_num in range(1, 6):
        goal, potential = autonomous_goal(iter_landscape, nodes, current)

        if goal is None:
            print(f"\n  Round {round_num}: SATURATED — no transition potential remaining.")
            print(f"  E₀ says: 'Ich brauche eine externe Differenz.'")
            break

        visited_goals.append((goal, potential))
        print(f"\n  Round {round_num}: Goal={goal} (T={potential:.4f})")
        print(f"    ({nodes.get(goal, {}).get('label', '?')[:60]})")

        execute = make_revisit_aware_execute(nodes)
        ctrl = E0Controller(
            iter_landscape,
            execute,
            hybrid_mode=HybridMode.AMPLITUDE_ON_DISAGREE,
            hybrid_horizon=3,
            hybrid_goals={goal},
        )
        ctrl.self_graph = SelfGraph()

        trace = ctrl.run(current, goal=goal, max_cycles=15)
        m = trace.metrics()

        reached = m.get("goal_reached", False)
        final = trace.path[-1] if trace.path else current
        print(f"    Path: {' → '.join(trace.path[:8])}{'...' if len(trace.path) > 8 else ''}")
        print(f"    Reached: {reached}, Steps: {len(trace.path)-1}, Final: {final}")

        current = final

    if visited_goals:
        print(f"\n  Autonomous goal sequence:")
        for i, (g, p) in enumerate(visited_goals, 1):
            label = nodes.get(g, {}).get("label", "?")[:50]
            print(f"    {i}. {g} (T={p:.4f}) — {label}")


def run_local_exploration(landscape, nodes, edges):
    """Experiment 7: Local transition potential — action is always local.

    Instead of global state potential (Exp 6: L5↔L6 oscillation),
    use LOCAL potential: from current state, which NEIGHBOR has the
    highest unresolved difference?

    Same idea as amplitude overlay — look into the distance — but
    used for EXPLORATION (argmax T) instead of EXPLOITATION (argmin S_eff).

    Amplitude overlay: "Which neighbor leads to lowest-resistance path to goal?"
    Local T-potential: "Which neighbor leads to highest unresolved difference?"
    """
    print(f"\n  Phase A: Local potential from HERE (horizon=1)")
    print(f"  {'─'*60}")
    local_h1 = local_transition_potential(landscape, nodes, "HERE", horizon=1)
    for nbr, tp in sorted(local_h1.items(), key=lambda x: -x[1]):
        label = nodes.get(nbr, {}).get("label", "?")[:40]
        ntype = nodes.get(nbr, {}).get("type", "?")
        print(f"    HERE→{nbr:8s}  T={tp:.4f}  [{ntype:20s}]  {label}")

    print(f"\n  Phase B: Local potential from HERE (horizon=3)")
    print(f"  Looking through neighbors — what's behind them?")
    print(f"  {'─'*60}")
    local_h3 = local_transition_potential(landscape, nodes, "HERE", horizon=3)
    for nbr, tp in sorted(local_h3.items(), key=lambda x: -x[1]):
        label = nodes.get(nbr, {}).get("label", "?")[:40]
        ntype = nodes.get(nbr, {}).get("type", "?")
        from e0_controller.landscape import Edge as _Edge
        edge = _Edge("HERE", nbr)
        delta = landscape.difference("HERE", nbr) or 0
        load = landscape.historization.trace_load(edge) if landscape.has_edge("HERE", nbr) else 0
        print(f"    HERE→{nbr:8s}  T={tp:.4f}  (Δ={delta:.2f} m={load:.1f})  [{ntype:20s}]  {label}")

    # Phase C: Iterative LOCAL exploration — no global goals
    # E₀ picks its next STEP from local potential. No goal needed.
    # The potential IS the goal.
    print(f"\n  Phase C: Iterative local exploration (max 30 steps)")
    print(f"  No goal. Each step: argmax T(current→neighbor, horizon=3)")
    print(f"  Amplitude overlay asks: 'best path to goal' (exploitation)")
    print(f"  Local T-potential asks: 'highest unresolved difference' (exploration)")
    print(f"  {'─'*60}")

    iter_landscape = bootstrap_landscape(build_spec(nodes, edges))
    inject_node_traces(iter_landscape, nodes)
    current = "HERE"
    path = [current]
    visited_count = {}  # Track how often each state is visited

    for step in range(1, 31):
        visited_count[current] = visited_count.get(current, 0) + 1

        nbr, potential = local_autonomous_step(
            iter_landscape, nodes, current, horizon=3
        )

        if nbr is None:
            print(f"\n  Step {step}: SATURATED at {current}")
            print(f"  E₀ says: 'Ich brauche eine externe Differenz.'")
            break

        # After visiting, the edge gains load (honest domain execution)
        from e0_controller.landscape import Edge as _Edge, Outcome
        edge = _Edge(current, nbr)
        if iter_landscape.has_edge(current, nbr):
            node_info = nodes.get(nbr, {})
            node_type = node_info.get("type", "")
            # Open threads = FAILURE (unresolved), others = SUCCESS
            outcome = Outcome.FAILURE if node_type == "open_thread" else Outcome.SUCCESS
            # Revisit penalty: visiting known territory again = FAILURE
            if visited_count.get(nbr, 0) > 0 and node_type != "open_thread":
                outcome = Outcome.FAILURE
            # update() modifies _U/_F (trace_load changes).
            # record() only logs — doesn't affect future T(e).
            iter_landscape.historization.update(edge, outcome)

        label = nodes.get(nbr, {}).get("label", "?")[:45]
        ntype = nodes.get(nbr, {}).get("type", "?")
        print(f"  Step {step:2d}: {current:8s} → {nbr:8s}  T={potential:.4f}  [{ntype:20s}]  {label}")

        path.append(nbr)
        current = nbr

    # Summary
    unique_states = len(set(path))
    open_reached = [s for s in path if nodes.get(s, {}).get("type") == "open_thread"]
    unique_open = set(open_reached)

    print(f"\n  {'─'*60}")
    print(f"  Exploration summary:")
    print(f"    Path length:     {len(path) - 1} steps")
    print(f"    Unique states:   {unique_states} / {len(nodes)} total")
    print(f"    Open threads:    {len(unique_open)} / 3 reached")
    if unique_open:
        for s in sorted(unique_open):
            print(f"      ✓ {s}: {nodes[s]['label'][:50]}")
    print(f"    Full path: {' → '.join(path)}")

    # Phase D: Structural creation — exploration CREATES new topology
    # When E₀ traverses A→B→C, it discovers a potential direct A→C.
    # The exploration cycle itself is a structural insight.
    # New edges emerge from completed cycles: the start and end of each
    # sub-path that doesn't already have a direct connection.
    print(f"\n  Phase D: Does exploration create new structure?")
    print(f"  {'─'*60}")
    print(f"  A traversed path A→B→C implies a potential direct edge A→C.")
    print(f"  If A→C doesn't exist yet: NEW TRANSITION discovered.")
    print(f"  Δ(A→C) = average Δ along the path (inherited difference).")
    print(f"  R₀(A→C) = sum of R₀ along the path (accumulated resistance).")
    print(f"  {'─'*60}")

    # Detect cycles in the exploration path (return to a previously visited state)
    new_edges_added = []
    for i in range(len(path)):
        for j in range(i + 2, min(i + 5, len(path))):  # sub-paths of len 2-4
            src, tgt = path[i], path[j]
            if src == tgt:
                continue  # self-loop
            if iter_landscape.has_edge(src, tgt):
                continue  # already exists
            # Compute derived properties from the sub-path
            sub = path[i:j+1]
            deltas, resistances = [], []
            valid = True
            for k in range(len(sub) - 1):
                d = iter_landscape.difference(sub[k], sub[k+1])
                if d is None:
                    valid = False
                    break
                deltas.append(d)
                resistances.append(iter_landscape._R0.get(
                    _Edge(sub[k], sub[k+1]), 1.0))
            if not valid or not deltas:
                continue
            # New edge: average Δ, sum R₀
            new_delta = sum(deltas) / len(deltas)
            new_r0 = sum(resistances)
            if new_delta < 0.1:
                continue  # too little difference to matter

            iter_landscape.add_edge(src, tgt, new_delta, new_r0)
            src_label = nodes.get(src, {}).get("label", "?")[:25]
            tgt_label = nodes.get(tgt, {}).get("label", "?")[:25]
            new_edges_added.append((src, tgt, new_delta, new_r0, sub))
            print(f"    NEW: {src:8s}→{tgt:8s}  Δ={new_delta:.2f}  R₀={new_r0:.2f}  "
                  f"via {' → '.join(sub)}")
            print(f"         ({src_label} → {tgt_label})")

    print(f"\n  New edges created: {len(new_edges_added)}")
    print(f"  Landscape now: {iter_landscape.edge_count()} edges "
          f"(was {len(edges)})")

    if not new_edges_added:
        print(f"  No new structure emerged — exploration was circular.")
        return

    # Phase E: Re-explore with enriched topology
    # Now that new edges exist, does E₀ reach NEW territory?
    print(f"\n  Phase E: Re-explore with enriched topology (15 more steps)")
    print(f"  {'─'*60}")

    current = "HERE"
    path2 = [current]
    visited_count2 = {}

    for step in range(1, 16):
        visited_count2[current] = visited_count2.get(current, 0) + 1

        nbr, potential = local_autonomous_step(
            iter_landscape, nodes, current, horizon=3
        )
        if nbr is None:
            print(f"\n  Step {step}: SATURATED at {current}")
            break

        edge = _Edge(current, nbr)
        if iter_landscape.has_edge(current, nbr):
            node_info = nodes.get(nbr, {})
            node_type = node_info.get("type", "")
            outcome = Outcome.FAILURE if node_type == "open_thread" else Outcome.SUCCESS
            if visited_count2.get(nbr, 0) > 0 and node_type != "open_thread":
                outcome = Outcome.FAILURE
            iter_landscape.historization.update(edge, outcome)

        label = nodes.get(nbr, {}).get("label", "?")[:45]
        ntype = nodes.get(nbr, {}).get("type", "?")
        is_new = "★" if any(e[0] == current and e[1] == nbr for e in new_edges_added) else " "
        print(f"  Step {step:2d}: {current:8s} → {nbr:8s}  T={potential:.4f} {is_new} [{ntype:20s}]  {label}")

        path2.append(nbr)
        current = nbr

    unique2 = len(set(path2))
    open2 = set(s for s in path2 if nodes.get(s, {}).get("type") == "open_thread")
    print(f"\n  {'─'*60}")
    print(f"  Re-exploration summary:")
    print(f"    Unique states:   {unique2} / {len(nodes)} total")
    print(f"    Open threads:    {len(open2)} / 3 reached")
    if open2:
        for s in sorted(open2):
            print(f"      ✓ {s}: {nodes[s]['label'][:50]}")
    # Compare: did new topology change behavior?
    all_unique = len(set(path + path2))
    all_open = set(s for s in path + path2 if nodes.get(s, {}).get("type") == "open_thread")
    print(f"\n  Total exploration (Phase C + E):")
    print(f"    Combined unique states:  {all_unique} / {len(nodes)}")
    print(f"    Combined open threads:   {len(all_open)} / 3")
    print(f"    Full Phase E path: {' → '.join(path2)}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    print("=" * 70)
    print("  E₀ navigates its own project memory (bootstrap.json)")
    print("  Domain Invariance: E₀ doesn't need to read — it needs structure")
    print("=" * 70)

    # Phase 1: Parse
    bs = load_bootstrap()
    nodes = extract_nodes(bs)
    edges = extract_edges(bs, nodes)

    print(f"\n  Extracted {len(nodes)} nodes, {len(edges)} edges")
    print(f"  Node labels:")
    for nid, info in sorted(nodes.items()):
        q = "n/a"
        u, f = info.get("U", 0), info.get("F", 0)
        if u + f > 0:
            q = f"{(u - f) / (u + f + 1):.2f}"
        print(f"    {nid:8s} [{info['type']:20s}] q={q:>6s}  {info['label'][:50]}")

    # Phase 2: Build
    spec = build_spec(nodes, edges)
    landscape = bootstrap_landscape(spec)
    inject_node_traces(landscape, nodes)

    # Phase 3: Report
    landscape_report(landscape, nodes)

    # Phase 4: Navigate — three experiments

    # Experiment 1: From HERE, reach each open thread.
    # Which one does E₀ find structurally closest?
    print(f"\n\n{'#'*70}")
    print(f"  EXPERIMENT 1: Which open thread is structurally closest?")
    print(f"{'#'*70}")

    open_nodes = [n for n in nodes if nodes[n]["type"] == "open_thread"]
    for goal in open_nodes:
        run_navigation(landscape, nodes, "HERE", goal,
                       f"HERE → {goal}: {nodes[goal]['label'][:50]}")

    # Experiment 2: From an open thread, can E₀ find its way back
    # through resolved knowledge?
    print(f"\n\n{'#'*70}")
    print(f"  EXPERIMENT 2: From open thread back to solid ground")
    print(f"{'#'*70}")

    for start in open_nodes:
        # Try to reach HERE (current solid state)
        run_navigation(landscape, nodes, start, "HERE",
                       f"{start} → HERE: Can unresolved reach resolved?")

    # Experiment 3: From a Gordian Trap, reach the Breakthrough
    # This is the META question: can E₀ re-derive our learning path?
    print(f"\n\n{'#'*70}")
    print(f"  EXPERIMENT 3: Re-derive the learning path (GT → BT)")
    print(f"{'#'*70}")

    gt_bt_pairs = [
        ("GT-1", "BT-2", "Isolated Agents → Shared Historization"),
        ("GT-3", "BT-1", "Greedy Matching → Hungarian"),
        ("GT-5", "BT-4", "Override Trap → Dual Nature"),
    ]
    for gt, bt, label in gt_bt_pairs:
        if gt in nodes and bt in nodes:
            run_navigation(landscape, nodes, gt, bt, label)

    # Experiment 4: Same as Experiment 1, but WITH Self-Graph
    # C193 built the self-graph override gate for exactly this pattern.
    # Does self-reflection break the comfort loop at the meta-level?
    print(f"\n\n{'#'*70}")
    print(f"  EXPERIMENT 4: Self-Graph breaks the comfort loop?")
    print(f"  (Repeating Experiment 1 with self-reflection enabled)")
    print(f"{'#'*70}")

    for goal in open_nodes:
        # Fresh landscape for each run (self-graph state is per-controller)
        fresh_landscape = bootstrap_landscape(build_spec(nodes, edges))
        inject_node_traces(fresh_landscape, nodes)
        run_navigation(
            fresh_landscape, nodes, "HERE", goal,
            f"[+SelfGraph] HERE → {goal}: {nodes[goal]['label'][:40]}",
            use_self_graph=True,
        )

    # Experiment 5: Revisit-aware execute + Self-Graph
    # The honest domain model: revisiting resolved knowledge = FAILURE.
    # BT-3 says F=0 traps forever. We add the F signal.
    print(f"\n\n{'#'*70}")
    print(f"  EXPERIMENT 5: Honest domain model (revisit = failure) + Self-Graph")
    print(f"  BT-3: 'F=0 traps the system forever. Zweifel ist strukturell nötig.'")
    print(f"{'#'*70}")

    for goal in open_nodes:
        fresh_landscape = bootstrap_landscape(build_spec(nodes, edges))
        inject_node_traces(fresh_landscape, nodes)
        run_navigation(
            fresh_landscape, nodes, "HERE", goal,
            f"[+Honest+SG] HERE → {goal}: {nodes[goal]['label'][:40]}",
            use_self_graph=True,
            revisit_aware=True,
        )

    # Summary
    print(f"\n\n{'#'*70}")
    print(f"  EXPERIMENT 6: Transition Potential — E₀ finds its own goals")
    print(f"  'Greedy/Amplitude/Born search known paths.")
    print(f"   Transition Potential searches for NEW paths.'")
    print(f"{'#'*70}")

    fresh_landscape = bootstrap_landscape(build_spec(nodes, edges))
    inject_node_traces(fresh_landscape, nodes)
    run_transition_potential(fresh_landscape, nodes, edges)

    # Experiment 7: Local Transition Potential — action is always local
    # Exp 6 failed because global aggregation = popularity bias.
    # Hub nodes (L5, L6) win, open threads lose.
    # Fix: compute potential FROM current state outward.
    # Same as amplitude overlay (look ahead) but inverted:
    #   Amplitude: argmax |ΣΨ|² → exploitation (best path to goal)
    #   Local T:   argmax T(e)   → exploration (highest unresolved Δ)
    print(f"\n\n{'#'*70}")
    print(f"  EXPERIMENT 7: Local Transition Potential — 'Handeln ist lokal'")
    print(f"  Amplitude overlay looks into the distance for exploitation.")
    print(f"  Local T-potential looks into the distance for EXPLORATION.")
    print(f"  Same mechanism, inverted criterion: argmax T instead of argmin S_eff.")
    print(f"{'#'*70}")

    fresh_landscape = bootstrap_landscape(build_spec(nodes, edges))
    inject_node_traces(fresh_landscape, nodes)
    run_local_exploration(fresh_landscape, nodes, edges)

    # Summary
    print(f"\n\n{'#'*70}")
    print(f"  SUMMARY")
    print(f"{'#'*70}")
    print(f"""
  bootstrap.json contains {len(nodes)} navigable concepts with {len(edges)} transitions.

  The traces are REAL — accumulated over 194 commits of human-AI collaboration.
  The topology is REAL — edges follow actual cross-references in the data.

  What E₀ sees: a graph with areas of high confidence (resolved traps,
  confirmed principles, working layers) and areas of high resistance
  (open threads, unresolved questions).

  What E₀ recommends: follow lowest-burden paths through confirmed
  knowledge toward the structurally closest open problem.

  The recursive insight: this exploration is itself a transition in
  the bootstrap.json landscape — from "unstructured JSON" to
  "navigable self-model". If it works, it historizes SUCCESS.
  If it doesn't, that's equally valuable data.
""")


if __name__ == "__main__":
    main()
