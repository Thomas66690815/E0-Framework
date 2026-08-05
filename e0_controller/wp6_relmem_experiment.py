"""
WP-6.2 — Execution harness for `E0-WP6-RELMEM-v1`.

Implements the frozen preregistration
`docs/E0_WP6_RELIABILITY_MEMORY_PREREGISTRATION_v1.md` exactly:

- 3 regimes (R1 persistent structure, R2 drift at call 500, R3 context
  dependence with 3 task types) x 30 paired generator seeds x 4 arms
  (MEMORY, NO_MEMORY, STICKY, ORACLE);
- tasks of 5 steps, k=4 redundant tools per step, 1,000 tool calls per
  replicate;
- MEMORY runs `lean/reliability_memory.ReliabilityStore` with shipped
  defaults and a context-free state key (step-type only, also in R3);
- paired bootstrap (10,000 resamples, seed 20260805) and the frozen
  PASS/FAIL criteria.

Implementation details fixed here (within the frozen design): five shared
step-types `step_0..step_4`; task type in R3 cycles deterministically as
`task_index % 3`; string-based `random.Random` seeding (stable across
CPython runs); R2 pre-drift level for the recovery metric is the success
rate over calls 451-500, recovery is the first call t >= 500 whose trailing
50-call success rate reaches 90% of that level.

The object under test is bound by SHA-256 in `OBJECT_UNDER_TEST_SHA256`;
`verify_object_under_test()` fails closed if the lean package was modified.

CLI:
    py -3 -m e0_controller.wp6_relmem_experiment run --output DIR --execution-commit HASH
"""
from __future__ import annotations

import argparse
import hashlib
import json
import random
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

_REPO_ROOT = Path(__file__).resolve().parent.parent
_LEAN_DIR = _REPO_ROOT / "lean"
if str(_LEAN_DIR) not in sys.path:
    sys.path.insert(0, str(_LEAN_DIR))

from reliability_memory import ReliabilityStore  # noqa: E402

# ── frozen protocol constants (E0-WP6-RELMEM-v1) ──────────────────────────────

PROTOCOL_ID = "E0-WP6-RELMEM-v1"
REGIMES = ("R1_persistent", "R2_drift", "R3_context")
ARMS = ("MEMORY", "NO_MEMORY", "STICKY", "ORACLE")
RELIABILITY_LEVELS = (0.95, 0.6, 0.25, 0.05)
K_TOOLS = 4
STEPS_PER_TASK = 5
CALL_BUDGET = 1000
DRIFT_AT_CALL = 500
TASK_TYPES = 3
GENERATOR_SEEDS = tuple(range(30))
ENV_SEED_BASE = 400000
AGENT_SEED_BASE = 500000
BOOTSTRAP_SEED = 20260805
BOOTSTRAP_RESAMPLES = 10000
WASTED_RELIABILITY_THRESHOLD = 0.25
RECOVERY_WINDOW = 50
RECOVERY_FACTOR = 0.9
R1_MIN_RELATIVE_LIFT_VS_NO_MEMORY = 0.10
STICKY_DOC_NOTE_LIFT = 0.05
NON_INFERIORITY_FRACTION = 0.05
HARD_HARM_FRACTION = 0.20

TOOLS = tuple(f"tool_{i}" for i in range(K_TOOLS))
STEP_TYPES = tuple(f"step_{i}" for i in range(STEPS_PER_TASK))

OBJECT_UNDER_TEST_SHA256 = {
    "store.py": "d054493bdaa02a540452f5bc3ae0ea615032491488ac22b3d89e4e47f7469be8",
    "traces.py": "7a32b4754861fc802bfd740359032b087cb1bbb05ab33b0949ebd0ffb351888a",
    "primitives.py": "a9fc89095947c80e12f2500298921f3c1f859a2fda9e39c7b643d74da81bf035",
}


def verify_object_under_test() -> None:
    """Fail closed if lean/reliability_memory was modified after the freeze."""
    for name, expected in OBJECT_UNDER_TEST_SHA256.items():
        path = _LEAN_DIR / "reliability_memory" / name
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest != expected:
            raise RuntimeError(
                f"object under test modified: {name} has {digest}, "
                f"frozen protocol requires {expected} (needs protocol v2)"
            )


# ── environment ───────────────────────────────────────────────────────────────

def _draw_table(rng: random.Random, regime: str) -> Dict[Tuple[int, str, str], float]:
    """Reliability table keyed (task_type, step_type, tool).

    R1/R2 collapse the task-type dimension (key task_type=0); R3 draws per
    task type.
    """
    task_types = range(TASK_TYPES) if regime == "R3_context" else range(1)
    return {
        (tt, step, tool): rng.choice(RELIABILITY_LEVELS)
        for tt in task_types
        for step in STEP_TYPES
        for tool in TOOLS
    }


class ToolEnvironment:
    """Seeded tool ecosystem with per-call Bernoulli outcomes."""

    def __init__(self, regime: str, generator_seed: int) -> None:
        if regime not in REGIMES:
            raise ValueError(f"unknown regime {regime}")
        self.regime = regime
        self.generator_seed = generator_seed
        self._table = _draw_table(
            random.Random(f"{PROTOCOL_ID}:{regime}:gen:{generator_seed}"), regime
        )
        self._drift_rng = random.Random(
            f"{PROTOCOL_ID}:{regime}:drift:{generator_seed}"
        )
        self._outcome_rng = random.Random(
            f"{PROTOCOL_ID}:{regime}:outcome:{ENV_SEED_BASE + generator_seed}"
        )
        self.call_count = 0
        self.drifted = False

    def _key(self, task_type: int, step: str) -> Tuple[int, str]:
        return (task_type if self.regime == "R3_context" else 0, step)

    def reliability(self, task_type: int, step: str, tool: str) -> float:
        tt, s = self._key(task_type, step)
        return self._table[(tt, s, tool)]

    def call(self, task_type: int, step: str, tool: str) -> bool:
        if self.call_count >= CALL_BUDGET:
            raise RuntimeError("call budget exhausted")
        if (
            self.regime == "R2_drift"
            and not self.drifted
            and self.call_count >= DRIFT_AT_CALL
        ):
            self._table = _draw_table(self._drift_rng, self.regime)
            self.drifted = True
        success = self._outcome_rng.random() < self.reliability(task_type, step, tool)
        self.call_count += 1
        return success


# ── arms ──────────────────────────────────────────────────────────────────────

class Arm:
    name = "?"

    def choose(self, env: ToolEnvironment, task_type: int, step: str) -> str:
        raise NotImplementedError

    def observe(self, task_type: int, step: str, tool: str, success: bool) -> None:
        pass


class MemoryArm(Arm):
    """ReliabilityStore with shipped defaults; context-free state key."""

    name = "MEMORY"

    def __init__(self, rng: random.Random) -> None:
        self._rng = rng
        self.store = ReliabilityStore()

    def choose(self, env: ToolEnvironment, task_type: int, step: str) -> str:
        rec = self.store.recommend(step, list(TOOLS))
        if rec.recommended is None:
            return self._rng.choice(TOOLS)
        return rec.recommended

    def observe(self, task_type: int, step: str, tool: str, success: bool) -> None:
        self.store.observe_edge(step, tool, "success" if success else "failure")


class NoMemoryArm(Arm):
    name = "NO_MEMORY"

    def __init__(self, rng: random.Random) -> None:
        self._rng = rng

    def choose(self, env: ToolEnvironment, task_type: int, step: str) -> str:
        return self._rng.choice(TOOLS)


class StickyArm(Arm):
    """Keep the tool that last succeeded per context key; forget on failure."""

    name = "STICKY"

    def __init__(self, rng: random.Random, regime: str) -> None:
        self._rng = rng
        self._regime = regime
        self._last_success: Dict[str, str] = {}

    def _context(self, task_type: int, step: str) -> str:
        if self._regime == "R3_context":
            return f"t{task_type}:{step}"
        return step

    def choose(self, env: ToolEnvironment, task_type: int, step: str) -> str:
        remembered = self._last_success.get(self._context(task_type, step))
        if remembered is not None:
            return remembered
        return self._rng.choice(TOOLS)

    def observe(self, task_type: int, step: str, tool: str, success: bool) -> None:
        key = self._context(task_type, step)
        if success:
            self._last_success[key] = tool
        elif self._last_success.get(key) == tool:
            del self._last_success[key]


class OracleArm(Arm):
    """Upper reference: always the truly best tool under the current table."""

    name = "ORACLE"

    def choose(self, env: ToolEnvironment, task_type: int, step: str) -> str:
        return max(TOOLS, key=lambda t: (env.reliability(task_type, step, t), -TOOLS.index(t)))


def build_arm(arm: str, regime: str, generator_seed: int) -> Arm:
    rng = random.Random(
        f"{PROTOCOL_ID}:{regime}:agent:{AGENT_SEED_BASE + generator_seed}"
    )
    if arm == "MEMORY":
        return MemoryArm(rng)
    if arm == "NO_MEMORY":
        return NoMemoryArm(rng)
    if arm == "STICKY":
        return StickyArm(rng, regime)
    if arm == "ORACLE":
        return OracleArm()
    raise ValueError(f"unknown arm {arm}")


# ── replicate runner ──────────────────────────────────────────────────────────

@dataclass
class ReplicateResult:
    protocol_id: str
    regime: str
    arm: str
    generator_seed: int
    calls: int
    successes: int
    tasks_completed: int
    wasted_calls: int
    pre_drift_level: Optional[float]
    recovery_calls: Optional[int]
    recovered: Optional[bool]
    success_log: List[int] = field(repr=False, default_factory=list)

    def record(self) -> dict:
        data = {
            "protocol_id": self.protocol_id,
            "regime": self.regime,
            "arm": self.arm,
            "generator_seed": self.generator_seed,
            "calls": self.calls,
            "successes": self.successes,
            "tasks_completed": self.tasks_completed,
            "wasted_calls": self.wasted_calls,
        }
        if self.regime == "R2_drift":
            data["pre_drift_level"] = self.pre_drift_level
            data["recovery_calls"] = self.recovery_calls
            data["recovered"] = self.recovered
        return data


def _recovery_metrics(success_log: List[int]) -> Tuple[float, int, bool]:
    pre = success_log[DRIFT_AT_CALL - RECOVERY_WINDOW : DRIFT_AT_CALL]
    pre_level = sum(pre) / len(pre)
    if pre_level <= 0.0:
        return pre_level, 0, True
    target = RECOVERY_FACTOR * pre_level
    for t in range(DRIFT_AT_CALL + RECOVERY_WINDOW, len(success_log) + 1):
        window = success_log[t - RECOVERY_WINDOW : t]
        if sum(window) / RECOVERY_WINDOW >= target:
            return pre_level, t - DRIFT_AT_CALL, True
    return pre_level, len(success_log) - DRIFT_AT_CALL, False


def run_replicate(regime: str, arm_name: str, generator_seed: int) -> ReplicateResult:
    env = ToolEnvironment(regime, generator_seed)
    arm = build_arm(arm_name, regime, generator_seed)

    tasks_completed = 0
    task_index = 0
    wasted_calls = 0
    successes = 0
    success_log: List[int] = []

    while env.call_count < CALL_BUDGET:
        task_type = task_index % TASK_TYPES if regime == "R3_context" else 0
        steps_done = 0
        for step in STEP_TYPES:
            step_done = False
            while env.call_count < CALL_BUDGET:
                tool = arm.choose(env, task_type, step)
                success = env.call(task_type, step, tool)
                # reliability read after call() matches the table the call used:
                # R2 drift is applied inside call() before outcome evaluation
                # and cannot occur again until the next call.
                if env.reliability(task_type, step, tool) <= WASTED_RELIABILITY_THRESHOLD:
                    wasted_calls += 1
                successes += int(success)
                success_log.append(int(success))
                arm.observe(task_type, step, tool, success)
                if success:
                    step_done = True
                    break
            if not step_done:
                break
            steps_done += 1
        if steps_done == STEPS_PER_TASK:
            tasks_completed += 1
        task_index += 1

    pre_level: Optional[float] = None
    recovery: Optional[int] = None
    recovered: Optional[bool] = None
    if regime == "R2_drift":
        pre_level, recovery, recovered = _recovery_metrics(success_log)

    return ReplicateResult(
        protocol_id=PROTOCOL_ID,
        regime=regime,
        arm=arm_name,
        generator_seed=generator_seed,
        calls=env.call_count,
        successes=successes,
        tasks_completed=tasks_completed,
        wasted_calls=wasted_calls,
        pre_drift_level=pre_level,
        recovery_calls=recovery,
        recovered=recovered,
        success_log=success_log,
    )


def run_all() -> List[ReplicateResult]:
    verify_object_under_test()
    results = []
    for regime in REGIMES:
        for arm in ARMS:
            for seed in GENERATOR_SEEDS:
                results.append(run_replicate(regime, arm, seed))
    return results


# ── statistics ────────────────────────────────────────────────────────────────

def _percentile(sorted_values: List[float], p: float) -> float:
    position = p * (len(sorted_values) - 1)
    lower = int(position)
    upper = min(lower + 1, len(sorted_values) - 1)
    fraction = position - lower
    return sorted_values[lower] * (1 - fraction) + sorted_values[upper] * fraction


def paired_bootstrap(
    treatment: List[float], control: List[float]
) -> Dict[str, float]:
    if len(treatment) != len(control):
        raise ValueError("paired arrays must align")
    n = len(treatment)
    diffs = [treatment[i] - control[i] for i in range(n)]
    rng = random.Random(BOOTSTRAP_SEED)
    means = []
    for _ in range(BOOTSTRAP_RESAMPLES):
        sample = [diffs[rng.randrange(n)] for _ in range(n)]
        means.append(sum(sample) / n)
    means.sort()
    mean_t = sum(treatment) / n
    mean_c = sum(control) / n
    return {
        "treatment_mean": mean_t,
        "control_mean": mean_c,
        "mean_difference": mean_t - mean_c,
        "ci95_lower": _percentile(means, 0.025),
        "ci95_upper": _percentile(means, 0.975),
        "relative_lift": (mean_t - mean_c) / mean_c if mean_c else None,
        "paired_units": n,
        "bootstrap_resamples": BOOTSTRAP_RESAMPLES,
        "bootstrap_seed": BOOTSTRAP_SEED,
    }


def evaluate(results: List[ReplicateResult]) -> dict:
    """Apply the frozen decision criteria of section 7."""
    primary: Dict[Tuple[str, str], List[float]] = {}
    for r in sorted(results, key=lambda x: (x.regime, x.arm, x.generator_seed)):
        primary.setdefault((r.regime, r.arm), []).append(float(r.tasks_completed))

    comparisons = {}
    for regime in REGIMES:
        comparisons[regime] = {
            "MEMORY_vs_NO_MEMORY": paired_bootstrap(
                primary[(regime, "MEMORY")], primary[(regime, "NO_MEMORY")]
            ),
            "MEMORY_vs_STICKY": paired_bootstrap(
                primary[(regime, "MEMORY")], primary[(regime, "STICKY")]
            ),
        }

    r1_nm = comparisons["R1_persistent"]["MEMORY_vs_NO_MEMORY"]
    r1_st = comparisons["R1_persistent"]["MEMORY_vs_STICKY"]

    criterion_1 = (
        r1_nm["ci95_lower"] > 0
        and r1_nm["relative_lift"] is not None
        and r1_nm["relative_lift"] >= R1_MIN_RELATIVE_LIFT_VS_NO_MEMORY
    )
    criterion_2 = r1_st["ci95_lower"] > 0
    sticky_doc_note_required = criterion_2 and (
        (r1_st["relative_lift"] or 0.0) < STICKY_DOC_NOTE_LIFT
    )

    mandatory_notes = []
    if sticky_doc_note_required:
        mandatory_notes.append(
            "A stateless sticky heuristic captures most of the value; the"
            " library documentation must say so."
        )

    criterion_3 = True
    for regime in ("R2_drift", "R3_context"):
        cmp_nm = comparisons[regime]["MEMORY_vs_NO_MEMORY"]
        floor_soft = -NON_INFERIORITY_FRACTION * cmp_nm["control_mean"]
        floor_hard = -HARD_HARM_FRACTION * cmp_nm["control_mean"]
        cmp_nm["non_inferior"] = cmp_nm["ci95_lower"] > floor_soft
        cmp_nm["above_hard_floor"] = cmp_nm["ci95_lower"] > floor_hard
        if not cmp_nm["non_inferior"]:
            if cmp_nm["above_hard_floor"]:
                mandatory_notes.append(
                    f"{regime}: memory is not non-inferior to NO_MEMORY;"
                    " the corresponding warning becomes a permanent part of"
                    " the library README."
                )
            else:
                criterion_3 = False

    verdict = "PASS" if (criterion_1 and criterion_2 and criterion_3) else "FAIL"

    return {
        "protocol_id": PROTOCOL_ID,
        "primary_metric": "tasks_completed_per_1000_calls",
        "method_means": {
            f"{regime}:{arm}": sum(v) / len(v)
            for (regime, arm), v in sorted(primary.items())
        },
        "comparisons": comparisons,
        "criteria": {
            "c1_r1_beats_no_memory_lift10": criterion_1,
            "c2_r1_beats_sticky": criterion_2,
            "c3_stress_non_inferiority": criterion_3,
            "sticky_doc_note_required": sticky_doc_note_required,
        },
        "mandatory_notes": mandatory_notes,
        "verdict": verdict,
    }


# ── artifacts and CLI ─────────────────────────────────────────────────────────

def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def write_artifacts(
    results: List[ReplicateResult], summary: dict, output: Path, execution_commit: str
) -> dict:
    output.mkdir(parents=True, exist_ok=True)
    raw_lines = "".join(
        json.dumps(r.record(), sort_keys=True) + "\n"
        for r in sorted(results, key=lambda x: (x.regime, x.arm, x.generator_seed))
    ).encode("utf-8")
    (output / "raw_runs.jsonl").write_bytes(raw_lines)
    summary_bytes = json.dumps(summary, indent=2, sort_keys=True).encode("utf-8")
    (output / "summary.json").write_bytes(summary_bytes)
    manifest = {
        "artifact_kind": "wp6_relmem_decision_manifest",
        "protocol_id": PROTOCOL_ID,
        "execution_commit": execution_commit,
        "object_under_test_sha256": OBJECT_UNDER_TEST_SHA256,
        "counts": {
            "replicates": len(results),
            "regimes": len(REGIMES),
            "arms": len(ARMS),
            "seeds": len(GENERATOR_SEEDS),
            "calls_per_replicate": CALL_BUDGET,
        },
        "files": {
            "raw_runs.jsonl": _sha256_bytes(raw_lines),
            "summary.json": _sha256_bytes(summary_bytes),
        },
        "verdict": summary["verdict"],
    }
    manifest_bytes = json.dumps(manifest, indent=2, sort_keys=True).encode("utf-8")
    (output / "manifest.json").write_bytes(manifest_bytes)
    return manifest


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(prog="wp6_relmem_experiment")
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run", help="execute all 360 preregistered replicates")
    run.add_argument("--output", required=True)
    run.add_argument("--execution-commit", required=True)
    args = parser.parse_args(argv)

    if args.command == "run":
        results = run_all()
        summary = evaluate(results)
        manifest = write_artifacts(
            results, summary, Path(args.output), args.execution_commit
        )
        print(json.dumps({"verdict": summary["verdict"], "manifest": manifest["files"]}))
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
