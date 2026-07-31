"""Tests for the development-only G1 mechanism diagnosis."""

from __future__ import annotations

import unittest

from .g1_ablations import DecisionRecord
from .g1_mechanism_diagnosis import (
    _GateAccumulator,
    _PairAccumulator,
    diagnose_development_mechanism,
    summarize_episode_evidence,
)


def _record(
    *,
    method: str = "B_INCOHERENT",
    greedy: str = "A",
    preferred: str = "B",
    selected: str = "A",
    confidence: float = 0.2,
    imbalance: float = 1.0,
    override: bool = False,
    probabilities=None,
) -> DecisionRecord:
    return DecisionRecord(
        method=method,
        state="S",
        candidates=("A", "B"),
        greedy_action=greedy,
        preferred_action=preferred,
        selected_action=selected,
        scores={"A": 0.4, "B": 0.6},
        probabilities=probabilities or {"A": 0.4, "B": 0.6},
        path_counts={"A": 2, "B": 2},
        path_family_signature="same",
        paths_expanded=4,
        path_cap_hit=False,
        confidence=confidence,
        path_imbalance=imbalance,
        override=override,
        phase_regime=None,
    )


class TestGateAccumulator(unittest.TestCase):
    def test_separates_confidence_and_imbalance_blockers(self):
        accumulator = _GateAccumulator()
        accumulator.add(
            _record(confidence=0.2, imbalance=1.0),
            min_confidence=0.85,
            max_imbalance=3.0,
        )
        accumulator.add(
            _record(confidence=0.9, imbalance=4.0),
            min_confidence=0.85,
            max_imbalance=3.0,
        )
        accumulator.add(
            _record(confidence=0.2, imbalance=4.0),
            min_confidence=0.85,
            max_imbalance=3.0,
        )

        result = accumulator.to_record()
        self.assertEqual(result["greedy_preferred_disagreements"], 3)
        self.assertEqual(result["blocked_by_confidence"], 2)
        self.assertEqual(result["blocked_by_imbalance"], 2)
        self.assertEqual(result["blocked_by_both"], 1)
        self.assertEqual(result["disagreement_joint_passes"], 0)
        self.assertEqual(result["counterfactual_confidence_sweep"]["0.00"], 1)
        self.assertEqual(result["counterfactual_confidence_sweep"]["0.85"], 0)

    def test_joint_gate_pass_matches_override_shape(self):
        accumulator = _GateAccumulator()
        accumulator.add(
            _record(
                confidence=0.9,
                imbalance=1.0,
                selected="B",
                override=True,
            ),
            min_confidence=0.85,
            max_imbalance=3.0,
        )

        result = accumulator.to_record()
        self.assertEqual(result["disagreement_joint_passes"], 1)
        self.assertEqual(result["overrides"], 1)


class TestPairAccumulator(unittest.TestCase):
    def test_distinguishes_scores_preference_and_selection(self):
        left = {(0, 0): _record()}
        right = {
            (0, 0): _record(
                method="C_THETA_ZERO",
                probabilities={"A": 0.3, "B": 0.7},
            )
        }
        accumulator = _PairAccumulator()
        accumulator.compare(left, right)
        result = accumulator.to_record()

        self.assertEqual(result["probability_vector_divergences"], 1)
        self.assertEqual(result["score_ranking_divergences"], 0)
        self.assertEqual(result["preferred_action_divergences"], 0)
        self.assertEqual(result["selected_action_divergences"], 0)


class TestEpisodeEvidence(unittest.TestCase):
    def test_summarizes_only_lookahead_methods(self):
        records = [
            {
                "method": "D_U1_PHASE",
                "decision_count": 4,
                "override_count": 0,
                "override_success_count": 0,
                "path_cap_hits": 0,
                "phase_regime_gradient_count": 4,
                "phase_regime_interfering_count": 0,
                "phase_regime_wrapped_count": 0,
                "commit": "abc123",
                "holdout_accessed": False,
                "not_g1_result": True,
            },
            {
                "method": "A_STAR",
                "decision_count": 4,
                "override_count": 0,
                "override_success_count": 0,
                "path_cap_hits": 0,
            },
        ]
        result = summarize_episode_evidence(records)

        self.assertEqual(result["total_lookahead_decisions"], 4)
        self.assertEqual(result["total_overrides"], 0)
        self.assertEqual(result["source_commits"], ["abc123"])
        self.assertEqual(result["holdout_violations"], 0)
        self.assertEqual(result["gate_flag_violations"], 0)
        self.assertEqual(
            result["methods"]["D_U1_PHASE"]["phase_regimes"]["gradient"],
            4,
        )


class TestDevelopmentProbe(unittest.TestCase):
    def test_small_probe_is_development_only_and_complete(self):
        result = diagnose_development_mechanism(
            families=["wall_grid"],
            scales=[100],
            seeds=[0],
            episode_count=1,
            interaction_budget=1,
        )

        self.assertFalse(result["holdout_accessed"])
        self.assertTrue(result["not_g1_result"])
        self.assertEqual(result["probe"]["domain_count"], 1)
        for method in result["probe"]["methods"]:
            self.assertEqual(result["per_method"][method]["decisions"], 1)
        comparison = result["pairwise"]["B_INCOHERENT_vs_E_FULL_GEOMETRY"]
        self.assertEqual(comparison["comparable_decisions"], 1)
        self.assertEqual(comparison["selected_action_divergences"], 0)

    def test_rejects_holdout_seed(self):
        with self.assertRaises(ValueError):
            diagnose_development_mechanism(
                families=["wall_grid"],
                scales=[100],
                seeds=[10_000],
                episode_count=1,
                interaction_budget=1,
            )


if __name__ == "__main__":
    unittest.main()
