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

BOOTSTRAP_PATH = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "bootstrap.json"))
LEARNING_STATE_PATH = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "learning_state.json"))


def load_bootstrap():
    """Load and return the raw bootstrap.json."""
    with open(BOOTSTRAP_PATH, encoding="utf-8") as f:
        return json.load(f)


_EMPTY_LEARNING_STATE = {"discovered_edges": {"edges": []}, "cross_domain_bridges": {"bridges": []}}


def load_learning_state():
    """Load and return learning_state.json (discovered edges, bridges, history)."""
    if not os.path.exists(LEARNING_STATE_PATH):
        return dict(_EMPTY_LEARNING_STATE)
    try:
        with open(LEARNING_STATE_PATH, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return dict(_EMPTY_LEARNING_STATE)


def save_learning_state(ls):
    """Write learning_state.json atomically (write tmp, then rename).

    Falls back to direct write if atomic rename fails (Windows file locks).
    """
    tmp_path = LEARNING_STATE_PATH + ".tmp"
    try:
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(ls, f, indent=2, ensure_ascii=False)
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, LEARNING_STATE_PATH)
    except OSError:
        # Atomic rename failed (Windows lock) — fall back to direct write
        with open(LEARNING_STATE_PATH, "w", encoding="utf-8") as f:
            json.dump(ls, f, indent=2, ensure_ascii=False)
            f.write("\n")
        # Clean up temp file if it exists
        try:
            os.remove(tmp_path)
        except OSError:
            pass


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
            "description": gt.get("lesson", ""),
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
            "description": bt.get("insight", ""),
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
            "description": wp.get("principle", ""),
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
            "description": pc.get("question", ""),
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
            "description": ", ".join(layer.get("files", [])),
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
            "description": thread,
            "U": 0.0,  # Not resolved
            "F": 0.0,  # Not yet attempted in current form
        }

    # --- Meta node: current state ---
    state = bs.get("state", {})
    nodes["HERE"] = {
        "type": "current_state",
        "label": f"C{194} — v1.0.0",
        "description": state.get("latest_commit_msg", ""),
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
    add("GT-1", "PC-2", 0.5, 0.3, 0.8, "isolated agents (C189) → 'testing what I think?'")
    add("GT-5", "PC-5", 0.5, 0.3, 0.8, "override trap → 'if test fails, what do I learn?'")
    add("GT-3", "PC-6", 0.5, 0.3, 0.8, "greedy matching → 'fixing the right problem?'")

    # --- PC → WP: Perspective checks flow into principles ---
    add("PC-1", "WP-3", 0.4, 0.2, 0.8, "'sharing knowledge?' reinforces cooperation principle")
    add("PC-2", "WP-4", 0.4, 0.2, 0.8, "'testing what I think?' reinforces quality > quantity")
    add("PC-3", "WP-5", 0.4, 0.2, 0.8, "'infrastructure unused?' reinforces pipeline thinking")
    add("PC-4", "WP-5", 0.4, 0.2, 0.8, "'stall after 3+ commits?' reinforces pipeline thinking")
    add("PC-5", "WP-7", 0.4, 0.2, 0.8, "'what do I learn from failure?' reinforces doubt")
    add("PC-6", "WP-6", 0.4, 0.2, 0.8, "'wrong assumption?' reinforces signal monitoring")
    add("PC-7", "WP-6", 0.4, 0.2, 0.8, "'signal lies?' reinforces signal monitoring")

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
    add("HERE", "GT-2", 0.3, 0.2, 0.8, "blind trust trap was project lesson")

    # --- WP → Layer/HERE: Principles influence architecture ---
    add("WP-5", "L7", 0.3, 0.2, 0.85, "pipeline thinking → LLM integration layer")
    add("WP-5", "HERE", 0.2, 0.2, 0.8, "pipeline thinking informs current work")
    add("WP-6", "L5", 0.3, 0.2, 0.85, "signal monitoring → reflexion layer")
    add("WP-6", "HERE", 0.2, 0.2, 0.8, "signal monitoring informs current work")

    # --- Layer → HERE: All layers are operational from current state ---
    for nid in nodes:
        if nodes[nid]["type"] == "arch_layer":
            add(nid, "HERE", 0.1, 0.1, 0.95, f"{nid} operational → current state")

    # --- Discovered edges from prior exploration runs ---
    # These live in learning_state.json (separated from bootstrap.json in C203).
    # The topology grows across runs: exploration → persist → richer start.
    ls = load_learning_state()
    discovered = ls.get("discovered_edges", {}).get("edges", [])
    for de in discovered:
        src, tgt = de.get("from", ""), de.get("to", "")
        if src in nodes and tgt in nodes:
            # Don't duplicate if a hand-curated edge already exists
            existing = {(e["from"], e["to"]) for e in edges}
            if (src, tgt) not in existing:
                raw_delta = de.get("delta", 0.5)
                # Semantic modulation: LLM-validated quality scales Δ.
                # semantic_score 0.7 → keep 70% of Δ (real connection).
                # semantic_score 0.3 → only 30% of Δ (artifact).
                # No score yet → full Δ (awaiting validation).
                sem = de.get("semantic_score")
                effective_delta = raw_delta * sem if sem is not None else raw_delta
                add(src, tgt, effective_delta, de.get("resistance", 1.0),
                    de.get("confidence", 0.5),
                    de.get("derivation", "discovered by exploration"))

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


def inject_edge_metadata(landscape, edges):
    """Inject metadata from edge dicts into landscape (C205).

    Edge dicts may carry relation_type, derivation, bridge_type, confidence,
    and other semantic fields that the bootstrapper doesn't pass through.
    This function reads them back into the landscape's metadata layer.
    """
    META_KEYS = ("relation_type", "type", "derivation", "bridge_type",
                 "confidence", "semantic_score", "semantic_reason",
                 "discovered_at")
    for e in edges:
        src = e.get("from", "")
        tgt = e.get("to", "")
        if not landscape.has_edge(src, tgt):
            continue
        meta = {}
        for key in META_KEYS:
            if key in e:
                # Normalize "type" → "relation_type"
                store_key = "relation_type" if key == "type" else key
                meta[store_key] = e[key]
        if meta:
            landscape.set_edge_meta(src, tgt, **meta)


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


# ---------------------------------------------------------------------------
# Phase 6: Persistence — discovered edges survive across sessions
# ---------------------------------------------------------------------------


def filter_discovered_edges(new_edges, nodes, existing_edges):
    """Filter discovered edges for structural quality.

    Not every path shortcut is meaningful. Criteria:
    1. Connects different node TYPES (cross-type edges are structurally novel)
    2. Or connects open_thread nodes (frontier bridging)
    3. Minimum Δ threshold (too-small differences aren't actionable)
    4. No self-referential edges (src == tgt)
    5. No duplicates of existing edges
    """
    existing = {(e["from"], e["to"]) for e in existing_edges}
    filtered = []

    for edge_info in new_edges:
        src, tgt = edge_info["from"], edge_info["to"]

        # Basic validity
        if src == tgt:
            continue
        if (src, tgt) in existing:
            continue
        if src not in nodes or tgt not in nodes:
            continue
        if edge_info.get("delta", 0) < 0.15:
            continue

        src_type = nodes[src]["type"]
        tgt_type = nodes[tgt]["type"]

        # Cross-type edges are structurally novel
        cross_type = src_type != tgt_type

        # Frontier bridging: open_thread↔open_thread or open_thread↔anything
        frontier = src_type == "open_thread" or tgt_type == "open_thread"

        if cross_type or frontier:
            filtered.append(edge_info)
            existing.add((src, tgt))  # prevent duplicates within batch

    return filtered


def persist_discovered_edges(new_edges, nodes, existing_edges, dry_run=False):
    """Write discovered edges to learning_state.json.

    This closes the loop: exploration → discovery → persistence → richer start.
    Each edge carries its derivation path for traceability.

    Returns the filtered edges that were (or would be) persisted.
    """
    filtered = filter_discovered_edges(new_edges, nodes, existing_edges)

    if not filtered or dry_run:
        return filtered

    # Read current learning_state.json
    ls = load_learning_state()

    # Ensure section exists
    if "discovered_edges" not in ls:
        ls["discovered_edges"] = {
            "_comment": "Edges discovered through E₀ self-navigation.",
            "edges": [],
        }

    # Merge: don't duplicate edges already persisted
    persisted = {(e["from"], e["to"]) for e in ls["discovered_edges"]["edges"]}
    added = 0
    for edge in filtered:
        key = (edge["from"], edge["to"])
        if key not in persisted:
            ls["discovered_edges"]["edges"].append(edge)
            persisted.add(key)
            added += 1

    if added > 0:
        save_learning_state(ls)

    return filtered


def update_edge_confidence(landscape, nodes, path, phase_label="E"):
    """Update confidence of discovered edges based on actual usage.

    After Phase E (or any exploration), we know which discovered edges
    were actually used and what outcome they produced.

    Meta-level semantics: the confidence tracks whether a shortcut
    is USEFUL FOR NAVIGATION, not domain-level success/failure.
    An edge that gets traversed is useful (the system chose it).
    An edge that never gets traversed may be an artifact.

    Rules:
    - Traversed → confidence += 0.1 (capped at 1.0)
    - Not traversed → confidence -= 0.02 (slow decay, floored at 0.0)

    Returns dict of updated edges: {(from, to): new_confidence}
    """
    ls = load_learning_state()

    disc = ls.get("discovered_edges", {}).get("edges", [])
    if not disc:
        return {}

    # Build lookup: which discovered edges were traversed?
    traversed = set()
    for i in range(len(path) - 1):
        traversed.add((path[i], path[i + 1]))

    updates = {}
    for edge_info in disc:
        key = (edge_info["from"], edge_info["to"])
        old_conf = edge_info.get("confidence", 0.5)

        if key in traversed:
            # Traversed = the system found this edge useful enough to choose
            new_conf = min(1.0, old_conf + 0.1)
        else:
            # Slow decay for unused edges — structural entropy
            new_conf = max(0.0, old_conf - 0.02)

        new_conf = round(new_conf, 3)
        if new_conf != old_conf:
            edge_info["confidence"] = new_conf
            updates[key] = new_conf

    if updates:
        save_learning_state(ls)

    return updates


def llm_semantic_validation(nodes, dry_run=False):
    """Ask LLM to judge semantic plausibility of discovered edges.

    For each discovered edge, the LLM sees:
    - Source node (type, label, context)
    - Target node (type, label, context)
    - Derivation path

    And judges: "Is there a real conceptual connection?" → score 0.0–1.0

    This is the LLM=Muscle pattern: E₀ proposes structure, LLM evaluates meaning.
    """
    ls = load_learning_state()

    disc = ls.get("discovered_edges", {}).get("edges", [])
    if not disc:
        return []

    # Build edge descriptions for the LLM
    edge_descriptions = []
    for i, edge_info in enumerate(disc):
        src_id, tgt_id = edge_info["from"], edge_info["to"]
        src_node = nodes.get(src_id, {})
        tgt_node = nodes.get(tgt_id, {})
        desc = (
            f"Edge {i+1}: {src_id} → {tgt_id}\n"
            f"  Source: [{src_node.get('type', '?')}] {src_node.get('label', '?')}\n"
            f"  Target: [{tgt_node.get('type', '?')}] {tgt_node.get('label', '?')}\n"
            f"  Discovered via: {edge_info.get('derivation', '?')}\n"
            f"  Current confidence: {edge_info.get('confidence', 0.5)}"
        )
        edge_descriptions.append(desc)

    edges_text = "\n\n".join(edge_descriptions)

    system = (
        "You are evaluating structural connections in a software project's knowledge graph. "
        "The graph has nodes of types: gordian_trap (resolved mistakes), breakthrough (key insights), "
        "working_principle (confirmed lessons), perspective_check (review questions), "
        "arch_layer (code architecture layers), open_thread (unresolved problems), "
        "current_state (current project state). "
        "Edges represent meaningful conceptual connections between these elements. "
        "Some edges were discovered by automated exploration (path shortcuts) and may or may not "
        "be semantically meaningful."
    )

    user = (
        f"Rate each discovered edge for semantic plausibility. "
        f"Does a real conceptual connection exist between source and target?\n\n"
        f"Score each edge 0.0 to 1.0:\n"
        f"  1.0 = strong, obvious connection (e.g., adversarial problem → controller layer)\n"
        f"  0.7 = plausible connection (e.g., orchestrator problem → multiverse layer)\n"
        f"  0.3 = weak/indirect connection (e.g., dream mode → adversarial stability)\n"
        f"  0.0 = no real connection (artifact of path proximity)\n\n"
        f"Edges to evaluate:\n\n{edges_text}\n\n"
        f"Respond with ONLY a JSON array of objects, one per edge, like:\n"
        f'[{{"edge": 1, "score": 0.7, "reason": "brief reason"}}]\n'
        f"No other text."
    )

    if dry_run:
        return [{"edge": i + 1, "score": 0.5, "reason": "dry_run"} for i in range(len(disc))]

    try:
        from e0_controller.llm_adapter import LLMConfig, openai_call

        config = LLMConfig(
            model="gpt-4.1-mini",
            temperature=0.1,
            max_tokens=2048,
        )
        response = openai_call(system, user, config)

        # Parse JSON response
        # Strip markdown fences if present
        text = response.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1] if "\n" in text else text[3:]
            if text.endswith("```"):
                text = text[:-3]
            text = text.strip()

        results = json.loads(text)

        # Apply scores to bootstrap.json
        updated = 0
        for result in results:
            idx = result.get("edge", 0) - 1
            if 0 <= idx < len(disc):
                score = max(0.0, min(1.0, float(result.get("score", 0.5))))
                disc[idx]["semantic_score"] = round(score, 2)
                disc[idx]["semantic_reason"] = result.get("reason", "")[:100]
                updated += 1

        if updated > 0:
            save_learning_state(ls)

        return results

    except Exception as exc:
        print(f"  LLM semantic validation failed: {exc}")
        return []


# ---------------------------------------------------------------------------
# Phase H: Executable Transitions — navigation PRODUCES output
# ---------------------------------------------------------------------------

# Each node type has a specific execution template.
# The template tells the LLM *what kind of work* this transition demands.
EXECUTION_TEMPLATES = {
    "open_thread": (
        "Analyze this open research question in the E₀ framework.\n"
        "Question: {label}\n\n"
        "Based on the project context, produce:\n"
        "1. What specifically is blocking resolution?\n"
        "2. Which existing E₀ mechanisms (from the architecture layers) could help?\n"
        "3. A concrete next step (code change, test, or experiment) that would make progress.\n"
        "Be specific — reference actual module names and functions."
    ),
    "arch_layer": (
        "Assess the implementation completeness of this E₀ architecture layer.\n"
        "Layer: {label}\n"
        "Files: {files}\n\n"
        "Based on the project context:\n"
        "1. What works well in this layer? (strongest tests/features)\n"
        "2. What's missing or undertested?\n"
        "3. One concrete improvement that would strengthen this layer.\n"
        "Reference specific functions and test classes."
    ),
    "gordian_trap": (
        "Evaluate whether this resolved Gordian Trap is still holding.\n"
        "Trap: {label}\n"
        "Resolution: {resolution}\n"
        "Lesson: {lesson}\n\n"
        "Based on the project context:\n"
        "1. Has the resolution held? Any signs of recurrence?\n"
        "2. Are there new areas where the same pattern could emerge?\n"
        "3. One preventive action to strengthen the defense."
    ),
    "breakthrough": (
        "Evaluate exploitation depth of this breakthrough.\n"
        "Breakthrough: {label}\n"
        "Built upon by: {built_upon_by}\n\n"
        "Based on the project context:\n"
        "1. Has this insight been fully exploited across all relevant domains?\n"
        "2. Where else could it apply but hasn't been tried?\n"
        "3. One concrete extension that would leverage this insight further."
    ),
    "working_principle": (
        "Stress-test this working principle against recent project experience.\n"
        "Principle: {label}\n"
        "Confirmed: {U} times, Contradicted: {F} times\n\n"
        "Based on the project context:\n"
        "1. Does recent work confirm or challenge this principle?\n"
        "2. What would FALSIFY it? Is that test missing?\n"
        "3. One experiment that would stress-test this principle."
    ),
    "perspective_check": (
        "Assess whether this perspective check is still catching real issues.\n"
        "Check: {label}\n"
        "Triggered: {U} times\n\n"
        "Based on the project context:\n"
        "1. When was this last useful? Is it still relevant?\n"
        "2. What blind spot does it miss?\n"
        "3. Should it be refined, replaced, or extended?"
    ),
    "current_state": (
        "Assess the current project state and identify the highest-value next action.\n"
        "State: {label}\n\n"
        "Based on the project context:\n"
        "1. What is the single most impactful thing to work on next?\n"
        "2. What risk or technical debt is accumulating silently?\n"
        "3. A concrete action item (with file/function references)."
    ),
}


def build_execution_context(bs, nodes, src_id, tgt_id):
    """Build rich context string for an executable transition.

    Includes: project state, architecture summary, recent history,
    and specific context for both source and target nodes.
    """
    state = bs.get("state", {})
    ctx_parts = [
        f"Project: E₀-Framework v{bs.get('project', {}).get('version', '?')}",
        f"Tests: {state.get('test_count', '?')} passed, {state.get('test_failures', 0)} failures",
        f"Latest commit: {state.get('latest_commit', '?')} — {state.get('latest_commit_msg', '?')}",
        "",
        "Architecture layers:",
    ]

    for layer_key, layer in bs.get("architecture", {}).get("layers", {}).items():
        files = ", ".join(layer.get("files", [])[:3])
        ctx_parts.append(f"  {layer_key}: {files}")

    ctx_parts.append("")
    ctx_parts.append("Open threads:")
    for thread in bs.get("active_context", {}).get("open_threads", []):
        ctx_parts.append(f"  - {thread}")

    ctx_parts.append("")
    ctx_parts.append("Gordian Traps (resolved mistakes with lessons):")
    for gt in bs.get("reflexion", {}).get("gordian_traps", []):
        ctx_parts.append(f"  - {gt['id']}: {gt.get('name', '?')} → {gt.get('lesson', '?')[:80]}")

    ctx_parts.append("")
    ctx_parts.append("Breakthroughs:")
    for bt in bs.get("reflexion", {}).get("breakthroughs", []):
        ctx_parts.append(f"  - {bt['id']}: {bt.get('name', '?')} — {bt.get('insight', '?')[:80]}")

    return "\n".join(ctx_parts)


def format_execution_task(nodes, tgt_id):
    """Format the execution task for a target node using its type template."""
    node = nodes.get(tgt_id, {})
    ntype = node.get("type", "current_state")
    template = EXECUTION_TEMPLATES.get(ntype, EXECUTION_TEMPLATES["current_state"])

    # Build format kwargs from node data
    kwargs = {
        "label": node.get("label", tgt_id),
        "files": ", ".join(node.get("files", [])),
        "resolution": node.get("resolution", "n/a"),
        "lesson": node.get("lesson", "n/a"),
        "built_upon_by": ", ".join(node.get("built_upon_by", [])) or "none yet",
        "U": node.get("U", 0),
        "F": node.get("F", 0),
    }
    return template.format(**kwargs)


def execute_bootstrap_transition(bs, nodes, src_id, tgt_id, dry_run=False):
    """Execute a single bootstrap transition via LLM.

    Returns dict with: source, target, task, outcome, result, confidence, actionable.
    """
    task = format_execution_task(nodes, tgt_id)
    context = build_execution_context(bs, nodes, src_id, tgt_id)

    src_node = nodes.get(src_id, {})
    tgt_node = nodes.get(tgt_id, {})

    if dry_run:
        return {
            "source": src_id,
            "target": tgt_id,
            "target_type": tgt_node.get("type", "?"),
            "task_preview": task[:200],
            "outcome": "DRY_RUN",
            "result": f"Would execute: {src_id} → {tgt_id} ({tgt_node.get('type', '?')})",
            "confidence": 0.0,
            "actionable": False,
        }

    try:
        from e0_controller.llm_adapter import (
            E0LLMAdapter,
            LLMConfig,
            openai_call,
        )

        config = LLMConfig(
            model="gpt-4.1-mini",
            temperature=0.2,
            max_tokens=2048,
        )
        adapter = E0LLMAdapter(config, openai_call)

        result = adapter.execute_transition(
            source=f"{src_id} ({src_node.get('label', '?')})",
            target=f"{tgt_id} ({tgt_node.get('label', '?')})",
            task=task,
            scenario_block=context,
        )

        return {
            "source": src_id,
            "target": tgt_id,
            "target_type": tgt_node.get("type", "?"),
            "outcome": result.outcome.name,
            "result": result.result,
            "confidence": result.confidence,
            "actionable": result.outcome == Outcome.SUCCESS and result.confidence >= 0.5,
        }

    except Exception as exc:
        return {
            "source": src_id,
            "target": tgt_id,
            "target_type": tgt_node.get("type", "?"),
            "outcome": "ERROR",
            "result": str(exc)[:200],
            "confidence": 0.0,
            "actionable": False,
        }


def persist_execution_results(results, dry_run=False):
    """Persist execution results to bootstrap.json.

    Results are stored under execution_results with timestamp.
    Only actionable results are persisted (non-actionable = noise).

    Returns number of results persisted.
    """
    actionable = [r for r in results if r.get("actionable")]
    if not actionable or dry_run:
        return len(actionable)

    ls = load_learning_state()

    if "execution_results" not in ls:
        ls["execution_results"] = {
            "_comment": "Concrete outputs from LLM-executed bootstrap transitions.",
            "results": [],
        }

    from datetime import datetime, timezone
    timestamp = datetime.now(timezone.utc).isoformat()

    for r in actionable:
        entry = {
            "source": r["source"],
            "target": r["target"],
            "target_type": r["target_type"],
            "outcome": r["outcome"],
            "result": r["result"][:500],  # Cap length
            "confidence": r["confidence"],
            "executed_at": timestamp,
        }
        ls["execution_results"]["results"].append(entry)

    save_learning_state(ls)

    return len(actionable)


def select_transitions_for_execution(path, nodes, landscape, max_executions=5):
    """Select the most valuable transitions from an exploration path.

    Criteria for execution priority:
    1. Transitions TO open threads (frontier — highest learning value)
    2. Transitions TO architecture layers (concrete assessment)
    3. Cross-type transitions (structural novelty)
    4. Avoid duplicate targets (spread across different nodes)

    Returns list of (source, target) pairs.
    """
    candidates = []
    seen_targets = set()

    for i in range(len(path) - 1):
        src, tgt = path[i], path[i + 1]
        if tgt in seen_targets:
            continue
        tgt_node = nodes.get(tgt, {})
        tgt_type = tgt_node.get("type", "?")
        src_type = nodes.get(src, {}).get("type", "?")

        # Priority scoring
        priority = 0
        if tgt_type == "open_thread":
            priority = 3  # Highest: frontier exploration
        elif tgt_type == "arch_layer":
            priority = 2  # Concrete assessment
        elif tgt_type == "gordian_trap":
            priority = 2  # Defense check
        elif tgt_type == "breakthrough":
            priority = 1  # Exploitation check
        elif src_type != tgt_type:
            priority = 1  # Cross-type novelty

        if priority > 0:
            candidates.append((priority, src, tgt))
            seen_targets.add(tgt)

    # Sort by priority (descending), take top N
    candidates.sort(key=lambda x: -x[0])
    return [(src, tgt) for _, src, tgt in candidates[:max_executions]]


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

    # Phase D.2: Persist structurally meaningful edges to bootstrap.json
    # Filter: only cross-type or frontier-bridging edges survive.
    # This closes the loop: exploration → persist → richer next session.
    candidate_edges = []
    for src, tgt, delta, r0, sub in new_edges_added:
        candidate_edges.append({
            "from": src,
            "to": tgt,
            "delta": round(delta, 3),
            "resistance": round(r0, 3),
            "confidence": 0.5,
            "derivation": f"discovered via {' → '.join(sub)}",
            "discovered_at": "C196",
        })

    persisted = persist_discovered_edges(candidate_edges, nodes, edges)
    print(f"\n  Persisted to bootstrap.json: {len(persisted)} / {len(new_edges_added)} edges")
    print(f"  (Filter: cross-type or frontier-bridging, Δ ≥ 0.15)")
    if persisted:
        for e in persisted:
            print(f"    ✓ {e['from']:8s}→{e['to']:8s}  Δ={e['delta']:.3f}  {e['derivation'][:50]}")

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

    # Phase F: Confidence update — discovered edges learn from usage
    # Edges used in Phase E get confidence updated based on outcome.
    # Unused edges slowly decay. This is Historization for the meta-level.
    print(f"\n  Phase F: Confidence update (discovered edges learn from usage)")
    print(f"  {'─'*60}")

    conf_updates = update_edge_confidence(iter_landscape, nodes, path2)
    if conf_updates:
        used = sum(1 for k in conf_updates if k in {(path2[i], path2[i+1]) for i in range(len(path2)-1)})
        decayed = len(conf_updates) - used
        print(f"    Updated: {used} used edges, {decayed} decayed (unused)")
        for (src, tgt), new_conf in sorted(conf_updates.items(), key=lambda x: -x[1]):
            marker = "↑" if new_conf > 0.5 else ("↓" if new_conf < 0.48 else "→")
            print(f"    {marker} {src:8s}→{tgt:8s}  confidence={new_conf:.3f}")
    else:
        print(f"    No updates (no discovered edges to track)")

    # Phase G: LLM semantic validation — E₀=Skeleton, LLM=Muscle
    # E₀ proposed the edges (structural). LLM judges meaning (semantic).
    # Only runs when --llm flag is present (API costs).
    if "--llm" in sys.argv:
        print(f"\n  Phase G: LLM semantic validation")
        print(f"  {'─'*60}")
        print(f"  E₀ proposed {len(disc if 'disc' in dir() else [])} edges structurally.")
        print(f"  LLM evaluates: 'Is there a real conceptual connection?'")

        results = llm_semantic_validation(nodes)
        if results:
            for r in results:
                idx = r.get("edge", 0) - 1
                score = r.get("score", 0)
                reason = r.get("reason", "")[:60]
                marker = "✓" if score >= 0.6 else ("~" if score >= 0.3 else "✗")
                print(f"    {marker} Edge {r['edge']:2d}: score={score:.1f}  {reason}")
            # Summary
            scores = [r.get("score", 0) for r in results]
            good = sum(1 for s in scores if s >= 0.6)
            weak = sum(1 for s in scores if 0.3 <= s < 0.6)
            bad = sum(1 for s in scores if s < 0.3)
            avg = sum(scores) / len(scores) if scores else 0
            print(f"\n    Summary: {good} strong + {weak} weak + {bad} artifact = {len(scores)} total")
            print(f"    Mean semantic score: {avg:.2f}")
        else:
            print(f"    LLM validation returned no results.")
    elif "--llm-dry" in sys.argv:
        print(f"\n  Phase G: LLM semantic validation (DRY RUN)")
        print(f"  {'─'*60}")
        results = llm_semantic_validation(nodes, dry_run=True)
        print(f"    Would validate {len(results)} edges (skipped — dry run)")
    else:
        print(f"\n  Phase G: Skipped (use --llm to enable LLM semantic validation)")

    # Phase H: Executable transitions — navigation PRODUCES output
    # Each visited node is a potential execution target.
    # The LLM performs the work implied by each transition and returns
    # concrete, actionable output. U/F comes from actionability.
    combined_path = path + path2
    if "--llm" in sys.argv:
        print(f"\n  Phase H: Executable transitions — navigation produces output")
        print(f"  {'─'*60}")
        print(f"  Selecting highest-value transitions from exploration path...")

        selected = select_transitions_for_execution(combined_path, nodes, iter_landscape)
        print(f"  Selected {len(selected)} transitions for execution:")
        for src, tgt in selected:
            ttype = nodes.get(tgt, {}).get("type", "?")
            tlabel = nodes.get(tgt, {}).get("label", "?")[:45]
            print(f"    {src:8s} → {tgt:8s}  [{ttype:20s}]  {tlabel}")

        print(f"\n  Executing via LLM...")
        bs_fresh = load_bootstrap()
        exec_results = []
        for src, tgt in selected:
            r = execute_bootstrap_transition(bs_fresh, nodes, src, tgt)
            exec_results.append(r)
            marker = "✓" if r["actionable"] else "~" if r["outcome"] == "SUCCESS" else "✗"
            print(f"\n    {marker} {src} → {tgt} ({r['target_type']})")
            print(f"      Outcome: {r['outcome']}, Confidence: {r['confidence']:.2f}")
            # Print result, indented and truncated
            result_lines = r["result"][:400].split("\n")
            for line in result_lines:
                print(f"      {line}")

            # Historize: actionable = SUCCESS, not actionable = FAILURE
            from e0_controller.landscape import Edge as _Edge
            edge = _Edge(src, tgt)
            if iter_landscape.has_edge(src, tgt):
                outcome = Outcome.SUCCESS if r["actionable"] else Outcome.FAILURE
                iter_landscape.historization.update(edge, outcome)

        # Persist actionable results
        persisted_count = persist_execution_results(exec_results)
        actionable_count = sum(1 for r in exec_results if r["actionable"])
        print(f"\n  {'─'*60}")
        print(f"  Execution summary:")
        print(f"    Executed:   {len(exec_results)} transitions")
        print(f"    Actionable: {actionable_count}")
        print(f"    Persisted:  {persisted_count} results to bootstrap.json")

    elif "--llm-dry" in sys.argv:
        print(f"\n  Phase H: Executable transitions (DRY RUN)")
        print(f"  {'─'*60}")
        selected = select_transitions_for_execution(combined_path, nodes, iter_landscape)
        print(f"  Would execute {len(selected)} transitions:")
        bs_fresh = load_bootstrap()
        for src, tgt in selected:
            r = execute_bootstrap_transition(bs_fresh, nodes, src, tgt, dry_run=True)
            ttype = nodes.get(tgt, {}).get("type", "?")
            print(f"    {src:8s} → {tgt:8s}  [{ttype:20s}]")
            print(f"      Task: {r['task_preview'][:120]}...")
    else:
        print(f"\n  Phase H: Skipped (use --llm to enable executable transitions)")


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
    inject_edge_metadata(landscape, edges)

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
