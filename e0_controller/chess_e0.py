"""
E₀ Chess Engine — Strategic Dimension Navigation (C72)
======================================================

E₀ plays chess by navigating a landscape of strategic dimensions.
Each move: E₀ picks which dimension to optimize → deterministic
move selection for that dimension → historize the result.

No LLM required during play.  The LLM's role (future) is to
bootstrap the initial understanding.  Here, the dimension
evaluators ARE the bootstrap — they define *what can be measured*,
not *what is good*.  E₀ discovers what works through play.

Dimensions (= landscape states)::

    MATERIAL        — net piece value advantage
    KING_SAFETY     — pawn shield, castling rights, check penalty
    CENTER_CONTROL  — pieces/attacks on central squares
    PIECE_ACTIVITY  — piece mobility (attacked squares)
    PAWN_STRUCTURE  — connected minus isolated/doubled pawns
    DEVELOPMENT     — minor pieces off back rank

Edges: fully connected (any focus→any focus, Δ=0.5, R₀=1.0).
E₀ discovers which transitions are productive through historization.

Usage::

    from e0_controller.chess_e0 import ChessE0Player, play_game
    import chess

    white = ChessE0Player(chess.WHITE)
    black = ChessE0Player(chess.BLACK)
    result = play_game(white, black, max_moves=200)
    print(result.summary())
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import chess

from e0_controller.primitives import Outcome
from e0_controller.landscape import Landscape
from e0_controller.controller import E0Controller


# ══════════════════════════════════════════════
# Constants
# ══════════════════════════════════════════════

DIMENSIONS = [
    "MATERIAL",
    "KING_SAFETY",
    "CENTER_CONTROL",
    "PIECE_ACTIVITY",
    "PAWN_STRUCTURE",
    "DEVELOPMENT",
]

PIECE_VALUES = {
    chess.PAWN: 1,
    chess.KNIGHT: 3,
    chess.BISHOP: 3,
    chess.ROOK: 5,
    chess.QUEEN: 9,
}

CENTER_SQUARES = {chess.E4, chess.D4, chess.E5, chess.D5}

EXTENDED_CENTER = CENTER_SQUARES | {
    chess.C3, chess.D3, chess.E3, chess.F3,
    chess.C4, chess.F4, chess.C5, chess.F5,
    chess.C6, chess.D6, chess.E6, chess.F6,
}


# ══════════════════════════════════════════════
# Dimension Evaluators
# ══════════════════════════════════════════════

def evaluate_material(board: chess.Board, color: chess.Color) -> float:
    """Net material advantage for *color*."""
    score = 0.0
    for pt, val in PIECE_VALUES.items():
        score += len(board.pieces(pt, color)) * val
        score -= len(board.pieces(pt, not color)) * val
    return score


def evaluate_king_safety(board: chess.Board, color: chess.Color) -> float:
    """King safety: pawn shield + castling rights − check penalty."""
    king_sq = board.king(color)
    if king_sq is None:
        return -10.0

    score = 0.0
    # Castling rights bonus
    if board.has_kingside_castling_rights(color):
        score += 1.0
    if board.has_queenside_castling_rights(color):
        score += 1.0

    # Pawn shield: friendly pawns directly in front of king
    king_file = chess.square_file(king_sq)
    king_rank = chess.square_rank(king_sq)
    pawn_dir = 1 if color == chess.WHITE else -1
    for df in [-1, 0, 1]:
        f = king_file + df
        r = king_rank + pawn_dir
        if 0 <= f <= 7 and 0 <= r <= 7:
            sq = chess.square(f, r)
            piece = board.piece_at(sq)
            if (piece
                    and piece.piece_type == chess.PAWN
                    and piece.color == color):
                score += 1.0

    # Check penalty (only applies when it's our turn and we're in check)
    if board.turn == color and board.is_check():
        score -= 3.0

    return score


def evaluate_center_control(board: chess.Board, color: chess.Color) -> float:
    """Central occupation (×2) + attacks on center/extended center."""
    score = 0.0
    # Pieces on center squares
    for sq in CENTER_SQUARES:
        piece = board.piece_at(sq)
        if piece and piece.color == color:
            score += 2.0
    # Attacks on center
    for sq in CENTER_SQUARES:
        if board.is_attacked_by(color, sq):
            score += 1.0
    # Extended center attacks
    for sq in EXTENDED_CENTER - CENTER_SQUARES:
        if board.is_attacked_by(color, sq):
            score += 0.3
    return score


def evaluate_piece_activity(board: chess.Board, color: chess.Color) -> float:
    """Sum of squares attacked by each piece (mobility proxy)."""
    score = 0.0
    for pt in [chess.KNIGHT, chess.BISHOP, chess.ROOK, chess.QUEEN]:
        for sq in board.pieces(pt, color):
            score += len(board.attacks(sq))
    return score


def evaluate_pawn_structure(board: chess.Board, color: chess.Color) -> float:
    """Connected pawns − isolated × 1.5 − doubled × 2."""
    pawns = list(board.pieces(chess.PAWN, color))
    if not pawns:
        return 0.0

    files = [chess.square_file(sq) for sq in pawns]
    file_counts = Counter(files)

    # Doubled: multiple pawns on same file
    doubled = sum(c - 1 for c in file_counts.values() if c > 1)

    # Isolated: no friendly pawn on adjacent files
    file_set = set(files)
    isolated = 0
    for f in file_set:
        if (f - 1) not in file_set and (f + 1) not in file_set:
            isolated += file_counts[f]

    # Connected: pawn with friendly pawn on adjacent file
    connected = 0
    for sq in pawns:
        f = chess.square_file(sq)
        r = chess.square_rank(sq)
        for df in [-1, 1]:
            nf = f + df
            if 0 <= nf <= 7:
                for dr in [-1, 0, 1]:
                    nr = r + dr
                    if 0 <= nr <= 7:
                        nsq = chess.square(nf, nr)
                        p = board.piece_at(nsq)
                        if (p
                                and p.piece_type == chess.PAWN
                                and p.color == color):
                            connected += 1
                            break

    return float(connected - doubled * 2 - isolated * 1.5)


def evaluate_development(board: chess.Board, color: chess.Color) -> float:
    """Minor pieces (knights + bishops) off the back rank."""
    back_rank = 0 if color == chess.WHITE else 7
    developed = 0
    for pt in [chess.KNIGHT, chess.BISHOP]:
        for sq in board.pieces(pt, color):
            if chess.square_rank(sq) != back_rank:
                developed += 1
    return float(developed)


# Dispatcher
_EVALUATORS = {
    "MATERIAL": evaluate_material,
    "KING_SAFETY": evaluate_king_safety,
    "CENTER_CONTROL": evaluate_center_control,
    "PIECE_ACTIVITY": evaluate_piece_activity,
    "PAWN_STRUCTURE": evaluate_pawn_structure,
    "DEVELOPMENT": evaluate_development,
}


def evaluate_dimension(
    dim: str,
    board: chess.Board,
    color: chess.Color,
) -> float:
    """Evaluate a single strategic dimension."""
    return _EVALUATORS[dim](board, color)


def dimension_profile(
    board: chess.Board,
    color: chess.Color,
) -> Dict[str, float]:
    """All dimension scores for a position."""
    return {dim: evaluate_dimension(dim, board, color) for dim in DIMENSIONS}


# ══════════════════════════════════════════════
# Move Selection
# ══════════════════════════════════════════════

def best_move_for_dimension(
    dim: str,
    board: chess.Board,
    color: chess.Color,
) -> Optional[chess.Move]:
    """Pick the legal move that most improves the given dimension.

    If no move improves it, picks the one that degrades it least.
    """
    score_now = evaluate_dimension(dim, board, color)
    best_move = None
    best_delta = -float("inf")

    for move in board.legal_moves:
        board.push(move)
        score_after = evaluate_dimension(dim, board, color)
        board.pop()
        delta = score_after - score_now
        if delta > best_delta:
            best_delta = delta
            best_move = move

    return best_move


# ══════════════════════════════════════════════
# ChessE0Player
# ══════════════════════════════════════════════

class ChessE0Player:
    """E₀-guided chess player using strategic dimension navigation.

    Each move:
    1. Pre-compute dimension improvements for all legal moves.
    2. E₀ controller navigates strategic landscape (1 cycle).
    3. Controller picks which dimension to focus on.
    4. Best legal move for that dimension is selected.

    Historization accumulates across moves — the landscape learns
    which strategic transitions are productive in the current game.
    """

    def __init__(
        self,
        color: chess.Color,
        *,
        start_dim: str = "DEVELOPMENT",
        alpha: float = 2.0,
        recent_k: int = 3,
    ):
        self.color = color
        self.landscape = self._build_landscape()
        self.current_dim = start_dim
        self._move_scores: Dict[str, Dict[chess.Move, float]] = {}
        self.controller = E0Controller(
            self.landscape,
            self._execute_fn,
            alpha=alpha,
            recent_k=recent_k,
            overload_threshold=10.0,  # Suppress OVERLOADED (no peer yet)
        )
        self.dimension_history: List[str] = [start_dim]

    @staticmethod
    def _build_landscape() -> Landscape:
        """Fully connected landscape over strategic dimensions."""
        return Landscape.fully_connected(DIMENSIONS)

    def _execute_fn(self, source: str, target: str) -> Outcome:
        """Can we improve dimension *target* with available moves?"""
        scores = self._move_scores.get(target, {})
        if not scores:
            return Outcome.FAILURE
        best_improvement = max(scores.values())
        return Outcome.SUCCESS if best_improvement > 0 else Outcome.FAILURE

    def select_move(
        self,
        board: chess.Board,
    ) -> Tuple[chess.Move, str]:
        """Pick a chess move using E₀ strategic navigation.

        Returns:
            (move, dimension) — the chosen move and strategic focus.
        """
        # Pre-compute dimension improvements for all legal moves
        legal = list(board.legal_moves)
        self._move_scores = {}
        for dim in DIMENSIONS:
            score_now = evaluate_dimension(dim, board, self.color)
            dim_scores: Dict[chess.Move, float] = {}
            for move in legal:
                board.push(move)
                score_after = evaluate_dimension(dim, board, self.color)
                board.pop()
                dim_scores[move] = score_after - score_now
            self._move_scores[dim] = dim_scores

        # E₀ navigates 1 cycle: picks strategic dimension
        trace = self.controller.run(
            start=self.current_dim, max_cycles=1,
        )
        target_dim = trace.path[-1]

        # Pick best move for chosen dimension
        dim_scores = self._move_scores[target_dim]
        best_move = max(dim_scores, key=dim_scores.get)

        self.current_dim = target_dim
        self.dimension_history.append(target_dim)

        return best_move, target_dim

    def strategy_summary(self) -> str:
        """Which dimensions were used most (excluding initial)."""
        counts = Counter(self.dimension_history[1:])
        total = sum(counts.values())
        if total == 0:
            return "(no moves)"
        parts = [f"{dim}: {c}/{total}" for dim, c in counts.most_common()]
        return ", ".join(parts)

    def learned_transitions(self, top_n: int = 5) -> str:
        """Show top productive transitions discovered through play."""
        profile = self.landscape.historization.strategy_profile(top_n=top_n)
        if not profile:
            return "(no transitions observed)"
        parts = []
        for edge, quality, load in profile:
            parts.append(
                f"{edge.source}\u2192{edge.target}: "
                f"q={quality:+.2f} (load={load:.1f})"
            )
        return "\n".join(parts)


# ══════════════════════════════════════════════
# Game Runner
# ══════════════════════════════════════════════

@dataclass
class MoveRecord:
    """One move in a chess game."""
    move: chess.Move
    color: chess.Color
    dimension: str
    move_number: int


@dataclass
class ChessGameResult:
    """Result of a complete E₀ chess game."""
    moves: List[MoveRecord] = field(default_factory=list)
    result: str = "*"          # "1-0", "0-1", "1/2-1/2", "*"
    termination: str = ""
    white_player: Optional[ChessE0Player] = None
    black_player: Optional[ChessE0Player] = None

    @property
    def total_moves(self) -> int:
        return len(self.moves)

    @property
    def white_dimensions(self) -> List[str]:
        return [m.dimension for m in self.moves if m.color == chess.WHITE]

    @property
    def black_dimensions(self) -> List[str]:
        return [m.dimension for m in self.moves if m.color == chess.BLACK]

    def summary(self) -> str:
        lines = [
            "═══ E₀ Chess Game ═══",
            f"Result: {self.result} ({self.termination})",
            f"Moves: {self.total_moves} half-moves"
            f" ({(self.total_moves + 1) // 2} full)",
        ]
        if self.white_player:
            lines.append(
                f"White strategy: {self.white_player.strategy_summary()}")
        if self.black_player:
            lines.append(
                f"Black strategy: {self.black_player.strategy_summary()}")

        # Dimension comparison
        wd = Counter(self.white_dimensions)
        bd = Counter(self.black_dimensions)
        lines.append("")
        lines.append("Dimension focus:")
        for dim in DIMENSIONS:
            w = wd.get(dim, 0)
            b = bd.get(dim, 0)
            lines.append(f"  {dim:18s}  W:{w:2d}  B:{b:2d}")

        return "\n".join(lines)


def play_game(
    white: ChessE0Player,
    black: ChessE0Player,
    *,
    max_moves: int = 200,
    board: Optional[chess.Board] = None,
) -> ChessGameResult:
    """Play a complete chess game between two E₀ players.

    Args:
        white: White player (E₀-guided).
        black: Black player (E₀-guided).
        max_moves: Maximum total half-moves.
        board: Optional starting position (default: standard).

    Returns:
        ChessGameResult with full move log and strategy analysis.
    """
    board = board or chess.Board()
    game = ChessGameResult(white_player=white, black_player=black)
    move_num = 0

    while not board.is_game_over(claim_draw=True) and move_num < max_moves:
        player = white if board.turn == chess.WHITE else black
        move, dim = player.select_move(board)

        game.moves.append(MoveRecord(
            move=move,
            color=board.turn,
            dimension=dim,
            move_number=board.fullmove_number,
        ))
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
