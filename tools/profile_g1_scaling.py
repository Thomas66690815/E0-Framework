"""Profile the development-only Gate G1 ablation decision path.

This engineering tool accepts development seeds only.  It times the shared
field construction and path enumeration separately from the phase-dependent
aggregation used by D_U1_PHASE and E_FULL_GEOMETRY.
"""

from __future__ import annotations

import argparse
import json
import time
from typing import Any, Callable, Dict, Sequence

from e0_controller.g1_ablations import (
    LOOKAHEAD_METHODS,
    _manual_scores,
    _nav_field,
    _path_family,
    build_ablation_adapter,
)
from e0_controller.g1_baselines import _local_actions
from e0_controller.g1_domains import build_domain, validate_development_seed
from lean.structural_geometry import influence_map, phase_regime


def _timed(call: Callable[[], Any]) -> tuple[Any, float]:
    started = time.perf_counter()
    value = call()
    return value, (time.perf_counter() - started) * 1000.0


def profile_decision(family: str, scale: int, seed: int, method: str) -> Dict[str, Any]:
    """Return one cold-decision timing breakdown."""
    validate_development_seed(seed)
    if method not in LOOKAHEAD_METHODS:
        raise ValueError(f"method must be one of {LOOKAHEAD_METHODS}")

    domain, domain_ms = _timed(lambda: build_domain(family, scale, seed))
    adapter, adapter_ms = _timed(lambda: build_ablation_adapter(method, domain))
    actions = _local_actions(domain, domain.start)
    greedy = adapter._greedy(domain.start, actions)
    candidates = tuple(sorted(action.target for action in actions))

    field, field_ms = _timed(lambda: _nav_field(adapter.landscape))
    paths, paths_ms = _timed(
        lambda: _path_family(field, domain.start, candidates, adapter.shared)
    )

    if method == "E_FULL_GEOMETRY":
        _, aggregation_ms = _timed(
            lambda: influence_map(
                field,
                domain.start,
                horizon=int(adapter.shared["path_horizon"]),
                geometry=str(adapter.shared["path_geometry"]),
                candidates=candidates,
                max_paths=int(adapter.shared["max_paths_per_decision"]),
                keep_paths=True,
            )
        )
    else:
        _, aggregation_ms = _timed(lambda: _manual_scores(method, field, paths))

    if method in ("D_U1_PHASE", "E_FULL_GEOMETRY"):
        _, warm_phase_regime_ms = _timed(
            lambda: phase_regime(
                field,
                horizon=int(adapter.shared["path_horizon"]),
            )
        )
        cold_field = _nav_field(adapter.landscape)
        _, cold_phase_regime_ms = _timed(
            lambda: phase_regime(
                cold_field,
                horizon=int(adapter.shared["path_horizon"]),
            )
        )
    else:
        warm_phase_regime_ms = 0.0
        cold_phase_regime_ms = 0.0

    _, full_decision_ms = _timed(
        lambda: adapter._lookahead_record(domain.start, actions, greedy)
    )

    return {
        "family": family,
        "scale": scale,
        "actual_nodes": domain.actual_node_count,
        "edges": domain.landscape.edge_count(),
        "seed": seed,
        "method": method,
        "candidate_count": len(candidates),
        "paths_expanded": paths.paths_expanded,
        "path_cap_hit": paths.truncated,
        "timings_ms": {
            "domain_build": domain_ms,
            "adapter_build": adapter_ms,
            "nav_field_build": field_ms,
            "path_family": paths_ms,
            "aggregation_on_warm_field": aggregation_ms,
            "phase_regime_on_warm_field": warm_phase_regime_ms,
            "phase_regime_on_cold_field": cold_phase_regime_ms,
            "full_cold_decision": full_decision_ms,
        },
    }


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--family",
        choices=(
            "decoy_dag",
            "nonstationary_parallel",
            "trap_grid_v2",
            "wall_grid",
        ),
        default="wall_grid",
    )
    parser.add_argument("--scale", type=int, choices=(100, 500, 1000), default=100)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--method", choices=LOOKAHEAD_METHODS, default="D_U1_PHASE")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    result = profile_decision(args.family, args.scale, args.seed, args.method)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
