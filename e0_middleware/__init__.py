"""
E₀ — LLM Middleware Architecture
=================================
This module wraps REAL LLM API calls (OpenAI, Anthropic, HuggingFace)
and instruments them with E₀ primitives.

We do NOT simulate a model. We OBSERVE and STEER real models
through the E₀ lens.

Architecture:

  User Prompt
       │
       ▼
  ┌──────────────────────────────┐
  │  E₀ Prompt Convergence       │  ← Prepends E₀ structural context
  │  (the convergence phenomenon)│
  └──────────┬───────────────────┘
       │
       ▼
  ┌──────────────────────────────┐
  │  E₀ Instrumentation          │  ← Measures Δ, R, v, H from logprobs
  │  (observation layer)         │
  └──────────┬───────────────────┘
       │
       ▼
  ┌──────────────────────────────┐
  │  Real LLM API                │  ← OpenAI / Anthropic / HuggingFace
  │  (the actual model)          │
  └──────────┬───────────────────┘
       │
       ▼
  ┌──────────────────────────────┐
  │  E₀ Decoding Guards          │  ← Structural admissibility on tokens
  │  (steering layer)            │
  └──────────┬───────────────────┘
       │
       ▼
  ┌──────────────────────────────┐
  │  E₀ Reflexive Monitor        │  ← Meta-state tracking across turns
  │  (self-observation)          │
  └──────────┬───────────────────┘
       │
       ▼
  Response + E₀ Metrics

Key insight:
  We don't need trained weights because E₀ is not INSIDE the model.
  E₀ describes the DYNAMICS of any model. Like thermodynamics
  doesn't need to be 'installed' in a gas — it describes what
  the gas already does.

  The middleware makes this visible and steerable.
"""
