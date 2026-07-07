import sqlite3
import os
import datetime
import logging
from typing import Dict, Any, List

class DatabaseManager:
    """
    Manages SQLite database for storing game history and computing player statistics.
    Explicitly closes all connections to prevent Windows file locking.
    """
    def __init__(self, db_dir: str):
        self.db_path = os.path.join(db_dir, "chess_stats.db")
        self._initialize_db()

    def _get_connection(self) -> sqlite3.Connection:
        """Returns a connection to the SQLite database."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _initialize_db(self):
        """Creates tables if they do not exist."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS games (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date TEXT NOT NULL,
                    white_player TEXT NOT NULL,
                    black_player TEXT NOT NULL,
                    result TEXT NOT NULL,          -- '1-0', '0-1', '1/2-1/2', 'aborted'
                    termination_reason TEXT,       -- 'checkmate', 'stalemate', 'insufficient', 'repetition', 'fifty-moves', 'resignation', 'draw offer', 'timeout'
                    duration_seconds INTEGER,
                    moves_count INTEGER,
                    pgn TEXT,
                    opponent_type TEXT             -- 'human', 'ai'
                )
            """)
            conn.commit()
        except sqlite3.Error as e:
            logging.error(f"Failed to initialize database: {e}")
        finally:
            conn.close()

    def save_game(self, white: str, black: str, result: str, termination_reason: str, 
                  duration_seconds: int, moves_count: int, pgn: str, opponent_type: str) -> bool:
        """Saves a completed game to the database."""
        date_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO games (date, white_player, black_player, result, termination_reason, 
                                   duration_seconds, moves_count, pgn, opponent_type)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (date_str, white, black, result, termination_reason, 
                  duration_seconds, moves_count, pgn, opponent_type))
            conn.commit()
            return True
        except sqlite3.Error as e:
            logging.error(f"Failed to save game to database: {e}")
            return False
        finally:
            conn.close()

    def get_game_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Retrieves the latest games from the history."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, date, white_player, black_player, result, termination_reason, 
                       duration_seconds, moves_count, opponent_type
                FROM games 
                ORDER BY id DESC 
                LIMIT ?
            """, (limit,))
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        except sqlite3.Error as e:
            logging.error(f"Failed to query game history: {e}")
            return []
        finally:
            conn.close()

    def get_statistics(self) -> Dict[str, Any]:
        """Calculates and returns player statistics by querying the games table."""
        stats = {
            "games_played": 0,
            "wins": 0,
            "losses": 0,
            "draws": 0,
            "win_percentage": 0.0,
            "avg_duration": 0,
            "best_streak": 0,
            "current_streak": 0,
            "ai_victories": 0
        }
        
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT white_player, black_player, result, opponent_type, duration_seconds 
                FROM games 
                ORDER BY id ASC
            """)
            games = cursor.fetchall()
            
            if not games:
                return stats
            
            stats["games_played"] = len(games)
            
            durations = []
            current_streak = 0
            best_streak = 0
            
            for game in games:
                white = game["white_player"]
                black = game["black_player"]
                result = game["result"]
                opponent_type = game["opponent_type"]
                duration = game["duration_seconds"]
                
                if duration:
                    durations.append(duration)
                    
                is_white_user = (white.lower() == "player" or white.lower() == "human")
                is_black_user = (black.lower() == "player" or black.lower() == "human")
                
                if not is_white_user and not is_black_user:
                    is_white_user = True
                    
                user_won = False
                user_lost = False
                is_draw = (result == "1/2-1/2")
                
                if result == "1-0":
                    if is_white_user:
                        user_won = True
                    else:
                        user_lost = True
                elif result == "0-1":
                    if is_black_user:
                        user_won = True
                    else:
                        user_lost = True
                
                if is_draw:
                    stats["draws"] += 1
                    current_streak = 0
                elif user_won:
                    stats["wins"] += 1
                    current_streak += 1
                    best_streak = max(best_streak, current_streak)
                    if opponent_type == "ai":
                        stats["ai_victories"] += 1
                elif user_lost:
                    stats["losses"] += 1
                    current_streak = 0
            
            stats["win_percentage"] = round((stats["wins"] / stats["games_played"]) * 100, 1) if stats["games_played"] > 0 else 0.0
            stats["avg_duration"] = int(sum(durations) / len(durations)) if durations else 0
            stats["best_streak"] = best_streak
            stats["current_streak"] = current_streak
            
        except sqlite3.Error as e:
            logging.error(f"Failed to calculate statistics: {e}")
        finally:
            conn.close()
            
        return stats
        
    def clear_history(self) -> bool:
        """Deletes all game logs to reset history."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM games")
            conn.commit()
            return True
        except sqlite3.Error as e:
            logging.error(f"Failed to clear game history: {e}")
            return False
        finally:
            conn.close()
