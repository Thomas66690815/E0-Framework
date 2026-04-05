"""
E₀ Visual Pretraining (C164)
===============================
LLM-powered pretraining for the perception→rendering mapping.

Solves the cold-start problem for learnable rendering selection:
the perception landscape has initial heuristics for which widget
(heatmap, tree, ...) fits which perception primitive, but no real
experience. This module lets an LLM act as a **synthetic evaluator**,
generating feedback that builds trace mass before any real user sees
the UI.

Process:
    1. For each perception→rendering edge, ask the LLM to evaluate
       suitability (score 0–10).
    2. Map score → outcome (SUCCESS/FAILURE) → historize.
    3. Repeat for N rounds, building up trace_load.
    4. Save the trained perception domain to a memo file.

The LLM's evaluations are treated as hypothesis (§4.1 Learn Mode) —
the system starts cautious and refines through real user feedback later.

Usage (mock — no API key):
    py -3 -m e0_controller.visual_pretraining --mock

Usage (live LLM):
    py -3 -m e0_controller.visual_pretraining

See docs/E0_HUMAN_COMMUNICATION_DESIGN_v1.md §8.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from .communication import IntentType
from .perception import (
    RENDERING_PRIMITIVES,
    VISUAL_PRIMITIVES,
    PerceptionDomain,
    build_perception_domain,
)
from .primitives import Edge, Outcome
from .llm_adapter import LLMConfig, LLMCallFn, _parse_json_response


# ──────────────────────────────────────────────
# 1. Evaluation Prompt
# ──────────────────────────────────────────────

_SYSTEM = """\
You evaluate UI rendering choices for a structural reasoning system.

The system has perception primitives (how it perceives information):
  emphasis, contrast, hierarchy, sequence, grouping, density, motion,
  proximity, label, absence

And rendering widgets (how it displays information):
  heatmap, tree, timeline, bar, text, highlight, dashboard

Your job: rate how well a rendering widget fits a perception primitive
for a given communication intent. Consider visual clarity, cognitive
load, and information density."""

_EVAL_PROMPT = """\
Rate this rendering choice on a scale of 0-10:

Intent: {intent}
Perception: {perception}
Rendering widget: {rendering}
Context: {context}

Score meaning:
  0-2: Terrible fit — confusing or misleading
  3-4: Poor fit — works but suboptimal
  5-6: Acceptable — reasonable default
  7-8: Good fit — clear and effective
  9-10: Excellent fit — optimal for this combination

Respond with exactly this JSON (no other text):
{{"score": <int 0-10>, "reasoning": "<one sentence>"}}"""


# ──────────────────────────────────────────────
# 2. Score → Outcome Mapping
# ──────────────────────────────────────────────

def score_to_outcome(score: int) -> Outcome:
    """Map LLM evaluation score to E0 Outcome.

    0-4 → FAILURE (bad rendering choice)
    5-6 → SUCCESS (acceptable, mild positive)
    7-10 → SUCCESS (good to excellent)
    """
    if score <= 4:
        return Outcome.FAILURE
    return Outcome.SUCCESS


# ──────────────────────────────────────────────
# 3. Evaluation Result
# ──────────────────────────────────────────────

@dataclass(frozen=True)
class RenderingEval:
    """One LLM evaluation of a perception→rendering pairing."""
    perception: str
    rendering: str
    intent: str
    score: int
    reasoning: str
    outcome: Outcome


@dataclass
class PretrainingResult:
    """Summary of a pretraining run."""
    rounds: int
    evaluations: List[RenderingEval]
    memo_path: Optional[str] = None

    @property
    def total_evals(self) -> int:
        return len(self.evaluations)

    @property
    def success_rate(self) -> float:
        if not self.evaluations:
            return 0.0
        s = sum(1 for e in self.evaluations if e.outcome == Outcome.SUCCESS)
        return s / len(self.evaluations)

    def summary(self) -> str:
        lines = [
            f"Pretraining: {self.rounds} rounds, "
            f"{self.total_evals} evaluations",
            f"Success rate: {self.success_rate:.0%}",
        ]
        if self.memo_path:
            lines.append(f"Saved to: {self.memo_path}")
        return "\n".join(lines)


# ──────────────────────────────────────────────
# 4. Intent → Context Descriptions
# ──────────────────────────────────────────────

_INTENT_CONTEXTS: Dict[str, str] = {
    "uncertainty": "Component health is uncertain — user needs to quickly "
                   "identify which parts of the system are at risk.",
    "decision": "The system has reached a decision point — user needs to "
                "see the alternatives and their structural implications.",
    "pattern": "A recurring pattern has been detected — user needs to see "
               "the temporal or sequential structure of the pattern.",
    "request": "The system lacks data and is requesting input — user needs "
               "a clear, focused prompt for the missing information.",
    "status": "System overview — user needs a summary of all component "
              "states and their health metrics.",
    "anomaly": "An anomaly has been detected — user needs to immediately "
               "see what is abnormal and how it differs from expected.",
}


# ──────────────────────────────────────────────
# 5. Core Pretraining Loop
# ──────────────────────────────────────────────

def run_pretraining(
    domain: PerceptionDomain,
    llm_call: LLMCallFn,
    *,
    config: Optional[LLMConfig] = None,
    rounds: int = 3,
    intents: Optional[List[str]] = None,
) -> PretrainingResult:
    """Run LLM-powered pretraining on perception→rendering edges.

    For each round, iterates over all perception→rendering edges
    and all intent contexts, asks the LLM to evaluate the fit,
    and historizes the result.

    Args:
        domain: The perception domain to train.
        llm_call: LLM call function (real or mock).
        config: LLM configuration. Uses defaults if None.
        rounds: Number of pretraining rounds.
        intents: Intent types to evaluate. Defaults to all 6.

    Returns:
        PretrainingResult with all evaluations.
    """
    if config is None:
        config = LLMConfig()
    if intents is None:
        intents = list(_INTENT_CONTEXTS.keys())

    hist = domain.landscape.historization
    evaluations: List[RenderingEval] = []

    for round_idx in range(rounds):
        for perception in VISUAL_PRIMITIVES:
            for rendering in RENDERING_PRIMITIVES:
                if not domain.landscape.has_edge(perception, rendering):
                    continue
                edge = Edge(perception, rendering)

                for intent in intents:
                    context = _INTENT_CONTEXTS.get(intent, intent)
                    prompt = _EVAL_PROMPT.format(
                        intent=intent,
                        perception=perception,
                        rendering=rendering,
                        context=context,
                    )
                    try:
                        raw = llm_call(_SYSTEM, prompt, config)
                        data = _parse_json_response(raw, ["score"])
                        score = int(data["score"])
                        score = max(0, min(10, score))
                        reasoning = data.get("reasoning", "")
                    except Exception:
                        score = 5
                        reasoning = "evaluation failed, using neutral"

                    outcome = score_to_outcome(score)
                    hist.update(edge, outcome)

                    evaluations.append(RenderingEval(
                        perception=perception,
                        rendering=rendering,
                        intent=intent,
                        score=score,
                        reasoning=reasoning,
                        outcome=outcome,
                    ))

    return PretrainingResult(
        rounds=rounds,
        evaluations=evaluations,
    )


# ──────────────────────────────────────────────
# 6. Mock LLM for Testing
# ──────────────────────────────────────────────

# Reasonable heuristic scores for each (perception, rendering) pair.
_MOCK_SCORES: Dict[tuple, int] = {
    ("emphasis", "heatmap"): 8,
    ("emphasis", "highlight"): 9,
    ("emphasis", "bar"): 6,
    ("hierarchy", "tree"): 9,
    ("hierarchy", "dashboard"): 6,
    ("sequence", "timeline"): 9,
    ("grouping", "dashboard"): 8,
    ("density", "heatmap"): 8,
    ("contrast", "highlight"): 8,
    ("contrast", "bar"): 7,
    ("label", "text"): 8,
    ("motion", "timeline"): 7,
    ("absence", "text"): 7,
    ("proximity", "dashboard"): 6,
}


def mock_eval_call(system: str, user: str, config: LLMConfig) -> str:
    """Deterministic mock that returns heuristic scores."""
    # Parse perception and rendering from the prompt
    perception = ""
    rendering = ""
    for line in user.split("\n"):
        if line.startswith("Perception:"):
            perception = line.split(":", 1)[1].strip()
        elif line.startswith("Rendering widget:"):
            rendering = line.split(":", 1)[1].strip()

    score = _MOCK_SCORES.get((perception, rendering), 5)
    return json.dumps({
        "score": score,
        "reasoning": f"Mock evaluation: {perception}→{rendering}",
    })


# ──────────────────────────────────────────────
# 7. CLI Entry Point
# ──────────────────────────────────────────────

def main() -> None:
    """Run visual pretraining from the command line."""
    import sys

    use_mock = "--mock" in sys.argv
    rounds = 3
    for arg in sys.argv[1:]:
        if arg.startswith("--rounds="):
            rounds = int(arg.split("=", 1)[1])

    memo_path = "memos/perception_pretrained.json"
    for arg in sys.argv[1:]:
        if arg.startswith("--output="):
            memo_path = arg.split("=", 1)[1]

    print("=" * 60)
    print("  E₀ Visual Pretraining (C164)")
    print("=" * 60)

    domain = build_perception_domain()
    print(f"\n  Domain: {len(domain.primitives)} primitives, "
          f"{len(domain.landscape.edges)} edges")
    print(f"  Rendering primitives: {domain.rendering_primitives}")

    if use_mock:
        print("  Mode: MOCK (deterministic)")
        llm_call = mock_eval_call
    else:
        from .llm_adapter import openai_call
        print("  Mode: LIVE (OpenAI API)")
        llm_call = openai_call

    print(f"  Rounds: {rounds}")
    print()

    result = run_pretraining(
        domain, llm_call, rounds=rounds,
    )

    # Show results
    print(f"\n  Evaluations: {result.total_evals}")
    print(f"  Success rate: {result.success_rate:.0%}")

    # Show top rendering choices per perception
    print("\n  Learned rendering preferences:")
    for vp in VISUAL_PRIMITIVES:
        rend = domain.suggest_rendering(vp)
        edge = Edge(vp, rend)
        if domain.landscape.has_edge(vp, rend):
            q = domain.landscape.historization.trace_quality(edge)
            load = domain.landscape.historization.trace_load(edge)
            print(f"    {vp:12s} → {rend:12s}  "
                  f"(quality={q:+.3f}, load={load:.1f})")
        else:
            print(f"    {vp:12s} → {rend:12s}  (no edge)")

    # Save
    resolved = domain.save_state(memo_path)
    result.memo_path = str(resolved)
    print(f"\n  Saved to: {resolved}")

    print("\n" + "=" * 60)
    print("  Pretraining complete.")
    print("  Load with: PerceptionDomain.from_saved(path)")
    print("=" * 60)


if __name__ == "__main__":
    main()
