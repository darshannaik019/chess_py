import os
import logging
import chess
import chess.pgn
import json
from typing import List, Optional, Tuple, Dict
from src.settings import Settings
from src.utils import AssetManager
from src.board import ChessBoardGUI
from src.timer import ChessTimer
from src.database import DatabaseManager
from src.ai import ChessAI

class ChessGame:
    """
    Coordinates the chess rules engine (python-chess), GUI board rendering, 
    timers, sound triggers, AI calculations, SQLite records, and game flow states.
    """
    def __init__(self, settings: Settings, assets: AssetManager, db: DatabaseManager):
        self.settings = settings
        self.assets = assets
        self.db = db
        
        # Core engines
        self.board = chess.Board()
        self.board_gui = ChessBoardGUI(settings, assets)
        self.timer = ChessTimer(settings.time_limit, settings.time_increment)
        self.ai = ChessAI(settings.stockfish_path)
        
        # Log lists
        self.move_log: List[str] = []      # Move list in SAN notation
        self.redo_stack: List[chess.Move] = []
        
        # Gameplay states
        self.game_over = False
        self.winner: Optional[str] = None       # "White", "Black", or "Draw"
        self.termination_reason = ""            # "checkmate", "stalemate", etc.
        self.start_time_stamp = 0.0
        self.game_duration = 0
        
        # Player configuration
        self.white_player = "Player"
        self.black_player = "Player"
        self.opponent_type = "human"             # 'human' or 'ai'
        self.ai_color = chess.BLACK              # AI plays black by default
        
        self.reset_game()

    def reset_game(self, fens: Optional[str] = None):
        """Resets the game state, resetting board, timers, logs, and redo stacks."""
        if fens:
            try:
                self.board = chess.Board(fens)
            except ValueError:
                logging.error(f"Invalid FEN: {fens}. Loading default board.")
                self.board = chess.Board()
        else:
            self.board = chess.Board()
            
        self.board_gui.sync_pieces(self.board, animated=False)
        self.redo_stack.clear()
        
        # Re-parse move log if loading a FEN position
        self.move_log.clear()
        temp_board = chess.Board()
        for move in self.board.move_stack:
            self.move_log.append(temp_board.san(move))
            temp_board.push(move)
            
        # Reconfigure players based on selected mode
        self.white_player = "Player"
        if self.settings.game_mode == Settings.MODE_PVC:
            self.opponent_type = "ai"
            if self.board_gui.flipped:
                self.white_player = f"AI ({self.settings.difficulty})"
                self.black_player = "Player"
                self.ai_color = chess.WHITE
            else:
                self.white_player = "Player"
                self.black_player = f"AI ({self.settings.difficulty})"
                self.ai_color = chess.BLACK
        elif self.settings.game_mode == Settings.MODE_CVC:
            self.opponent_type = "ai"
            self.white_player = f"AI-1 ({self.settings.difficulty})"
            self.black_player = f"AI-2 ({self.settings.difficulty})"
        else:
            self.opponent_type = "human"
            self.white_player = "White"
            self.black_player = "Black"
            
        # Reset clocks
        self.timer.reset(self.settings.time_limit, self.settings.time_increment)
        self.timer.set_active_color(self.board.turn)
        
        self.game_over = False
        self.winner = None
        self.termination_reason = ""
        self.game_duration = 0
        self.start_time_stamp = os.times().elapsed

    def make_move(self, move: chess.Move) -> bool:
        """
        Executes a legal chess move on the board, updates history, 
        and plays corresponding audio indicators. Returns True if successful.
        """
        if self.game_over or move not in self.board.legal_moves:
            return False
            
        # Record SAN move string for move panel log
        san_str = self.board.san(move)
        
        # Detect captures and checks for audio triggers
        is_capture = self.board.is_capture(move)
        
        self.board.push(move)
        self.move_log.append(san_str)
        self.redo_stack.clear()  # Clear redo history on new move
        
        # Trigger audio playback
        if self.board.is_check():
            self.assets.play_sound("check", self.settings.sound_enabled)
        elif is_capture:
            self.assets.play_sound("capture", self.settings.sound_enabled)
        else:
            self.assets.play_sound("move", self.settings.sound_enabled)
            
        # Update clocks and board GUI
        self.timer.switch_turn()
        self.board_gui.sync_pieces(self.board, animated=True)
        
        # Reset visual selections
        self.board_gui.selected_square = None
        self.board_gui.dragging_square = None
        
        # Check end game status
        self.check_game_status()
        return True

    def undo_move(self):
        """
        Undoes the last move. In Player vs AI mode, undos two moves 
        to ensure the board reverts back to the player's turn.
        """
        if len(self.board.move_stack) == 0:
            return
            
        # PVC Mode: Undo both the AI's move and the user's move
        if self.settings.game_mode == Settings.MODE_PVC and len(self.board.move_stack) >= 2:
            # Check if it's currently the player's turn (AI just moved) or AI's turn
            # In either case, we want to roll back to the user's previous action
            m1 = self.board.pop()
            m2 = self.board.pop()
            self.redo_stack.append(m1)
            self.redo_stack.append(m2)
            self.move_log.pop()
            self.move_log.pop()
            
            # Recalculate timer active color
            self.timer.set_active_color(self.board.turn)
        else:
            # Simple PVP or other mode: pop once
            move = self.board.pop()
            self.redo_stack.append(move)
            if self.move_log:
                self.move_log.pop()
            self.timer.switch_turn()
            
        self.board_gui.sync_pieces(self.board, animated=False)
        self.board_gui.selected_square = None
        
        if self.game_over:
            self.game_over = False
            self.winner = None
            self.termination_reason = ""

    def redo_move(self):
        """Replays a move from the redo stack."""
        if not self.redo_stack:
            return
            
        # PVC Mode: Redo two moves (Player's move + AI's response)
        if self.settings.game_mode == Settings.MODE_PVC and len(self.redo_stack) >= 2:
            m2 = self.redo_stack.pop()
            m1 = self.redo_stack.pop()
            self.make_move(m1)
            self.make_move(m2)
        else:
            # Single move redo
            move = self.redo_stack.pop()
            self.make_move(move)

    def check_game_status(self) -> bool:
        """
        Checks if the game has concluded according to official chess rules.
        Logs final outcome to SQLite database.
        """
        if self.game_over:
            return True
            
        if self.board.is_game_over():
            self.game_over = True
            self.timer.pause()
            
            # Determine outcomes
            outcome = self.board.outcome()
            if outcome:
                # Result format: '1-0', '0-1', '1/2-1/2'
                result_str = outcome.result()
                
                # Winner identity
                if outcome.winner == chess.WHITE:
                    self.winner = "White"
                elif outcome.winner == chess.BLACK:
                    self.winner = "Black"
                else:
                    self.winner = "Draw"
                    
                # Reason map
                reason_map = {
                    chess.Termination.CHECKMATE: "checkmate",
                    chess.Termination.STALEMATE: "stalemate",
                    chess.Termination.INSUFFICIENT_MATERIAL: "insufficient",
                    chess.Termination.SEVENTYFIVE_MOVES: "fifty-moves",
                    chess.Termination.FIVEFOLD_REPETITION: "repetition",
                    chess.Termination.THREEFOLD_REPETITION: "repetition",
                    chess.Termination.FIFTY_MOVES: "fifty-moves"
                }
                self.termination_reason = reason_map.get(outcome.termination, "draw")
            else:
                result_str = "1/2-1/2"
                self.winner = "Draw"
                self.termination_reason = "draw"

            self.assets.play_sound("game_over", self.settings.sound_enabled)
            self._log_to_db(result_str)
            return True
            
        # Timer check is handled in main loop
        return False

    def handle_timeout(self, timed_out_color: chess.Color):
        """Concludes the game when a player runs out of time."""
        if self.game_over:
            return
            
        self.game_over = True
        self.timer.pause()
        self.termination_reason = "timeout"
        
        if timed_out_color == chess.WHITE:
            self.winner = "Black"
            result_str = "0-1"
        else:
            self.winner = "White"
            result_str = "1-0"
            
        self.assets.play_sound("game_over", self.settings.sound_enabled)
        self._log_to_db(result_str)

    def resign_game(self, color: chess.Color):
        """Permits a player to resign, granting victory to the opponent."""
        if self.game_over:
            return
            
        self.game_over = True
        self.timer.pause()
        self.termination_reason = "resignation"
        
        if color == chess.WHITE:
            self.winner = "Black"
            result_str = "0-1"
        else:
            self.winner = "White"
            result_str = "1-0"
            
        self.assets.play_sound("game_over", self.settings.sound_enabled)
        self._log_to_db(result_str)

    def offer_draw(self):
        """Allows claiming a draw by consensus."""
        if self.game_over:
            return
            
        self.game_over = True
        self.timer.pause()
        self.winner = "Draw"
        self.termination_reason = "draw offer"
        
        self.assets.play_sound("game_over", self.settings.sound_enabled)
        self._log_to_db("1/2-1/2")

    def _log_to_db(self, result: str):
        """Saves game logs to database."""
        end_time_stamp = os.times().elapsed
        self.game_duration = int(max(0.0, end_time_stamp - self.start_time_stamp))
        
        # Save game history
        pgn_str = self.export_pgn_str()
        
        self.db.save_game(
            white=self.white_player,
            black=self.black_player,
            result=result,
            termination_reason=self.termination_reason,
            duration_seconds=self.game_duration,
            moves_count=len(self.board.move_stack),
            pgn=pgn_str,
            opponent_type=self.opponent_type
        )

    def export_pgn_str(self) -> str:
        """Generates PGN string representation of the match."""
        pgn_game = chess.pgn.Game.from_board(self.board)
        pgn_game.headers["Event"] = "Local Game"
        pgn_game.headers["White"] = self.white_player
        pgn_game.headers["Black"] = self.black_player
        pgn_game.headers["Result"] = self.board.result()
        return str(pgn_game)

    def export_pgn_file(self, filepath: str) -> bool:
        """Saves current match to PGN file on disk."""
        try:
            pgn_content = self.export_pgn_str()
            with open(filepath, "w") as f:
                f.write(pgn_content)
            logging.info(f"PGN exported successfully: {filepath}")
            return True
        except Exception as e:
            logging.error(f"Failed to export PGN: {e}")
            return False

    def import_pgn_file(self, filepath: str) -> bool:
        """Loads a game from a PGN file."""
        if not os.path.exists(filepath):
            return False
            
        try:
            with open(filepath, "r") as f:
                game = chess.pgn.read_game(f)
                
            if game:
                self.board = game.board()
                self.move_log.clear()
                self.redo_stack.clear()
                
                # Replay moves
                for move in game.mainline_moves():
                    self.board.push(move)
                    
                self.board_gui.sync_pieces(self.board, animated=False)
                
                # Rebuild SAN log
                temp_board = game.board()
                for move in game.mainline_moves():
                    self.move_log.append(temp_board.san(move))
                    temp_board.push(move)
                    
                # Reset timers and game over state
                self.game_over = False
                self.winner = None
                self.termination_reason = ""
                self.timer.reset(self.settings.time_limit, self.settings.time_increment)
                self.timer.set_active_color(self.board.turn)
                
                logging.info(f"PGN loaded successfully: {filepath}")
                return True
        except Exception as e:
            logging.error(f"Failed to import PGN: {e}")
            
        return False
        
    def save_json(self, name: str) -> bool:
        """Saves game state to saves directory as JSON (useful for custom resuming)."""
        data = {
            "fen": self.board.fen(),
            "move_log": self.move_log,
            "white_time": self.timer.white_time,
            "black_time": self.timer.black_time,
            "mode": self.settings.game_mode,
            "difficulty": self.settings.difficulty,
            "opponent": self.opponent_type,
            "flipped": self.board_gui.flipped
        }
        
        filepath = os.path.join(self.settings.SAVES_DIR, f"{name}.json")
        try:
            with open(filepath, "w") as f:
                json.dump(data, f, indent=4)
            return True
        except Exception as e:
            logging.error(f"Failed to save JSON game state: {e}")
            return False
            
    def load_json(self, filepath: str) -> bool:
        """Loads game state from a JSON save file."""
        if not os.path.exists(filepath):
            return False
            
        try:
            with open(filepath, "r") as f:
                data = json.load(f)
                
            self.board = chess.Board(data["fen"])
            self.move_log = data["move_log"]
            self.redo_stack.clear()
            
            self.board_gui.flipped = data.get("flipped", False)
            self.board_gui.sync_pieces(self.board, animated=False)
            
            # Setup timers
            self.timer.white_time = data["white_time"]
            self.timer.black_time = data["black_time"]
            self.timer.set_active_color(self.board.turn)
            
            # Setup properties
            self.settings.game_mode = data.get("mode", self.settings.game_mode)
            self.settings.difficulty = data.get("difficulty", self.settings.difficulty)
            self.opponent_type = data.get("opponent", self.opponent_type)
            
            self.game_over = False
            self.winner = None
            self.termination_reason = ""
            
            return True
        except Exception as e:
            logging.error(f"Failed to load JSON save file: {e}")
            return False
