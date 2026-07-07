import unittest
import os
import shutil
import tempfile
import chess
from src.settings import Settings
from src.database import DatabaseManager
from src.timer import ChessTimer
from src.ai import ChessAI
from src.game import ChessGame
from src.utils import AssetManager

class TestChessComponents(unittest.TestCase):
    """
    Test suite verifying chess rules integration, clocks, SQLite logging, 
    and built-in AI search logic.
    """
    def setUp(self):
        # Create temporary directory for database and settings testing
        self.test_dir = tempfile.mkdtemp()
        self.settings = Settings()
        self.settings.DB_DIR = self.test_dir
        self.settings.SAVES_DIR = self.test_dir
        self.db = DatabaseManager(self.test_dir)
        self.assets = AssetManager()
        self.assets.ASSETS_DIR = self.test_dir
        
    def tearDown(self):
        # Clean up temporary directory
        shutil.rmtree(self.test_dir)

    def test_timer(self):
        """Verify clock initialization, tick decrements, and turn switching."""
        timer = ChessTimer(600, 5)  # 10 mins, 5s increment
        self.assertEqual(timer.get_time_left(chess.WHITE), 600)
        self.assertEqual(timer.get_time_left(chess.BLACK), 600)
        
        # Switch turn adds increment to the player completing turn
        timer.switch_turn()
        self.assertEqual(timer.active_color, chess.BLACK)
        # White just moved, so White gets +5s increment
        self.assertEqual(timer.get_time_left(chess.WHITE), 605)
        
        # Switch back adds increment to Black
        timer.switch_turn()
        self.assertEqual(timer.active_color, chess.WHITE)
        self.assertEqual(timer.get_time_left(chess.BLACK), 605)

    def test_database_stats(self):
        """Verify sqlite database logging, streaks, wins and draws computation."""
        # Check initial stats
        stats = self.db.get_statistics()
        self.assertEqual(stats["games_played"], 0)
        self.assertEqual(stats["wins"], 0)
        
        # Log a white victory (White win result is '1-0')
        self.db.save_game(
            white="Player", black="AI (Medium)", result="1-0", 
            termination_reason="checkmate", duration_seconds=120, 
            moves_count=15, pgn="", opponent_type="ai"
        )
        
        # Log a black victory (Player plays black, result '0-1')
        self.db.save_game(
            white="AI (Medium)", black="Player", result="0-1", 
            termination_reason="checkmate", duration_seconds=180, 
            moves_count=22, pgn="", opponent_type="ai"
        )
        
        # Log a draw (result '1/2-1/2')
        self.db.save_game(
            white="Player", black="AI (Medium)", result="1/2-1/2", 
            termination_reason="stalemate", duration_seconds=300, 
            moves_count=45, pgn="", opponent_type="ai"
        )
        
        # Fetch stats
        stats = self.db.get_statistics()
        self.assertEqual(stats["games_played"], 3)
        self.assertEqual(stats["wins"], 2)  # Both White win and Black win were "Player"
        self.assertEqual(stats["losses"], 0)
        self.assertEqual(stats["draws"], 1)
        self.assertEqual(stats["ai_victories"], 2)
        self.assertEqual(stats["best_streak"], 2)
        self.assertEqual(stats["avg_duration"], 200)  # (120+180+300)/3 = 200s

    def test_minimax_ai(self):
        """Verify minimax fallback AI moves generation and evaluation."""
        ai = ChessAI()
        board = chess.Board()
        
        # Initial board static evaluation should be close to 0 (equal position)
        eval_score = ai.evaluate_board(board)
        self.assertEqual(eval_score, 0)
        
        # AI decision check
        best_move, score = ai._run_minimax(board, "EASY")
        self.assertIsNotNone(best_move)
        self.assertIn(best_move, board.legal_moves)

    def test_game_undo_redo(self):
        """Verify move execution, turn switching, and undo/redo stacks."""
        # Create game instance
        game = ChessGame(self.settings, self.assets, self.db)
        game.reset_game()
        
        # Initial turn is White
        self.assertEqual(game.board.turn, chess.WHITE)
        
        # Move: e2e4 (1. e4)
        move_e4 = chess.Move.from_uci("e2e4")
        success = game.make_move(move_e4)
        self.assertTrue(success)
        self.assertEqual(game.board.turn, chess.BLACK)
        self.assertEqual(len(game.move_log), 1)
        self.assertEqual(game.move_log[0], "e4")
        
        # Undo move
        game.undo_move()
        self.assertEqual(game.board.turn, chess.WHITE)
        self.assertEqual(len(game.move_log), 0)
        self.assertEqual(len(game.redo_stack), 1)
        
        # Redo move
        game.redo_move()
        self.assertEqual(game.board.turn, chess.BLACK)
        self.assertEqual(len(game.move_log), 1)
        self.assertEqual(game.move_log[0], "e4")

    def test_pgn_export(self):
        """Verify PGN string export matches standard chess formatting."""
        game = ChessGame(self.settings, self.assets, self.db)
        game.reset_game()
        
        # Play standard fool's mate: 1. f3 e5 2. g4 Qh4#
        game.make_move(chess.Move.from_uci("f2f3"))
        game.make_move(chess.Move.from_uci("e7e5"))
        game.make_move(chess.Move.from_uci("g2g4"))
        game.make_move(chess.Move.from_uci("d8h4"))
        
        # Game should be checkmate
        self.assertTrue(game.board.is_checkmate())
        game.check_game_status()
        self.assertTrue(game.game_over)
        self.assertEqual(game.winner, "Black")
        
        pgn_str = game.export_pgn_str()
        self.assertIn("[Result \"0-1\"]", pgn_str)
        self.assertIn("1. f3 e5 2. g4 Qh4#", pgn_str)

if __name__ == "__main__":
    unittest.main()
