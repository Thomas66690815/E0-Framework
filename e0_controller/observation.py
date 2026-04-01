"""
E₀ Observation Landscape (C94)
================================
Visualization as a domain.

Canon basis:
  "Domain specificity enters only through embedding, not through
   mechanism." (AGI Blueprint §7)

  "A state is a distinguishable configuration." (Canon §2.1)

An Observation Landscape (O-Landscape) treats information about a
running E₀ system as a navigable state space:

  States = what the observer can currently distinguish
  Edges  = admissible transitions between observation configurations
  Δ      = magnitude of information change
  R₀     = cognitive resistance (cost of comprehension)

The O-Landscape is built FROM a domain Landscape.  The same E0Controller
that navigates Gordian Knots navigates the observation space.

Historization works identically: repeated observation of a pattern
lowers resistance for related transitions (the observer learns).

State encoding: "{scope}:{depth}"

  scope ∈ { "g", "n:<node_id>" }
    g        = global view (all nodes/edges)
    n:<id>   = local view (node and its neighborhood)

  depth ∈ { "topo", "field", "dyn", "mech", "intf" }
    topo     = topology only (nodes/edges exist, no values)
    field    = scalar field projected (S_eff, q, m, ...)
    dyn      = dynamics visible (position, trajectory, historization)
    mech     = mechanism visible (greedy vs override, escalation)
    intf     = interference visible (amplitude overlay, constructive/destructive)

Depth is monotone — each level includes the previous.

Edge rules:
  1. Within same scope, adjacent depths are connected (depth progression)
  2. Retreat to shallower depth is always cheap
  3. At same depth, global↔local transitions exist
  4. At same depth, local↔local transitions exist (between domain neighbors)
  5. Cross-transitions (scope + depth simultaneously) are inadmissible
     Canon §9: "bypasses local resistance via purely global optimization"
"""

from __future__ import annotations

from typing import List, Optional, Set, Tuple

from .landscape import Landscape
from .primitives import Edge


# ── Depth levels, ordered by information density ─────────

DEPTHS = ("topo", "field", "dyn", "mech", "intf")
DEPTH_INDEX = {d: i for i, d in enumerate(DEPTHS)}


# ── Parameters: Δ and R₀ for each transition type ───────

# Depth-forward transitions (deeper = more information, harder)
DEPTH_FORWARD = {
    ("topo", "field"): (0.3, 0.3),   # add color/values — easy
    ("field", "dyn"):  (0.4, 0.5),   # add motion/history — moderate
    ("dyn", "mech"):   (0.6, 0.8),   # add causal logic — harder
    ("mech", "intf"):  (0.8, 1.2),   # add amplitude interpretation — hardest
}

# Depth-retreat transitions (return to shallower — always cheap)
DEPTH_RETREAT_DELTA = 0.1
DEPTH_RETREAT_R0 = 0.1

# Scope transitions (same depth)
SCOPE_FOCUS_DELTA = 0.2       # global → local: narrow focus
SCOPE_FOCUS_R0 = 0.2
SCOPE_DEFOCUS_DELTA = 0.3     # local → global: widen view
SCOPE_DEFOCUS_R0 = 0.3
SCOPE_MOVE_DELTA = 0.2        # local → local (neighbor)
SCOPE_MOVE_R0 = 0.3           # R₀ for moving between adjacent nodes


# ── State encoding / decoding ────────────────────────────

def encode_state(scope: str, depth: str) -> str:
    """Encode an observation state as a landscape state-ID."""
    return f"{scope}:{depth}"


def decode_state(state_id: str) -> Tuple[str, str]:
    """Decode scope and depth from a state-ID.

    Returns (scope, depth).
    """
    idx = state_id.rfind(":")
    if idx < 0:
        raise ValueError(f"Invalid observation state: {state_id!r}")
    return state_id[:idx], state_id[idx + 1:]


def is_global(state_id: str) -> bool:
    """True if state has global scope."""
    scope, _ = decode_state(state_id)
    return scope == "g"


def is_local(state_id: str) -> bool:
    """True if state has node-local scope."""
    scope, _ = decode_state(state_id)
    return scope.startswith("n:")


def local_node(state_id: str) -> Optional[str]:
    """Return the domain node for a local state, or None if global."""
    scope, _ = decode_state(state_id)
    if scope.startswith("n:"):
        return scope[2:]
    return None


def depth_of(state_id: str) -> str:
    """Return the depth level of a state."""
    _, depth = decode_state(state_id)
    return depth


# ── Domain graph neighbor extraction ─────────────────────

def _domain_neighbors(domain: Landscape, node: str) -> Set[str]:
    """Outgoing neighbors in the domain graph (directed)."""
    neighbors = set()
    for edge in domain._delta:
        if edge.source == node:
            neighbors.add(edge.target)
    return neighbors


# ── O-Landscape Builder ──────────────────────────────────

def build_observation_landscape(
    domain: Landscape,
    *,
    depths: Optional[List[str]] = None,
) -> Landscape:
    """Build an O-Landscape from a domain Landscape.

    Parameters
    ----------
    domain : Landscape
        The domain landscape being observed.
    depths : list of str, optional
        Which depth levels to include.
        Default: all five ("topo", "field", "dyn", "mech", "intf").

    Returns
    -------
    Landscape
        The observation landscape, navigable by E0Controller.
    """
    d_list = list(depths) if depths else list(DEPTHS)
    for d in d_list:
        if d not in DEPTH_INDEX:
            raise ValueError(f"Unknown depth: {d!r}")

    o = Landscape()
    domain_nodes = sorted(domain._states)

    # Scopes: global + one per domain node
    scopes = ["g"] + [f"n:{n}" for n in domain_nodes]

    # ── 1. Register all states ───────────────────────────
    for scope in scopes:
        for depth in d_list:
            o.add_state(encode_state(scope, depth))

    # ── 2. Depth transitions (within same scope) ────────
    for scope in scopes:
        for i in range(len(d_list) - 1):
            d_from, d_to = d_list[i], d_list[i + 1]
            fwd_key = (d_from, d_to)
            if fwd_key in DEPTH_FORWARD:
                delta, r0 = DEPTH_FORWARD[fwd_key]
                # Forward: go deeper
                o.add_edge(
                    encode_state(scope, d_from),
                    encode_state(scope, d_to),
                    delta=delta, resistance=r0,
                )
                # Retreat: return to shallower
                o.add_edge(
                    encode_state(scope, d_to),
                    encode_state(scope, d_from),
                    delta=DEPTH_RETREAT_DELTA,
                    resistance=DEPTH_RETREAT_R0,
                )

    # ── 3. Scope transitions (at same depth) ────────────
    for depth in d_list:
        # global ↔ local(n) for each domain node
        for node in domain_nodes:
            local_scope = f"n:{node}"
            o.add_edge(
                encode_state("g", depth),
                encode_state(local_scope, depth),
                delta=SCOPE_FOCUS_DELTA,
                resistance=SCOPE_FOCUS_R0,
            )
            o.add_edge(
                encode_state(local_scope, depth),
                encode_state("g", depth),
                delta=SCOPE_DEFOCUS_DELTA,
                resistance=SCOPE_DEFOCUS_R0,
            )

        # local(n) → local(m) for domain-graph neighbors
        for node in domain_nodes:
            for nb in _domain_neighbors(domain, node):
                o.add_edge(
                    encode_state(f"n:{node}", depth),
                    encode_state(f"n:{nb}", depth),
                    delta=SCOPE_MOVE_DELTA,
                    resistance=SCOPE_MOVE_R0,
                )

    return o


# ── O-Landscape Metrics ──────────────────────────────────

def observation_states(o_landscape: Landscape) -> List[str]:
    """Return all observation states, sorted."""
    return sorted(o_landscape._states)


def observation_edges(o_landscape: Landscape) -> List[Edge]:
    """Return all observation edges."""
    return list(o_landscape._delta.keys())


def info_at(state_id: str) -> dict:
    """Describe what information is available at a given observation state.

    Returns a dict with scope, depth, depth_index, and a human-readable
    description of what the observer can distinguish.
    """
    scope, depth = decode_state(state_id)
    d_idx = DEPTH_INDEX.get(depth, -1)

    descriptions = {
        "topo": "Nodes and edges exist. No values.",
        "field": "Scalar field projected (S_eff, q, m, ...).",
        "dyn": "Position, trajectory, and historization visible.",
        "mech": "Decision mechanism visible (greedy vs override, escalation).",
        "intf": "Amplitude overlay: constructive/destructive interference.",
    }

    if scope == "g":
        scope_desc = "Global — all nodes and edges"
    elif scope.startswith("n:"):
        node = scope[2:]
        scope_desc = f"Local — node {node} and its neighborhood"
    else:
        scope_desc = f"Unknown scope: {scope}"

    return {
        "state": state_id,
        "scope": scope,
        "depth": depth,
        "depth_index": d_idx,
        "scope_desc": scope_desc,
        "depth_desc": descriptions.get(depth, "Unknown depth"),
    }
