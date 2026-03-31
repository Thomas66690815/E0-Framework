"""
Tests for E₀ Chess Engine (C72)
================================

Deterministic tests for strategic dimension evaluation,
move selection, E₀ player integration, and self-play.
"""

from __future__ import annotations

import unittest

import chess

from e0_controller.primitives import Edge
from e0_controller.chess_e0 import (
    DIMENSIONS,
    evaluate_dimension,
    evaluate_material,
    evaluate_king_safety,
    evaluate_center_control,
    evaluate_piece_activity,
    evaluate_pawn_structure,
    evaluate_development,
    dimension_profile,
    best_move_for_dimension,
    ChessE0Player,
    play_game,
)


# ══════════════════════════════════════════════
# Module-level cache: play one game for multi-property testing
# ══════════════════════════════════════════════

_WHITE = ChessE0Player(chess.WHITE)
_BLACK = ChessE0Player(chess.BLACK)
_GAME = play_game(_WHITE, _BLACK, max_moves=80)


# ══════════════════════════════════════════════
# Test Class 1: Dimension Evaluators
# ══════════════════════════════════════════════

class TestDimensionEvaluators(unittest.TestCase):
    """Each dimension evaluator returns correct values for known positions."""

    def test_starting_material_zero(self):
        board = chess.Board()
        self.assertEqual(evaluate_material(board, chess.WHITE), 0.0)
        self.assertEqual(evaluate_material(board, chess.BLACK), 0.0)

    def test_material_after_capture(self):
        board = chess.Board()
        board.push_san("e4")
        board.push_san("d5")
        board.push_san("exd5")
        self.assertEqual(evaluate_material(board, chess.WHITE), 1.0)
        self.assertEqual(evaluate_material(board, chess.BLACK), -1.0)

    def test_king_safety_starting_has_castling(self):
        board = chess.Board()
        score = evaluate_king_safety(board, chess.WHITE)
        self.assertGreaterEqual(score, 2.0)  # Both castling rights

    def test_center_control_after_e4(self):
        board = chess.Board()
        before = evaluate_center_control(board, chess.WHITE)
        board.push_san("e4")
        after = evaluate_center_control(board, chess.WHITE)
        self.assertGreater(after, before)

    def test_piece_activity_symmetric_at_start(self):
        board = chess.Board()
        w = evaluate_piece_activity(board, chess.WHITE)
        b = evaluate_piece_activity(board, chess.BLACK)
        self.assertEqual(w, b)

    def test_pawn_structure_starting_positive(self):
        board = chess.Board()
        score = evaluate_pawn_structure(board, chess.WHITE)
        self.assertGreater(score, 0.0)  # All connected, none isolated

    def test_development_zero_at_start(self):
        board = chess.Board()
        self.assertEqual(evaluate_development(board, chess.WHITE), 0.0)
        self.assertEqual(evaluate_development(board, chess.BLACK), 0.0)

    def test_development_after_knight_move(self):
        board = chess.Board()
        board.push_san("Nf3")
        self.assertEqual(evaluate_development(board, chess.WHITE), 1.0)
        self.assertEqual(evaluate_development(board, chess.BLACK), 0.0)

    def test_dimension_profile_all_present(self):
        board = chess.Board()
        profile = dimension_profile(board, chess.WHITE)
        for dim in DIMENSIONS:
            self.assertIn(dim, profile)


# ══════════════════════════════════════════════
# Test Class 2: Move Selection
# ══════════════════════════════════════════════

class TestBestMoveSelection(unittest.TestCase):
    """Move selection picks moves that improve the chosen dimension."""

    def test_picks_capture_for_material(self):
        board = chess.Board()
        board.push_san("e4")
        board.push_san("d5")
        move = best_move_for_dimension("MATERIAL", board, chess.WHITE)
        mat_before = evaluate_material(board, chess.WHITE)
        board.push(move)
        mat_after = evaluate_material(board, chess.WHITE)
        self.assertGreater(mat_after, mat_before)

    def test_picks_development_move(self):
        board = chess.Board()
        move = best_move_for_dimension("DEVELOPMENT", board, chess.WHITE)
        dev_before = evaluate_development(board, chess.WHITE)
        board.push(move)
        dev_after = evaluate_development(board, chess.WHITE)
        self.assertGreater(dev_after, dev_before)

    def test_always_returns_a_move(self):
        board = chess.Board()
        for dim in DIMENSIONS:
            move = best_move_for_dimension(dim, board, chess.WHITE)
            self.assertIsNotNone(move)
            self.assertIn(move, board.legal_moves)


# ══════════════════════════════════════════════
# Test Class 3: ChessE0Player
# ══════════════════════════════════════════════

class TestChessE0Player(unittest.TestCase):
    """ChessE0Player integrates E₀ controller with chess."""

    def test_landscape_has_all_dimensions(self):
        player = ChessE0Player(chess.WHITE)
        for dim in DIMENSIONS:
            self.assertIn(dim, player.landscape.states)

    def test_landscape_fully_connected(self):
        player = ChessE0Player(chess.WHITE)
        expected = len(DIMENSIONS) * (len(DIMENSIONS) - 1)
        self.assertEqual(player.landscape.edge_count(), expected)

    def test_select_move_returns_valid_move(self):
        player = ChessE0Player(chess.WHITE)
        board = chess.Board()
        move, dim = player.select_move(board)
        self.assertIn(move, board.legal_moves)
        self.assertIn(dim, DIMENSIONS)

    def test_dimension_recorded_in_history(self):
        player = ChessE0Player(chess.WHITE)
        board = chess.Board()
        _, dim = player.select_move(board)
        self.assertEqual(player.dimension_history[-1], dim)
        self.assertEqual(len(player.dimension_history), 2)  # initial + 1

    def test_strategy_summary_nonempty(self):
        player = ChessE0Player(chess.WHITE)
        board = chess.Board()
        player.select_move(board)
        s = player.strategy_summary()
        self.assertGreater(len(s), 0)


# ══════════════════════════════════════════════
# Test Class 4: Self-Play
# ══════════════════════════════════════════════

class TestSelfPlay(unittest.TestCase):
    """Complete self-play game produces valid results."""

    def test_game_terminates(self):
        self.assertGreater(_GAME.total_moves, 0)

    def test_result_is_valid(self):
        self.assertIn(_GAME.result, ["1-0", "0-1", "1/2-1/2", "*"])

    def test_termination_nonempty(self):
        self.assertGreater(len(_GAME.termination), 0)

    def test_moves_recorded(self):
        self.assertEqual(len(_GAME.moves), _GAME.total_moves)

    def test_both_colors_played(self):
        self.assertGreater(len(_GAME.white_dimensions), 0)
        self.assertGreater(len(_GAME.black_dimensions), 0)

    def test_summary_contains_result(self):
        s = _GAME.summary()
        self.assertIn(_GAME.result, s)
        self.assertIn("E₀ Chess", s)


# ══════════════════════════════════════════════
# Test Class 5: Historization Learning
# ══════════════════════════════════════════════

class TestHistorizationLearning(unittest.TestCase):
    """E₀ landscape historization accumulates during a game."""

    def test_some_edges_historized(self):
        has_history = False
        for a in DIMENSIONS:
            for b in DIMENSIONS:
                if a != b:
                    e = Edge(a, b)
                    load = _WHITE.landscape.historization.trace_load(e)
                    if load > 0:
                        has_history = True
                        break
            if has_history:
                break
        self.assertTrue(has_history, "No edges were historized during the game")

    def test_quality_varies_across_edges(self):
        qualities = set()
        for a in DIMENSIONS:
            for b in DIMENSIONS:
                if a != b:
                    e = Edge(a, b)
                    q = _WHITE.landscape.historization.trace_quality(e)
                    qualities.add(round(q, 4))
        self.assertGreater(len(qualities), 1)

    def test_dimension_variety_in_game(self):
        """Player uses at least 3 different dimensions."""
        unique = set(_WHITE.dimension_history[1:])
        self.assertGreaterEqual(len(unique), 3)


if __name__ == "__main__":
    unittest.main()
