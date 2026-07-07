import time
import chess
from typing import Tuple

class ChessTimer:
    """
    Manages the game timers for both players, supporting increments, pauses, 
    and detecting when a player runs out of time.
    """
    def __init__(self, time_limit: float, increment: float):
        """
        Args:
            time_limit: Starting time per player in seconds (0 for infinite).
            increment: Time increment in seconds added per move.
        """
        self.time_limit = time_limit
        self.increment = increment
        
        self.white_time = time_limit
        self.black_time = time_limit
        self.active_color = chess.WHITE
        self.is_running = False
        
        self.last_tick = 0.0

    def start(self):
        """Starts or resumes the clock."""
        if self.time_limit > 0 and not self.is_running:
            self.is_running = True
            self.last_tick = time.time()

    def pause(self):
        """Pauses the clock."""
        if self.is_running:
            self.update()
            self.is_running = False

    def reset(self, time_limit: float, increment: float):
        """Resets the timers to a new time control."""
        self.time_limit = time_limit
        self.increment = increment
        self.white_time = time_limit
        self.black_time = time_limit
        self.active_color = chess.WHITE
        self.is_running = False
        self.last_tick = 0.0

    def update(self) -> bool:
        """
        Updates the remaining time for the active player.
        Returns True if a timeout occurred, False otherwise.
        """
        if not self.is_running or self.time_limit <= 0:
            return False
            
        now = time.time()
        elapsed = now - self.last_tick
        self.last_tick = now
        
        if self.active_color == chess.WHITE:
            self.white_time = max(0.0, self.white_time - elapsed)
            if self.white_time <= 0:
                self.is_running = False
                return True
        else:
            self.black_time = max(0.0, self.black_time - elapsed)
            if self.black_time <= 0:
                self.is_running = False
                return True
                
        return False

    def switch_turn(self):
        """
        Switches the active timer and applies the time increment 
        to the player who just completed their turn.
        """
        if self.time_limit <= 0:
            self.active_color = not self.active_color
            return

        # Perform final time update for current turn before switching
        self.update()
        
        # Apply increment to the player completing their move
        if self.active_color == chess.WHITE:
            self.white_time += self.increment
        else:
            self.black_time += self.increment
            
        # Switch active player
        self.active_color = not self.active_color
        
        # Refresh last tick timestamp for the new turn
        if self.is_running:
            self.last_tick = time.time()

    def set_active_color(self, color: chess.Color):
        """Explicitly sets who is on move."""
        self.active_color = color
        if self.is_running:
            self.last_tick = time.time()

    def get_time_left(self, color: chess.Color) -> float:
        """Returns remaining time in seconds for the given player."""
        return self.white_time if color == chess.WHITE else self.black_time

    @staticmethod
    def format_time(seconds: float) -> str:
        """Formats time in seconds to a human-readable MM:SS or HH:MM:SS format."""
        if seconds <= 0:
            return "00:00"
            
        total_seconds = int(seconds)
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        secs = total_seconds % 60
        tenths = int((seconds - total_seconds) * 10)
        
        if hours > 0:
            return f"{hours:02d}:{minutes:02d}:{secs:02d}"
        
        # If time is running low (under 20 seconds), show tenths of a second for tension!
        if total_seconds < 20:
            return f"{minutes:02d}:{secs:02d}.{tenths:d}"
            
        return f"{minutes:02d}:{secs:02d}"
