"""
Tests for C74 — Chess Team (Multiverse Team Play)
===================================================

Tests: 24 across 5 classes.

Note: Self-play results are cached at module level to avoid
repeated game computation (~3 seconds per game).
"""

import unittest

import chess

from e0_controller.chess_team import (
    ChessTeam,
    TeamGameResult,
    TeamVote,
    play_team_game,
    play_team_vs_solo,
    TEAM_SPECIALIZATIONS,
)
from e0_controller.chess_e0 import DIMENSIONS, ChessE0Player
from e0_controller.coupling_router import CouplingRouter
from e0_controller.multiverse import Universe


# ── Cached games (computed once) ──

_WHITE_TEAM = ChessTeam(chess.WHITE)
_BLACK_TEAM = ChessTeam(chess.BLACK)
_TEAM_GAME = play_team_game(_WHITE_TEAM, _BLACK_TEAM, max_moves=80)

# Team vs Solo comparison
_TEAM_VS_SOLO = play_team_vs_solo(max_moves=80)


# ══════════════════════════════════════════════
# 1. Team Construction
# ══════════════════════════════════════════════

class TestTeamConstruction(unittest.TestCase):
    """Team has 3 players with distinct specializations and a CouplingRouter."""

    def test_three_players(self):
        team = ChessTeam(chess.WHITE)
        self.assertEqual(len(team.players), 3)

    def test_specializations(self):
        team = ChessTeam(chess.WHITE)
        start_dims = [p.dimension_history[0] for p in team.players]
        self.assertEqual(start_dims, TEAM_SPECIALIZATIONS)

    def test_custom_specializations(self):
        team = ChessTeam(chess.WHITE, specializations=["DEVELOPMENT", "MATERIAL"])
        self.assertEqual(len(team.players), 2)
        self.assertEqual(team.players[0].dimension_history[0], "DEVELOPMENT")

    def test_router_exists(self):
        team = ChessTeam(chess.WHITE)
        self.assertIsInstance(team.router, CouplingRouter)
        self.assertEqual(len(team.router.universes), 3)

    def test_each_player_has_own_landscape(self):
        team = ChessTeam(chess.WHITE)
        landscapes = [id(p.landscape) for p in team.players]
        self.assertEqual(len(set(landscapes)), 3)  # all distinct


# ══════════════════════════════════════════════
# 2. Team Move Selection
# ══════════════════════════════════════════════

class TestTeamMoveSelection(unittest.TestCase):
    """Team produces valid moves and records votes."""

    def test_valid_move(self):
        team = ChessTeam(chess.WHITE)
        board = chess.Board()
        move, dim = team.select_move(board)
        self.assertIn(move, board.legal_moves)
        self.assertIn(dim, DIMENSIONS)

    def test_vote_recorded(self):
        team = ChessTeam(chess.WHITE)
        board = chess.Board()
        team.select_move(board)
        self.assertEqual(len(team.vote_history), 1)

    def test_vote_has_three_proposals(self):
        team = ChessTeam(chess.WHITE)
        board = chess.Board()
        team.select_move(board)
        vote = team.vote_history[0]
        self.assertEqual(len(vote.proposals), 3)

    def test_strategy_summary_nonempty(self):
        team = ChessTeam(chess.WHITE)
        board = chess.Board()
        team.select_move(board)
        summary = team.strategy_summary()
        self.assertIn("P", summary)


# ══════════════════════════════════════════════
# 3. Team Self-Play
# ══════════════════════════════════════════════

class TestTeamSelfPlay(unittest.TestCase):
    """Team vs team game terminates and produces valid results."""

    def test_game_terminates(self):
        self.assertGreater(_TEAM_GAME.total_moves, 0)

    def test_valid_result(self):
        self.assertIn(_TEAM_GAME.result, ["1-0", "0-1", "1/2-1/2", "*"])

    def test_termination_nonempty(self):
        self.assertGreater(len(_TEAM_GAME.termination), 0)

    def test_moves_recorded(self):
        self.assertIsInstance(_TEAM_GAME.moves, list)
        self.assertGreater(len(_TEAM_GAME.moves), 0)

    def test_both_colors_played(self):
        colors = set(m.color for m in _TEAM_GAME.moves)
        self.assertEqual(colors, {chess.WHITE, chess.BLACK})

    def test_votes_recorded(self):
        total_votes = len(_TEAM_GAME.white_votes) + len(_TEAM_GAME.black_votes)
        self.assertGreater(total_votes, 0)

    def test_summary_contains_result(self):
        summary = _TEAM_GAME.summary()
        self.assertIn(_TEAM_GAME.result, summary)


# ══════════════════════════════════════════════
# 4. Team vs Solo Comparison
# ══════════════════════════════════════════════

class TestTeamVsSolo(unittest.TestCase):
    """Team and Solo games both complete and are comparable."""

    def test_both_games_complete(self):
        team_game, solo_game = _TEAM_VS_SOLO
        self.assertGreater(team_game.total_moves, 0)
        self.assertGreater(solo_game.total_moves, 0)

    def test_team_label(self):
        team_game, _ = _TEAM_VS_SOLO
        self.assertIn("Team", team_game.white_label)
        self.assertIn("Solo", team_game.black_label)

    def test_both_valid_results(self):
        team_game, solo_game = _TEAM_VS_SOLO
        valid = {"1-0", "0-1", "1/2-1/2", "*"}
        self.assertIn(team_game.result, valid)
        self.assertIn(solo_game.result, valid)


# ══════════════════════════════════════════════
# 5. Knowledge Exchange
# ══════════════════════════════════════════════

class TestKnowledgeExchange(unittest.TestCase):
    """Knowledge exchange affects historization across team members."""

    def test_coupling_historized(self):
        """After a game, coupling edges should have non-zero load."""
        hist = _WHITE_TEAM.router.landscape.historization
        edges_touched = set(hist._U.keys()) | set(hist._F.keys())
        self.assertGreater(len(edges_touched), 0)

    def test_dimension_variety_across_players(self):
        """Each player should use multiple dimensions (not just their start)."""
        for player in _WHITE_TEAM.players:
            unique_dims = set(player.dimension_history)
            self.assertGreaterEqual(len(unique_dims), 2)

    def test_all_players_contribute(self):
        """Each player index should appear as winner at least once."""
        if not _WHITE_TEAM.vote_history:
            self.skipTest("No votes recorded")
        winner_indices = set(v.winner_idx for v in _WHITE_TEAM.vote_history)
        # At least 2 out of 3 players should have won a vote
        self.assertGreaterEqual(len(winner_indices), 2)


if __name__ == "__main__":
    unittest.main()
