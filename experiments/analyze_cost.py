#!/usr/bin/env python3
"""
Cost Analysis for E₀ Experiments
=================================
Analyzes token usage and API cost across experimental conditions.

Together AI pricing for Llama-3.3-70B-Instruct-Turbo:
  Realtime: Input $0.88/M, Output $0.88/M
  Batch:    Input $0.29/M, Output $0.88/M

Key distinction:
  - output_tokens: measured directly (token_count in CSV = logprob tokens)
  - input_tokens: estimated from prompt structure (system + init + history)
  - init_output_tokens: NOT measured (init responses, ~1024 each)

Conceptual framing (E₀ perspective):
  Cost ∝ total tokens.
  But: R̄ is the mean INFORMATION COST per token (R = -log p).
  Total information cost = Σ R_i across all tokens.
  If R̄ is lower, the same number of tokens carries less "surprise."
  
  The question is: does lower R̄ also correlate with fewer tokens?
  That would mean: E₀ priming → more concise → literally cheaper.
"""

import csv
import json
import sys
from pathlib import Path
from dataclasses import dataclass
from typing import List, Optional

# Together AI pricing (per token)
INPUT_PRICE_PER_TOKEN = 0.88 / 1_000_000
OUTPUT_PRICE_PER_TOKEN = 0.88 / 1_000_000

# Batch pricing
BATCH_INPUT_PRICE_PER_TOKEN = 0.29 / 1_000_000
BATCH_OUTPUT_PRICE_PER_TOKEN = 0.88 / 1_000_000

# Estimated token counts for init phase (not measured by runner)
# These are rough estimates based on typical tokenization of the config content
INIT_TOKEN_ESTIMATES = {
    "e0_initialized": {
        "system_prompt_tokens": 180,
        "init_prompt_1_tokens": 580,  # Canon
        "init_prompt_2_tokens": 480,  # Ontodynamics
        "init_response_tokens": 1024,  # ~max_tokens each, 2 responses
    },
    "null_control": {
        "system_prompt_tokens": 0,
        "init_prompt_1_tokens": 0,
        "init_prompt_2_tokens": 0,
        "init_response_tokens": 0,
    },
    "placebo_control": {
        "system_prompt_tokens": 220,   # ZFC system prompt
        "init_prompt_1_tokens": 550,   # ZFC axioms
        "init_prompt_2_tokens": 350,   # Math structures
        "init_response_tokens": 1024,  # 2 responses
    },
    "inverted_control": {
        "system_prompt_tokens": 180,   # Same E₀ system prompt
        "init_prompt_1_tokens": 580,   # Same Canon
        "init_prompt_2_tokens": 480,   # Same Ontodynamics
        "init_response_tokens": 1024,  # 2 responses
    },
}


@dataclass
class TurnCost:
    run_id: int
    turn_index: int
    output_tokens: int
    estimated_input_tokens: int
    R_mean: float
    H_mean: float
    total_info_cost: float  # output_tokens × R̄
    output_cost_usd: float
    input_cost_usd: float
    total_cost_usd: float


@dataclass 
class ConditionCost:
    condition: str
    n_runs: int
    total_output_tokens: int
    total_estimated_input_tokens: int
    estimated_init_output_tokens: int
    total_cost_usd: float
    cost_per_run_usd: float
    mean_output_tokens_per_step: float
    mean_R: float
    total_information_cost: float  # Σ(tokens × R̄) across all turns
    info_cost_per_token: float     # = mean R̄


def load_summary(csv_path: Path) -> list:
    rows = []
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)
    return rows


def estimate_input_tokens_for_turn(condition: str, turn_index: int, 
                                     test_prompt_tokens: int,
                                     prior_output_tokens: List[int]) -> int:
    """Estimate input token count for a given turn.
    
    Input = system_prompt + init_prompts + init_responses + 
            sum(prior test_prompts + prior test_responses) + current test_prompt
    """
    est = INIT_TOKEN_ESTIMATES.get(condition, INIT_TOKEN_ESTIMATES["null_control"])
    
    # Fixed overhead: system + init
    base = (est["system_prompt_tokens"] + 
            est["init_prompt_1_tokens"] + 
            est["init_prompt_2_tokens"] +
            est["init_response_tokens"] * 2)  # 2 init responses
    
    # Prior conversation: each prior turn = prompt (~80 tokens) + response
    prior_context = sum(80 + out for out in prior_output_tokens[:turn_index])
    
    # Current test prompt
    current_prompt = test_prompt_tokens  # ~80 tokens
    
    return base + prior_context + current_prompt


def analyze_condition(summary_path: Path, condition: str) -> Optional[ConditionCost]:
    if not summary_path.exists():
        return None
    
    rows = load_summary(summary_path)
    if not rows:
        return None
    
    # Group by run
    runs = {}
    for row in rows:
        rid = int(row["run_id"])
        if rid not in runs:
            runs[rid] = []
        runs[rid].append(row)
    
    total_output = 0
    total_input_est = 0
    total_info_cost = 0.0
    all_R = []
    all_output_tokens = []
    
    for rid, turns in sorted(runs.items()):
        prior_outputs = []
        for row in turns:
            tidx = int(row["turn_index"])
            out_tokens = int(row["token_count"])
            R_mean = float(row["R_mean"])
            
            # Estimate input tokens
            in_tokens = estimate_input_tokens_for_turn(
                condition, tidx, 80, prior_outputs
            )
            
            total_output += out_tokens
            total_input_est += in_tokens
            total_info_cost += out_tokens * R_mean
            all_R.append(R_mean)
            all_output_tokens.append(out_tokens)
            prior_outputs.append(out_tokens)
    
    n_runs = len(runs)
    est = INIT_TOKEN_ESTIMATES.get(condition, INIT_TOKEN_ESTIMATES["null_control"])
    init_output_per_run = est["init_response_tokens"] * 2  # 2 init responses
    total_init_output = init_output_per_run * n_runs
    
    # Input cost includes init prompts input too
    total_input_cost = total_input_est * INPUT_PRICE_PER_TOKEN
    total_output_cost = (total_output + total_init_output) * OUTPUT_PRICE_PER_TOKEN
    total_cost = total_input_cost + total_output_cost
    
    return ConditionCost(
        condition=condition,
        n_runs=n_runs,
        total_output_tokens=total_output,
        total_estimated_input_tokens=total_input_est,
        estimated_init_output_tokens=total_init_output,
        total_cost_usd=total_cost,
        cost_per_run_usd=total_cost / n_runs if n_runs > 0 else 0,
        mean_output_tokens_per_step=sum(all_output_tokens) / len(all_output_tokens) if all_output_tokens else 0,
        mean_R=sum(all_R) / len(all_R) if all_R else 0,
        total_information_cost=total_info_cost,
        info_cost_per_token=total_info_cost / total_output if total_output > 0 else 0,
    )


def print_report(conditions: List[ConditionCost]):
    print("=" * 72)
    print("COST ANALYSIS — E₀ Experiment Battery")
    print("=" * 72)
    print(f"\nTogether AI Pricing: Llama-3.3-70B-Instruct-Turbo")
    print(f"  Realtime: Input ${INPUT_PRICE_PER_TOKEN * 1_000_000:.2f}/M  Output ${OUTPUT_PRICE_PER_TOKEN * 1_000_000:.2f}/M")
    print(f"  Batch:    Input ${BATCH_INPUT_PRICE_PER_TOKEN * 1_000_000:.2f}/M  Output ${BATCH_OUTPUT_PRICE_PER_TOKEN * 1_000_000:.2f}/M")
    
    print(f"\n{'─' * 72}")
    print(f"{'Condition':<20} {'N':>3} {'Out Tok':>8} {'In Tok*':>8} {'Init Tok*':>9} {'Total $':>8} {'$/run':>7}")
    print(f"{'─' * 72}")
    
    grand_total = 0.0
    for c in conditions:
        print(f"{c.condition:<20} {c.n_runs:>3} {c.total_output_tokens:>8,} "
              f"{c.total_estimated_input_tokens:>8,} {c.estimated_init_output_tokens:>9,} "
              f"${c.total_cost_usd:>7.4f} ${c.cost_per_run_usd:>6.4f}")
        grand_total += c.total_cost_usd
    
    print(f"{'─' * 72}")
    print(f"{'TOTAL':<20} {'':>3} {'':>8} {'':>8} {'':>9} ${grand_total:>7.4f}")
    print(f"\n* Input tokens and init output tokens are ESTIMATED (not tracked by API)")
    
    # Output tokens per step comparison
    print(f"\n{'═' * 72}")
    print(f"OUTPUT TOKENS PER STEP (measured)")
    print(f"{'─' * 72}")
    print(f"{'Condition':<20} {'Mean Tok/Step':>14} {'R̄ (mean)':>10} {'Info Cost/Tok':>14}")
    print(f"{'─' * 72}")
    for c in conditions:
        print(f"{c.condition:<20} {c.mean_output_tokens_per_step:>14.1f} "
              f"{c.mean_R:>10.4f} {c.info_cost_per_token:>14.4f}")
    
    # The key insight
    print(f"\n{'═' * 72}")
    print(f"KEY INSIGHT: INFORMATION COST vs TOKEN COST")
    print(f"{'─' * 72}")
    print(f"""
API cost depends on TOKEN COUNT (input + output).
Information cost depends on R̄ × token count.

If E₀ reduces R̄ but not token count → same $ cost, less information content.
If E₀ reduces BOTH R̄ and token count → less $ AND less information content.

This distinction matters because:
  - Realtime pricing: $0.88/M (all tokens equal)
  - Batch pricing:    $0.29/M input (67% cheaper!)
  - From an information-theoretic view, a token with R=0.01 carries 
    much less 'surprise' than a token with R=0.19
  - E₀ may make generation more 'efficient' — fewer bits per dollar
""")
    
    if len(conditions) >= 2:
        e0 = next((c for c in conditions if c.condition == "e0_initialized"), None)
        null = next((c for c in conditions if c.condition == "null_control"), None)
        if e0 and null:
            print(f"  E₀ mean tokens/step:  {e0.mean_output_tokens_per_step:.0f}")
            print(f"  Null mean tokens/step: {null.mean_output_tokens_per_step:.0f}")
            tok_ratio = e0.mean_output_tokens_per_step / null.mean_output_tokens_per_step if null.mean_output_tokens_per_step > 0 else 0
            R_ratio = e0.mean_R / null.mean_R if null.mean_R > 0 else 0
            print(f"  Token count ratio:     {tok_ratio:.2f}x")
            print(f"  R̄ ratio:               {R_ratio:.2f}x")
            print(f"  → E₀ uses {tok_ratio:.0%} of null's tokens at {R_ratio:.0%} of null's R̄")
            print(f"  → Net information ratio: {tok_ratio * R_ratio:.2f}x")

    # Batch pricing comparison
    print(f"\n{'═' * 72}")
    print(f"BATCH PRICING COMPARISON")
    print(f"{'─' * 72}")
    print(f"{'Condition':<20} {'Realtime $':>11} {'Batch $':>9} {'Savings':>8}")
    print(f"{'─' * 72}")
    grand_batch = 0.0
    for c in conditions:
        batch_input_cost = c.total_estimated_input_tokens * BATCH_INPUT_PRICE_PER_TOKEN
        batch_output_cost = (c.total_output_tokens + c.estimated_init_output_tokens) * BATCH_OUTPUT_PRICE_PER_TOKEN
        batch_total = batch_input_cost + batch_output_cost
        savings = 1 - (batch_total / c.total_cost_usd) if c.total_cost_usd > 0 else 0
        grand_batch += batch_total
        print(f"{c.condition:<20} ${c.total_cost_usd:>10.4f} ${batch_total:>8.4f} {savings:>7.0%}")
    print(f"{'─' * 72}")
    print(f"{'TOTAL':<20} ${grand_total:>10.4f} ${grand_batch:>8.4f} {1 - grand_batch/grand_total if grand_total > 0 else 0:>7.0%}")

    # Projection for full battery
    print(f"\n{'═' * 72}")
    print(f"PROJECTED COST — FULL BATTERY (4 conditions × 10 runs)")
    print(f"{'─' * 72}")
    
    print(f"  Actual total (realtime): ${grand_total:.4f}")
    print(f"  Actual total (batch):    ${grand_batch:.4f}")
    print(f"\n  → THE ENTIRE EXPERIMENT BATTERY COSTS < ${max(grand_total, 0.50):.2f} (realtime)")
    print(f"  → WITH BATCH PRICING: < ${max(grand_batch, 0.25):.2f}")


def main():
    results_dir = Path("experiments/results")
    
    conditions_to_check = [
        ("qm_derivation_e0", "e0_initialized"),
        ("qm_derivation_null", "null_control"),
        ("qm_derivation_placebo", "placebo_control"),
        ("qm_derivation_inverted", "inverted_control"),
    ]
    
    found = []
    for dirname, condition in conditions_to_check:
        summary = results_dir / dirname / "summary.csv"
        result = analyze_condition(summary, condition)
        if result:
            found.append(result)
    
    if not found:
        print("No results found.")
        sys.exit(1)
    
    print_report(found)


if __name__ == "__main__":
    main()
