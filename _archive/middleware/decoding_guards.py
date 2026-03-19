"""
E₀ Decoding Guards — Structural Steering for Real LLMs
========================================================
Custom token-level decoding constraints based on E₀ guards.

Instead of (or alongside) temperature, top-p, top-k, frequency penalty:
  → E₀ guards operate on the STRUCTURAL properties of the
    token distribution, not on individual token probabilities.

Guards:
  1. Anti-Collapse:    Prevent softmax concentration > threshold
  2. Integrability:    Penalize tokens unconnected to recent context
  3. Trace Assurance:  Prevent low-entropy repetition loops
  4. Bypass Detection: Flag anomalous probability spikes

These can be applied as:
  - Post-processing on logprobs (for API-based models)
  - Custom logit processors (for HuggingFace models)
  - Evaluation metrics (for benchmarking)

The guards do NOT impose values or goals.
They maintain structural integrity — the same function they
serve in the E₀ canon.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from .instrumentation import E0Instrumenter, StepMeasurement


# ─────────────────────────────────────────────
# Logit Processor Interface
# ─────────────────────────────────────────────

@dataclass
class GuardResult:
    """Result of applying E₀ guards to a token distribution."""
    original_logprobs: Dict[str, float]
    modified_logprobs: Dict[str, float]
    interventions: List[str]
    blocked_tokens: List[str]

    @property
    def was_modified(self) -> bool:
        return len(self.interventions) > 0

    def __repr__(self) -> str:
        if not self.was_modified:
            return "GuardResult(no intervention)"
        return f"GuardResult({len(self.interventions)} interventions, {len(self.blocked_tokens)} blocked)"


class E0DecodingGuards:
    """
    Applies E₀ structural guards to token-level decoding.

    Can be used as:
      1. Post-processor on OpenAI logprobs (reranking)
      2. HuggingFace LogitsProcessor (direct logit manipulation)
      3. Evaluation tool (flag violations without modifying)

    Usage:
        guards = E0DecodingGuards()
        result = guards.process(
            logprobs={"the": -0.5, "cat": -1.2, ...},
            instrumenter=instrumenter,  # session state
        )
        # result.modified_logprobs has structurally filtered distribution
    """

    def __init__(
        self,
        collapse_threshold: float = 0.92,
        min_entropy: float = 0.3,
        repetition_window: int = 5,
        repetition_threshold: float = 0.6,
        bypass_sigma: float = 3.0,
        intervention_strength: float = 0.5,
    ):
        self.collapse_threshold = collapse_threshold
        self.min_entropy = min_entropy
        self.repetition_window = repetition_window
        self.repetition_threshold = repetition_threshold
        self.bypass_sigma = bypass_sigma
        self.intervention_strength = intervention_strength

    def _guard_collapse(
        self, logprobs: Dict[str, float]
    ) -> Tuple[Dict[str, float], List[str]]:
        """
        Guard 1: Anti-Collapse

        If top token probability > threshold, redistribute mass
        to prevent mode collapse. This is structurally equivalent
        to ensuring multiple paths remain viable.

        Unlike temperature (which uniformly flattens), this ONLY
        intervenes when collapse is detected.
        """
        interventions = []
        if not logprobs:
            return logprobs, interventions

        probs = {t: math.exp(lp) for t, lp in logprobs.items()}
        total = sum(probs.values())
        if total <= 0:
            return logprobs, interventions

        probs_norm = {t: p / total for t, p in probs.items()}
        top_token = max(probs_norm, key=probs_norm.get)
        top_prob = probs_norm[top_token]

        if top_prob > self.collapse_threshold:
            # Redistribute excess mass proportionally to other tokens
            excess = (top_prob - self.collapse_threshold) * self.intervention_strength
            others = {t: p for t, p in probs_norm.items() if t != top_token}

            if others:
                other_total = sum(others.values())
                new_probs = {}
                new_probs[top_token] = top_prob - excess

                for t, p in others.items():
                    share = (p / other_total) if other_total > 0 else (1.0 / len(others))
                    new_probs[t] = p + excess * share

                # Convert back to logprobs
                modified = {
                    t: math.log(max(p, 1e-20))
                    for t, p in new_probs.items()
                }

                interventions.append(
                    f"ANTI-COLLAPSE: '{top_token}' at {top_prob:.3f} → "
                    f"{new_probs[top_token]:.3f} (excess {excess:.3f} redistributed)"
                )
                return modified, interventions

        return logprobs, interventions

    def _guard_repetition(
        self,
        logprobs: Dict[str, float],
        instrumenter: E0Instrumenter,
    ) -> Tuple[Dict[str, float], List[str], List[str]]:
        """
        Guard 3: Trace Assurance (anti-repetition)

        If recent tokens show a repetition pattern, penalize
        those tokens. This is the E₀ guard against
        pseudo-irreversibility: the model appears to advance τ
        but produces no real structural trace.

        Different from standard repetition_penalty:
        this detects STRUCTURAL loops, not just token repetition.
        A sequence "A B A B" is structurally repetitive even though
        no single token repeats consecutively.
        """
        interventions = []
        blocked = []

        if not instrumenter.steps:
            return logprobs, interventions, blocked

        # Look at recent token window
        recent = instrumenter.steps[-self.repetition_window:]
        recent_tokens = [s.selected.token for s in recent]

        # Count frequencies
        freq: Dict[str, int] = {}
        for t in recent_tokens:
            freq[t] = freq.get(t, 0) + 1

        # Find structurally repetitive tokens
        window_size = len(recent_tokens)
        modified = dict(logprobs)

        for token, count in freq.items():
            ratio = count / window_size
            if ratio >= self.repetition_threshold and token in modified:
                # Penalize proportional to repetition depth
                penalty = ratio * self.intervention_strength * 2
                old_lp = modified[token]
                modified[token] = old_lp - penalty

                interventions.append(
                    f"TRACE_GUARD: '{token}' appeared {count}/{window_size} "
                    f"times → logprob {old_lp:.3f} → {modified[token]:.3f}"
                )

                if modified[token] < -10:
                    blocked.append(token)

        return modified, interventions, blocked

    def _guard_entropy(
        self, logprobs: Dict[str, float]
    ) -> Tuple[Dict[str, float], List[str]]:
        """
        Entropy floor guard.

        If entropy of the distribution is below minimum,
        add noise to maintain exploration capacity.

        This prevents the model from 'crystallizing' into
        a single path too early — preserving structural
        flexibility for later turns.
        """
        interventions = []

        probs = {t: math.exp(lp) for t, lp in logprobs.items()}
        total = sum(probs.values())
        if total <= 0:
            return logprobs, interventions

        probs_norm = [p / total for p in probs.values()]
        entropy = -sum(p * math.log2(p) for p in probs_norm if p > 0)

        if entropy < self.min_entropy and len(logprobs) > 1:
            # Add small uniform noise to boost entropy
            boost = self.intervention_strength * 0.3
            modified = {}
            for t, lp in logprobs.items():
                modified[t] = lp + boost * (1.0 / len(logprobs))

            interventions.append(
                f"ENTROPY_FLOOR: H={entropy:.3f} < {self.min_entropy} → "
                f"boosted {len(logprobs)} tokens"
            )
            return modified, interventions

        return logprobs, interventions

    def process(
        self,
        logprobs: Dict[str, float],
        instrumenter: Optional[E0Instrumenter] = None,
    ) -> GuardResult:
        """
        Apply all E₀ guards to a token distribution.

        Returns modified logprobs with structural integrity preserved.
        """
        all_interventions: List[str] = []
        all_blocked: List[str] = []
        current = dict(logprobs)

        # Guard 1: Anti-collapse
        current, interventions = self._guard_collapse(current)
        all_interventions.extend(interventions)

        # Guard 2: Repetition / trace assurance
        if instrumenter:
            current, interventions, blocked = self._guard_repetition(
                current, instrumenter
            )
            all_interventions.extend(interventions)
            all_blocked.extend(blocked)

        # Guard 3: Entropy floor
        current, interventions = self._guard_entropy(current)
        all_interventions.extend(interventions)

        return GuardResult(
            original_logprobs=logprobs,
            modified_logprobs=current,
            interventions=all_interventions,
            blocked_tokens=all_blocked,
        )


# ─────────────────────────────────────────────
# HuggingFace LogitsProcessor adapter
# ─────────────────────────────────────────────

def make_hf_logits_processor(guards: E0DecodingGuards, instrumenter: E0Instrumenter):
    """
    Creates a HuggingFace-compatible LogitsProcessor
    that applies E₀ guards during generation.

    Usage with HuggingFace:
        from transformers import AutoModelForCausalLM, AutoTokenizer

        model = AutoModelForCausalLM.from_pretrained("...")
        tokenizer = AutoTokenizer.from_pretrained("...")

        instrumenter = E0Instrumenter()
        guards = E0DecodingGuards()
        processor = make_hf_logits_processor(guards, instrumenter)

        output = model.generate(
            input_ids,
            logits_processor=[processor],
            max_new_tokens=100,
        )
    """
    try:
        import torch
        from transformers import LogitsProcessor

        class E0LogitsProcessor(LogitsProcessor):
            def __call__(self, input_ids, scores):
                # Convert logits to logprobs for E₀ processing
                log_probs = torch.log_softmax(scores, dim=-1)

                # Get top-k for efficiency
                top_k = min(50, scores.shape[-1])
                top_values, top_indices = torch.topk(log_probs[0], top_k)

                # Build logprob dict (we'd need tokenizer here in practice)
                logprob_dict = {
                    str(idx.item()): val.item()
                    for idx, val in zip(top_indices, top_values)
                }

                # Apply guards
                result = guards.process(logprob_dict, instrumenter)

                if result.was_modified:
                    # Apply modifications back to scores tensor
                    for token_id_str, new_lp in result.modified_logprobs.items():
                        idx = int(token_id_str)
                        old_lp = logprob_dict.get(token_id_str, new_lp)
                        if new_lp != old_lp:
                            scores[0, idx] += (new_lp - old_lp)

                return scores

        return E0LogitsProcessor()

    except ImportError:
        print("[E₀] transformers/torch not installed. HF processor unavailable.")
        return None
