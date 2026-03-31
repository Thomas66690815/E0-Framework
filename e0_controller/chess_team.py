"""
E₀ Chess Teams — Multiverse Team Play (C74)
=============================================

Two teams of 3 E₀ players compete at chess. Within each team,
players share knowledge via CouplingRouter; between teams,
the board is the only interface.

Architecture::

    Team White                    Team Black
    ┌─────────────────┐           ┌─────────────────┐
    │ P1: MATERIAL    │           │ P1: MATERIAL    │
    │ P2: KING_SAFETY │──board──→ │ P2: KING_SAFETY │
    │ P3: CENTER_CTRL │           │ P3: CENTER_CTRL │
    └────────┬────────┘           └────────┬────────┘
         CouplingRouter               CouplingRouter
       (knowledge_exchange)          (knowledge_exchange)

Per move:
1. All 3 players evaluate the position independently → (move, dimension)
2. CouplingRouter selects best partner pair for knowledge exchange
3. Transferred edges update teammates' landscapes
4. The player whose dimension has the best cumulative trace_quality
   determines the team's move
5. All 3 players historize the outcome

Comparison metric: Team (3×E₀) vs Solo (1×E₀)
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import chess

from e0_controller.primitives import Edge, Outcome
from e0_controller.landscape import Landscape
from e0_controller.multiverse import Universe
from e0_controller.coupling_router import CouplingRouter, CouplingReason
from e0_controller.chess_e0 import (
    ChessE0Player, ChessGameResult, MoveRecord,
    DIMENSIONS, evaluate_dimension, play_game,
)


# ══════════════════════════════════════════════
# Team
# ══════════════════════════════════════════════

# Each player specializes in a different starting dimension
TEAM_SPECIALIZATIONS = ["MATERIAL", "KING_SAFETY", "CENTER_CONTROL"]


class ChessTeam:
    """A team of 3 E₀ players sharing knowledge via CouplingRouter.

    Each player starts from a different strategic dimension,
    developing a distinct perspective on positions.  Knowledge
    exchange lets productive patterns spread across the team.
    """

    def __init__(
        self,
        color: chess.Color,
        *,
        specializations: Optional[List[str]] = None,
    ):
        self.color = color
        specs = specializations or TEAM_SPECIALIZATIONS
        self.players: List[ChessE0Player] = [
            ChessE0Player(color, start_dim=dim)
            for dim in specs
        ]
        # Wrap players as Universe objects for CouplingRouter
        self._universes = self._build_universes()
        self.router = CouplingRouter(
            self._universes,
            base_resistance=1.0,
        )
        self.vote_history: List[TeamVote] = []

    def _build_universes(self) -> List[Universe]:
        """Wrap each player's landscape as a Universe for coupling."""
        universes = []
        for i, player in enumerate(self.players):
            name = f"{'W' if self.color == chess.WHITE else 'B'}_P{i}"
            universes.append(Universe(
                name=name,
                landscape=player.landscape,
                execute_fn=player._execute_fn,
                start=player.current_dim,
                goal="",   # no fixed goal — dimension navigation
            ))
        return universes

    def select_move(self, board: chess.Board) -> Tuple[chess.Move, str]:
        """Team decision: all evaluate → exchange → best quality wins.

        Returns:
            (move, dimension) — the team's chosen move and strategic focus.
        """
        # 1. All players evaluate independently
        proposals: List[Tuple[chess.Move, str, int]] = []
        for i, player in enumerate(self.players):
            move, dim = player.select_move(board)
            proposals.append((move, dim, i))

        # 2. Knowledge exchange: best pair via CouplingRouter
        self._exchange_knowledge()

        # 3. Select: player whose dimension has best cumulative quality wins
        best_idx = 0
        best_quality = float("-inf")
        for move, dim, i in proposals:
            player = self.players[i]
            # Cumulative quality of transitions INTO this dimension
            quality = self._dimension_quality(player, dim)
            if quality > best_quality:
                best_quality = quality
                best_idx = i

        chosen_move, chosen_dim, _ = proposals[best_idx]

        # Record vote
        self.vote_history.append(TeamVote(
            proposals=[(m.uci(), d, i) for m, d, i in proposals],
            winner_idx=best_idx,
            winner_dim=chosen_dim,
            winner_quality=best_quality,
        ))

        return chosen_move, chosen_dim

    def _exchange_knowledge(self) -> None:
        """One round of knowledge exchange between team members.

        The player with the worst recent performance requests
        knowledge from the best-rated partner.
        """
        # Find the player with the most recent FAILUREs
        worst_idx = 0
        worst_quality = float("inf")
        for i, player in enumerate(self.players):
            hist = player.landscape.historization
            edges_touched = set(hist._U.keys()) | set(hist._F.keys())
            if not edges_touched:
                continue
            avg_q = sum(hist.trace_quality(e) for e in edges_touched) / len(edges_touched)
            if avg_q < worst_quality:
                worst_quality = avg_q
                worst_idx = i

        requester = self._universes[worst_idx]
        selections = self.router.select_partner(
            requester, CouplingReason.RECOVERY,
        )
        if not selections:
            return

        donor = selections[0].partner
        donor_player = self.players[self._universe_index(donor.name)]
        requester_player = self.players[worst_idx]

        # Transfer productive edges from donor to requester
        donor_hist = donor_player.landscape.historization
        profile = donor_hist.strategy_profile(top_n=2)
        transferred = False
        for edge, quality, load in profile:
            if quality > 0.0:
                req_landscape = requester_player.landscape
                if not req_landscape.has_edge(edge.source, edge.target):
                    continue  # Only transfer edges both landscapes share
                # Boost the requester's historization on productive edges
                req_landscape.historization.update(edge, Outcome.SUCCESS)
                transferred = True

        # Historize the coupling
        outcome = Outcome.SUCCESS if transferred else Outcome.FAILURE
        self.router.historize(
            requester.name, donor.name, outcome,
        )

    def _universe_index(self, name: str) -> int:
        """Find player index by universe name."""
        for i, u in enumerate(self._universes):
            if u.name == name:
                return i
        return 0

    def _dimension_quality(self, player: ChessE0Player, dim: str) -> float:
        """Average trace_quality of all transitions INTO dim."""
        hist = player.landscape.historization
        total_q = 0.0
        count = 0
        for other in DIMENSIONS:
            if other == dim:
                continue
            edge = Edge(other, dim)
            load = hist.trace_load(edge)
            if load > 0:
                total_q += hist.trace_quality(edge)
                count += 1
        return total_q / max(count, 1)

    def strategy_summary(self) -> str:
        """Combined team strategy: who decided most often."""
        if not self.vote_history:
            return "(no moves)"
        winner_counts = Counter(v.winner_idx for v in self.vote_history)
        total = len(self.vote_history)
        parts = []
        for idx, count in winner_counts.most_common():
            spec = self.players[idx].dimension_history[0]
            parts.append(f"P{idx}({spec}): {count}/{total}")
        return ", ".join(parts)


# ══════════════════════════════════════════════
# Vote Record
# ══════════════════════════════════════════════

@dataclass
class TeamVote:
    """Record of one team decision."""
    proposals: List[Tuple[str, str, int]]  # (uci, dim, player_idx)
    winner_idx: int
    winner_dim: str
    winner_quality: float


# ══════════════════════════════════════════════
# Team Game Result
# ══════════════════════════════════════════════

@dataclass
class TeamGameResult:
    """Result of a team vs team (or team vs solo) chess game."""
    moves: List[MoveRecord] = field(default_factory=list)
    result: str = "*"
    termination: str = ""
    white_label: str = ""
    black_label: str = ""
    white_votes: List[TeamVote] = field(default_factory=list)
    black_votes: List[TeamVote] = field(default_factory=list)

    @property
    def total_moves(self) -> int:
        return len(self.moves)

    def summary(self) -> str:
        lines = [
            "═══ E₀ Team Chess ═══",
            f"Result: {self.result} ({self.termination})",
            f"Moves: {self.total_moves} half-moves"
            f" ({(self.total_moves + 1) // 2} full)",
            f"White: {self.white_label}",
            f"Black: {self.black_label}",
        ]

        # Vote agreement analysis
        for label, votes in [
            ("White", self.white_votes),
            ("Black", self.black_votes),
        ]:
            if not votes:
                continue
            # How often did all 3 propose the same move?
            unanimous = sum(
                1 for v in votes
                if len(set(m for m, _, _ in v.proposals)) == 1
            )
            lines.append(
                f"{label} unanimity: {unanimous}/{len(votes)}"
                f" ({unanimous / len(votes):.0%})"
            )

        # Dimension focus
        wd = Counter(m.dimension for m in self.moves if m.color == chess.WHITE)
        bd = Counter(m.dimension for m in self.moves if m.color == chess.BLACK)
        lines.append("")
        lines.append("Dimension focus:")
        for dim in DIMENSIONS:
            w = wd.get(dim, 0)
            b = bd.get(dim, 0)
            lines.append(f"  {dim:18s}  W:{w:2d}  B:{b:2d}")

        return "\n".join(lines)


# ══════════════════════════════════════════════
# Game Runner
# ══════════════════════════════════════════════

def play_team_game(
    white: ChessTeam,
    black: ChessTeam,
    *,
    max_moves: int = 200,
    board: Optional[chess.Board] = None,
) -> TeamGameResult:
    """Play a chess game between two E₀ teams.

    Args:
        white: White team (3 E₀ players).
        black: Black team (3 E₀ players).
        max_moves: Maximum total half-moves.
        board: Optional starting position.

    Returns:
        TeamGameResult with full move log and vote analysis.
    """
    board = board or chess.Board()
    game = TeamGameResult(
        white_label="Team (3×E₀)",
        black_label="Team (3×E₀)",
    )
    move_num = 0

    while not board.is_game_over(claim_draw=True) and move_num < max_moves:
        team = white if board.turn == chess.WHITE else black
        move, dim = team.select_move(board)

        game.moves.append(MoveRecord(
            move=move,
            color=board.turn,
            dimension=dim,
            move_number=board.fullmove_number,
        ))

        # Record vote
        if board.turn == chess.WHITE:
            game.white_votes = white.vote_history[:]
        else:
            game.black_votes = black.vote_history[:]

        board.push(move)
        move_num += 1

    # Determine result
    outcome = board.outcome(claim_draw=True)
    if outcome is not None:
        if outcome.winner == chess.WHITE:
            game.result = "1-0"
        elif outcome.winner == chess.BLACK:
            game.result = "0-1"
        else:
            game.result = "1/2-1/2"
        game.termination = outcome.termination.name.lower().replace("_", " ")
    elif move_num >= max_moves:
        game.result = "*"
        game.termination = f"max moves ({max_moves})"

    return game


def play_team_vs_solo(
    *,
    max_moves: int = 200,
) -> Tuple[TeamGameResult, ChessGameResult]:
    """Play Team (3×E₀) vs Solo (1×E₀), both as white, for comparison.

    Returns:
        (team_result, solo_result) — both play the same color (white)
        against a fresh solo opponent.
    """
    # Team game: Team White vs Solo Black
    team_white = ChessTeam(chess.WHITE)
    solo_black_opponent = ChessE0Player(chess.BLACK)

    board1 = chess.Board()
    team_game = TeamGameResult(
        white_label="Team (3×E₀)",
        black_label="Solo (1×E₀)",
    )
    move_num = 0
    while not board1.is_game_over(claim_draw=True) and move_num < max_moves:
        if board1.turn == chess.WHITE:
            move, dim = team_white.select_move(board1)
            team_game.white_votes = team_white.vote_history[:]
        else:
            move, dim = solo_black_opponent.select_move(board1)

        team_game.moves.append(MoveRecord(
            move=move, color=board1.turn,
            dimension=dim, move_number=board1.fullmove_number,
        ))
        board1.push(move)
        move_num += 1

    outcome1 = board1.outcome(claim_draw=True)
    if outcome1 is not None:
        if outcome1.winner == chess.WHITE:
            team_game.result = "1-0"
        elif outcome1.winner == chess.BLACK:
            team_game.result = "0-1"
        else:
            team_game.result = "1/2-1/2"
        team_game.termination = outcome1.termination.name.lower().replace("_", " ")
    elif move_num >= max_moves:
        team_game.result = "*"
        team_game.termination = f"max moves ({max_moves})"

    # Solo game: Solo White vs Solo Black
    solo_white = ChessE0Player(chess.WHITE)
    solo_black = ChessE0Player(chess.BLACK)
    solo_game = play_game(solo_white, solo_black, max_moves=max_moves)

    return team_game, solo_game
