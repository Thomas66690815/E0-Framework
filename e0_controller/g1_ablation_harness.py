"""Development-only compatibility harness for the five E0 ablations (WP-2.3).

The default command exercises one environment interaction for every selected
method/domain pair.  This is a bounded adapter and causal-contract check, not a
performance experiment.  WP-2.4 owns full 30-episode development raw data and
the preregistered simpler-control selection.

Example:

    py -3 -m e0_controller.g1_ablation_harness
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from .g1_ablations import (
    ABLATION_METHODS,
    CONFIG_PATH,
    INFORMATION_ACCESS,
    ablation_config_sha256,
    load_ablation_configs,
    run_ablation_replicate,
    validate_ablation_contract,
)
from .g1_domains import (
    GENERATOR_VERSION,
    PROTOCOL_ID,
    build_development_matrix,
    development_seeds,
    load_g1_protocol,
    protocol_sha256,
    validate_development_seed,
)
from .g1_harness import environment_record

DEFAULT_OUTPUT = Path("artifacts/g1/E0-G1-v1/development/wp2_3")
ARTIFACT_FILES = (
    "frozen_configs.json",
    "ablation_compatibility.jsonl",
    "environment.json",
    "manifest.json",
)


def _json_bytes(data: Any, *, indent: Optional[int] = 2) -> bytes:
    text = json.dumps(data, ensure_ascii=False, sort_keys=True, indent=indent)
    return (text + "\n").encode("utf-8")


def _write_atomic(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_bytes(content)
    os.replace(temporary, path)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _git_value(*args: str) -> Optional[str]:
    try:
        result = subprocess.run(
            ["git", *args],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return result.stdout.strip()


def _ensure_output_available(output_dir: Path, overwrite: bool) -> None:
    existing = [name for name in ARTIFACT_FILES if (output_dir / name).exists()]
    if existing and not overwrite:
        raise FileExistsError(
            f"{output_dir} already contains {existing}; pass --overwrite "
            "to replace only these WP-2.3 files"
        )


def run_ablation_compatibility(
    output_dir: Path,
    *,
    families: Optional[Sequence[str]] = None,
    scales: Optional[Sequence[int]] = None,
    seeds: Optional[Sequence[int]] = None,
    methods: Optional[Sequence[str]] = None,
    episode_count: int = 1,
    interaction_budget: int = 1,
    overwrite: bool = False,
) -> Dict[str, Any]:
    """Exercise the selected development matrix and write audit artifacts."""
    protocol = load_g1_protocol()
    validate_ablation_contract()
    config = load_ablation_configs()
    selected_seeds = list(seeds if seeds is not None else development_seeds())
    for seed in selected_seeds:
        validate_development_seed(int(seed))
    selected_methods = list(methods or ABLATION_METHODS)
    unknown = sorted(set(selected_methods) - set(ABLATION_METHODS))
    if unknown:
        raise ValueError(f"Unknown E0 ablations: {unknown}")
    total_episodes = int(protocol["interaction_protocol"]["adaptation_episodes"]) + int(
        protocol["interaction_protocol"]["evaluation_episodes"]
    )
    if episode_count <= 0 or episode_count > total_episodes:
        raise ValueError(f"episode_count must lie in 1..{total_episodes}")
    if interaction_budget <= 0:
        raise ValueError("interaction_budget must be positive")

    output_dir = Path(output_dir)
    _ensure_output_available(output_dir, overwrite)
    source_dirty = _git_value("status", "--porcelain", "--untracked-files=all")
    domains = list(
        build_development_matrix(
            families=families,
            scales=scales,
            seeds=selected_seeds,
        )
    )
    records: List[Dict[str, Any]] = []
    for domain in domains:
        for method in selected_methods:
            result = run_ablation_replicate(
                domain,
                method,
                episode_count=episode_count,
                interaction_budget=interaction_budget,
            )
            records.append(
                {
                    "protocol_id": PROTOCOL_ID,
                    "artifact_kind": "development_ablation_compatibility",
                    "not_g1_result": True,
                    "holdout_accessed": False,
                    "split": "development",
                    "method": method,
                    "information_access": INFORMATION_ACCESS,
                    "domain_family": domain.family,
                    "target_node_count": domain.target_node_count,
                    "actual_node_count": domain.actual_node_count,
                    "generator_seed": domain.generator_seed,
                    "outcome_seed": domain.outcome_seed,
                    "policy_seed": domain.policy_seed,
                    "episode_count": len(result.episodes),
                    "interaction_budget_per_episode": interaction_budget,
                    "full_protocol_budget": (interaction_budget == 4 * domain.actual_node_count),
                    "adapter_status": (
                        "completed"
                        if all(episode.status == "completed" for episode in result.episodes)
                        else "valid_negative"
                    ),
                    "interactions_used": sum(
                        episode.summary.interactions_used for episode in result.episodes
                    ),
                    "paths_expanded": sum(episode.paths_expanded for episode in result.episodes),
                    "path_cap_hits": sum(episode.path_cap_hits for episode in result.episodes),
                }
            )
    expected = len(domains) * len(selected_methods)
    if len(records) != expected:
        raise RuntimeError(f"Compatibility matrix incomplete: {len(records)} != {expected}")

    configs_path = output_dir / "frozen_configs.json"
    records_path = output_dir / "ablation_compatibility.jsonl"
    environment_path = output_dir / "environment.json"
    manifest_path = output_dir / "manifest.json"
    _write_atomic(configs_path, CONFIG_PATH.read_bytes())
    _write_atomic(
        records_path,
        b"".join(_json_bytes(record, indent=None) for record in records),
    )
    _write_atomic(environment_path, _json_bytes(environment_record()))
    manifest = {
        "protocol_id": PROTOCOL_ID,
        "protocol_sha256": protocol_sha256(),
        "generator_version": GENERATOR_VERSION,
        "ablation_config_version": config["config_version"],
        "ablation_config_sha256": ablation_config_sha256(),
        "artifact_kind": "development_ablation_compatibility_manifest",
        "not_g1_result": True,
        "holdout_accessed": False,
        "holdout_execution_started": protocol["holdout_execution_started"],
        "split": "development",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_commit": _git_value("rev-parse", "HEAD"),
        "source_dirty": bool(source_dirty),
        "selection": {
            "families": sorted({domain.family for domain in domains}),
            "scales": sorted({domain.target_node_count for domain in domains}),
            "generator_seeds": sorted({domain.generator_seed for domain in domains}),
            "methods": selected_methods,
            "episodes_per_adapter": episode_count,
            "interaction_budget_per_episode": interaction_budget,
        },
        "counts": {
            "domain_instances": len(domains),
            "methods": len(selected_methods),
            "planned_adapter_runs": expected,
            "completed_adapter_runs": len(records),
            "path_cap_hits": sum(record["path_cap_hits"] for record in records),
        },
        "files": {
            "frozen_configs.json": {"sha256": _sha256(configs_path)},
            "ablation_compatibility.jsonl": {
                "sha256": _sha256(records_path),
                "records": len(records),
            },
            "environment.json": {"sha256": _sha256(environment_path)},
        },
        "scope_note": (
            "One-interaction compatibility by default. No performance comparison, "
            "control selection, full protocol result, holdout access, or Gate G1 finding."
        ),
        "next_work_package": (
            "WP-2.4 full development raw-data execution, report, and preregistered "
            "simpler-control selection"
        ),
    }
    _write_atomic(manifest_path, _json_bytes(manifest))
    return manifest


def _parse_int_selection(value: str) -> List[int]:
    values: List[int] = []
    for part in value.split(","):
        token = part.strip()
        if not token:
            continue
        if "-" in token:
            start_text, stop_text = token.split("-", 1)
            start, stop = int(start_text), int(stop_text)
            if stop < start:
                raise argparse.ArgumentTypeError(f"Invalid range {token!r}")
            values.extend(range(start, stop + 1))
        else:
            values.append(int(token))
    if not values:
        raise argparse.ArgumentTypeError("Selection must not be empty")
    return values


def _parse_text_selection(value: str) -> List[str]:
    values = [item.strip() for item in value.split(",") if item.strip()]
    if not values:
        raise argparse.ArgumentTypeError("Selection must not be empty")
    return values


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Exercise E0-G1-v1 ablation adapters on development domains. "
            "This WP-2.3 command cannot access holdout seeds or produce G1 results."
        )
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--seeds",
        type=_parse_int_selection,
        default=list(development_seeds()),
        help="Development seeds, e.g. 0-9 or 0,3,7 (default: 0-9)",
    )
    parser.add_argument(
        "--scales",
        type=_parse_int_selection,
        default=None,
        help="Subset of preregistered scales, e.g. 100,500",
    )
    parser.add_argument(
        "--families",
        type=_parse_text_selection,
        default=None,
        help="Comma-separated subset of preregistered family IDs",
    )
    parser.add_argument(
        "--methods",
        type=_parse_text_selection,
        default=None,
        help="Comma-separated subset of preregistered ablation IDs",
    )
    parser.add_argument(
        "--episodes",
        type=int,
        default=1,
        help="Episodes per adapter compatibility run (default: 1; max: 30)",
    )
    parser.add_argument(
        "--interactions",
        type=int,
        default=1,
        help="Interactions per compatibility episode (default: 1; WP-2.4 uses 4*N)",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Replace only the four known WP-2.3 artifact files",
    )
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        manifest = run_ablation_compatibility(
            args.output,
            families=args.families,
            scales=args.scales,
            seeds=args.seeds,
            methods=args.methods,
            episode_count=args.episodes,
            interaction_budget=args.interactions,
            overwrite=args.overwrite,
        )
    except (FileExistsError, ValueError, RuntimeError) as error:
        print(f"ERROR: {error}", file=os.sys.stderr)
        return 2
    print(
        json.dumps(
            {
                "status": "PASS",
                "protocol_id": manifest["protocol_id"],
                "artifact_kind": manifest["artifact_kind"],
                "not_g1_result": manifest["not_g1_result"],
                "holdout_accessed": manifest["holdout_accessed"],
                "completed_adapter_runs": manifest["counts"]["completed_adapter_runs"],
                "path_cap_hits": manifest["counts"]["path_cap_hits"],
                "output": str(args.output),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
