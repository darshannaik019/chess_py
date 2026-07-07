import random
import threading
import time
import logging
import chess
import chess.engine
from typing import Optional, Tuple, List, Callable

# Standard piece values for evaluation
PIECE_VALUES = {
    chess.PAWN: 100,
    chess.KNIGHT: 320,
    chess.BISHOP: 330,
    chess.ROOK: 500,
    chess.QUEEN: 900,
    chess.KING: 20000
}

# Piece-Square Tables (PST) for positional evaluation
# (Values are from White's perspective; Black's perspective is mirrored)

PST_PAWN = [
    0,  0,  0,  0,  0,  0,  0,  0,
    50, 50, 50, 50, 50, 50, 50, 50,
    10, 10, 20, 30, 30, 20, 10, 10,
     5,  5, 10, 25, 25, 10,  5,  5,
     0,  0,  0, 20, 20,  0,  0,  0,
     5, -5,-10,  0,  0,-10, -5,  5,
     5, 10, 10,-20,-20, 10, 10,  5,
     0,  0,  0,  0,  0,  0,  0,  0
]

PST_KNIGHT = [
    -50,-40,-30,-30,-30,-30,-40,-50,
    -40,-20,  0,  0,  0,  0,-20,-40,
    -30,  0, 10, 15, 15, 10,  0,-30,
    -30,  5, 15, 20, 20, 15,  5,-30,
    -30,  0, 15, 20, 20, 15,  0,-30,
    -30,  5, 10, 15, 15, 10,  5,-30,
    -40,-20,  0,  5,  5,  0,-20,-40,
    -50,-40,-30,-30,-30,-30,-40,-50
]

PST_BISHOP = [
    -20,-10,-10,-10,-10,-10,-10,-20,
    -10,  0,  0,  0,  0,  0,  0,-10,
    -10,  0,  5, 10, 10,  5,  0,-10,
    -10,  5,  5, 10, 10,  5,  5,-10,
    -10,  0, 10, 10, 10, 10,  0,-10,
    -10, 10, 10, 10, 10, 10, 10,-10,
    -10,  5,  0,  0,  0,  0,  5,-10,
    -20,-10,-10,-10,-10,-10,-10,-20
]

PST_ROOK = [
      0,  0,  0,  0,  0,  0,  0,  0,
      5, 10, 10, 10, 10, 10, 10,  5,
     -5,  0,  0,  0,  0,  0,  0, -5,
     -5,  0,  0,  0,  0,  0,  0, -5,
     -5,  0,  0,  0,  0,  0,  0, -5,
     -5,  0,  0,  0,  0,  0,  0, -5,
     -5,  0,  0,  0,  0,  0,  0, -5,
      0,  0,  0,  5,  5,  0,  0,  0
]

PST_QUEEN = [
    -20,-10,-10, -5, -5,-10,-10,-20,
    -10,  0,  0,  0,  0,  0,  0,-10,
    -10,  0,  5,  5,  5,  5,  0,-10,
     -5,  0,  5,  5,  5,  5,  0, -5,
      0,  0,  5,  5,  5,  5,  0, -5,
    -10,  5,  5,  5,  5,  5,  0,-10,
    -10,  0,  5,  0,  0,  5,  0,-10,
    -20,-10,-10, -5, -5,-10,-10,-20
]

# King middle-game PST (encourages castling)
PST_KING_MIDDLE = [
    -30,-40,-40,-50,-50,-40,-40,-30,
    -30,-40,-40,-50,-50,-40,-40,-30,
    -30,-40,-40,-50,-50,-40,-40,-30,
    -30,-40,-40,-50,-50,-40,-40,-30,
    -20,-30,-30,-40,-40,-30,-30,-20,
    -10,-20,-20,-20,-20,-20,-20,-10,
     20, 20,  0,  0,  0,  0, 20, 20,
     20, 30, 10,  0,  0, 10, 30, 20
]

# King endgame PST (encourages king activity)
PST_KING_END = [
    -50,-40,-30,-20,-20,-30,-40,-50,
    -30,-20,-10,  0,  0,-10,-20,-30,
    -30,-10, 20, 30, 30, 20,-10,-30,
    -30,-10, 30, 40, 40, 30,-10,-30,
    -30,-10, 30, 40, 40, 30,-10,-30,
    -30,-10, 20, 30, 30, 20,-10,-30,
    -30,-30,  0,  0,  0,  0,-30,-30,
    -50,-30,-30,-30,-30,-30,-30,-50
]

PST_TABLES = {
    chess.PAWN: PST_PAWN,
    chess.KNIGHT: PST_KNIGHT,
    chess.BISHOP: PST_BISHOP,
    chess.ROOK: PST_ROOK,
    chess.QUEEN: PST_QUEEN,
    chess.KING: PST_KING_MIDDLE  # Will select based on stage
}


class ChessAI:
    """
    Manages AI move calculation and position evaluation.
    Tries Stockfish first (if path provided), falling back to a custom Minimax engine.
    """
    def __init__(self, stockfish_path: str = ""):
        self.stockfish_path = stockfish_path
        self.engine: Optional[chess.engine.SimpleEngine] = None
        self.is_thinking = False
        self._thread: Optional[threading.Thread] = None

        if stockfish_path and os.path.exists(stockfish_path):
            self.init_stockfish()

    def init_stockfish(self):
        """Initializes the Stockfish UCI engine."""
        try:
            self.engine = chess.engine.SimpleEngine.popen_uci(self.stockfish_path)
            logging.info("Stockfish engine initialized successfully.")
        except Exception as e:
            logging.error(f"Failed to initialize Stockfish: {e}. Falling back to internal engine.")
            self.engine = None

    def close(self):
        """Cleanly shuts down the Stockfish process if active."""
        if self.engine:
            try:
                self.engine.quit()
            except Exception:
                pass
            self.engine = None

    def set_stockfish_path(self, path: str):
        """Updates the Stockfish path and re-initializes if path changed."""
        if self.stockfish_path != path:
            self.close()
            self.stockfish_path = path
            if path:
                self.init_stockfish()

    def get_best_move_async(self, board: chess.Board, difficulty: str, 
                            callback: Callable[[Optional[chess.Move], float], None]):
        """
        Calculates the best move on a background thread.
        Triggers `callback(best_move, evaluation_score)` upon completion.
        """
        if self.is_thinking:
            return
            
        self.is_thinking = True
        
        # Clone board to avoid race conditions as GUI updates
        board_copy = board.copy()
        
        def worker():
            start_time = time.time()
            best_move = None
            eval_score = 0.0
            
            try:
                if self.engine:
                    best_move, eval_score = self._query_stockfish(board_copy, difficulty)
                else:
                    best_move, eval_score = self._run_minimax(board_copy, difficulty)
            except Exception as e:
                logging.error(f"Error during AI move calculation: {e}")
                # Ultimate fallback: play a random legal move
                if list(board_copy.legal_moves):
                    best_move = random.choice(list(board_copy.legal_moves))
                    eval_score = 0.0
            
            # Enforce a minimum display latency (e.g. 0.4s) for smooth UX feel
            elapsed = time.time() - start_time
            if elapsed < 0.4:
                time.sleep(0.4 - elapsed)
                
            self.is_thinking = False
            callback(best_move, eval_score)

        self._thread = threading.Thread(target=worker, daemon=True)
        self._thread.start()

    def get_evaluation(self, board: chess.Board) -> float:
        """
        Synchronously calculates the positional evaluation score.
        Used to update the advantage evaluation bar in UI.
        Returns a score in centipawns (positive = White advantage, negative = Black advantage).
        """
        if self.engine:
            try:
                # Fast Stockfish analysis
                info = self.engine.analyse(board, chess.engine.Limit(time=0.05))
                score = info["score"].white()
                if score.is_mate():
                    # Return large value representing mate direction
                    return 9999.0 if score.mate() > 0 else -9999.0
                return score.score() / 100.0  # Convert to pawns
            except Exception:
                pass
        
        # Fallback to internal static evaluation
        return self.evaluate_board(board) / 100.0

    def _query_stockfish(self, board: chess.Board, difficulty: str) -> Tuple[chess.Move, float]:
        """Queries Stockfish adjusting depth and parameters based on difficulty."""
        assert self.engine is not None
        
        # Map difficulty to limits (time & search depths) and Stockfish options
        if difficulty == "EASY":
            self.engine.configure({"Skill Level": 0})
            limit = chess.engine.Limit(time=0.05, depth=1)
        elif difficulty == "MEDIUM":
            self.engine.configure({"Skill Level": 5})
            limit = chess.engine.Limit(time=0.1, depth=5)
        elif difficulty == "HARD":
            self.engine.configure({"Skill Level": 13})
            limit = chess.engine.Limit(time=0.25, depth=10)
        else:  # EXPERT
            self.engine.configure({"Skill Level": 20})
            limit = chess.engine.Limit(time=0.6, depth=15)
            
        result = self.engine.play(board, limit)
        
        # Get evaluation of the board
        info = self.engine.analyse(board, chess.engine.Limit(depth=result.depth or 8))
        score = info["score"].white()
        eval_val = score.score() / 100.0 if not score.is_mate() else (999.0 if score.mate() > 0 else -999.0)
        
        return result.move, eval_val

    def _run_minimax(self, board: chess.Board, difficulty: str) -> Tuple[Optional[chess.Move], float]:
        """Runs the built-in Minimax algorithm."""
        # Map difficulty to search depths
        if difficulty == "EASY":
            depth = 1
        elif difficulty == "MEDIUM":
            depth = 2
        elif difficulty == "HARD":
            depth = 3
        else:  # EXPERT
            depth = 4
            
        # Get list of moves and order them
        moves = list(board.legal_moves)
        if not moves:
            return None, 0.0
            
        best_move = random.choice(moves)
        best_val = -float('inf') if board.turn == chess.WHITE else float('inf')
        
        # Sort moves for faster pruning
        moves = self._order_moves(board, moves)
        
        alpha = -float('inf')
        beta = float('inf')
        
        for move in moves:
            board.push(move)
            val = self._minimax(board, depth - 1, alpha, beta, board.turn == chess.WHITE)
            board.pop()
            
            if board.turn == chess.WHITE:
                if val > best_val:
                    best_val = val
                    best_move = move
                alpha = max(alpha, val)
            else:
                if val < best_val:
                    best_val = val
                    best_move = move
                beta = min(beta, val)
                
            if beta <= alpha:
                break
                
        return best_move, best_val / 100.0

    def _minimax(self, board: chess.Board, depth: int, alpha: float, beta: float, maximizing: bool) -> float:
        """Minimax with Alpha-Beta Pruning recursively evaluating positions."""
        if depth == 0 or board.is_game_over():
            return self.evaluate_board(board)
            
        moves = self._order_moves(board, list(board.legal_moves))
        if not moves:
            return self.evaluate_board(board)
            
        if maximizing:
            max_eval = -float('inf')
            for move in moves:
                board.push(move)
                ev = self._minimax(board, depth - 1, alpha, beta, False)
                board.pop()
                max_eval = max(max_eval, ev)
                alpha = max(alpha, ev)
                if beta <= alpha:
                    break
            return max_eval
        else:
            min_eval = float('inf')
            for move in moves:
                board.push(move)
                ev = self._minimax(board, depth - 1, alpha, beta, True)
                board.pop()
                min_eval = min(min_eval, ev)
                beta = min(beta, ev)
                if beta <= alpha:
                    break
            return min_eval

    def _order_moves(self, board: chess.Board, moves: List[chess.Move]) -> List[chess.Move]:
        """
        Orders moves to optimize alpha-beta pruning.
        Checks, captures, and promotions are evaluated first.
        """
        def score_move(move: chess.Move) -> int:
            score = 0
            # Captures: prioritize capturing valuable pieces with cheap pieces
            if board.is_capture(move):
                attacker = board.piece_type_at(move.from_square)
                victim = board.piece_type_at(move.to_square)
                attacker_val = PIECE_VALUES.get(attacker, 0) if attacker else 0
                victim_val = PIECE_VALUES.get(victim, 0) if victim else 0
                score += 10 * victim_val - attacker_val
                
            # Promotions
            if move.promotion:
                score += PIECE_VALUES.get(move.promotion, 0)
                
            # Checks
            board.push(move)
            if board.is_check():
                score += 50
            board.pop()
            
            return score
            
        return sorted(moves, key=score_move, reverse=True)

    def evaluate_board(self, board: chess.Board) -> float:
        """
        Performs static evaluation of the board.
        Positive value is good for White; negative is good for Black.
        """
        if board.is_checkmate():
            return -99999 if board.turn == chess.WHITE else 99999
        if board.is_game_over(): # Draw
            return 0
            
        # Determine game phase: switch king PST in endgame
        # Counts remaining pieces (excluding pawns) to detect endgame
        minor_major_count = 0
        for sq in chess.SQUARES:
            p = board.piece_at(sq)
            if p and p.piece_type in [chess.KNIGHT, chess.BISHOP, chess.ROOK, chess.QUEEN]:
                minor_major_count += 1
                
        is_endgame = (minor_major_count <= 4)
        
        white_score = 0.0
        black_score = 0.0
        
        # Sum piece material and positional values
        for square in chess.SQUARES:
            piece = board.piece_at(square)
            if not piece:
                continue
                
            p_type = piece.piece_type
            p_val = PIECE_VALUES.get(p_type, 0)
            
            # Select proper King table based on game phase
            if p_type == chess.KING:
                table = PST_KING_END if is_endgame else PST_KING_MIDDLE
            else:
                table = PST_TABLES.get(p_type, [0]*64)
                
            if piece.color == chess.WHITE:
                white_score += p_val + table[square]
            else:
                # Black's squares are indexed upside down
                black_idx = chess.square_mirror(square)
                black_score += p_val + table[black_idx]
                
        return white_score - black_score
