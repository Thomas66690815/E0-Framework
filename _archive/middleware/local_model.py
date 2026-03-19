"""
E₀ Local Model Runner — Real E₀ Dynamics on a Real Model
==========================================================
Loads a HuggingFace model locally (CPU, no GPU required)
and instruments every generation step with E₀ measurements.

This is where E₀ stops being simulation and becomes observation.

Every token probability is a real Resistance measurement.
Every attention head produces a real admissibility landscape.
Every generation step is a real structural transition.

Designed to run on minimal hardware:
  - GPT-2 (124M):  ~500MB RAM, runs on any laptop
  - TinyLlama:     ~550MB quantized, feasible on Raspberry Pi 4
  - Phi-2:         ~2.7GB, good for detailed analysis

Usage:
    from e0_middleware.local_model import E0LocalModel

    model = E0LocalModel("gpt2")
    result = model.generate("The structure of reality is")
    result.print_e0_report()
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from .instrumentation import E0Instrumenter, TokenMeasurement, StepMeasurement


# ─────────────────────────────────────────────
# E₀ Generation Result
# ─────────────────────────────────────────────

@dataclass
class E0GenerationResult:
    """
    Complete E₀-instrumented generation result.

    Contains the generated text AND the full E₀ transition
    history — every step's resistance landscape, every
    difference measurement, every phase transition.
    """
    prompt: str
    generated_text: str
    full_text: str
    steps: List[StepMeasurement]
    generation_time: float
    model_name: str

    # ── Derived E₀ metrics ──

    @property
    def mean_resistance(self) -> float:
        """Average R across all selected tokens."""
        if not self.steps:
            return 0.0
        return sum(s.selected.resistance for s in self.steps) / len(self.steps)

    @property
    def mean_entropy(self) -> float:
        """Average Shannon entropy — landscape stability."""
        if not self.steps:
            return 0.0
        return sum(s.entropy for s in self.steps) / len(self.steps)

    @property
    def phase_transitions(self) -> List[int]:
        """
        Steps where |ΔH| exceeds 1 standard deviation.
        These are structural reconfigurations — the landscape
        of possible transitions changes suddenly.
        """
        if len(self.steps) < 3:
            return []
        deltas = [abs(s.delta_entropy) for s in self.steps]
        mean_d = sum(deltas) / len(deltas)
        std_d = (sum((d - mean_d) ** 2 for d in deltas) / len(deltas)) ** 0.5
        if std_d < 1e-10:
            return []
        threshold = mean_d + std_d
        return [s.tau for s in self.steps if abs(s.delta_entropy) > threshold]

    @property
    def collapse_risk_max(self) -> float:
        """Maximum top_rate_ratio — how close to mode collapse."""
        if not self.steps:
            return 0.0
        return max(s.top_rate_ratio for s in self.steps)

    @property
    def resistance_range(self) -> Tuple[float, float]:
        """(min_R, max_R) — the full resistance spectrum observed."""
        if not self.steps:
            return (0.0, 0.0)
        rs = [s.selected.resistance for s in self.steps]
        return (min(rs), max(rs))

    @property
    def velocity_profile(self) -> List[float]:
        """v = Δ/R for each step — the transition velocity sequence."""
        return [s.selected.rate for s in self.steps]

    def print_e0_report(self) -> None:
        """Print a human-readable E₀ analysis of the generation."""
        print()
        print("=" * 70)
        print("  E₀ TRANSITION REPORT — Real Model Measurements")
        print("=" * 70)
        print(f"  Model:     {self.model_name}")
        print(f"  Prompt:    {self.prompt[:60]}{'...' if len(self.prompt) > 60 else ''}")
        print(f"  Generated: {len(self.steps)} tokens in {self.generation_time:.2f}s")
        print("-" * 70)

        # ── The generated text ──
        print(f"\n  Output: {self.generated_text}\n")
        print("-" * 70)

        # ── Global E₀ metrics ──
        r_min, r_max = self.resistance_range
        print(f"  Mean Resistance (R̄):    {self.mean_resistance:.4f}")
        print(f"  Resistance Range:       [{r_min:.4f}, {r_max:.4f}]")
        print(f"  Mean Entropy (H̄):       {self.mean_entropy:.4f}")
        print(f"  Phase Transitions:      {len(self.phase_transitions)} detected")
        if self.phase_transitions:
            print(f"    at τ = {self.phase_transitions}")
        print(f"  Max Collapse Risk:      {self.collapse_risk_max:.4f}")
        print()

        # ── Token-by-token trace ──
        print("  τ  | Token              | R        | v=Δ/R    | H        | ΔH")
        print("  " + "-" * 66)
        for s in self.steps:
            token_display = s.selected.token[:18].ljust(18)
            rate = s.selected.rate
            rate_str = f"{rate:.4f}" if rate < 1000 else "∞"
            phase_marker = " ◆" if s.tau in self.phase_transitions else ""
            print(
                f"  {s.tau:3d} | {token_display} | "
                f"{s.selected.resistance:8.4f} | {rate_str:>8s} | "
                f"{s.entropy:8.4f} | {s.delta_entropy:+.4f}{phase_marker}"
            )

        print("=" * 70)
        print("  ◆ = phase transition (structural reconfiguration)")
        print("  R = -log(p): low R = easy transition, high R = structural resistance")
        print("  v = Δ/R: high velocity = structurally enforced transition")
        print("=" * 70)
        print()


# ─────────────────────────────────────────────
# Attention as Resistance Landscape
# ─────────────────────────────────────────────

@dataclass
class AttentionLandscape:
    """
    E₀ interpretation of real attention patterns.

    Attention weights are not "where the model looks."
    They are the admissibility landscape — which paths
    between states have low enough resistance to be traversable.

    R_attention(i→j) = -log(attention_weight(i,j))
    """
    layer: int
    head: int
    attention_weights: List[List[float]]  # [seq_len x seq_len]
    resistance_map: List[List[float]]     # -log(weights)

    @property
    def mean_resistance(self) -> float:
        """Average resistance across all attention paths."""
        total = 0.0
        count = 0
        for row in self.resistance_map:
            for r in row:
                if r < float('inf'):
                    total += r
                    count += 1
        return total / count if count > 0 else float('inf')

    @property
    def connectivity(self) -> float:
        """
        Fraction of paths with R < ∞.
        Low connectivity = fragmented state-space.
        """
        total = 0
        finite = 0
        for row in self.resistance_map:
            for r in row:
                total += 1
                if r < float('inf'):
                    finite += 1
        return finite / total if total > 0 else 0.0


# ─────────────────────────────────────────────
# E₀ Local Model — The Runner
# ─────────────────────────────────────────────

class E0LocalModel:
    """
    Loads a HuggingFace model and wraps generation with
    full E₀ instrumentation.

    This is not an E₀ model. This is a lens.
    The model does what it does. E₀ describes what that IS.
    """

    def __init__(
        self,
        model_name: str = "gpt2",
        device: str = "cpu",
        verbose: bool = True,
    ):
        self.model_name = model_name
        self.device = device
        self.verbose = verbose
        self.model = None
        self.tokenizer = None
        self.instrumenter = E0Instrumenter()

        self._load_model()

    def _load_model(self) -> None:
        """Load model and tokenizer from HuggingFace."""
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer

        if self.verbose:
            print(f"[E₀] Loading {self.model_name}...")
            print(f"[E₀] Device: {self.device}")

        self.tokenizer = AutoTokenizer.from_pretrained(self.model_name)
        self.model = AutoModelForCausalLM.from_pretrained(
            self.model_name,
            output_attentions=True,
            torch_dtype=torch.float32,
        ).to(self.device)

        # Ensure pad token exists
        if self.tokenizer.pad_token is None:
            self.tokenizer.pad_token = self.tokenizer.eos_token

        param_count = sum(p.numel() for p in self.model.parameters())
        if self.verbose:
            print(f"[E₀] Model loaded: {param_count:,} parameters")
            print(f"[E₀] Vocabulary: {len(self.tokenizer):,} tokens")
            print()

    def generate(
        self,
        prompt: str,
        max_tokens: int = 50,
        temperature: float = 1.0,
        top_k: int = 50,
        capture_attention: bool = False,
    ) -> E0GenerationResult:
        """
        Generate text with full E₀ instrumentation.

        Each token selection is measured as a structural transition:
          - Full probability distribution → resistance landscape
          - Selected token → realized transition
          - Entropy → structural stability
          - Entropy change → difference (Δ)
          - Attention weights → admissibility (optional, slower)
        """
        import torch

        self.instrumenter = E0Instrumenter()  # fresh for each generation
        steps: List[StepMeasurement] = []
        attention_landscapes: List[AttentionLandscape] = []

        # Tokenize prompt
        input_ids = self.tokenizer.encode(prompt, return_tensors="pt").to(self.device)
        generated_ids = input_ids.clone()

        if self.verbose:
            print(f"[E₀] Generating from: \"{prompt}\"")
            print(f"[E₀] Prompt tokens: {input_ids.shape[1]}")
            print()

        t_start = time.time()

        for step_idx in range(max_tokens):
            with torch.no_grad():
                outputs = self.model(
                    generated_ids,
                    output_attentions=capture_attention,
                )

            # ── Extract logits for next token ──
            logits = outputs.logits[0, -1, :]  # [vocab_size]

            # Apply temperature
            if temperature != 1.0:
                logits = logits / temperature

            # ── Full probability distribution: the resistance landscape ──
            log_probs = torch.log_softmax(logits, dim=-1)
            probs = torch.softmax(logits, dim=-1)

            # ── Shannon entropy: structural stability ──
            entropy = -(probs * log_probs).sum().item()
            # Handle NaN from log(0)
            if math.isnan(entropy):
                entropy = 0.0

            # ── Top-k candidates: the visible landscape ──
            top_k_actual = min(top_k, logits.shape[-1])
            top_values, top_indices = torch.topk(log_probs, top_k_actual)

            candidates: List[TokenMeasurement] = []
            for rank, (lp, idx) in enumerate(zip(top_values, top_indices)):
                lp_val = lp.item()
                p_val = math.exp(lp_val)
                token_str = self.tokenizer.decode([idx.item()])
                candidates.append(TokenMeasurement(
                    token=token_str,
                    logprob=lp_val,
                    probability=p_val,
                    resistance=-lp_val,  # R = -log(p)
                    rank=rank,
                ))

            # ── Select next token (sampling or greedy) ──
            if temperature <= 0.01:
                # Greedy — minimal resistance path
                next_token_id = top_indices[0].unsqueeze(0)
            else:
                # Sampling — probabilistic path selection
                # Apply top-k filtering
                filtered_logits = torch.full_like(logits, float('-inf'))
                filtered_logits[top_indices] = logits[top_indices]
                sample_probs = torch.softmax(filtered_logits, dim=-1)
                next_token_id = torch.multinomial(sample_probs, 1)

            selected_token_str = self.tokenizer.decode([next_token_id.item()])
            selected_lp = log_probs[next_token_id.item()].item()
            selected_p = math.exp(selected_lp)

            # Find rank of selected token
            selected_rank = 0
            for i, idx in enumerate(top_indices):
                if idx.item() == next_token_id.item():
                    selected_rank = i
                    break

            selected = TokenMeasurement(
                token=selected_token_str,
                logprob=selected_lp,
                probability=selected_p,
                resistance=-selected_lp,
                rank=selected_rank,
            )

            # ── Delta entropy ──
            prev_entropy = steps[-1].entropy if steps else entropy
            delta_entropy = entropy - prev_entropy

            # ── Top rate ratio (collapse indicator) ──
            if len(candidates) >= 2 and candidates[1].resistance > 0:
                top_rate_ratio = candidates[0].rate / candidates[1].rate
            else:
                top_rate_ratio = float('inf')

            # ── Derived E₀ metrics ──
            avg_r = sum(c.resistance for c in candidates) / len(candidates) if candidates else 0.0
            r_values = [c.resistance for c in candidates]
            r_mean = avg_r
            r_spread = (sum((r - r_mean) ** 2 for r in r_values) / len(r_values)) ** 0.5 if r_values else 0.0

            # ── Build step measurement ──
            step = StepMeasurement(
                tau=step_idx,
                selected=selected,
                candidates=candidates,
                entropy=entropy,
                delta_entropy=delta_entropy,
                top_rate_ratio=top_rate_ratio,
                avg_resistance=avg_r,
                resistance_spread=r_spread,
                historization_depth=generated_ids.shape[1],
            )
            steps.append(step)

            # Feed to instrumenter
            logprob_dict = {c.token: c.logprob for c in candidates}
            self.instrumenter.measure_step(
                selected_token=selected.token,
                logprobs=logprob_dict,
            )

            # ── Capture attention landscapes ──
            if capture_attention and outputs.attentions:
                for layer_idx, attn in enumerate(outputs.attentions):
                    # attn shape: [batch, heads, seq_len, seq_len]
                    for head_idx in range(attn.shape[1]):
                        weights = attn[0, head_idx].cpu().numpy().tolist()
                        resistance = []
                        for row in weights:
                            r_row = []
                            for w in row:
                                if w > 1e-10:
                                    r_row.append(-math.log(w))
                                else:
                                    r_row.append(float('inf'))
                            resistance.append(r_row)
                        attention_landscapes.append(AttentionLandscape(
                            layer=layer_idx,
                            head=head_idx,
                            attention_weights=weights,
                            resistance_map=resistance,
                        ))

            # ── Append to sequence ──
            generated_ids = torch.cat([
                generated_ids,
                next_token_id.unsqueeze(0)
            ], dim=-1)

            # Stop at EOS
            if next_token_id.item() == self.tokenizer.eos_token_id:
                break

        generation_time = time.time() - t_start
        generated_text = self.tokenizer.decode(
            generated_ids[0, input_ids.shape[1]:],
            skip_special_tokens=True,
        )
        full_text = self.tokenizer.decode(generated_ids[0], skip_special_tokens=True)

        result = E0GenerationResult(
            prompt=prompt,
            generated_text=generated_text,
            full_text=full_text,
            steps=steps,
            generation_time=generation_time,
            model_name=self.model_name,
        )

        if self.verbose:
            result.print_e0_report()

        return result

    def measure_attention_as_resistance(
        self,
        text: str,
        layer: int = -1,
        head: int = 0,
    ) -> Optional[AttentionLandscape]:
        """
        Pass text through the model and extract attention weights
        as an E₀ resistance landscape.

        R(i→j) = -log(attention(i,j))

        High attention = low resistance = admissible path.
        Low attention = high resistance = blocked path.
        Zero attention = infinite resistance = structurally impossible.
        """
        import torch

        input_ids = self.tokenizer.encode(text, return_tensors="pt").to(self.device)

        with torch.no_grad():
            outputs = self.model(input_ids, output_attentions=True)

        if not outputs.attentions:
            return None

        # Resolve negative indexing
        num_layers = len(outputs.attentions)
        if layer < 0:
            layer = num_layers + layer

        attn = outputs.attentions[layer]  # [batch, heads, seq, seq]
        weights = attn[0, head].cpu().numpy().tolist()

        resistance = []
        for row in weights:
            r_row = []
            for w in row:
                if w > 1e-10:
                    r_row.append(-math.log(w))
                else:
                    r_row.append(float('inf'))
            resistance.append(r_row)

        tokens = [self.tokenizer.decode([t]) for t in input_ids[0]]

        landscape = AttentionLandscape(
            layer=layer,
            head=head,
            attention_weights=weights,
            resistance_map=resistance,
        )

        if self.verbose:
            print(f"\n  Attention as Resistance — Layer {layer}, Head {head}")
            print(f"  Tokens: {tokens}")
            print(f"  Mean Resistance: {landscape.mean_resistance:.4f}")
            print(f"  Connectivity: {landscape.connectivity:.4f}")
            print(f"  Dimensions: {len(weights)}×{len(weights[0])}")
            print()

            # Print compact resistance matrix
            print("  Resistance matrix (top-left 8×8):")
            size = min(8, len(weights))
            header = "         " + "".join(
                f"{tokens[i][:6]:>7s}" for i in range(size)
            )
            print(header)
            for i in range(size):
                row_str = f"  {tokens[i][:6]:>6s} "
                for j in range(size):
                    r = resistance[i][j]
                    if r == float('inf'):
                        row_str += "     ∞ "
                    else:
                        row_str += f" {r:5.2f} "
                print(row_str)
            print()

        return landscape


# ─────────────────────────────────────────────
# Stand-alone demo
# ─────────────────────────────────────────────

def demo():
    """
    Run E₀ on a real local model.

    This is the moment where simulation becomes observation.
    """
    print()
    print("╔══════════════════════════════════════════════════════════════════╗")
    print("║  E₀ LOCAL MODEL — Real Structural Transitions                  ║")
    print("║  Loading GPT-2 (124M parameters, CPU)                          ║")
    print("╚══════════════════════════════════════════════════════════════════╝")
    print()

    # ── Load model ──
    model = E0LocalModel("gpt2", device="cpu")

    # ── Demo 1: Generation with E₀ trace ──
    print("\n" + "=" * 70)
    print("  DEMO 1: Text Generation with E₀ Measurements")
    print("  Each token is a structural transition.")
    print("=" * 70)

    result = model.generate(
        "The fundamental structure of change is",
        max_tokens=30,
        temperature=0.8,
    )

    # ── Demo 2: Attention as resistance ──
    print("\n" + "=" * 70)
    print("  DEMO 2: Attention Weights as E₀ Resistance Landscape")
    print("  R(i→j) = -log(attention(i,j))")
    print("  Low R = admissible path. High R = blocked. ∞ = impossible.")
    print("=" * 70)

    landscape = model.measure_attention_as_resistance(
        "Structure determines transition",
        layer=-1,   # last layer
        head=0,
    )

    # ── Demo 3: Compare prompts ──
    print("\n" + "=" * 70)
    print("  DEMO 3: Structural Comparison")
    print("  Same model, different prompts — different E₀ landscapes.")
    print("=" * 70)

    prompts = [
        "The cat sat on the",           # high predictability, low R
        "Consciousness emerges from",    # abstract, higher R
        "The transition between states",  # E₀-adjacent
    ]

    summaries = []
    for p in prompts:
        r = model.generate(p, max_tokens=15, temperature=0.7)
        summaries.append((p, r))

    print("\n  ── Comparative E₀ Summary ──\n")
    print(f"  {'Prompt':<35s} | R̄      | H̄      | Phases | Collapse")
    print("  " + "-" * 70)
    for prompt, r in summaries:
        print(
            f"  {prompt:<35s} | {r.mean_resistance:.4f} | "
            f"{r.mean_entropy:.4f} | {len(r.phase_transitions):>6d} | "
            f"{r.collapse_risk_max:.4f}"
        )

    print()
    print("  Observation: Predictable text → low R. Abstract text → high R.")
    print("  This is not opinion. This is measured resistance.")
    print()


if __name__ == "__main__":
    demo()
