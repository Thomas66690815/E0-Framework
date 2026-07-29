"""Development-only Gate G1 domain harness (WP-2.1).

Example:

    py -3 -m e0_controller.g1_harness

The command writes generator-validation artifacts below
``artifacts/g1/E0-G1-v1/development/wp2_1``.  They are not method results and
must not be interpreted as a Gate G1 outcome.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from .g1_domains import (
    GENERATOR_VERSION,
    PROTOCOL_ID,
    build_development_matrix,
    development_seeds,
    load_g1_protocol,
    protocol_sha256,
    validate_development_seed,
)

DEFAULT_OUTPUT = Path("artifacts/g1/E0-G1-v1/development/wp2_1")
ARTIFACT_FILES = ("domain_instances.jsonl", "environment.json", "manifest.json")


def _json_bytes(data: Any, *, indent: Optional[int] = 2) -> bytes:
    text = json.dumps(
        data,
        ensure_ascii=False,
        sort_keys=True,
        indent=indent,
    )
    return (text + "\n").encode("utf-8")


def _write_atomic(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_bytes(content)
    os.replace(temporary, path)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


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


def _package_version(name: str) -> Optional[str]:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return None


def environment_record() -> Dict[str, Any]:
    """Capture the execution environment without secrets or local paths."""
    return {
        "protocol_id": PROTOCOL_ID,
        "artifact_kind": "development_environment",
        "not_g1_result": True,
        "python_version": platform.python_version(),
        "python_implementation": platform.python_implementation(),
        "platform": platform.platform(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "packages": {
            "numpy": _package_version("numpy"),
            "pytest": _package_version("pytest"),
            "scipy": _package_version("scipy"),
        },
    }


def _ensure_output_available(output_dir: Path, overwrite: bool) -> None:
    existing = [name for name in ARTIFACT_FILES if (output_dir / name).exists()]
    if existing and not overwrite:
        raise FileExistsError(
            f"{output_dir} already contains {existing}; pass --overwrite "
            "to replace only these WP-2.1 files"
        )


def run_development_inventory(
    output_dir: Path,
    *,
    families: Optional[Sequence[str]] = None,
    scales: Optional[Sequence[int]] = None,
    seeds: Optional[Sequence[int]] = None,
    overwrite: bool = False,
) -> Dict[str, Any]:
    """Generate, validate, and record a development-only domain matrix."""
    protocol = load_g1_protocol()
    selected_seeds = list(seeds if seeds is not None else development_seeds())
    for seed in selected_seeds:
        validate_development_seed(int(seed))

    output_dir = Path(output_dir)
    _ensure_output_available(output_dir, overwrite)
    generated_at = datetime.now(timezone.utc).isoformat()
    commit = _git_value("rev-parse", "HEAD")
    dirty_output = _git_value("status", "--porcelain", "--untracked-files=all")

    records = [
        domain.to_record()
        for domain in build_development_matrix(
            families=families,
            scales=scales,
            seeds=selected_seeds,
        )
    ]
    if not records:
        raise ValueError("The requested development matrix is empty")
    if not all(record["invariant_pass"] for record in records):
        failed = [record["run_id"] for record in records if not record["invariant_pass"]]
        raise RuntimeError(f"Domain invariant failure: {failed}")

    jsonl = b"".join(_json_bytes(record, indent=None) for record in records)
    instances_path = output_dir / "domain_instances.jsonl"
    environment_path = output_dir / "environment.json"
    manifest_path = output_dir / "manifest.json"
    _write_atomic(instances_path, jsonl)
    _write_atomic(environment_path, _json_bytes(environment_record()))

    manifest = {
        "protocol_id": PROTOCOL_ID,
        "protocol_sha256": protocol_sha256(),
        "generator_version": GENERATOR_VERSION,
        "artifact_kind": "development_domain_validation_manifest",
        "not_g1_result": True,
        "holdout_accessed": False,
        "holdout_execution_started": protocol["holdout_execution_started"],
        "split": "development",
        "generated_at_utc": generated_at,
        "source_commit": commit,
        "source_dirty": bool(dirty_output),
        "selection": {
            "families": sorted({record["domain_family"] for record in records}),
            "scales": sorted({record["target_node_count"] for record in records}),
            "generator_seeds": sorted({record["generator_seed"] for record in records}),
        },
        "counts": {
            "domain_instances": len(records),
            "invariant_pass": sum(1 for record in records if record["invariant_pass"]),
            "invariant_fail": sum(1 for record in records if not record["invariant_pass"]),
        },
        "files": {
            "domain_instances.jsonl": {
                "sha256": _sha256(instances_path),
                "records": len(records),
            },
            "environment.json": {
                "sha256": _sha256(environment_path),
            },
        },
        "next_work_packages": [
            "WP-2.2 method adapters and fair baseline training",
            "WP-2.3 five-level E0 ablation adapters",
        ],
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
            "Generate and validate E0-G1-v1 development domains. "
            "This WP-2.1 command cannot access holdout seeds or produce G1 results."
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
        "--overwrite",
        action="store_true",
        help="Replace only the three known WP-2.1 artifact files",
    )
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        manifest = run_development_inventory(
            args.output,
            families=args.families,
            scales=args.scales,
            seeds=args.seeds,
            overwrite=args.overwrite,
        )
    except (FileExistsError, ValueError, RuntimeError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2
    print(
        json.dumps(
            {
                "status": "PASS",
                "protocol_id": manifest["protocol_id"],
                "artifact_kind": manifest["artifact_kind"],
                "not_g1_result": manifest["not_g1_result"],
                "holdout_accessed": manifest["holdout_accessed"],
                "domain_instances": manifest["counts"]["domain_instances"],
                "output": str(args.output),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
