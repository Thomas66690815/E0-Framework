"""
E₀ Experiment Runner — Reproducible Structural Measurement
============================================================
Runs controlled experiments: N repetitions of identical prompt sequences,
with full E₀ metric capture, per-token traces, and CSV/JSON export.

Supports:
  - Multiple experimental conditions (E₀-initialized, null, placebo, inverted)
  - Temperature control (default temp=0 for deterministic baselines)
  - Per-turn and per-token metric capture
  - Automatic export to experiments/results/

Usage:
    py -m experiments.runner --config experiments/configs/qm_derivation.json
    py -m experiments.runner --config experiments/configs/qm_derivation.json --runs 10
"""

from __future__ import annotations

import json
import math
import os
import sys
import time
import hashlib
import csv
from copy import deepcopy
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from e0_middleware.instrumentation import E0Instrumenter, StepMeasurement


# ─────────────────────────────────────────────────────
# Data Structures
# ─────────────────────────────────────────────────────

@dataclass
class TurnMetrics:
    """Metrics for a single turn (prompt → response)."""
    turn_index: int
    prompt: str
    response_text: str
    token_count: int
    R_mean: float          # R̄ — mean resistance
    H_mean: float          # H̄ — mean entropy
    Phi: int               # Φ — reconfiguration count (sign changes in ΔH)
    v_mean: float          # v̄ — mean velocity
    R_std: float           # σ(R)
    H_std: float           # σ(H)
    R_min: float
    R_max: float
    latency_ms: float      # API call latency
    timestamp: str

    # Per-token trace (optional, for detailed analysis)
    token_trace: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class RunResult:
    """Result of a single experimental run (full prompt sequence)."""
    run_id: int
    condition: str         # e.g. "e0_initialized", "null_control", "placebo"
    model: str
    temperature: float
    turns: List[TurnMetrics]
    total_tokens: int
    total_latency_ms: float
    timestamp: str
    config_hash: str       # SHA256 of config for reproducibility


@dataclass
class ExperimentResult:
    """Full experiment: multiple runs of the same condition."""
    experiment_id: str
    condition: str
    description: str
    model: str
    n_runs: int
    runs: List[RunResult]
    config: Dict[str, Any]
    started_at: str
    completed_at: str = ""


# ─────────────────────────────────────────────────────
# Metric Computation
# ─────────────────────────────────────────────────────

def compute_turn_metrics(
    turn_index: int,
    prompt: str,
    response_text: str,
    steps: List[StepMeasurement],
    latency_ms: float,
) -> TurnMetrics:
    """
    Compute E₀ aggregate metrics for one turn.

    Matches the metrics from our manual experiments:
      R̄  = mean of selected token resistance
      H̄  = mean of step entropy
      Φ   = number of sign changes in ΔH (reconfigurations)
      v̄  = mean of 1/R for selected tokens (velocity)
    """
    if not steps:
        return TurnMetrics(
            turn_index=turn_index, prompt=prompt, response_text=response_text,
            token_count=0, R_mean=0, H_mean=0, Phi=0, v_mean=0,
            R_std=0, H_std=0, R_min=0, R_max=0,
            latency_ms=latency_ms, timestamp=datetime.now().isoformat(),
        )

    # Per-token values
    resistances = [s.selected.resistance for s in steps]
    entropies = [s.entropy for s in steps]
    delta_entropies = [s.delta_entropy for s in steps]

    # Velocities: v = 1/R, cap at 99999 for R≈0
    velocities = []
    for s in steps:
        r = s.selected.resistance
        if r > 1e-10:
            velocities.append(1.0 / r)
        else:
            velocities.append(99999.0)

    # R̄
    R_mean = sum(resistances) / len(resistances)
    # H̄
    H_mean = sum(entropies) / len(entropies)
    # v̄
    v_mean = sum(velocities) / len(velocities)

    # Φ — reconfiguration count: sign changes in ΔH
    Phi = 0
    for i in range(1, len(delta_entropies)):
        if delta_entropies[i] * delta_entropies[i - 1] < 0:
            Phi += 1

    # Standard deviations
    R_std = math.sqrt(sum((r - R_mean) ** 2 for r in resistances) / len(resistances)) if len(resistances) > 1 else 0.0
    H_std = math.sqrt(sum((h - H_mean) ** 2 for h in entropies) / len(entropies)) if len(entropies) > 1 else 0.0

    # Token trace (compact format for CSV/JSON export)
    token_trace = []
    for s in steps:
        token_trace.append({
            "tau": s.tau,
            "token": s.selected.token,
            "R": round(s.selected.resistance, 4),
            "v": round(velocities[s.tau - steps[0].tau] if (s.tau - steps[0].tau) < len(velocities) else 0, 1),
            "H": round(s.entropy, 4),
            "dH": round(s.delta_entropy, 4),
        })

    return TurnMetrics(
        turn_index=turn_index,
        prompt=prompt,
        response_text=response_text,
        token_count=len(steps),
        R_mean=round(R_mean, 6),
        H_mean=round(H_mean, 6),
        Phi=Phi,
        v_mean=round(v_mean, 3),
        R_std=round(R_std, 6),
        H_std=round(H_std, 6),
        R_min=round(min(resistances), 6),
        R_max=round(max(resistances), 6),
        latency_ms=round(latency_ms, 1),
        timestamp=datetime.now().isoformat(),
        token_trace=token_trace,
    )


# ─────────────────────────────────────────────────────
# Experiment Runner
# ─────────────────────────────────────────────────────

class ExperimentRunner:
    """
    Runs controlled E₀ experiments.

    Each experiment consists of:
      1. An initialization phase (system prompt + optional primers)
      2. A sequence of test prompts
      3. Per-turn metric capture
      4. Repeated N times for statistical power

    Experiment config format:
    {
        "experiment_id": "qm_derivation_e0",
        "condition": "e0_initialized",
        "description": "QM derivation with full E₀ initialization",
        "model": "meta-llama/Llama-3.3-70B-Instruct-Turbo",
        "temperature": 0,
        "api_base_url": "https://api.together.xyz/v1",
        "system_prompt": "...",          // null for no system prompt
        "initialization_prompts": [...], // fed before test prompts
        "test_prompts": [...],           // the actual measured prompts
        "n_runs": 10,
        "max_tokens": 1024
    }
    """

    def __init__(
        self,
        api_key: str,
        config: Dict[str, Any],
        output_dir: Optional[str] = None,
        verbose: bool = True,
    ):
        self.api_key = api_key
        self.config = config
        self.verbose = verbose

        self.experiment_id = config["experiment_id"]
        self.condition = config["condition"]
        self.description = config.get("description", "")
        self.model = config["model"]
        self.temperature = config.get("temperature", 0)
        self.api_base_url = config.get("api_base_url", "https://api.together.xyz/v1")
        self.system_prompt = config.get("system_prompt")
        self.init_prompts = config.get("initialization_prompts", [])
        self.test_prompts = config.get("test_prompts", [])
        self.n_runs = config.get("n_runs", 10)
        self.max_tokens = config.get("max_tokens", 1024)

        # Output directory
        if output_dir:
            self.output_dir = Path(output_dir)
        else:
            self.output_dir = PROJECT_ROOT / "experiments" / "results" / self.experiment_id
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Config hash for reproducibility tracking
        config_str = json.dumps(config, sort_keys=True)
        self.config_hash = hashlib.sha256(config_str.encode()).hexdigest()[:16]

    def _log(self, msg: str):
        if self.verbose:
            print(f"  [E₀ Exp] {msg}")

    def _make_api_call(
        self,
        messages: List[Dict[str, str]],
    ) -> Tuple[str, List[StepMeasurement], float]:
        """
        Make a single API call and return (text, steps, latency_ms).
        """
        import openai

        client = openai.OpenAI(
            api_key=self.api_key,
            base_url=self.api_base_url,
        )

        instrumenter = E0Instrumenter()

        request = {
            "model": self.model,
            "messages": messages,
            "logprobs": True,
            "top_logprobs": 5,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
        }

        t0 = time.time()
        raw = client.chat.completions.create(**request)
        latency_ms = (time.time() - t0) * 1000

        raw_dict = raw.model_dump()
        choice = raw_dict["choices"][0]
        text = choice["message"]["content"]

        # Extract logprobs and instrument
        steps: List[StepMeasurement] = []
        lp_data = choice.get("logprobs")
        if lp_data:
            if lp_data.get("content"):
                # OpenAI format
                for token_data in lp_data["content"]:
                    selected_token = token_data["token"]
                    selected_logprob = token_data["logprob"]
                    logprob_dict = {selected_token: selected_logprob}
                    if token_data.get("top_logprobs"):
                        for alt in token_data["top_logprobs"]:
                            logprob_dict[alt["token"]] = alt["logprob"]
                    step = instrumenter.measure_step(
                        logprobs=logprob_dict,
                        selected_token=selected_token,
                    )
                    steps.append(step)

            elif lp_data.get("tokens") and lp_data.get("token_logprobs"):
                # Together AI / vLLM format
                tokens = lp_data["tokens"]
                token_lps = lp_data["token_logprobs"]
                top_lps = lp_data.get("top_logprobs") or [None] * len(tokens)
                for i, (tok, lp) in enumerate(zip(tokens, token_lps)):
                    if lp is None:
                        continue
                    logprob_dict = {tok: lp}
                    if i < len(top_lps) and top_lps[i]:
                        for alt_tok, alt_lp in top_lps[i].items():
                            logprob_dict[alt_tok] = alt_lp
                    step = instrumenter.measure_step(
                        logprobs=logprob_dict,
                        selected_token=tok,
                    )
                    steps.append(step)

        return text, steps, latency_ms

    def _run_single(self, run_id: int) -> RunResult:
        """Execute one complete run: init phase + test phase."""
        self._log(f"Run {run_id + 1}/{self.n_runs} starting...")

        messages: List[Dict[str, str]] = []
        all_turns: List[TurnMetrics] = []
        total_tokens = 0
        total_latency = 0.0

        # 1. System prompt
        if self.system_prompt:
            messages.append({"role": "system", "content": self.system_prompt})

        # 2. Initialization prompts (not measured — these set up the condition)
        for i, init_prompt in enumerate(self.init_prompts):
            self._log(f"  Init prompt {i + 1}/{len(self.init_prompts)}...")
            messages.append({"role": "user", "content": init_prompt})
            try:
                text, steps, latency = self._make_api_call(messages)
                messages.append({"role": "assistant", "content": text})
                self._log(f"    → {len(steps)} tokens, {latency:.0f}ms")
            except Exception as e:
                self._log(f"    → ERROR in init: {e}")
                messages.append({"role": "assistant", "content": f"[ERROR: {e}]"})

        # 3. Test prompts (MEASURED — these produce the data)
        for t, test_prompt in enumerate(self.test_prompts):
            self._log(f"  Test prompt {t + 1}/{len(self.test_prompts)}: {test_prompt[:60]}...")
            messages.append({"role": "user", "content": test_prompt})

            try:
                text, steps, latency = self._make_api_call(messages)
                messages.append({"role": "assistant", "content": text})

                turn = compute_turn_metrics(
                    turn_index=t,
                    prompt=test_prompt,
                    response_text=text,
                    steps=steps,
                    latency_ms=latency,
                )
                all_turns.append(turn)
                total_tokens += turn.token_count
                total_latency += latency

                self._log(
                    f"    → R̄={turn.R_mean:.4f}  H̄={turn.H_mean:.4f}  "
                    f"Φ={turn.Phi}  v̄={turn.v_mean:.1f}  "
                    f"({turn.token_count} tokens, {latency:.0f}ms)"
                )

            except Exception as e:
                self._log(f"    → ERROR: {e}")
                # Record error as a turn with zero metrics
                all_turns.append(TurnMetrics(
                    turn_index=t, prompt=test_prompt,
                    response_text=f"[ERROR: {e}]",
                    token_count=0, R_mean=0, H_mean=0, Phi=0, v_mean=0,
                    R_std=0, H_std=0, R_min=0, R_max=0,
                    latency_ms=0, timestamp=datetime.now().isoformat(),
                ))

        return RunResult(
            run_id=run_id,
            condition=self.condition,
            model=self.model,
            temperature=self.temperature,
            turns=all_turns,
            total_tokens=total_tokens,
            total_latency_ms=total_latency,
            timestamp=datetime.now().isoformat(),
            config_hash=self.config_hash,
        )

    def run(self) -> ExperimentResult:
        """Run the full experiment: N runs of the same prompt sequence."""
        self._log(f"{'═' * 60}")
        self._log(f"Experiment: {self.experiment_id}")
        self._log(f"Condition:  {self.condition}")
        self._log(f"Model:      {self.model}")
        self._log(f"Temp:       {self.temperature}")
        self._log(f"Runs:       {self.n_runs}")
        self._log(f"Init:       {len(self.init_prompts)} prompts")
        self._log(f"Test:       {len(self.test_prompts)} prompts")
        self._log(f"Config:     {self.config_hash}")
        self._log(f"Output:     {self.output_dir}")
        self._log(f"{'═' * 60}")

        started = datetime.now().isoformat()
        runs: List[RunResult] = []

        for i in range(self.n_runs):
            try:
                result = self._run_single(i)
                runs.append(result)

                # Save intermediate results after each run
                self._save_run_csv(result)

            except Exception as e:
                self._log(f"Run {i + 1} FAILED: {e}")
                continue

            # Rate limiting: 2 second pause between runs
            if i < self.n_runs - 1:
                self._log(f"  Waiting 2s before next run...")
                time.sleep(2)

        experiment = ExperimentResult(
            experiment_id=self.experiment_id,
            condition=self.condition,
            description=self.description,
            model=self.model,
            n_runs=len(runs),
            runs=runs,
            config=self.config,
            started_at=started,
            completed_at=datetime.now().isoformat(),
        )

        # Save final results
        self._save_experiment_json(experiment)
        self._save_summary_csv(experiment)

        self._log(f"{'═' * 60}")
        self._log(f"Experiment complete: {len(runs)}/{self.n_runs} runs successful")
        self._log(f"Results: {self.output_dir}")
        self._log(f"{'═' * 60}")

        return experiment

    # ─────────────────────────────────────────────────
    # Export
    # ─────────────────────────────────────────────────

    def _save_run_csv(self, run: RunResult):
        """Save per-turn metrics for one run as CSV."""
        csv_path = self.output_dir / f"run_{run.run_id:03d}_turns.csv"
        fieldnames = [
            "run_id", "turn_index", "prompt", "token_count",
            "R_mean", "H_mean", "Phi", "v_mean",
            "R_std", "H_std", "R_min", "R_max",
            "latency_ms", "timestamp",
        ]

        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for turn in run.turns:
                writer.writerow({
                    "run_id": run.run_id,
                    "turn_index": turn.turn_index,
                    "prompt": turn.prompt[:100],
                    "token_count": turn.token_count,
                    "R_mean": turn.R_mean,
                    "H_mean": turn.H_mean,
                    "Phi": turn.Phi,
                    "v_mean": turn.v_mean,
                    "R_std": turn.R_std,
                    "H_std": turn.H_std,
                    "R_min": turn.R_min,
                    "R_max": turn.R_max,
                    "latency_ms": turn.latency_ms,
                    "timestamp": turn.timestamp,
                })

        # Also save token trace for detailed analysis
        trace_path = self.output_dir / f"run_{run.run_id:03d}_tokens.csv"
        with open(trace_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["run_id", "turn_index", "tau", "token", "R", "v", "H", "dH"])
            writer.writeheader()
            for turn in run.turns:
                for tok in turn.token_trace:
                    writer.writerow({
                        "run_id": run.run_id,
                        "turn_index": turn.turn_index,
                        **tok,
                    })

    def _save_experiment_json(self, experiment: ExperimentResult):
        """Save full experiment as JSON (including response texts)."""
        json_path = self.output_dir / f"experiment_{self.config_hash}.json"

        def serialize(obj):
            if hasattr(obj, '__dict__'):
                d = {}
                for k, v in obj.__dict__.items():
                    d[k] = serialize(v)
                return d
            elif isinstance(obj, list):
                return [serialize(item) for item in obj]
            elif isinstance(obj, dict):
                return {k: serialize(v) for k, v in obj.items()}
            else:
                return obj

        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(serialize(experiment), f, indent=2, ensure_ascii=False)

        self._log(f"  Saved: {json_path}")

    def _save_summary_csv(self, experiment: ExperimentResult):
        """Save aggregated summary across all runs."""
        csv_path = self.output_dir / "summary.csv"
        fieldnames = [
            "experiment_id", "condition", "model", "temperature",
            "run_id", "turn_index", "prompt",
            "R_mean", "H_mean", "Phi", "v_mean",
            "R_std", "H_std", "token_count", "latency_ms",
        ]

        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for run in experiment.runs:
                for turn in run.turns:
                    writer.writerow({
                        "experiment_id": experiment.experiment_id,
                        "condition": experiment.condition,
                        "model": experiment.model,
                        "temperature": run.temperature,
                        "run_id": run.run_id,
                        "turn_index": turn.turn_index,
                        "prompt": turn.prompt[:100],
                        "R_mean": turn.R_mean,
                        "H_mean": turn.H_mean,
                        "Phi": turn.Phi,
                        "v_mean": turn.v_mean,
                        "R_std": turn.R_std,
                        "H_std": turn.H_std,
                        "token_count": turn.token_count,
                        "latency_ms": turn.latency_ms,
                    })

        self._log(f"  Saved: {csv_path}")


# ─────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────

def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="E₀ Experiment Runner — Reproducible structural measurement",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
        "--config", required=True,
        help="Path to experiment config JSON",
    )
    parser.add_argument(
        "--api-key", default=None,
        help="API key (or set TOGETHER_API_KEY / OPENAI_API_KEY env var)",
    )
    parser.add_argument(
        "--runs", type=int, default=None,
        help="Override number of runs from config",
    )
    parser.add_argument(
        "--output", default=None,
        help="Override output directory",
    )
    parser.add_argument(
        "--quiet", action="store_true",
        help="Suppress verbose output",
    )
    parser.add_argument(
        "--analyze", action="store_true",
        help="Run statistical analysis after experiment completes",
    )

    args = parser.parse_args()

    # Load config
    config_path = Path(args.config)
    if not config_path.exists():
        print(f"Error: Config not found: {config_path}")
        sys.exit(1)

    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)

    # Override runs if specified
    if args.runs is not None:
        config["n_runs"] = args.runs

    # Find API key
    api_key = (
        args.api_key
        or os.environ.get("TOGETHER_API_KEY")
        or os.environ.get("OPENAI_API_KEY")
        or ""
    )
    if not api_key:
        print("Error: No API key. Use --api-key or set TOGETHER_API_KEY env var.")
        sys.exit(1)

    # Run experiment
    runner = ExperimentRunner(
        api_key=api_key,
        config=config,
        output_dir=args.output,
        verbose=not args.quiet,
    )
    experiment = runner.run()

    # Optional: run analysis
    if args.analyze:
        try:
            from experiments.stats import analyze_experiment
            analysis = analyze_experiment(experiment)
            print("\n" + analysis)
        except ImportError:
            print("\n  [Warning] experiments.stats module not available for analysis.")


if __name__ == "__main__":
    main()
